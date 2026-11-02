#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`scripts/clean_scratch.py` 保护名单的回归测试。

事故背景（2026-11-02）
----------------------
一次「清理 scratch」把整个 `output/` 移进归档，连带带走 5 份已交付的蒸馏报告
与 `报告索引.html`；而 `output/` 被 .gitignore 忽略，git 里没有备份可回滚。

修法不是写文档提醒，而是把这套判断写成代码 + 钉成测试：
**只要有人改坏了保护名单，这些用例必须变红。**

    python tests/test_clean_scratch.py
    python -m unittest discover -s tests

回退验证：删掉 clean_scratch.py 里 `distill-*` 那一行 →
TestClassify.test_distill_pack_is_protected 必红。

刻意只用 unittest（不用 pytest）：本仓库 CI 用 `unittest discover`，
且有「零依赖」守卫，测试文件不得引入第三方包。
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import clean_scratch  # noqa: E402


class TestClassify(unittest.TestCase):
    """分类判定：交付物必须 protected，调试残留才是 safe。"""

    def test_distill_pack_is_protected(self):
        """★ 核心：5 个真实蒸馏包名都必须判为 protected。"""
        names = [
            "distill-20261030-031221",
            "distill-20261030-043155",
            "distill-20261101-094557",
            "distill-20261101-145606",
            "distill-20261101-153152",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(clean_scratch.classify(name), "protected")

    def test_deliverables_and_data_are_protected(self):
        names = [
            "报告索引.html",
            "index.html",
            "comments-1780000000.csv",
            "prep-20261101-101010",
            "all_comments.txt",
            "id_map.json",
            ".writable",
            "README.md",
            "_backup",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(clean_scratch.classify(name), "protected")

    def test_debug_leftovers_are_safe(self):
        names = [
            "e2e-smoke", "dbg-1", "tmp-x", "ctl", "p13b",
            "ui-final", "__pycache__", "a.tmp", "b.log",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(clean_scratch.classify(name), "safe")

    def test_unknown_defaults_to_keep(self):
        """未知条目一律保留 —— 宁可漏删，不可误删。"""
        for name in ["some_unknown_dir", "notes", "whatever.html"]:
            with self.subTest(name=name):
                self.assertEqual(clean_scratch.classify(name), "keep")


class TestCleanEndToEnd(unittest.TestCase):
    """端到端：dry-run 不删；--yes 只删 safe；保护名单优先于白名单。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        out = self.project / "output"
        out.mkdir()
        (out / "distill-20261101-153152").mkdir()
        (out / "distill-20261101-153152" / "report.html").write_text(
            "<html>keep me</html>", "utf-8")
        (out / "报告索引.html").write_text("<html>index</html>", "utf-8")
        (out / "comments-1780000000.csv").write_text("id,text\n1,hi\n", "utf-8")
        (out / ".writable").write_text("ok", "utf-8")
        (out / "e2e-junk").mkdir()
        (out / "e2e-junk" / "f.txt").write_text("junk", "utf-8")
        (out / "dbg.log").write_text("junk", "utf-8")
        self.out = out

    def tearDown(self):
        self._tmp.cleanup()

    def test_dry_run_deletes_nothing(self):
        rc = clean_scratch.main(["--project", str(self.project)])
        self.assertEqual(rc, 0)
        self.assertTrue((self.out / "e2e-junk").exists(), "dry-run 不能删任何东西")
        self.assertTrue((self.out / "dbg.log").exists(), "dry-run 不能删任何东西")

    def test_yes_deletes_only_safe(self):
        rc = clean_scratch.main(["--project", str(self.project), "--yes"])
        self.assertEqual(rc, 0)

        # 调试残留被清掉
        self.assertFalse((self.out / "e2e-junk").exists())
        self.assertFalse((self.out / "dbg.log").exists())

        # ★ 交付物一个都不能少
        self.assertTrue((self.out / "distill-20261101-153152" / "report.html").exists())
        self.assertTrue((self.out / "报告索引.html").exists())
        self.assertTrue((self.out / "comments-1780000000.csv").exists())
        self.assertTrue((self.out / ".writable").exists())

    def test_protected_survives_even_when_added_to_safe_patterns(self):
        """即使有人把交付物名字写进 SAFE_PATTERNS，受保护名单也必须赢。"""
        original = clean_scratch.SAFE_PATTERNS[:]
        try:
            clean_scratch.SAFE_PATTERNS = original + ["distill-*", "报告索引*"]
            rc = clean_scratch.main(["--project", str(self.project), "--yes"])
            self.assertEqual(rc, 0)
        finally:
            clean_scratch.SAFE_PATTERNS = original

        self.assertTrue(
            (self.out / "distill-20261101-153152" / "report.html").exists(),
            "保护名单优先级必须高于白名单")
        self.assertTrue((self.out / "报告索引.html").exists())


class TestBackupReports(unittest.TestCase):
    """交付物快照 + 误删后从快照恢复。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        out = self.project / "output"
        out.mkdir()
        (out / "distill-20261101-153152").mkdir()
        (out / "distill-20261101-153152" / "report.html").write_text(
            "<html>keep me</html>", "utf-8")
        (out / "报告索引.html").write_text("<html>index</html>", "utf-8")
        self.out = out

    def tearDown(self):
        self._tmp.cleanup()

    def _backup_module(self):
        import importlib
        return importlib.import_module("backup_reports")

    def test_snapshot_and_restore(self):
        import shutil

        br = self._backup_module()
        self.assertEqual(br.main(["--project", str(self.project)]), 0)

        snaps = list((self.out / "_backup").iterdir())
        self.assertEqual(len(snaps), 1)
        snap = snaps[0]
        self.assertTrue((snap / "distill-20261101-153152" / "report.html").exists())
        self.assertTrue((snap / "报告索引.html").exists())

        # 模拟误删，再从快照恢复
        shutil.rmtree(self.out / "distill-20261101-153152")
        (self.out / "报告索引.html").unlink()

        self.assertEqual(br.main(["--project", str(self.project), "--restore", snap.name]), 0)
        self.assertTrue((self.out / "distill-20261101-153152" / "report.html").exists())
        self.assertTrue((self.out / "报告索引.html").exists())

    def test_nothing_to_backup_returns_nonzero(self):
        import shutil

        shutil.rmtree(self.out / "distill-20261101-153152")
        (self.out / "报告索引.html").unlink()
        br = self._backup_module()
        self.assertEqual(br.main(["--project", str(self.project)]), 1)


class TestGitignoreRule(unittest.TestCase):
    """防护说明本身必须能进版本库：.gitignore 要放行 output/README.md。"""

    def test_gitignore_allows_output_readme(self):
        gi_path = ROOT / ".gitignore"
        self.assertTrue(gi_path.exists())
        gi = gi_path.read_text("utf-8")
        self.assertIn("!output/README.md", gi, "必须用 !output/README.md 放行防护说明")
        self.assertIn("output/*", gi, "必须用 output/* 而非 output/ ，否则无法放行子文件")


if __name__ == "__main__":
    unittest.main(verbosity=2)
