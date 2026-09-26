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
