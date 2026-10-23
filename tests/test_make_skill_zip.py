#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能包 ZIP（`scripts/make_skill_zip.py`）的回归测试。

三条主线：
    1. 结构：必需文件齐全 / 排除项一个都不许进（真实语料、维护侧、仓库脚手架）
    2. **可复现性**：同一份源码两次打包 SHA-256 必须相同
       —— 这条是"ZIP 能自动挂 Release 而 exe 不能"的唯一依据，塌了就得改回人工挂载
    3. 判据自身有效：`check()` 必须真能抓出错包（变异验证）

零第三方依赖，仅标准库。
"""

import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "scripts"))
import make_skill_zip as mk  # noqa: E402


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="cd-zip-test-"))
        cls.res = mk.build(out=str(cls.tmp / "a.zip"))
        cls.res2 = mk.build(out=str(cls.tmp / "b.zip"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_no_missing_from_manifest(self):
        self.assertEqual(self.res["missing"], [],
                         "清单里有的文件却不存在——清单漂移了")

    def test_required_files_present(self):
        with zipfile.ZipFile(self.res["out"]) as z:
            have = {n.split("/", 1)[1] for n in z.namelist() if "/" in n}
        for req in mk.REQUIRED:
            self.assertIn(req, have, f"包内缺少必需文件：{req}")

    def test_forbidden_entries_absent(self):
        with zipfile.ZipFile(self.res["out"]) as z:
            names = z.namelist()
        for bad in mk.FORBIDDEN:
            self.assertFalse(any(bad in n for n in names),
                             f"包内混入了不该有的条目：{bad}")

    def test_no_path_traversal_in_archive(self):
        with zipfile.ZipFile(self.res["out"]) as z:
            for n in z.namelist():
                self.assertFalse(n.startswith("/") or ".." in n.split("/"),
                                 f"包内路径不安全：{n}")
                self.assertNotIn("\\", n)

    def test_skill_md_has_frontmatter(self):
        with zipfile.ZipFile(self.res["out"]) as z:
            sk = next(n for n in z.namelist() if n.endswith("SKILL.md"))
            head = z.read(sk).decode("utf-8")[:200]
        self.assertTrue(head.startswith("---"), "SKILL.md 必须带 frontmatter")
        self.assertIn("name: comment-distillery", head)

    def test_version_comes_from_skill_frontmatter(self):
        """版本只能有一个真值源：SKILL.md 的 frontmatter。"""
        self.assertEqual(self.res["version"], mk.skill_version())

    def test_stem_carries_version(self):
        self.assertEqual(self.res["stem"],
                         f"comment-distillery-skill-v{self.res['version']}")

    def test_reproducible_build(self):
        """可复现性 —— ZIP 之所以能自动挂载 Release，靠的就是这一条。"""
        self.assertEqual(self.res["sha256"], self.res2["sha256"],
                         "两次打包 SHA-256 不同：可复现构建被破坏，"
                         "自动挂载 Release 会让已发布的哈希失真")

    def test_zip_is_small_enough_to_upload(self):
        """给"上传给网页版 AI"用，体积必须小。"""
        self.assertLess(self.res["bytes"], 400_000,
                        f"技能包 {self.res['bytes']} 字节，对上传场景偏大")


class TestCheckCatches(unittest.TestCase):
    """判据自身的变异验证：check() 必须真能抓错，否则它只是装饰。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cd-zip-bad-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _make(self, name, members):
        p = self.tmp / name
        with zipfile.ZipFile(p, "w") as z:
            for arc, data in members.items():
                z.writestr(arc, data)
        return str(p)

    def test_good_archive_passes(self):
        good = self._make("good.zip", {
            "x/SKILL.md": "---\nname: comment-distillery\n---\nbody\n",
            "x/LICENSE": "MIT",
            "x/PROMPT.md": "p",
            "x/README.md": "r",
            "x/scripts/prep.py": "",
            "x/scripts/verify_citations.py": "",
            "x/scripts/emit_html.py": "",
            "x/examples/sample_corpus.csv": "id,content\n",
        })
        self.assertEqual(mk.check(good), [], "合规的包不该报错")

    def test_missing_required_is_caught(self):
        bad = self._make("noskill.zip", {"x/LICENSE": "MIT"})
        problems = mk.check(bad)
        self.assertTrue(any("SKILL.md" in m for m in problems))

    def test_missing_frontmatter_is_caught(self):
        bad = self._make("nofm.zip", {
            "x/SKILL.md": "# 没有 frontmatter\n", "x/LICENSE": "MIT"})
        self.assertTrue(any("frontmatter" in m for m in mk.check(bad)))

    def test_forbidden_entry_is_caught(self):
        bad = self._make("leak.zip", {
            "x/SKILL.md": "---\nname: c\n---\n", "x/cases/08/raw.csv": "真实语料"})
        self.assertTrue(any("cases/" in m for m in mk.check(bad)),
                        "真实语料混进包必须被抓")

    def test_unsafe_path_is_caught(self):
        p = self.tmp / "unsafe.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("../../evil.py", "x")
        self.assertTrue(any("不安全" in m for m in mk.check(str(p))))

    def test_nonexistent_file_reports(self):
        self.assertTrue(any("不存在" in m for m in mk.check(str(self.tmp / "nope.zip"))))


if __name__ == "__main__":
    unittest.main()
