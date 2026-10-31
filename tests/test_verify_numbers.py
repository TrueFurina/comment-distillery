#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字机验 + 黑话提示的回归测试。

为什么单独一个文件：这两项都是**机验抓不到的错误类型**的补丁——
引用全真但数字算错、引用全真但术语理解错。它们不像幻觉引用那样
有一个天然的差集判据，所以更需要测试钉住判据本身。

    python tests/test_verify_numbers.py
    python tests/test_glossary.py     （本文件同时覆盖）
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


vn = _load("vn", "scripts/verify_numbers.py")
from app import glossary  # noqa: E402


# 26 条样例，赞数固定，便于复算
CORPUS = """id,text,score
c1,a,100
c2,b,50
c3,c,20
c4,d,10
c5,e,5
c6,f,5
c7,g,2
c8,h,1
"""


def write(tmp, name, text):
    p = Path(tmp) / name
    p.write_text(text, encoding="utf-8")
    return str(p)


class TestVerifyNumbers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vn-")
        self.corpus = write(self.tmp, "c.csv", CORPUS)
        # 合计 193，最高 100；≤5 的有 4 条（5,5,2,1）共 13 赞 = 6.736% → 6.7%

    def test_correct_numbers_pass(self):
        g = write(self.tmp, "g.md",
                  "语料 8 条，赞合计 193，最高赞 100。\n\n"
                  "权重 ≤5 的评论共 4 条，赞合计仅 13，占全部赞的 6.7%。\n")
        issues, checked = vn.collect(g, self.corpus)
        self.assertEqual(issues, [], f"应无矛盾，却报：{issues}")
        self.assertGreater(checked, 0)

    def test_wrong_sum_caught(self):
        g = write(self.tmp, "g.md",
                  "语料 8 条，赞合计 193，最高赞 100。\n\n"
                  "权重 ≤5 的评论共 4 条，赞合计仅 99，占全部赞的 6.7%。\n")
        issues, _ = vn.collect(g, self.corpus)
        self.assertTrue(any("赞合计写 99" in i for i in issues), issues)

    def test_wrong_percent_caught(self):
        g = write(self.tmp, "g.md",
                  "语料 8 条，赞合计 193，最高赞 100。\n\n"
                  "权重 ≤5 的评论共 4 条，赞合计仅 13，占全部赞的 50.0%。\n")
        issues, _ = vn.collect(g, self.corpus)
        self.assertTrue(any("占比写 50.0%" in i for i in issues), issues)

    def test_wrong_count_caught(self):
        g = write(self.tmp, "g.md",
                  "语料 8 条，赞合计 193，最高赞 100。\n\n"
                  "权重 ≤5 的评论共 7 条，赞合计仅 13，占全部赞的 6.7%。\n")
        issues, _ = vn.collect(g, self.corpus)
        self.assertTrue(any("条数写 7" in i for i in issues), issues)

    def test_wrong_total_corpus_caught(self):
        g = write(self.tmp, "g.md", "去噪后 99 条，赞合计 193，最高赞 100。\n")
        issues, _ = vn.collect(g, self.corpus)
        self.assertTrue(any("语料条数写 99" in i for i in issues), issues)

    def test_code_block_ignored(self):
        """代码块里的数字是示例，不该被当成正文去查。"""
        g = write(self.tmp, "g.md",
                  "语料 8 条，赞合计 193，最高赞 100。\n\n"
                  "```\n语料 999 条，赞合计 1\n```\n")
        issues, _ = vn.collect(g, self.corpus)
        self.assertFalse(any("999" in i for i in issues), issues)

    def test_no_false_positive_on_plain_text(self):
        """没有数字表述时，不该硬凑出问题。"""
        g = write(self.tmp, "g.md", "# 标题\n\n只有文字，没有任何可复算的数字。\n")
        issues, checked = vn.collect(g, self.corpus)
        self.assertEqual(issues, [])
        self.assertEqual(checked, 0)


class TestGlossary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gl-")
        # 造一个含黑话 + 别称 + 错字的语料包
        (Path(self.tmp) / "all_comments.txt").write_text(
            "[c1 | 权重10 | 一级 | 复0]\n"
            "虚环能不能成，二游玩家不看好，皮套和中之人的问题很大\n"
            "[c2 | 权重5 | 一级 | 复0]\n"
            "乐府有节目效果跟勒夫是出有什么矛盾吗\n"
            "[c3 | 权重1 | 一级 | 复0]\n"
            "勒夫说他看好虚环，tx 不差钱，杏也在观望\n",
            encoding="utf-8")

    def test_jargon_detected(self):
        h = glossary.scan_hints(self.tmp)
        terms = {j["term"] for j in h["jargon"]}
        for must in ("虚环", "二游", "皮套", "中之人", "tx"):
            self.assertIn(must, terms, f"未识别出术语：{must}")

    def test_aliases_not_flagged_as_typo(self):
        """乐府/勒夫 是同一对象的别称，不该被报成错字。"""
        h = glossary.scan_hints(self.tmp)
        seen = {o["seen"] for o in h["odd"]}
        self.assertNotIn("乐府", seen, "别称被误报成错字")
        self.assertNotIn("勒夫", seen, "别称被误报成错字")
        self.assertTrue(any("乐府" in g for g in h["aliases"]), "别名组未识别")

    def test_alias_group_listed(self):
        md = glossary.glossary_md(self.tmp)
        self.assertIn("同一对象的多种叫法", md)
        self.assertIn("乐府", md)

    def test_numbers_not_flagged_as_repeat(self):
        """'1000''000' 这类数字重复是正常写法，不该报输入打滑。"""
        (Path(self.tmp) / "all_comments.txt").write_text(
            "播放量有 1000 多万，000 号房间\n", encoding="utf-8")
        h = glossary.scan_hints(self.tmp)
        self.assertEqual([o for o in h["odd"] if "000" in o["seen"]], [])

    def test_glossary_written(self):
        p = glossary.write_glossary(self.tmp)
        t = Path(p).read_text(encoding="utf-8")
        self.assertIn("术语与黑话提示", t)
        self.assertIn("宁可留空，不要编释义", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
