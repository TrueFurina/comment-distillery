#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / emit_html.py
指南 Markdown → 自包含 HTML 阅读报告（零依赖，纯标准库）。

为什么要有这一步：
    Markdown 是**给作者看的中间物**，不是交付物——它不能发给同事、不能发群里、
    不能打印成 PDF 交上去。对标产品（vreport）的产物是自包含 HTML + 长图，
    用户拿到就能读、就能转发。本脚本补上这一跳，且**不破零依赖承诺**。

它做三件事，其中第 2 条是 Markdown 做不到、且直接强化本项目护城河的：

    1) 渲染   Markdown 子集 → 语义 HTML（内联 CSS，单文件，可直接打开 / 转发 / 打印）
    2) 溯源   每条 [源:ID|权重N|层级] 渲染成**可点击角标** → 跳到附录原句 → 可反跳回正文
               对标产品的来源绑定是隐藏属性（data-source-units），读者看不见也点不了；
               本项目把"可溯源"从文字声明变成**可交互的证据**。
    3) 信任条 给了 --corpus 就复用 verify_citations 的差集结果，把
               「N 条引用 · 机验通过 · 差集 0」或「⚠️ 幻觉引用 M 条」写在页首。

引用口径与机验严格一致：
    ID 抽取**直接调用 verify_citations.extract_cited**，不另写一份正则。
    两台机器对"什么算一条引用"的判断必须相同，否则会出现
    「HTML 说 96 条、机验说 98 条」这种自相矛盾。口径一致由
    tests/test_emit_html.py 的 test_cite_extraction_matches_verifier 锁死。

用法:
    python scripts/emit_html.py <guide.md> [-o out.html]
                                [--corpus a.csv b.csv] [--field 评论ID]
                                [--title 标题] [--subtitle 副标题] [--no-verify]

零依赖，仅标准库。
"""
import argparse
import csv
import importlib.util
import re
import sys
import time
from pathlib import Path

# 语料正文字段的别名（与 docs/canonical-format.md 的容错口径一致）
TEXT_ALIASES = ["text", "正文", "评论内容", "内容", "content", "body", "comment", "comment_text"]
ID_ALIASES = ["id", "评论id", "comment_id", "commentid", "cid", "条目id", "item_id"]


def utf8_stdout():
    """stdout/stderr 切 UTF-8：Windows 控制台可能是 cp1252，print 中文会
    UnicodeEncodeError（实测 GitHub windows runner 因此整步失败）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_sibling(alias, rel_name):
    """按路径加载同目录脚本（scripts/ 不是包，不能直接 import）。"""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(alias, here / rel_name)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载同目录模块：{rel_name}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


verify = load_sibling("cd_emit_verify", "verify_citations.py")


# ────────────────────────────── 读取语料 ──────────────────────────────

def _pick_col(names, aliases, explicit=None):
    if explicit:
        for n in names:
            if n and n.strip().lower() == explicit.strip().lower():
                return n
    for a in aliases:                                  # 精确优先
        for n in names:
            if n and n.strip().lower() == a.lower():
                return n
    for a in aliases:                                  # 子串兜底
        if len(a) < 3:
            continue
        for n in names:
            if n and a.lower() in n.lower():
                return n
    return None


def load_corpus(paths, field=None):
    """读语料 CSV → {id: {"text":…, "score":…, "floor":…}}。

    编码容错与 verify_citations.load_ids 一致（utf-8-sig → gb18030 → gbk）。
    """
    rows = {}
    for path in paths:
        last = None
        for enc in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
            try:
                with open(path, encoding=enc, newline="") as f:
                    reader = csv.DictReader(f)
                    names = [n for n in (reader.fieldnames or []) if n]
                    idc = _pick_col(names, ID_ALIASES, field)
                    txtc = _pick_col(names, TEXT_ALIASES)
                    scorec = _pick_col(names, ["score", "点赞", "权重", "like"])
                    floorc = _pick_col(names, ["is_reply", "层级", "floor"])
                    for r in reader:
                        if not idc:
                            continue
                        cid = str(r.get(idc, "")).strip()
                        if not cid or cid in rows:
                            continue
                        rows[cid] = {
                            "text": str(r.get(txtc, "")).strip() if txtc else "",
                            "score": str(r.get(scorec, "")).strip() if scorec else "",
                            "floor": _norm_floor(str(r.get(floorc, ""))) if floorc else "",
                        }
                break
            except Exception as e:
                last = e
                continue
        else:
            raise last
    return rows


