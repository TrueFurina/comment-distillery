# -*- coding: utf-8 -*-
"""test_rule_tags.py —— 裸铁律机验的回归测试。

核心不是"跑通"，而是**判据本身有效**：
一个永远说 OK 的检查器毫无价值，所以每个测试都配一个"故意违反"的反例。
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_rule_tags as crt  # noqa: E402

SKILL = ROOT / "SKILL.md"


class TestRepoSkill(unittest.TestCase):
    def test_repo_skill_has_no_bare_rules(self):
        """仓库自身的 SKILL.md 必须零裸铁律。"""
        errors, checked, tagged, _ = crt.check(SKILL)
        self.assertEqual([], errors)
        self.assertEqual(checked, tagged)
        self.assertGreater(checked, 10, "条目太少，判据可能没扫到规则区")

    def test_self_test_passes(self):
        """变异验证必须全拦截。"""
        self.assertEqual(0, crt.self_test(SKILL))


class TestJudgementIsReal(unittest.TestCase):
    """反例：故意违反，检查器必须报错。"""

    def _write(self, body):
        d = tempfile.mkdtemp()
        p = Path(d) / "s.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_bare_rule_is_caught(self):
        p = self._write(
            "## 实施注意\n\n- **这条规则没有任何标记**：应该被抓出来。\n"
        )
        errors, _, _, _ = crt.check(p)
        self.assertTrue(errors, "裸铁律漏检 —— 判据无效")

    def test_tagged_rule_passes(self):
        p = self._write(
            "## 实施注意\n\n- **这条规则有标记** `[战3][战6]`：应当通过。\n"
        )
        errors, _, _, _ = crt.check(p)
        self.assertEqual([], errors)

    def test_pending_section_demotes(self):
        """待复现章节里用铁律标记 = 伪装，必须被抓。"""
        p = self._write(
            "## 待复现观察\n\n- **降级条目却用铁律标记** `[战7]`：应当被抓。\n"
        )
        errors, _, _, _ = crt.check(p)
        self.assertTrue(errors, "伪装条目漏检 —— 判据无效")

    def test_triplet_without_tag_is_caught(self):
        p = self._write(
            "**三件套护城河**：\n"
            "1. **反例对冲**——没有标记\n"
            "2. **引用溯源** `[战4]`\n"
        )
        errors, _, _, _ = crt.check(p)
        self.assertEqual(1, len(errors))
        self.assertIn("三件套", errors[0])


if __name__ == "__main__":
    unittest.main()
