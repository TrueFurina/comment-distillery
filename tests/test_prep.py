# -*- coding: utf-8 -*-
"""
prep.py 回归测试（零依赖，仅标准库 unittest）。

运行:
    python -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "sample_corpus.csv"


def load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


prep = load_module("cd_prep", "scripts/prep.py")


class PrepOnExampleCorpus(unittest.TestCase):
    """对 examples/sample_corpus.csv 的端到端断言（值为实测基线）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = cls.tmp.name
        prep.main([str(EXAMPLE), cls.out])
        cls.stats = json.loads((Path(cls.out) / "stats.json").read_text(encoding="utf-8"))
        cls.text = (Path(cls.out) / "all_comments.txt").read_text(encoding="utf-8")
        cls.low = (Path(cls.out) / "low_score_long.txt").read_text(encoding="utf-8")
        cls.idmap = json.loads((Path(cls.out) / "id_map.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_denoise_counts(self):
        """26 条原始 -> 去噪 3 条（广告/纯链接/过短）-> 23 条。"""
        self.assertEqual(self.stats["total_raw"], 26)
        self.assertEqual(self.stats["total_after_denoise"], 23)

    def test_level_split(self):
        """层级拆分：一级 14 / 回复 9。"""
        self.assertEqual(self.stats["n_top_level"], 14)
        self.assertEqual(self.stats["n_reply"], 9)

    def test_sorted_desc_by_score(self):
        """输出按权重降序；首条应为最高权重条目 c1001(842)。"""
        first = self.text.splitlines()[0]
        self.assertIn("c1001", first)
        self.assertIn("权重842", first)

    def test_low_score_long_detection(self):
        """低权重长文（真信号区）应筛出 5 条，且包含 c1006/c1011/c1012/c1017/c1020。"""
        self.assertEqual(self.stats["n_low_score_long"], 5)
        for cid in ("c1006", "c1011", "c1012", "c1017", "c1020"):
            self.assertIn(f"[{cid} |", self.low)

    def test_noise_removed(self):
        """广告、纯链接、过短条目不得出现在产出中。"""
        for noisy in ("c1007", "c1026", "c1008"):
            self.assertNotIn(f"[{noisy} |", self.text)

    def test_id_map_is_traceable(self):
        """id_map.json 必须覆盖全部保留条目，且含溯源所需字段。"""
        self.assertEqual(len(self.idmap), 23)
        sample = next(x for x in self.idmap if x["id"] == "c1001")
        for key in ("id", "score", "floor", "reply"):
            self.assertIn(key, sample)
        self.assertEqual(sample["score"], 842)
        self.assertEqual(sample["floor"], "一级")

    def test_output_files_exist(self):
        for fn in ("all_comments.txt", "low_score_long.txt", "stats.json", "id_map.json"):
            self.assertTrue((Path(self.out) / fn).exists(), f"缺少产出 {fn}")


class FieldAliasAndRobustness(unittest.TestCase):
    """字段别名、最小集、编码容错、去噪规则。"""

    def _run(self, content, encoding="utf-8", args=None):
        d = tempfile.mkdtemp()
        p = Path(d) / "in.csv"
        p.write_text(content, encoding=encoding, newline="")
        out = Path(d) / "out"
        prep.main([str(p), str(out)] + (args or []))
        return out

    def test_english_aliases(self):
        """英文别名 comment_id/content/like_count/reply_count 应被识别。"""
        out = self._run(
            "comment_id,content,like_count,reply_count\n"
            "a1,这是一条足够长的英文别名测试评论,12,3\n"
            "a2,另一条也足够长的测试用评论内容,5,0\n"
        )
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["total_after_denoise"], 2)
        self.assertEqual(stats["score_max"], 12)
        self.assertEqual(stats["reply_sum"], 3)

    def test_minimal_columns(self):
        """只有 id + text 也应能跑，score 缺省为 0。"""
        out = self._run("id,text\nx1,只有两列也能运行的语料内容\nx2,第二条同样可被处理的内容\n")
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["total_after_denoise"], 2)
        self.assertEqual(stats["score_max"], 0)

    def test_gbk_encoding_tolerance(self):
        """GBK 编码输入应被自动识别。"""
        out = self._run("评论ID,评论内容,点赞数\ng1,这是一条用国标编码写成的评论,7\n", encoding="gb18030")
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["total_after_denoise"], 1)
        self.assertEqual(stats["score_max"], 7)

    def test_id_fallback_when_missing(self):
        """无 ID 列时按行号生成 r{i}，保证仍可溯源。"""
        out = self._run("评论内容,点赞数\n没有编号列的评论内容一,3\n没有编号列的评论内容二,1\n")
        txt = (out / "all_comments.txt").read_text(encoding="utf-8")
        self.assertIn("[r0 |", txt)

    def test_noise_rules(self):
        """广告词 / 纯链接 / 纯符号 / 过短均被剔除。"""
        out = self._run(
            "id,text,score\n"
            "n1,加微信代做脚本优惠,9\n"                       # 广告关键词
            "n2,https://spam.invalid/promo,9\n"              # 纯链接
            "n3,哈哈哈哈哈哈哈哈哈哈哈哈,9\n"                  # 纯符号(? 中文算字符)
            "n4,哈,9\n"                                       # 过短
            "n5,这是一条正常长度的有效评论,9\n"               # 保留
        )
        txt = (out / "all_comments.txt").read_text(encoding="utf-8")
        self.assertIn("n5", txt)
        for bad in ("n1", "n2", "n4"):
            self.assertNotIn(f"[{bad} |", txt)

    def test_low_max_threshold_respected(self):
        """--low-max / --low-min-len 应生效。"""
        long_text = "这是一条很长的评论内容" * 12   # 144 字
        out = self._run(
            f"id,text,score\nL1,{long_text},3\nL2,{long_text},99\n",
            args=["--low-max", "5", "--low-min-len", "100"],
        )
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["n_low_score_long"], 1)   # 只有 L1 同时满足两个条件

    def test_isdir_created_recursively(self):
        """输出目录不存在时应自动创建（含多级）。"""
        d = tempfile.mkdtemp()
        out = Path(d) / "a" / "b" / "c"
        prep.main([str(EXAMPLE), str(out)])
        self.assertTrue((out / "stats.json").exists())

    def test_duplicate_ids_are_dropped(self):
        """同一 ID 的完全重复行必须被去重，并计入 stats.dup_dropped。

        背景：热度排序下分页游标重叠，抓取端会产出「同 ID 同内容同赞数」的重复行
        （实测某 2 万条语料里约 22% 是纯重复）。不去重会让评论总数虚高、并让同一条
        观点被重复计入共识度。
        """
        out = self._run(
            "id,text,score\n"
            "d1,这是一条会被重复抓取的评论内容,10\n"
            "d1,这是一条会被重复抓取的评论内容,10\n"      # 与上一行完全相同的重复行
            "d2,另一条正常的评论内容,5\n"
        )
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["total_raw"], 3)
        self.assertEqual(stats["dup_dropped"], 1)
        self.assertEqual(stats["total_after_denoise"], 2)
        txt = (out / "all_comments.txt").read_text(encoding="utf-8")
        self.assertEqual(txt.count("[d1 |"), 1, "重复 ID 只应保留一条")

    def test_dup_dropped_zero_on_clean_corpus(self):
        """无重复语料时 dup_dropped 必须为 0（守卫：去重不能误伤正常条目的赞数统计）。"""
        out = self._run("id,text,score\nz1,第一条正常评论内容,3\nz2,第二条正常评论内容,2\n")
        stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(stats["dup_dropped"], 0)
        self.assertEqual(stats["total_after_denoise"], 2)
        self.assertEqual(stats["score_sum"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