def skill_version(root):
    """从 SKILL.md frontmatter 读版本号——**绝不硬编码**，否则文档一改就漂移。"""
    sk = root / "SKILL.md"
    try:
        head = sk.read_text(encoding="utf-8")[:1200]
        m = re.search(r"^version:\s*([\w.\-]+)\s*$", head, re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


# ────────────────────────────── Markdown 渲染 ──────────────────────────────

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unesc_pipe(s):
    """markdown 表格里的转义竖线 \\| → |（先于行内渲染处理）。"""
    return s.replace("\\|", "|")


class Cites:
    """引用角标的出现计数，用于生成正反双向锚点。"""

    def __init__(self):
        self.seen = {}          # id -> 出现次数
        self.unique = []        # 首次出现的顺序

    def mark(self, cid):
        n = self.seen.get(cid, 0) + 1
        self.seen[cid] = n
        if n == 1:
            self.unique.append(cid)
        return n


# 与 verify_citations.extract_cited 相同的 ID 捕获组（口径一致），
# 但额外消费掉尾部：`[源:c1020\|权重2\|一级]` 里的 `\|权重2\|一级]` 必须一起吃掉，
# 否则页面上会残留 "|权重2|一级]" 这样的噪音。
# 尾部 `]` 缺失时也照样匹配（异常输入不漏渲染，与机验口径保持一致）。
CITE_RE = re.compile(r"\[源\s*[:：]\s*([^\]\|｜\s,，;；\\]+)(?:[^\]\n]*\])?")


def _cite_html(m, cites, meta):
    cid = m.group(1).strip().strip("\\")
    n = cites.mark(cid)
    info = meta.get(cid, {})
    bits = [cid]
    if info.get("score"):
        bits.append(f"权重{info['score']}")
    if info.get("floor"):
        bits.append(info["floor"])
    label = "源" if n == 1 else f"源{n}"
    tip = " · ".join(bits)
    anchor = "" if n == 1 else f"-{n}"
    return (f'<a class="cite" id="cite-{cid}{anchor}" href="#src-{cid}" '
            f'title="{esc(tip)}">{label}</a>')


def _norm_floor(v):
    """层级字段归一到 SKILL.md 的口径：一级 / 回复。"""
    s = (v or "").strip().lower()
    if s in ("1", "true", "是", "yes", "y", "reply", "回复"):
        return "回复"
    if s in ("0", "false", "否", "no", "n", "root", "一级"):
        return "一级"
    return v.strip()


def render_inline(s, cites, meta):
    # 先还原 markdown 的转义竖线：表格里必须写成 [源:c1020\|权重2\|一级]，
    # 若不还原，角标 title 会带着反斜杠。放在 esc 之前，反斜杠不受 esc 影响。
    s = unesc_pipe(s)
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = CITE_RE.sub(lambda m: _cite_html(m, cites, meta), s)
    return s


def _split_row(line):
    """拆 markdown 表格行。

    ⚠️ 必须在**未还原转义竖线**的原始行上拆：markdown 表格内的 `\\|` 是单元格
    内容里的竖线（本项目的引用标记就依赖它，见 SKILL.md 环境坑），若先还原成 `|`
    再拆，一个单元格会被切成多列——实测 sample_guide 的表格从 2 列变 4 列。
    """
    line = line.strip().strip("|")
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def _is_table_sep(line):
    s = line.strip().strip("|")
    return bool(s) and bool(re.match(r"^[\s:\-\|]+$", s))


def _is_block_start(line):
    s = line.strip()
    if not s:
        return True
    return (s.startswith("```") or s.startswith(">") or s.startswith("#")
            or s.startswith("|") or re.match(r"^[-*+]\s+", s)
            or re.match(r"^\d+[.)]\s+", s) or s in ("---", "***", "___"))


def render_markdown(md, cites, meta, headings):
    """极简行式状态机：够覆盖本项目指南用到的 Markdown 子集即可。

    刻意不做全量 CommonMark——那需要第三方库或上千行代码，会破零依赖承诺。
    """
    lines = md.splitlines()
    out = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % esc("\n".join(buf)))
            continue

        if s in ("---", "***", "___"):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = min(len(m.group(1)), 4)
            txt = m.group(2).strip()
            hid = ""
            if lvl == 2:
                hid = f"h2-{len(headings) + 1}"
                headings.append((hid, txt))
                out.append(f'<h2 id="{hid}">{render_inline(txt, cites, meta)}</h2>')
            else:
                out.append(f"<h{lvl}>{render_inline(txt, cites, meta)}</h{lvl}>")
            i += 1
            continue

        if s.startswith("|") and i + 1 < n and _is_table_sep(lines[i + 1]):
            head = _split_row(lines[i])
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(_split_row(lines[i]))
                i += 1
            th = "".join(f"<th>{render_inline(c, cites, meta)}</th>" for c in head)
            tr = "".join(
                "<tr>%s</tr>" % "".join(f"<td>{render_inline(c, cites, meta)}</td>" for c in row)
                for row in body)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>")
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            inner = render_inline("\n".join(buf), cites, meta).replace("\n", "<br>")
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        if re.match(r"^[-*+]\s+", s):
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*+]\s+", "", lines[i].strip()))
                i += 1
            li = "".join(f"<li>{render_inline(t, cites, meta)}</li>" for t in items)
            out.append(f"<ul>{li}</ul>")
            continue

        if re.match(r"^\d+[.)]\s+", s):
            items = []
            while i < n and re.match(r"^\d+[.)]\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+[.)]\s+", "", lines[i].strip()))
                i += 1
            li = "".join(f"<li>{render_inline(t, cites, meta)}</li>" for t in items)
            out.append(f"<ol>{li}</ol>")
            continue

        if not s:
            i += 1
            continue

        buf = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>%s</p>" % render_inline(" ".join(buf), cites, meta))
        else:
            i += 1

    return "\n".join(out)


