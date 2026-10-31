#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app/core.py 回归测试（不依赖 tkinter，CI 上可跑）。

为什么只测 core 不测 GUI：GUI 的价值全在 core 上，而 core 覆盖了
"采集/预处理/校验/打包" 全部真实逻辑。GUI 层本身的正确性由打包后的
`<exe> --selftest-gui` 真建窗口兜底（见 app_main.py）。

若这里出现"为了通过测试而改测试"，那说明测试写错了 —— 改判据，别改期望。
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import core  # noqa: E402

EXAMPLE = ROOT / "examples" / "sample_corpus.csv"
EXAMPLE_GUIDE = ROOT / "examples" / "sample_guide.md"


class TestResources(unittest.TestCase):
    def test_resource_root_is_repo_root(self):
        self.assertTrue((core.resource_root() / "SKILL.md").exists())

    def test_selfcheck_all_ok(self):
        ok, msgs = core.selfcheck()
        self.assertTrue(ok, f"自检失败：{msgs}")
        self.assertTrue(any("SKILL.md" in m for _, m in msgs))

    def test_skill_path_exists(self):
        self.assertTrue(core.skill_path().exists())

    def test_outputs_live_under_app_root(self):
        """所有产物统一落在程序目录下，不散到用户主目录。

        早先默认是 `Path.home()/comment-distillery-output`：程序在 E 盘、
        产物在 C 盘，同一个项目的文件分两个盘放，用户根本找不齐。
        """
        d = core.default_outdir()
        self.assertEqual(d.resolve(), (ROOT / "output").resolve(),
                         "源码运行时默认输出应为 <仓库根>/output")
        self.assertTrue(d.is_dir(), "默认输出目录应被创建出来")
        self.assertNotEqual(d.resolve(), (Path.home() / "comment-distillery-output").resolve())

    def test_outdir_or_default_normalizes(self):
        self.assertEqual(core.outdir_or_default(""), str(core.default_outdir()))
        self.assertEqual(core.outdir_or_default("   "), str(core.default_outdir()))
        self.assertEqual(core.outdir_or_default("D:/somewhere"), "D:/somewhere")

    def test_app_root_differs_from_resource_root_when_frozen(self):
        """打包后 resource_root 是 _MEIPASS（临时解包目录），不能当输出位置。"""
        import inspect
        src = inspect.getsource(core.app_root)
        self.assertIn("sys.executable", src,
                      "打包后 app_root 必须取 exe 所在目录，而不是 _MEIPASS")

    def test_gui_and_web_share_one_default(self):
        """GUI 与 Web 的默认输出必须是同一个地方（单一来源）。"""
        gsrc = (ROOT / "app" / "gui.py").read_text(encoding="utf-8")
        # 静态检查即可：不为一条断言去 import tkinter（无图形环境会挂）
        import re as _re
        m = _re.search(r"def default_outdir\(\)[^\n]*:\n(.*?)\n\n\n", gsrc, _re.S)
        self.assertIsNotNone(m, "找不到 gui.default_outdir")
        self.assertIn("core.default_outdir()", m.group(1),
                      "GUI 应委托 core.default_outdir()，不再各自维护一份")
        wsrc = (ROOT / "app" / "webui.py").read_text(encoding="utf-8")
        self.assertNotIn('Path.home() / "comment-distillery-output"',
                         wsrc.replace('`Path.home() / "comment-distillery-output"`', ""),
                         "webui 不应再硬编码用户主目录作为默认输出")


class TestPrepare(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="cdtest-"))

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_prepare_writes_canonical_corpus(self):
        stats, paths = core.prepare(str(EXAMPLE), str(self.out))
        ccf = Path(paths["corpus_ccf"])
        self.assertTrue(ccf.exists(), "缺少规范语料 corpus_ccf.csv")
        # 行数必须等于去噪后的条数（+1 表头）——口径不能漂
        lines = ccf.read_text(encoding="utf-8-sig").strip().splitlines()
        self.assertEqual(len(lines) - 1, stats["total_after_denoise"])
        self.assertEqual(lines[0].split(",")[0], "id")

    def test_prepare_paths_complete(self):
        _, paths = core.prepare(str(EXAMPLE), str(self.out))
        self.assertEqual(set(paths),
                         {"all_comments", "low_score_long", "stats", "id_map", "corpus_ccf"})


