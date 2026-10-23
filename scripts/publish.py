#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / publish.py
自用多平台发布器（零依赖，仅标准库 urllib / json / subprocess）。

把 cases/ 里的「评论深度指南」投到四个渠道：
    github    —— 自有域名（GitHub Pages）。写 site/cases/<slug>.html + 更新 sitemap.xml。
                AI 爬虫几天内即可命中，且完全可控，用作「规范源 canonical」。
    csdn      —— CSDN 博客。Markdown 正文，需登录 Cookie（UserToken / log_Id_Token）。
    bilibili  —— B站专栏。HTML 正文，需 SESSDATA + bili_jct（+DedeUserID）Cookie。
    zhihu     —— 知乎专栏。HTML 正文，需 Cookie + _xsrf。**最脆**，失败回退到粘贴草稿。

为什么自己写一个、不买 CSDN 同步会员：
    四个渠道的发文接口都是「登录态 + 一个 HTTP 请求」，没有任何会员才能用的能力。
    会员插件做的是同样的 CURL，只是加了 GUI。self-use 场景下，一个脚本 + 自己的 Cookie
    就够了，且能一键跑全套、能 dry-run 先验请求、能把规范源回链到自有域名做 SEO。

设计原则（与项目一致）：
    * 零运行时依赖：只用标准库。
    * 密钥只存在 publish_config.local.json（已被 .gitignore 屏蔽），绝不入库、绝不上线。
    * 外部平台一律先 --dry-run 验请求；未填 Cookie 直接拒绝，不裸奔。
    * 合规护栏：只发公开产出层的指南；CSV 仅本地渲染用，绝不外传原始语料文件。