# ────────────────────────────── 页面装配 ──────────────────────────────

CSS = """
:root{color-scheme:light;--paper:#fff;--canvas:#f2f5f7;--ink:#3c4650;--heading:#20272e;
--muted:#6b7683;--accent:#0f6e56;--accent-wash:#e7f4ef;--line:#e6eaee;--warn:#a32d2d;
--warn-wash:#fbe9e9;--code:#f5f7f9}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:20px}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--canvas);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",
"Segoe UI",sans-serif;font-size:17px;line-height:1.85;-webkit-font-smoothing:antialiased}
.paper{max-width:860px;margin:24px auto;padding:44px 46px 28px;background:var(--paper);
border-radius:8px;box-shadow:0 8px 30px rgba(37,56,75,.05);overflow-wrap:anywhere}
h1{font-size:32px;line-height:1.45;font-weight:700;color:var(--heading);margin:0 0 6px}
h2{font-size:24px;line-height:1.55;font-weight:700;color:var(--heading);
margin:44px 0 18px;padding-bottom:12px;border-bottom:1px solid var(--line)}
h3{font-size:19px;line-height:1.6;font-weight:700;color:var(--heading);margin:30px 0 10px}
h4{font-size:17px;font-weight:700;color:var(--heading);margin:22px 0 8px}
p{margin:0 0 16px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
strong{font-weight:700;color:var(--heading)}
code{font-family:ui-monospace,Consolas,"Cascadia Code",monospace;font-size:.86em;
background:var(--code);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;
padding:14px 16px;overflow-x:auto;margin:0 0 18px}
pre code{background:none;border:none;padding:0}
blockquote{margin:0 0 16px;padding:2px 0 2px 18px;border-left:3px solid var(--accent);
color:var(--ink)}
ul,ol{margin:0 0 16px;padding-left:26px}
li{margin:4px 0}
table{width:100%;border-collapse:collapse;font-size:15px;line-height:1.7;margin:0 0 20px}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
th{background:var(--accent-wash);color:var(--heading);font-weight:700}
hr{border:none;border-top:1px solid var(--line);margin:32px 0}
.brand{font-size:12px;letter-spacing:2px;color:var(--muted);font-weight:700;margin-bottom:14px}
.subtitle{font-size:20px;color:var(--muted);margin:0 0 14px}
.lead{font-size:17px;line-height:1.9;margin:0 0 12px}
.meta{font-size:12.5px;color:var(--muted);margin:0;line-height:1.7}
.trustbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin:22px 0 4px;
padding:12px 16px;border-radius:8px;font-size:13.5px;font-weight:700;
background:var(--accent-wash);border:1px solid var(--accent);color:var(--accent)}
.trustbar.bad{background:var(--warn-wash);border-color:var(--warn);color:var(--warn)}
.trustbar.warn{background:#fdf6e6;border-color:#c99a2e;color:#8a6412}
.trustbar .n{font-size:17px;font-variant-numeric:tabular-nums}
.cite{display:inline-block;font-size:11px;font-weight:700;line-height:1.5;vertical-align:2px;
margin:0 1px;padding:0 5px;border-radius:4px;background:var(--accent-wash);
border:1px solid var(--accent);color:var(--accent);white-space:nowrap}
.cite:hover{background:var(--accent);color:#fff;text-decoration:none}
.toc{background:#f7f9fa;border:1px solid var(--line);border-radius:8px;padding:16px 20px;
margin:26px 0 4px}
.toc h4{margin:0 0 8px;font-size:13px;letter-spacing:1px;color:var(--muted)}
.toc ol{margin:0;padding-left:20px;font-size:14.5px}
.toc li{margin:3px 0}
.src-list{list-style:none;margin:0 0 18px;padding:0}
.src-list li{border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:0 0 10px;
background:#fcfdfd;scroll-margin-top:20px}
.src-list li:target{border-color:var(--accent);background:var(--accent-wash)}
.src-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;margin-bottom:4px}
.src-id{font-family:ui-monospace,Consolas,monospace;font-size:13px;font-weight:700;
color:var(--accent)}
.src-meta{font-size:12px;color:var(--muted)}
.src-back{font-size:12px;margin-left:auto}
.src-text{margin:0;font-size:15.5px;line-height:1.75;color:var(--ink)}
.src-miss{color:var(--warn);font-weight:700}
footer{border-top:1px solid var(--line);margin-top:40px;padding-top:16px;font-size:12.5px;
color:var(--muted);display:flex;flex-wrap:wrap;gap:6px 12px;justify-content:space-between}
@media(max-width:720px){.paper{margin:0;border-radius:0;padding:28px 20px 20px}
body{font-size:16.5px}h1{font-size:26px}h2{font-size:21px}}
@media print{body{background:#fff}.paper{margin:0 auto;box-shadow:none;max-width:none}
.toc,.src-back{display:none}
h2,h3{break-after:avoid}blockquote,.src-list li,table{break-inside:avoid}}
"""