class TestExportPackage(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="cdpack-"))

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_pack_contains_everything_needed(self):
        res = core.export_package(str(EXAMPLE), str(self.out), "demo",
                                  on_log=lambda m: None)
        names = set(res["files"])
        for need in ("PROMPT.md", "README.md", "SKILL.md",
                     "canonical-format.md", "pipeline.md",
                     "corpus_ccf.csv", "all_comments.txt",
                     "low_score_long.txt", "stats.json", "id_map.json"):
            self.assertIn(need, names, f"蒸馏包缺少 {need}")

    def test_prompt_carries_hard_requirements(self):
        res = core.export_package(str(EXAMPLE), str(self.out), "demo",
                                  on_log=lambda m: None)
        prompt = (Path(res["pack_dir"]) / "PROMPT.md").read_text(encoding="utf-8")
        # 提示词必须把两条硬要求带出去，否则用户拿到的是"随便总结一下"
        self.assertIn("verify_citations.py", prompt)      # 引用机验
        self.assertIn("dup_dropped", prompt)              # 先查重复再信规模
        self.assertIn("[源:", prompt)                     # 引用格式

    def test_readme_reports_real_stats(self):
        res = core.export_package(str(EXAMPLE), str(self.out), "demo",
                                  on_log=lambda m: None)
        readme = (Path(res["pack_dir"]) / "README.md").read_text(encoding="utf-8")
        self.assertIn(str(res["stats"]["total_after_denoise"]), readme)

    def test_name_traversal_is_contained(self):
        """判据用"父目录就是目标目录"——比"名字里不许出现 .."更准：
        `.._.._escape` 这种名字虽然含点，但根本没有逃逸能力。"""
        res = core.export_package(str(EXAMPLE), str(self.out), "../../escape",
                                  on_log=lambda m: None)
        pack = Path(res["pack_dir"]).resolve()
        self.assertEqual(pack.parent, self.out.resolve(),
                         f"包目录逃出了目标目录：{pack}")
        self.assertNotIn("/", pack.name)
        self.assertNotIn("\\", pack.name)

    def test_missing_input_raises(self):
        with self.assertRaises(FileNotFoundError):
            core.export_package(str(self.out / "nope.csv"), str(self.out))


class TestEmitReport(unittest.TestCase):
    """`core.emit_report` —— GUI 与 Web 界面共同的 HTML 报告出口。

    为什么必须在 core 层测：`app/gui.py` 的改动在本机与 CI **都跑不了**
    （两边都没有 tkinter），GUI 接线只能靠 `test_gui_wiring.py` 的静态 AST 兜底；
    那么这条链路的"真的能产出报告"就只能由本类端到端证明。
    """

    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="cdtest-emit-"))

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def test_report_is_written(self):
        dst = self.out / "report.html"
        res = core.emit_report(str(EXAMPLE_GUIDE), out=str(dst),
                               corpora=[str(EXAMPLE)])
        self.assertEqual(res["out"], str(dst))
        self.assertTrue(dst.exists(), "报告文件没写出来")
        self.assertGreater(res["bytes"], 0)

    def test_report_is_self_contained(self):
        dst = self.out / "report.html"
        core.emit_report(str(EXAMPLE_GUIDE), out=str(dst), corpora=[str(EXAMPLE)])
        html = dst.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn("<script", html.lower(),
                        "自包含报告不该带脚本（要能离线双击打开、也要能通过 CSP）")

    def test_report_reuses_citation_diff(self):
        """信任条必须复用 verify_citations 的差集，不能另写一套口径。"""
        dst = self.out / "report.html"
        res = core.emit_report(str(EXAMPLE_GUIDE), out=str(dst),
                               corpora=[str(EXAMPLE)])
        ver = res["verify"] or {}
        self.assertTrue(ver.get("ran"), "挂了语料就该真跑引用机验")
        self.assertEqual(ver.get("bad"), [], "样例指南的引用应全部可溯源")
        self.assertGreater(len(res["cites"]), 0)


class TestVerify(unittest.TestCase):
    def test_clean_guide_passes(self):
        res = core.verify_guide(str(EXAMPLE_GUIDE), [str(EXAMPLE)])
        self.assertEqual(res["bad"], [])
        self.assertGreater(len(res["cited"]), 0)

    def test_hallucinated_id_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            g = Path(td) / "guide.md"
            g.write_text("某条结论 [源:c999999999|权重9|一级] 与另一条 "
                         "[源:c1001|权重1|一级]。\n", encoding="utf-8")
            res = core.verify_guide(str(g), [str(EXAMPLE)])
            self.assertIn("c999999999", res["bad"])
            self.assertNotIn("c1001", res["bad"])

    def test_missing_guide_raises(self):
        with self.assertRaises(FileNotFoundError):
            core.verify_guide("no_such_guide.md", [str(EXAMPLE)])


class TestRuleTags(unittest.TestCase):
    def test_skill_has_no_bare_rules(self):
        res = core.check_skill()
        self.assertEqual(res["errors"], [], f"SKILL.md 出现裸铁律：{res['errors']}")
        self.assertGreater(res["checked"], 0)


class TestSanitize(unittest.TestCase):
    def test_strips_dangerous_chars(self):
        for bad in ('a/b', 'a\\b', 'a:b', 'a*b', 'a?b', 'a"b', 'a<b', 'a>b', 'a|b'):
            self.assertNotEqual(core._sanitize_name(bad), bad)

    def test_empty_becomes_none(self):
        self.assertEqual(core._sanitize_name("   "), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