用法：
    # 初始化配置模板（自己填 Cookie）
    python scripts/publish.py --init-config

    # 先 dry-run 看四个渠道会发什么（不真正发送）
    python scripts/publish.py cases/11-degree-and-fate/《学历·命运》评论深度指南.md \
        --platform all --dry-run

    # 真实发布到自有域名（写文件 + sitemap，需你之后 commit & push 才上线）
    python scripts/publish.py cases/11-degree-and-fate/《学历·命运》评论深度指南.md \
        --platform github --corpus cases/11-degree-and-fate/*.csv

    # 真实发布到 CSDN / B站 / 知乎（需先在配置里填好 Cookie）
    python scripts/publish.py <指南.md> --platform csdn,bilibili,zhihu

    # 目录模式：自动挑最新一篇（每日蒸馏场景）
    python scripts/publish.py cases/ --platform all --dry-run
"""

import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE_DIR = ROOT / "site"
CASES_DIR = SITE_DIR / "cases"
SITEMAP = SITE_DIR / "sitemap.xml"
CONFIG_PATH = ROOT / "publish_config.local.json"
CONFIG_EXAMPLE = ROOT / "publish_config.local.json.example"
# 自有域名 Pages 基址（与 pages.yml 部署目标一致）
PAGES_BASE = "https://truefurina.github.io/comment-distillery/"


def utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ── 加载 emit_html（scripts/ 不是包，用 importlib 同目录加载）──────────
def _load_emit():
    spec = importlib.util.spec_from_file_location("cd_emit_html", HERE / "emit_html.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cd_emit_html"] = mod
    spec.loader.exec_module(mod)
    return mod


emit_html = _load_emit()


# ── 合规护栏 ──────────────────────────────────────────────────────────
def _guard_no_csv(guide, corpora):
    """合规护栏：发布对象（指南）必须是 .md，绝不把原始语料 .csv 当作发布目标上传。

    corpora 是本地渲染「引用溯源」附录用的，本就不离开本机，且必然就是 .csv ——
    所以护栏只查 guide，不查 corpora，否则会误杀文件头示例里的
    `--corpus cases/.../*.csv` 这条正常用法（已实测：原实现会直接 SystemExit）。
    """
    if Path(guide).suffix.lower() == ".csv":
        raise SystemExit(
            f"[合规拦截] 发布只接受指南 .md，绝不直接上传语料 {Path(guide).name}。"
            f"CSV 仅用于本地渲染挂载「引用溯源」附录，不会离开本机。")


# ── 文章模型 ──────────────────────────────────────────────────────────
@dataclass
class Article:
    title: str
    markdown: str            # 原始指南 markdown（CSDN 用）
    html_full: str           # emit_html 自包含 HTML（GitHub Pages 用）
    html_body: str           # <article>..</main> 正文+溯源（B站/知乎用）
    slug: str
    canonical_url: str
    summary: str             # 纯文本摘要（B站 summary 等用）

    @property
    def rel_path(self):
        return f"cases/{self.slug}.html"

    @property
    def url(self):
        return PAGES_BASE + urllib.parse.quote(self.rel_path)


def slugify(name: str) -> str:
    """保留中英文与连字符，其余（含《》、空格、点、标点）替换为 -。
    中文留在 slug 对中文 SEO 反而有利；URL 由 quote() 处理。"""
    s = re.sub(r"[\\/<>:《》\"|?*]", "-", name)
    s = re.sub(r"[\s·.。，、]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "guide"


def _plain_summary(md: str, limit: int = 120) -> str:
    """取第一段纯文本作摘要（去 markdown 标记）。"""
    txt = re.sub(r"^#.*$", "", md, flags=re.M)          # 去标题
    txt = re.sub(r"[#>*`|_\[\]()]", "", txt)            # 去常见标记
    txt = re.sub(r"\[源\s*[:：][^\]]*\]", "", txt)       # 去引用角标
    paras = [p.strip() for p in txt.splitlines() if p.strip()]
    if not paras:
        return ""
    s = paras[0]
    return s if len(s) <= limit else s[:limit] + "…"


def build_article(guide: Path, corpora, slug_override=None) -> Article:
    _guard_no_csv(str(guide), corpora)
    md = guide.read_text(encoding="utf-8")
    h1 = re.search(r"^#\s+(.*)$", md, re.M)
    title = h1.group(1).strip() if h1 else guide.stem

    # 渲染自包含 HTML（corpora 仅本地挂载溯源附录，不外传）
    tmp = Path(tempfile.gettempdir()) / f"_cd_pub_{int(time.time()*1000)}.html"
    emit_html.run(str(guide), str(tmp), corpora, None, None, None, False, str(ROOT))
    html_full = tmp.read_text(encoding="utf-8")
    tmp.unlink(missing_ok=True)

    m = re.search(r"<article>(.*?)</main>", html_full, re.S)
    html_body = m.group(1) if m else html_full

    slug = slug_override or slugify(guide.stem)
    return Article(
        title=title, markdown=md, html_full=html_full, html_body=html_body,
        slug=slug, canonical_url="", summary=_plain_summary(md))
    # canonical_url 在 publish 时按实际 url 回填（见 publish_all）


def canonical_footer(canonical_url: str) -> str:
    return ("\n\n---\n\n"
            "> 本文由 comment-distillery 蒸馏 B站评论生成，文中引用均可溯源到原始评论。\n"
            f"> 带**点击溯源**的完整版（可交互证据）：{canonical_url}\n")


# ── HTTP 工具（零依赖）────────────────────────────────────────────────
def http_post_json(url, payload, headers, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def http_post_form(url, fields, headers, timeout=30):
    # 手工拼 x-www-form-urlencoded（避免依赖 urllib 的受限编码）
    body = "&".join(f"{urllib.parse.quote(k, safe='')}="
                    f"{urllib.parse.quote(str(v), safe='')}"
                    for k, v in fields.items()).encode("utf-8")
    h = dict(headers)
    h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _ua():
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "Chrome/124.0 Safari/537.36")


def _mask(cookie: str) -> str:
    if not cookie:
        return "(空)"
    head = cookie[:18]
    return f"{head}…(len={len(cookie)})"


# ── 配置 ──────────────────────────────────────────────────────────────
def default_config() -> dict:
    return {
        "github": {"enabled": True},
        "csdn": {
            "enabled": False,
            "endpoint": "https://bizapi.csdn.net/blog-console-api/v1/post/save",
            "cookie": "",
            "extra_headers": {},
            "tags": "人工智能,数据分析",
            "category_id": 1,
            "status": 1,            # 1=发布 0=草稿
        },
        "bilibili": {
            "enabled": False,
            "cookie": "",
            "category_id": 0,        # 0=默认；如需精确分类请在浏览器拿 creative/categories
            "list_id": 0,           # 文集编号，0=不加入文集
            "original": 1,          # 1=原创
            "submit": True,         # True=创建后直接提交发布；False=仅存草稿
        },
        "zhihu": {
            "enabled": False,
            "cookie": "",
            "xsrf": "",             # 留空则自动从 cookie 的 _xsrf 取
        },
    }


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return default_config()
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[配置错误] 解析 {CONFIG_PATH.name} 失败：{e}")


def write_example_config():
    CONFIG_EXAMPLE.write_text(
        json.dumps(default_config(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] 已写入配置模板 {CONFIG_EXAMPLE.name}")
    print(f"     复制为 {CONFIG_PATH.name} 并填入你的 Cookie 即可：")
    print(f"     cp {CONFIG_EXAMPLE.name} {CONFIG_PATH.name}")


# ── 适配器 ────────────────────────────────────────────────────────────
class Result:
    def __init__(self, platform, ok, url="", msg="", dry=False):
        self.platform = platform
        self.ok = ok
        self.url = url
        self.msg = msg
        self.dry = dry

    def __str__(self):
        tag = "DRY" if self.dry else ("OK " if self.ok else "ERR")
        line = f"  [{tag}] {self.platform}"
        if self.url:
            line += f"  →  {self.url}"
        if self.msg:
            line += f"   ({self.msg})"
        return line


class GithubAdapter:
    name = "github"

    def publish(self, art: Article, cfg, dry_run) -> Result:
        if dry_run:
            return Result(self.name, True, art.url, "将写 site/cases + 更新 sitemap", dry=True)
        CASES_DIR.mkdir(parents=True, exist_ok=True)
        out = CASES_DIR / f"{art.slug}.html"
        out.write_text(art.html_full, encoding="utf-8")
        _update_sitemap(art)
        return Result(self.name, True, art.url,
                      "已写文件；请 review 后 commit & push 才上线（我未自动推送）")


def _update_sitemap(art: Article):
    if not SITEMAP.exists():
        return
    xml = SITEMAP.read_text(encoding="utf-8")
    if art.rel_path in xml:
        return                      # 幂等：已有就不重复加
    entry = (f"  <url>\n"
             f"    <loc>{art.url}</loc>\n"
             f"    <lastmod>{time.strftime('%Y-%m-%d')}</lastmod>\n"
             f"    <changefreq>weekly</changefreq>\n"
             f"    <priority>0.8</priority>\n"
             f"  </url>\n")
    xml = xml.replace("</urlset>", entry + "</urlset>")
    SITEMAP.write_text(xml, encoding="utf-8")


class CsdnAdapter:
    name = "csdn"

    def publish(self, art: Article, cfg, dry_run) -> Result:
        if not cfg.get("enabled"):
            return Result(self.name, False, msg="配置未启用（enabled=false）")
        cookie = cfg.get("cookie", "")
        if not cookie:
            return Result(self.name, False, msg="未配置 CSDN cookie（登录后从浏览器复制）")
        content = art.markdown + canonical_footer(art.url)
        payload = {
            "title": art.title,
            "content": content,
            "markdowncontent": content,
            "tags": cfg.get("tags", ""),
            "categoryId": cfg.get("category_id", 1),
            "status": cfg.get("status", 1),
            "type": "original",
            "readType": "public",
        }
        headers = {
            "Cookie": cookie,
            "Content-Type": "application/json",
            "User-Agent": _ua(),
            "Origin": "https://editor.csdn.net",
            "Referer": "https://editor.csdn.net/",
        }
        headers.update(cfg.get("extra_headers", {}) or {})
        if dry_run:
            return Result(self.name, True, art.url,
                          f"POST {cfg.get('endpoint')} cookie={_mask(cookie)} "
                          f"title={art.title!r} len={len(content)}", dry=True)
        try:
            status, text = http_post_json(cfg.get("endpoint"), payload, headers)
            try:
                data = json.loads(text)
            except Exception:
                return Result(self.name, False, msg=f"HTTP {status} 非 JSON：{text[:200]}")
            if data.get("code") == 200:
                url = (data.get("data") or {}).get("url", "")
                return Result(self.name, True, url or art.url, f"code=200")
            return Result(self.name, False,
                          msg=f"code={data.get('code')} msg={data.get('msg')}")
        except Exception as e:
            return Result(self.name, False, msg=f"请求失败：{e}")


class BilibiliAdapter:
    name = "bilibili"

    def publish(self, art: Article, cfg, dry_run) -> Result:
        if not cfg.get("enabled"):
            return Result(self.name, False, msg="配置未启用（enabled=false）")
        cookie = cfg.get("cookie", "")
        if not cookie:
            return Result(self.name, False, msg="未配置 B站 cookie")
        bili_jct = _cookie_val(cookie, "bili_jct")
        if not bili_jct:
            return Result(self.name, False,
                          msg="cookie 缺少 bili_jct（CSRF）；请在浏览器复制完整 Cookie")
        base = "https://api.bilibili.com/x/article/creative"
        content = art.html_body + canonical_footer(art.url)
        draft_fields = {
            "title": art.title,
            "content": content,
            "category": cfg.get("category_id", 0),
            "list_id": cfg.get("list_id", 0),
            "tid": 4,                  # 4=单图/无封面
            "reprint": 0,
            "media_id": 0,
            "spoiler": 0,
            "original": cfg.get("original", 1),
            "summary": art.summary,
            "csrf": bili_jct,
        }
        headers = {
            "Cookie": cookie,
            "User-Agent": _ua(),
            "Referer": "https://member.bilibili.com/",
        }
        if dry_run:
            return Result(self.name, True, art.url,
                          f"draft(addupdate)+submit cookie={_mask(cookie)} "
                          f"category={draft_fields['category']} len={len(content)}", dry=True)
        try:
            status, text = http_post_form(f"{base}/draft/addupdate", draft_fields, headers)
            data = _safe_json(text, status)
            if data.get("code") != 0:
                return Result(self.name, False,
                              msg=f"draft code={data.get('code')} msg={data.get('message')}")
            aid = (data.get("data") or {}).get("aid")
            if not cfg.get("submit", True) or not aid:
                return Result(self.name, True, art.url,
                              f"已存草稿 aid={aid}（submit=false）")
            sub_fields = {"aid": aid, "csrf": bili_jct}
            s2, t2 = http_post_form(f"{base}/article/submit", sub_fields, headers)
            d2 = _safe_json(t2, s2)
            if d2.get("code") == 0:
                return Result(self.name, True, f"https://www.bilibili.com/read/cv{aid}",
                              f"已发布 aid={aid}")
            return Result(self.name, False,
                          msg=f"submit code={d2.get('code')} msg={d2.get('message')}")
        except Exception as e:
            return Result(self.name, False, msg=f"请求失败：{e}")


class ZhihuAdapter:
    name = "zhihu"

    def publish(self, art: Article, cfg, dry_run) -> Result:
        if not cfg.get("enabled"):
            return Result(self.name, False, msg="配置未启用（enabled=false）")
        cookie = cfg.get("cookie", "")
        if not cookie:
            return Result(self.name, False, msg="未配置知乎 cookie")
        xsrf = cfg.get("xsrf") or _cookie_val(cookie, "_xsrf")
        if not xsrf:
            return Result(self.name, False, msg="cookie 缺少 _xsrf（知乎 CSRF）")
        content = art.html_body + canonical_footer(art.url)
        payload = {"title": art.title, "content": content}
        headers = {
            "Cookie": cookie,
            "User-Agent": _ua(),
            "Referer": "https://zhuanlan.zhihu.com/",
            "x-xsrftoken": xsrf,
            "Content-Type": "application/json",
        }
        if dry_run:
            return Result(self.name, True, art.url,
                          f"POST api/v4/articles cookie={_mask(cookie)} "
                          f"xsrf=•• len={len(content)}", dry=True)
        # best-effort：知乎接口极脆，失败则回退到「生成可粘贴草稿」
        try:
            status, text = http_post_json(
                "https://www.zhihu.com/api/v4/articles", payload, headers)
            data = _safe_json(text, status)
            if isinstance(data, dict) and data.get("id"):
                zurl = data.get("url") or f"https://zhuanlan.zhihu.com/p/{data['id']}"
                return Result(self.name, True, zurl, "已发布")
            return self._fallback(art, data)
        except Exception as e:
            return self._fallback(art, {"error": str(e)})

    @staticmethod
    def _fallback(art: Article, detail) -> Result:
        draft = ROOT / f"out/{art.slug}.zhihu.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(art.markdown + canonical_footer(art.url), encoding="utf-8")
        return Result(art and "zhihu", False,
                      msg=f"知乎接口未成功（{detail}）；已生成可粘贴草稿 {draft.name}，"
                          f"请到 https://zhuanlan.zhihu.com/write 手动发布")


def _cookie_val(cookie: str, key: str) -> str:
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(f"{key}="):
            return part[len(key) + 1:]
    return ""


def _safe_json(text: str, status):
    try:
        return json.loads(text)
    except Exception:
        return {"code": -1, "message": f"HTTP {status} 非 JSON：{text[:200]}"}


ADAPTERS = {
    "github": GithubAdapter,
    "csdn": CsdnAdapter,
    "bilibili": BilibiliAdapter,
    "zhihu": ZhihuAdapter,
}


# ── 主流程 ────────────────────────────────────────────────────────────
def pick_guide(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        mds = sorted(p.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        mds = [m for m in mds if m.name != "README.md"]
        if not mds:
            raise SystemExit(f"[ERR] 目录 {arg} 下没有 .md 指南")
        print(f"[info] 目录模式：自动选最新一篇 → {mds[0].name}")
        return mds[0]
    if not p.exists():
        raise SystemExit(f"[ERR] 指南不存在：{arg}")
    return p


def publish_all(guide_arg, platforms, dry_run, corpora, slug_override):
    guide = pick_guide(guide_arg)
    art = build_article(guide, corpora, slug_override)
    art.canonical_url = art.url          # 回填规范源 URL

    cfg = load_config()
    if "all" in platforms:
        platforms = list(ADAPTERS.keys())

    print(f"[info] 指南：{guide.name}")
    print(f"[info] 标题：{art.title}")
    print(f"[info] canonical：{art.url}")
    print(f"[info] 渠道：{', '.join(platforms)}"
          f"{'  （DRY-RUN，不会真正发送）' if dry_run else ''}\n")

    results = []
    for name in platforms:
        adapter = ADAPTERS[name]()
        pcfg = cfg.get(name, {}) or {}
        try:
            res = adapter.publish(art, pcfg, dry_run)
        except Exception as e:
            res = Result(name, False, msg=f"适配器异常：{e}")
        results.append(res)
        print(res)

    ok = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    print(f"\n[summary] 成功 {len(ok)} / 失败 {len(fail)}")
    if fail:
        print("  失败渠道：", ", ".join(r.platform for r in fail))
    return 0 if (dry_run or not fail) else 1


def main(argv=None):
    utf8_stdout()
    ap = argparse.ArgumentParser(
        description="自用多平台发布器：GitHub Pages + CSDN + B站专栏 + 知乎")
    ap.add_argument("guide", nargs="?", default=None,
                    help="指南 .md 文件，或含 .md 的目录（自动选最新）；"
                         "--init-config / --list 时不需要")
    ap.add_argument("--platform", default="github",
                    help="渠道，逗号分隔或 all（默认 github）")
    ap.add_argument("--corpus", nargs="*", default=None,
                    help="语料 CSV（仅本地渲染挂载溯源附录，不外传）")
    ap.add_argument("--slug", default=None, help="覆盖 URL slug")
    ap.add_argument("--dry-run", action="store_true",
                    help="只构造并打印请求，不真正发送（外部平台必先用它验过）")
    ap.add_argument("--init-config", action="store_true",
                    help="写入 publish_config.local.json.example 模板")
    ap.add_argument("--list", action="store_true",
                    help="显示当前配置中各渠道启用状态")
    args = ap.parse_args(argv)

    if args.init_config:
        write_example_config()
        return 0
    if args.list:
        cfg = load_config()
        print("[config] 渠道启用状态：")
        for k in ADAPTERS:
            c = cfg.get(k, {}) or {}
            en = c.get("enabled", k == "github")
            print(f"  {k:10} {'启用' if en else '关闭'}"
                  f"{'' if k!='github' else '（默认开，无 Cookie 需求）'}")
        return 0
    if not args.guide:
        raise SystemExit("[ERR] 发布需要 guide 参数（--init-config / --list 时不需要）")

    platforms = [p.strip().lower() for p in args.platform.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in ADAPTERS and p != "all"]
    if unknown:
        raise SystemExit(f"[ERR] 未知渠道：{unknown}（可选：{list(ADAPTERS)} 或 all）")
    return publish_all(args.guide, platforms, args.dry_run, args.corpus, args.slug)


if __name__ == "__main__":
    sys.exit(main())
