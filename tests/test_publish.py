#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/publish.py 的单元测试（零依赖，不联网：所有 HTTP 调用均打桩）。

覆盖：
  - slugify
  - build_article（真实调 emit_html 渲染 sample_guide）
  - _cookie_val / _mask
  - 合规护栏 _guard_no_csv（绝不接受 .csv 作为发布对象）
  - GithubAdapter：dry-run / 真实写盘 / sitemap 幂等
  - CsdnAdapter：请求构造（打桩 HTTP，断言 endpoint + payload）
  - BilibiliAdapter：两步流程（addupdate→submit）+ csrf 抽取
  - ZhihuAdapter：成功返回 URL / 失败回退写草稿
"""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("cd_publish", ROOT / "scripts" / "publish.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

SAMPLE = ROOT / "examples" / "sample_guide.md"
CFG = publish.default_config()


def _fake_cfg(**over):
    c = publish.default_config()
    for k, v in over.items():
        c[k].update(v)
    return c


class TestSlugify(unittest.TestCase):
    def test_keeps_cn_and_dash(self):
        self.assertEqual(publish.slugify("《学历·命运》评论深度指南"),
                         "学历-命运-评论深度指南")

    def test_strips_path_chars(self):
        self.assertEqual(publish.slugify("a/b:c*"), "a-b-c")

    def test_fallback(self):
        self.assertEqual(publish.slugify("///"), "guide")


class TestHelpers(unittest.TestCase):
    def test_cookie_val(self):
        c = "SESSDATA=abc; bili_jct=xyz123; DedeUserID=42"
        self.assertEqual(publish._cookie_val(c, "bili_jct"), "xyz123")
        self.assertEqual(publish._cookie_val(c, "_xsrf"), "")

    def test_mask(self):
        self.assertIn("len=", publish._mask("x" * 50))
        self.assertEqual(publish._mask(""), "(空)")


class TestCompliance(unittest.TestCase):
    def test_guard_rejects_csv_guide(self):
        with self.assertRaises(SystemExit):
            publish._guard_no_csv("corpus.csv", None)

    def test_guard_allows_md(self):
        # 不应抛异常
        publish._guard_no_csv(str(SAMPLE), None)

    def test_guard_allows_csv_corpus(self):
        # 文档示例用法：`--corpus cases/.../*.csv`，corpus 是 .csv 但属正常本地输入，
        # 护栏只查 guide，绝不应误杀这条路径（原实现会直接 SystemExit）。
        csv_path = next((p for p in (ROOT / "cases").rglob("*.csv")), None)
        if csv_path is None:
            self.skipTest("仓库无现成 csv 可供 corpus 护栏复验")
        # 不应抛异常（guide 仍是 .md）
        publish._guard_no_csv(str(SAMPLE), [str(csv_path)])


class TestBuildArticle(unittest.TestCase):
    def test_render(self):
        art = publish.build_article(SAMPLE, None)
        self.assertIn("<article>", art.html_full)
        self.assertIn("</main>", art.html_full)
        # html_body 是 <article>…</main> 的内部内容（不含 <article> 包裹标签）
        self.assertTrue(art.html_body.strip())
        self.assertIn("一、数据底座", art.html_body)
        self.assertTrue(art.url.endswith(".html"))
        # canonical 回填
        art.canonical_url = art.url
        self.assertIn(art.url, art.markdown + publish.canonical_footer(art.url))


class TestGithubAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.orig_site = publish.SITE_DIR
        self.orig_cases = publish.CASES_DIR
        self.orig_sm = publish.SITEMAP
        publish.SITE_DIR = self.tmp
        publish.CASES_DIR = self.tmp / "cases"
        publish.SITEMAP = self.tmp / "sitemap.xml"
        # GithubAdapter._update_sitemap 只在 sitemap 已存在时才插入条目
        publish.SITEMAP.write_text(
            '<?xml version="1.0"?>\n<urlset '
            'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            '  <url><loc>https://x/</loc></url>\n</urlset>\n', encoding="utf-8")

    def tearDown(self):
        publish.SITE_DIR = self.orig_site
        publish.CASES_DIR = self.orig_cases
        publish.SITEMAP = self.orig_sm

    def test_dry_run_no_write(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        r = publish.GithubAdapter().publish(art, CFG["github"], dry_run=True)
        self.assertTrue(r.dry)
        self.assertFalse((self.tmp / "cases").exists())

    def test_real_write_and_sitemap_idempotent(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        r1 = publish.GithubAdapter().publish(art, CFG["github"], dry_run=False)
        self.assertTrue(r1.ok)
        self.assertTrue((publish.CASES_DIR / f"{art.slug}.html").exists())
        self.assertTrue(publish.SITEMAP.exists())
        # 第二次同 slug 不应重复写 sitemap 条目
        publish.GithubAdapter().publish(art, CFG["github"], dry_run=False)
        n = publish.SITEMAP.read_text(encoding="utf-8").count(art.rel_path)
        self.assertEqual(n, 1)


class TestCsdnAdapter(unittest.TestCase):
    def test_disabled(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        r = publish.CsdnAdapter().publish(art, CFG["csdn"], dry_run=False)
        self.assertFalse(r.ok)

    def test_request_shape(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        cfg = _fake_cfg(csdn={"enabled": True, "cookie": "UserToken=FAKE",
                              "endpoint": "https://example.test/save"})
        captured = {}
        with mock.patch.object(publish, "http_post_json",
                               lambda url, payload, headers: captured.update(
                                   url=url, payload=payload, headers=headers) or (200, '{"code":200,"data":{"url":"u"}}')):
            r = publish.CsdnAdapter().publish(art, cfg["csdn"], dry_run=False)
        self.assertTrue(r.ok)
        self.assertEqual(captured["url"], "https://example.test/save")
        self.assertEqual(captured["payload"]["title"], art.title)
        self.assertEqual(captured["payload"]["type"], "original")
        self.assertIn(art.url, captured["payload"]["content"])
        self.assertEqual(captured["headers"]["Cookie"], "UserToken=FAKE")


class TestBilibiliAdapter(unittest.TestCase):
    def test_missing_csrf(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        cfg = _fake_cfg(bilibili={"enabled": True, "cookie": "SESSDATA=x"})
        r = publish.BilibiliAdapter().publish(art, cfg["bilibili"], dry_run=False)
        self.assertFalse(r.ok)
        self.assertIn("bili_jct", r.msg)

    def test_two_step_flow(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        cookie = "SESSDATA=x; bili_jct=csrfTOKEN; DedeUserID=1"
        cfg = _fake_cfg(bilibili={"enabled": True, "cookie": cookie, "submit": True})
        calls = []
        def fake_form(url, fields, headers, timeout=30):
            calls.append((url, fields))
            if url.endswith("/draft/addupdate"):
                return 200, '{"code":0,"data":{"aid":12345}}'
            if url.endswith("/article/submit"):
                return 200, '{"code":0,"message":"ok"}'
            return 200, '{"code":0}'
        with mock.patch.object(publish, "http_post_form", fake_form):
            r = publish.BilibiliAdapter().publish(art, cfg["bilibili"], dry_run=False)
        self.assertTrue(r.ok)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith("/draft/addupdate"))
        self.assertEqual(calls[0][1]["csrf"], "csrfTOKEN")
        self.assertEqual(calls[0][1]["original"], 1)
        self.assertTrue(calls[1][0].endswith("/article/submit"))
        self.assertEqual(calls[1][1]["aid"], 12345)


class TestZhihuAdapter(unittest.TestCase):
    def test_success(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        cfg = _fake_cfg(zhihu={"enabled": True, "cookie": "a=b; _xsrf=XYZ",
                               "xsrf": ""})
        with mock.patch.object(publish, "http_post_json",
                               lambda url, payload, headers: (
                                   200, '{"id":9988,"url":"https://zhuanlan.zhihu.com/p/9988"}')):
            r = publish.ZhihuAdapter().publish(art, cfg["zhihu"], dry_run=False)
        self.assertTrue(r.ok)
        self.assertIn("9988", r.url)
        self.assertEqual(r.msg, "已发布")

    def test_fallback_writes_draft(self):
        art = publish.build_article(SAMPLE, None)
        art.canonical_url = art.url
        cfg = _fake_cfg(zhihu={"enabled": True, "cookie": "a=b; _xsrf=XYZ"})
        with mock.patch.object(publish, "http_post_json",
                               lambda url, payload, headers: (
                                   200, '{"code":1,"msg":"blocked"}')):
            r = publish.ZhihuAdapter().publish(art, cfg["zhihu"], dry_run=False)
        self.assertFalse(r.ok)  # 失败 → 回退
        draft = ROOT / "out" / f"{art.slug}.zhihu.md"
        self.assertTrue(draft.exists(), "应生成可粘贴草稿")
        draft.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