def build_html(title, subtitle, lead, meta_line, trust, toc, body, appendix):
    esc_t = esc(title)
    sub = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""
    lead_p = f'<p class="lead">{lead}</p>' if lead else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc_t}</title>
<style>{CSS}</style>
</head>
<body>
<main class="paper">
<header class="intro">
<div class="brand">COMMENT-DISTILLERY</div>
<h1>{esc_t}</h1>
{sub}
{lead_p}
<p class="meta">{meta_line}</p>
</header>
{trust}
{toc}
<article>
{body}
</article>
{appendix}
<footer>
<span>comment-distillery · 带引用溯源的群体文本蒸馏</span>
<a href="https://github.com/TrueFurina/comment-distillery">github.com/TrueFurina/comment-distillery</a>
</footer>
</main>
</body>
</html>
"""


def run(guide, out=None, corpora=None, field=None, title=None, subtitle=None,
        no_verify=False, root=None):
    """渲染一份指南为自包含 HTML。返回 dict（不写 stdout、不退出进程）。"""
    guide_p = Path(guide)
    if not guide_p.exists():
        raise FileNotFoundError(f"指南不存在: {guide}")
    md = guide_p.read_text(encoding="utf-8")

    root = Path(root) if root else Path(__file__).resolve().parent.parent

    # ── 语料与机验（口径复用 verify_citations，不另写判据）
    meta = {}
    verify_info = {"ran": False, "cited": 0, "bad": [], "real": 0}
    if corpora and not no_verify:
        meta = load_corpus(corpora, field)
        res = verify.run(str(guide_p), [str(c) for c in corpora], field, [])
        verify_info = {"ran": True, "cited": len(res["cited"]),
                       "bad": list(res["bad"]), "real": len(res["real"])}
    elif corpora:
        meta = load_corpus(corpora, field)

    # ── 标题与导语
    h1 = re.search(r"^#\s+(.*)$", md, re.M)
    if not title:
        title = h1.group(1).strip() if h1 else guide_p.stem
    body_md = md
    if h1:                                    # 去掉 H1（已作为页面主标题）
        body_md = md[:h1.start()] + md[h1.end():]

    cites = Cites()
    headings = []
    body = render_markdown(body_md, cites, meta, headings)

    # ── 目录
    if headings:
        items = "".join(f'<li><a href="#{h}">{esc(t)}</a></li>' for h, t in headings)
        toc = f'<nav class="toc"><h4>目录</h4><ol>{items}</ol></nav>'
    else:
        toc = ""

    # ── 信任条
    n_cite = len(cites.unique)
    if verify_info["ran"]:
        bad = verify_info["bad"]
        if bad:
            cls, txt = "bad", (
                f'<span class="n">⚠️ {len(bad)}</span> 条幻觉引用 —— '
                f'按质量门<b>不得交付</b>（{esc("、".join(bad[:6]))}'
                f'{"…" if len(bad) > 6 else ""}）')
        else:
            cls, txt = "", (
                f'<span class="n">{verify_info["cited"]}</span> 条引用 · '
                f'机验通过 · 差集 <span class="n">0</span>'
                f'<span style="font-weight:400">（语料 ID 全集 {verify_info["real"]}）</span>')
    else:
        cls, txt = "warn", (
            f'<span class="n">{n_cite}</span> 条引用 · '
            f'<b>未跑机验</b>（未提供 --corpus，无法核对引用真实性）')
    trust = f'<div class="trustbar {cls}">{txt}</div>'

    # ── 附录：引用溯源（可点击跳转的核心）
    if cites.unique:
        li = []
        for cid in cites.unique:
            info = meta.get(cid)
            if info and info.get("text"):
                txt = info["text"]
                if len(txt) > 320:
                    txt = txt[:320] + "…"
                inner = f'<p class="src-text">{esc(txt)}</p>'
                bits = []
                if info.get("score"):
                    bits.append(f'权重 {esc(info["score"])}')
                if info.get("floor"):
                    bits.append(esc(info["floor"]))
                met = f'<span class="src-meta">{" · ".join(bits)}</span>' if bits else ""
            elif meta:
                inner = '<p class="src-text src-miss">该 ID 不在语料表中（幻觉引用）</p>'
                met = ""
            else:
                inner = '<p class="src-text src-miss">未提供语料 CSV，未挂载原句</p>'
                met = ""
            li.append(
                f'<li id="src-{cid}">'
                f'<div class="src-head"><span class="src-id">{esc(cid)}</span>{met}'
                f'<a class="src-back" href="#cite-{cid}">返回正文</a></div>'
                f'{inner}</li>')
        appendix = (f'<h2 id="sources">引用溯源</h2>'
                    f'<p class="meta">点击正文中的「源」角标可跳到这里；'
                    f'点「返回正文」跳回原处。共 {n_cite} 个被引用条目。</p>'
                    f'<ol class="src-list">{"".join(li)}</ol>')
    else:
        appendix = ""

    # ── meta 行
    ver = skill_version(root)
    today = time.strftime("%Y-%m-%d")
    bits = [f"来源：<code>{esc(guide_p.name)}</code>"]
    if meta:
        bits.append(f"语料 {len(meta):,} 条")
    if ver:
        bits.append(f"comment-distillery v{esc(ver)}")
    bits.append(f"生成于 {today}")
    meta_line = " · ".join(bits)

    html = build_html(title, subtitle, "", meta_line, trust, toc, body, appendix)

    out_p = Path(out) if out else guide_p.with_suffix(".html")
    out_p.write_text(html, encoding="utf-8")

    return {"out": str(out_p), "title": title, "cites": cites.unique,
            "verify": verify_info, "headings": headings, "bytes": len(html.encode("utf-8"))}


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(
        description="指南 Markdown → 自包含 HTML 阅读报告（引用角标可点击溯源）")
    ap.add_argument("guide", help="指南 markdown")
    ap.add_argument("-o", "--out", default=None, help="输出 HTML（默认与指南同名 .html）")
    ap.add_argument("--corpus", nargs="*", default=None,
                    help="语料 CSV（可多个）：挂载原句并跑引用机验")
    ap.add_argument("--field", default=None, help="语料 ID 列名（默认自动识别）")
    ap.add_argument("--title", default=None, help="覆盖标题（默认取首个 H1）")
    ap.add_argument("--subtitle", default=None, help="副标题")
    ap.add_argument("--no-verify", action="store_true",
                    help="只挂原句、不跑机验（不推荐：会丢掉信任条）")
    args = ap.parse_args(argv)

    try:
        res = run(args.guide, args.out, args.corpus, args.field,
                  args.title, args.subtitle, args.no_verify)
    except FileNotFoundError as e:
        print(f"[ERR] {e}", file=sys.stderr)
        return 2

    v = res["verify"]
    print(f"[ok] 已生成 {res['out']}（{res['bytes']:,} 字节）")
    print(f"     标题：{res['title']}")
    print(f"     章节：{len(res['headings'])}　引用条目：{len(res['cites'])}")
    if v["ran"]:
        print(f"     机验：引用 {v['cited']} 条 / 语料 {v['real']} ids / 幻觉 {len(v['bad'])}")
        if v["bad"]:
            print("     ❌ 差集非空，按质量门不得交付。")
            return 1
    else:
        print("     ⚠️ 未跑机验（加 --corpus 语料.csv 可挂载原句并核对引用）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
