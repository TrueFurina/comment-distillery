# -*- coding: utf-8 -*-
"""
verify_citations.py 回归测试 —— 幻觉引用检测是强制质量门，必须自身可靠。

运行:
    python -m unittest discover -s tests -v
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CSV = ROOT / "examples" / "sample_corpus.csv"
EXAMPLE_GUIDE = ROOT / "examples" / "sample_guide.md"


def load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


verify = load_module("cd_verify", "scripts/verify_citations.py")


class VerifyCitations(unittest.TestCase):

    def _guide(self, content):
        d = tempfile.mkdtemp()
        p = Path(d) / "guide.md"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_example_guide_passes(self):
        """examples/sample_guide.md 的所有引用都应真实存在（退出码 0）。"""
        rc = verify.main([str(EXAMPLE_GUIDE), str(EXAMPLE_CSV)])
        self.assertEqual(rc, 0)

    def test_hallucinated_id_fails(self):
        """引用一个不存在的 ID 必须判定失败（退出码 1）。"""
        g = self._guide("# 测试\n\n> 「某条不存在的引用」[源:c999999999999|权重5|一级]\n")
        rc = verify.main([g, str(EXAMPLE_CSV)])
        self.assertEqual(rc, 1)

    def test_real_id_via_bracket_marker_passes(self):
        g = self._guide("# 测试\n\n> 「真实引用」[源:c1006|权重7|一级]\n")
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 0)

    def test_mixed_real_and_fake_fails(self):
        """真伪混合时必须失败，不能因为"大部分是真的"而放过。"""
        g = self._guide(
            "# 测试\n\n> 「真的」[源:c1006|权重7|一级]\n> 「假的」[源:c888888888888|权重1|一级]\n"
        )
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 1)

    def test_fallback_regex_catches_bare_ids(self):
        """即便没有 [源:] 标记，裸 ID 也应被兜底正则捕获。"""
        g = self._guide("# 测试\n\n正文里直接写了 c999999999999 这个 ID\n")
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 1)

    def test_no_citations_is_not_pass(self):
        """没有引用 -> 不是"通过"，而是"未验证"（退出码 3）。

        原断言是 `== 0`（通过），文档字符串自己也承认「这是『无据可查』，
        调用方需自行判断质量」——可三个调用方（GUI / WebUI / emit_html）
        谁都没有做这个判断，全都把"差集为空"渲染成 ✅ 可交付。
        一条谁都不执行的免责说明，等于没有。现在把判断收回到本模块：
        没验过一律退出码 3，调用方无法把它误读成通过。
        """
        g = self._guide("# 测试\n\n这篇没有任何引用。\n")
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 3)
        # run() 必须给出与退出码一致的标记，避免调用方各自重算判据
        res = verify.run(g, [str(EXAMPLE_CSV)])
        self.assertFalse(res["verified"])
        self.assertEqual(res["unverified_reason"], "指南中未识别到引用标记")

    def test_empty_corpus_is_not_pass(self):
        """语料读不出 ID（只有表头 / ID 列没识别到）-> 未验证（3），不是通过。

        real=0 时差集必然为空，原实现会打印「✅ 所有引用均可在语料中溯源」，
        而实际上校验完全没有地基。
        """
        d = tempfile.mkdtemp()
        empty = Path(d) / "empty.csv"
        empty.write_text("title,body\n", encoding="utf-8")
        g = self._guide("# 测试\n\n> 引用 [源:c1006|权重7|一级]\n")
        self.assertEqual(verify.main([g, str(empty)]), 3)
        res = verify.run(g, [str(empty)])
        self.assertFalse(res["verified"])
        self.assertEqual(res["unverified_reason"], "语料未读出任何 ID")

    def test_verified_pass_when_both_sides_present(self):
        """反向自检：real>0 且 cited>0 时才允许判通过。

        没有这条，上面两条"未验证"断言可能因为 verified 恒假而空转通过。
        """
        g = self._guide("# 测试\n\n> 引用 [源:c1006|权重7|一级]\n")
        res = verify.run(g, [str(EXAMPLE_CSV)])
        self.assertTrue(res["verified"])
        self.assertEqual(res["bad"], [])
        self.assertIsNone(res["unverified_reason"])
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 0)

    def test_missing_file_returns_2(self):
        g = self._guide("# 测试\n")
        self.assertEqual(verify.main([g, "no_such_file.csv"]), 2)
        self.assertEqual(verify.main(["no_such_guide.md", str(EXAMPLE_CSV)]), 2)

    def test_multiple_corpora_union(self):
        """多份语料时，ID 来源应取并集。"""
        d = tempfile.mkdtemp()
        c2 = Path(d) / "c2.csv"
        c2.write_text("id,text\nz900,第二份语料里的条目\n", encoding="utf-8")
        g = self._guide("# 测试\n\n> 来自第一份 [源:c1006|权重7|一级]\n> 来自第二份 [源:z900|权重1|一级]\n")
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV), str(c2)]), 0)

    def test_full_width_colon_supported(self):
        """全角冒号 [源：ID] 也应被识别。"""
        g = self._guide("# 测试\n\n> 「中文全角冒号」[源：c1006|权重7|一级]\n")
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 0)

    def test_escaped_pipe_in_markdown_table(self):
        """markdown 表格内竖线需转义 -> [源:c1006\\|权重7\\|一级]，不得把结尾反斜杠并入 ID。"""
        g = self._guide(
            "# 测试\n\n| 时间 | 行动 |\n|---|---|\n"
            "| 本周 | 做点什么 [源:c1006\\|权重7\\|一级] |\n"
        )
        self.assertEqual(verify.main([g, str(EXAMPLE_CSV)]), 0)
        cited = verify.extract_cited(
            "x [源:c1006\\|权重7\\|一级] y", verify.DEFAULT_PATTERNS
        )
        self.assertIn("c1006", cited)
        self.assertNotIn("c1006\\", cited)

    def test_extract_cited_directly(self):
        text = "见 [源:c1006|权重7|一级] 与 [源: c1017 |权重3|一级] 以及 [源：c1020|权重2|一级]"
        cited = verify.extract_cited(text, verify.DEFAULT_PATTERNS)
        for cid in ("c1006", "c1017", "c1020"):
            self.assertIn(cid, cited)


if __name__ == "__main__":
    unittest.main(verbosity=2)
