# -*- coding: utf-8 -*-
"""
emit_html.py 回归测试 —— HTML 是新的交付形态，渲染错了就是交付错了。

为什么值得写测试：
    1) 引用角标的正/反向锚点一旦错位，读者点进去是死链——而"可溯源"是本项目的
       核心承诺，锚点断了等于承诺破了；
    2) 抽取口径必须与 verify_citations **逐字节一致**，否则会出现
       「HTML 说 9 条、机验说 10 条」的自相矛盾；
    3) 表格里的转义竖线 `\\|` 曾把一行切成 4 列（实测 bug），必须锁死。

运行:
    python -m unittest discover -s tests -v
"""
import importlib.util
import re
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


emit = load_module("cd_emit_html", "scripts/emit_html.py")
verify = load_module("cd_verify2", "scripts/verify_citations.py")


class EmitHtml(unittest.TestCase):

    def _render(self, md, **kw):
        d = tempfile.mkdtemp()
        g = Path(d) / "g.md"
        g.write_text(md, encoding="utf-8")
        out = str(Path(d) / "out.html")
        res = emit.run(str(g), out, **kw)
        return Path(out).read_text(encoding="utf-8"), res

    def _render_file(self, guide, **kw):
        d = tempfile.mkdtemp()
        out = str(Path(d) / "out.html")
        res = emit.run(str(guide), out, **kw)
        return Path(out).read_text(encoding="utf-8"), res

    # ── 1. 结构不变量 ──────────────────────────────────────────────
    def test_no_dead_anchors(self):
        """核心不变量：页面内所有 #锚点 都必须有对应元素（角标↔附录双向可达）。"""
        html, _ = self._render_file(EXAMPLE_GUIDE, corpora=[str(EXAMPLE_CSV)])
        ids = set(re.findall(r'id="([^"]+)"', html))
        refs = set(re.findall(r'href="#([^"]+)"', html))
        self.assertEqual(set(), refs - ids, f"死链锚点：{sorted(refs - ids)}")

    def test_self_contained_no_external_assets(self):
        """自包含：不得引用任何外链 js/css/字体（对标产品的硬约束）。"""
        html, _ = self._render_file(EXAMPLE_GUIDE, corpora=[str(EXAMPLE_CSV)])
        ext = re.findall(r'(?:src|href)="https?://[^"]+\.(?:js|css|woff2?)"', html)
        self.assertEqual([], ext)

    def test_has_required_blocks(self):
        html, res = self._render_file(EXAMPLE_GUIDE, corpora=[str(EXAMPLE_CSV)])
        for tag in ("<html", "</html>", "<head>", "</head>", "<body>", "</body>"):
            self.assertIn(tag, html)
        self.assertIn('class="trustbar', html)
        self.assertIn('class="toc"', html)
        self.assertIn('id="sources"', html)
        self.assertEqual(5, len(res["headings"]), "sample_guide 应有 5 个 H2 章节")

    # ── 2. 引用口径与机验一致 ──────────────────────────────────────
    def test_cite_extraction_matches_verifier(self):
        """口径一致：emit 渲染出的引用 ID 集合 == verify 抽取的集合。

        两台机器对"什么算一条引用"的判断必须相同——这是靠直接复用
        verify 的抽取逻辑（而非另写正则）+ 本测试双重锁死的。
        """
        md = EXAMPLE_GUIDE.read_text(encoding="utf-8")
        cites = emit.Cites()
        emit.render_markdown(md, cites, {}, [])
        by_emit = set(cites.unique)
        by_verify = verify.extract_cited(md, [])      # 空 patterns = 只要结构化标记
        self.assertEqual(by_verify, by_emit,
                         f"口径漂移：emit={sorted(by_emit)} verify={sorted(by_verify)}")

    def test_escaped_pipe_in_table_not_split(self):
        """表格里的 \\| 是单元格内容，不是列分隔符（实测 bug：2 列被切成 4 列）。"""
        md = ("| 时间 | 行动 |\n|---|---|\n"
              "| 本周 | 先界定问题 [源:c1020\\|权重2\\|一级] |\n")
        html, _ = self._render(md)
        self.assertEqual(2, len(re.findall(r"<th>", html)), "表头应 2 列")
        self.assertEqual(2, len(re.findall(r"<td>", html)), "单元格应 2 个")
        self.assertNotIn("|权重2|", html, "引用标记尾部必须被整体消费掉")

    def test_cite_tail_is_consumed(self):
        md = "一句结论 [源:c1006|权重7|一级] 结束。"
        html, _ = self._render(md)
        self.assertIn('href="#src-c1006"', html)
        self.assertNotIn("权重7|一级]", html, "引用标记尾部不应残留在页面上")

    # ── 3. 信任条三种状态 ──────────────────────────────────────────
    def test_trustbar_pass(self):
        html, res = self._render_file(EXAMPLE_GUIDE, corpora=[str(EXAMPLE_CSV)])
        self.assertEqual([], res["verify"]["bad"])
        self.assertIn("机验通过", html)
        self.assertIn("差集", html)
        self.assertNotIn("trustbar bad", html)

    def test_trustbar_hallucination_is_flagged(self):
        """变异验证：把假 ID 塞进去，信任条必须翻红、且 main 退出码非 0。"""
        md = "一条引用 [源:c9999999|权重1|一级] 和真引用 [源:c1006|权重7|一级]。"
        d = tempfile.mkdtemp()
        g = Path(d) / "g.md"
        g.write_text(md, encoding="utf-8")
        out = str(Path(d) / "o.html")
        res = emit.run(str(g), out, corpora=[str(EXAMPLE_CSV)])
        html = Path(out).read_text(encoding="utf-8")
        self.assertEqual(["c9999999"], res["verify"]["bad"])
        self.assertIn("trustbar bad", html, "幻觉引用必须让信任条翻红")
        self.assertIn("不得交付", html)
        rc = emit.main([str(g), "-o", out, "--corpus", str(EXAMPLE_CSV)])
        self.assertEqual(1, rc, "差集非空时 CLI 必须返回非 0")

    def test_trustbar_warn_without_corpus(self):
        html, res = self._render_file(EXAMPLE_GUIDE)
        self.assertFalse(res["verify"]["ran"])
        self.assertIn("未跑机验", html)

    # ── 4. 安全 / 编码 ─────────────────────────────────────────────
    def test_html_is_escaped(self):
        md = "危险内容 <script>alert(1)</script> 与 & 符号"
        html, _ = self._render(md)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_markdown_subset_renders(self):
        md = ("# 标题\n\n段落 **粗体** 与 `代码`。\n\n"
              "## 章节\n\n- 项目甲\n- 项目乙\n\n"
              "1. 第一步\n2. 第二步\n\n"
              "> 引用块\n\n```\ncode block\n```\n\n---\n")
        html, _ = self._render(md)
        self.assertIn("<strong>粗体</strong>", html)
        self.assertIn("<code>代码</code>", html)
        self.assertIn("<ul><li>项目甲</li>", html)
        self.assertIn("<ol><li>第一步</li>", html)
        self.assertIn("<blockquote>", html)
        self.assertIn("<pre><code>code block</code></pre>", html)
        self.assertIn("<hr>", html)
        self.assertNotIn("```", html)

    def test_missing_guide_raises(self):
        with self.assertRaises(FileNotFoundError):
            emit.run("nonexistent-guide.md", "/tmp/x.html")


if __name__ == "__main__":
    unittest.main(verbosity=2)
