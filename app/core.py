#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具 · 逻辑层（无 GUI 依赖）。

四条能力，全部**委托**给仓库已有脚本，不另立实现：

    采集     -> contrib/fetch_bilibili_comments.py :: crawl()
    预处理   -> scripts/prep.py                    :: run()
    引用机验 -> scripts/verify_citations.py        :: run()
    规则机验 -> scripts/check_rule_tags.py         :: check()
    HTML报告 -> scripts/emit_html.py               :: run()

为什么坚持委托而不重写：本项目对"数字漂移 / 口径漂移"零容忍。
只要有两套实现，就一定会分叉——CLI 修了 bug 而 exe 里还是旧的。
本层可以被任何前端复用（tkinter / CLI / 未来 webview），也可被测试直接导入。

零第三方依赖，仅标准库。
"""

import importlib.util
import os
import re
import shutil
import sys
import time
from pathlib import Path

# 与 SKILL.md 的 version 字段、Git tag 保持同一口径。
# 早先长期停在 "1.0.0"，导致界面徽章 / GUI 标题 / exe --selfcheck 对外报告的
# 版本，与真实发布版（1.7.0）对不上——用户据此判断"我装的是哪版"会直接误判。
APP_VERSION = "1.7.0"

# 随包资源相对路径（打包时需由 scripts/build_exe.py 的 --add-data 收进来）
RES_SKILL = "SKILL.md"
RES_DOCS = ("docs/canonical-format.md", "docs/pipeline.md")
RES_PREP = "scripts/prep.py"
RES_VERIFY = "scripts/verify_citations.py"
RES_VERIFYNUM = "scripts/verify_numbers.py"
RES_RULETAGS = "scripts/check_rule_tags.py"
RES_EMIT = "scripts/emit_html.py"
RES_CRAWL = "contrib/fetch_bilibili_comments.py"

_MOD_CACHE = {}


# ────────────────────────────── 资源定位 ──────────────────────────────

def resource_root() -> Path:
    """只读资源根目录。

    - 源码运行：仓库根（本文件的上一级目录）
    - PyInstaller 打包后：sys._MEIPASS（--add-data 的解包目录）
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """程序**自己的位置**——用来落盘所有产物。

    和 `resource_root()` 的区别很关键：
    - 源码运行：两者都是仓库根；
    - 打包后：`resource_root()` 是 `_MEIPASS`（每次启动解到临时目录、退出即删），
      拿它当输出位置会**每次换个地方**、甚至写完就被清掉。
      真正稳定的位置是 exe 自己所在的目录（`sys.executable`）。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_outdir() -> Path:
    """默认输出根：**统一放在程序目录下**，不写用户主目录。

    早先取 `Path.home() / "comment-distillery-output"`，理由是"装到 Program Files
    会没权限"。但实际使用中这造成了两处割裂：程序在 E 盘、产物在 C 盘用户目录，
    同一个项目的文件散在两个盘上，找起来全靠翻。

    现在的规则：产物一律落在 `<程序目录>/output/`。
    - 源码运行 → 仓库根下的 `output/`（已在 .gitignore 里）
    - exe → exe 同级的 `output/`
    只有该位置不可写（如被装进 Program Files 且无权限）时，才退回用户目录。
    """
    preferred = app_root() / "output"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".writable"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = Path.home() / "comment-distillery-output"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def outdir_or_default(value=None) -> str:
    """把用户给的输出目录按统一规则归一：空值 -> 默认根。"""
    s = (value or "").strip()
    return s if s else str(default_outdir())


def _load(alias: str, rel_path: str):
    """按文件路径加载仓库脚本。

    这些脚本不是 package（没有 __init__.py），不能用常规 import；
    与 tests/ 里的加载方式保持一致。
    """
    key = (alias, rel_path)
    if key in _MOD_CACHE:
        return _MOD_CACHE[key]
    path = resource_root() / rel_path
    if not path.exists():
        raise FileNotFoundError(
            f"缺少随包资源 {rel_path}。打包时需要把它加进 --add-data；"
            f"当前资源根：{resource_root()}"
        )
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MOD_CACHE[key] = mod
    return mod


def _prep_mod():
    return _load("cd_prep", RES_PREP)


def _verify_mod():
    return _load("cd_verify", RES_VERIFY)


def _verify_num_mod():
    return _load("cd_verifynum", RES_VERIFYNUM)


def _ruletags_mod():
    return _load("cd_ruletags", RES_RULETAGS)


def _emit_mod():
    return _load("cd_emit", RES_EMIT)


def _crawl_mod():
    return _load("cd_crawl", RES_CRAWL)


def skill_path() -> Path:
    return resource_root() / RES_SKILL


# ────────────────────────────── 采集（可选桥接） ──────────────────────────────

def crawl_comments(arg, out_csv, roots_only=False,
                   on_log=None, on_progress=None, should_stop=None):
    """抓取 B 站视频评论并写 CSV。返回 dict，见 contrib 里 crawl() 的文档。"""
    return _crawl_mod().crawl(
        arg, out_csv, roots_only=roots_only,
        on_log=on_log, on_progress=on_progress, should_stop=should_stop,
    )


# ────────────────────────────── 预处理 ──────────────────────────────

def prepare(input_csv, outdir, low_max=8, low_min_len=120):
    """语料 CSV -> 规范语料 + 易读文本 + 统计 + ID 映射。返回 (stats, paths)。"""
    return _prep_mod().run(input_csv, outdir, low_max, low_min_len)


# ────────────────────────────── 引用机验 ──────────────────────────────

def verify_guide(guide, corpora, field=None):
    """引用真实性机验（幻觉引用检测）。文件缺失时抛 FileNotFoundError。"""
    return _verify_mod().run(guide, corpora, field)


# ────────────────────────────── 规则机验 ──────────────────────────────

def check_skill(path=None):
    """机验 SKILL.md 是否有"裸铁律"（规则必须带溯源标记）。"""
    target = Path(path) if path else skill_path()
    errors, checked, tagged, _ = _ruletags_mod().check(target)
    return {"path": str(target), "errors": errors,
            "checked": checked, "tagged": tagged}


# ────────────────────────────── HTML 报告 ──────────────────────────────

def emit_report(guide, out=None, corpora=None, field=None,
                title=None, subtitle=None, no_verify=False):
    """指南 Markdown -> 自包含 HTML 报告（引用角标可点击溯源）。

    corpora 非空时会挂原句并跑引用机验，差集非空时返回的 verify["bad"] 不为空；
    **是否算交付由调用方判定**，本层不替前端做产品决策。
    """
    return _emit_mod().run(
        guide, out, corpora, field, title, subtitle, no_verify,
        root=str(resource_root()),
    )


# ────────────────────── 蒸馏（可选：用户自带 AI） ──────────────────────
#
# ⚠️ 这一节**没有**引入"内置 LLM"，只是把 v1.7.0 里"用户自己把包拖给 AI"
# 那一跳自动化了——模型、Key、额度全在用户侧。
# 未配置时 `llm_status()["configured"]` 为 False，一键流程与旧版逐字一致。

def llm_status():
    """读当前 AI 配置（不含 Key 明文）。"""
    from . import llm as _llm
    cfg = _llm.load_config(app_root())
    return {"configured": bool(cfg.get("configured")),
            "model": cfg.get("model", ""),
            "base_url": cfg.get("base_url", ""),
            "source": cfg.get("source", "none"),
            "missing": cfg.get("missing", []),
            "describe": _llm.describe(cfg),
            "path": cfg.get("path", "")}


def save_llm_config(base_url, api_key, model, timeout=600, max_corpus_chars=120000):
    """写 <程序目录>/llm.json。api_key 传空串表示"不改动已存的 Key"。"""
    import json as _json
    from . import llm as _llm
    p = _llm.config_path(app_root())
    old = {}
    if p.exists():
        try:
            old = _json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            old = {}
    cfg = dict(old)
    cfg["base_url"] = (base_url or "").strip().rstrip("/")
    if model is not None:
        cfg["model"] = (model or "").strip()
    if api_key:                                   # 空 = 保留旧 Key
        cfg["api_key"] = api_key.strip()
    cfg["timeout"] = int(timeout or 600)
    cfg["max_corpus_chars"] = int(max_corpus_chars or 120000)
    cfg.setdefault("max_repair_rounds", 2)
    p.write_text(_json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)     # 尽力而为：Windows 上是 no-op，POSIX 上收权限
    except Exception:
        pass
    return {"path": str(p), "status": llm_status()}


def distill_package(pack_dir, on_log=None, on_delta=None, should_stop=None,
                    max_rounds=None):
    """对一个已生成的蒸馏包跑「AI 写指南 → 机验 → 修正」。

    返回见 app/distill.py::distill()。未配置 AI 时抛 RuntimeError（带人话提示）。
    """
    from . import distill as _distill
    from . import llm as _llm
    cfg = _llm.load_config(app_root())
    if not cfg.get("configured"):
        raise RuntimeError("未配置 AI：" + _llm.describe(cfg)
                           + "。请先在「AI 设置」里填 endpoint / Key / 模型名，"
                             "或留空以只生成蒸馏包。")

    def _verify(guide_path, corpus_csv):
        r = verify_guide(guide_path, [corpus_csv])
        out = {"cited": len(r.get("cited") or []),
               "bad": list(r.get("bad") or []), "num_issues": []}
        # 数字机验：抓"引用全真但数字算错"——那是最像可信的错误。
        try:
            n = _verify_num_mod()
            issues, _checked = n.collect(str(guide_path), str(corpus_csv))
            out["num_issues"] = list(issues or [])
        except Exception as e:
            out["num_issues"] = []
            out["num_error"] = f"{type(e).__name__}: {e}"
        return out

    return _distill.distill(pack_dir, cfg, on_log=on_log, on_delta=on_delta,
                            should_stop=should_stop, verify_fn=_verify,
                            max_rounds=max_rounds)


def finish_after_pack(pack_dir, on_log=None, should_stop=None):
    """蒸馏包已就绪之后的收尾：配了 AI 就继续到报告，没配就到此为止。

    **这是「一键」真正语义的唯一实现**，GUI 与 Web 都必须走它。
    为什么抽到 core：两个前端各写一遍必然漂移（本仓库为此付过代价），
    而且"到底算不算跑完"这种事，只该有一个地方说了算。

    返回值（都带 mode 字段，前端据此决定文案）：
        mode="pack-only"       未配置 AI，只出了包（也可因 AI 失败而降级）
        mode="guide-unverified" 指南生成了但机验没过，**未出报告**
        mode="full"            报告已生成且机验通过
    附带 ai / ai_error / distill / report / stale_report 等字段供展示。
    """
    log = on_log or (lambda m: None)
    pack = Path(pack_dir)
    out = {"mode": "pack-only", "pack_dir": str(pack), "ai": {}, "distill": None,
           "report": None, "ai_error": "", "needs_ai_setup": False}

    status = llm_status()
    out["ai"] = {"configured": bool(status.get("configured")),
                 "model": status.get("model", "")}

    if not status.get("configured"):
        # ⚠️ 必须说清「没有报告」，不能只说「跳过蒸馏」。
        # 2026-11-02 的教训：用户看到"跑完了"却拿不到 report.html，以为程序坏了。
        log("")
        log("⚠️  ④ 已跳过 AI 蒸馏 —— 本次**不会产出报告**")
        log("    原因：" + status.get("describe", "未配置"))
        log("    现在只有蒸馏包（report.html 需要 AI 写指南后才会生成）。")
        log("    两条路选一条：")
        log("      · 零成本：把包目录拖进任意 AI，按包内 PROMPT.md 让它写指南")
        log("      · 全自动：去「AI 设置」填 endpoint / Key / 模型名，然后重跑")
        out["skipped_reason"] = "no-ai"
        out["needs_ai_setup"] = True
        out["missing"] = list(status.get("missing") or [])
        return out

    if should_stop and should_stop():
        out["skipped_reason"] = "stopped"
        return out

    log("")
    log("④ AI 蒸馏：" + status.get("describe", ""))
    try:
        d = distill_package(str(pack), on_log=log, should_stop=should_stop)
    except RuntimeError as e:
        # AI 挂了不该把前三步成果作废：包已在，用户能手动拿走。
        log(f"   ⚠️ AI 蒸馏失败：{e}")
        log(f"   前三步的蒸馏包仍然可用：{pack}")
        out["ai_error"] = str(e)
        return out

    out["distill"] = d

    if d.get("passed") is False:
        moved = _stale_report(str(pack))
        if moved:
            log(f"   上一轮的报告已改名避让：{moved}")
        log("   机验未过：不出 HTML 报告。差集非空的指南不算可交付报告。")
        out["mode"] = "guide-unverified"
        out["stale_report"] = moved
        return out

    if should_stop and should_stop():
        return out

    log("⑤ 出报告…")
    em = emit_report(d["guide_path"], str(pack / "report.html"),
                     [str(pack / "corpus_ccf.csv")])
    out["report"] = em
    out["mode"] = "full"
    log(f"   报告：{em['out']}")
    # report.html 是机器接口名，再存一份按标题命名的，方便人翻目录。
    named = _title_report_path(d["guide_path"], pack)
    if named:
        try:
            shutil.copyfile(em["out"], str(named))
            out["report_titled"] = str(named)
            log(f"   标题副本：{named.name}")
        except OSError as e:
            log(f"   标题副本写入失败（不影响主报告）：{e}")

    return out




_TITLE_BAD_CHARS = '<>:"/\\|?*'


def _title_report_path(guide_path, pack_dir):
    """按指南标题算出人类可读的报告文件名。

    output/ 里全是 `report.html` 的话，一眼分不清哪份是哪份，
    所以额外存一份按标题命名的副本。
    只做副本、不动 report.html —— WebUI 预览、陈旧报告避让、
    端到端测试都还指着那个固定名。
    """
    try:
        md = Path(guide_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(r"^#\s+(.+?)\s*$", md, re.M)
    if not m:
        return None
    title = m.group(1).strip()
    # 标题里的引号直接去掉，别把「只筛选不培养」变成「只筛选-不培养」。
    # 只去掉文件名非法或容易出歧义的引号；「」这类中文书名号保留。
    for q in '"':
        title = title.replace(q, "")
    for ch in _TITLE_BAD_CHARS:
        title = title.replace(ch, "-")
    title = re.sub(r"\s+", " ", title).strip(" .-")
    if not title:
        return None
    if len(title) > 60:
        title = title[:60].rstrip(" .-") + "\u2026"
    # 标题自己已经写了「指南」的不再重复拼后缀。
    if "\u6307\u5357" not in title:
        title += "-\u8bc4\u8bba\u6df1\u5ea6\u6307\u5357"
    return Path(pack_dir) / (title + ".html")


def _stale_report(pack_dir):
    """机验未过时，把上一轮的 report.html 挪开。

    否则会出现最坏的一种误导：用户重跑了一次，机验其实没过，
    但目录里躺着一份**上一轮**的报告——点开看着完好，页首还写着
    "机验通过"。那比没有报告更糟：它让人相信了一份没被验证的东西。

    不删除，只改名加 .stale-<时间戳>，用户想找回来还在。
    """
    rep = Path(pack_dir) / "report.html"
    if not rep.exists():
        return ""
    dst = rep.with_name(f"report.html.stale-{time.strftime('%Y%m%d-%H%M%S')}")
    try:
        rep.replace(dst)
        return str(dst)
    except OSError:
        return ""


# ────────────────────────────── 蒸馏包导出 ──────────────────────────────

PROMPT_TEMPLATE = """# 任务：把这份语料蒸馏成一份带引用的深度指南

你现在是 **comment-distillery** 的执行者。请严格按本目录 `SKILL.md` 的完整方法论处理语料。

## 语料（就在本目录）

| 文件 | 说明 |
|---|---|
| `all_comments.txt` | 按权重（点赞）降序的**全量易读语料**，每条形如 `[ID \\| 权重N \\| 层级 \\| 复M]` |
| `low_score_long.txt` | **低权重长文区**——真信号常藏在这里，而不是高赞区 |
| `corpus_ccf.csv` | 规范语料（Canonical Corpus Format），字段定义见 `canonical-format.md` |
| `stats.json` | 规模 / 互动 / 楼层 / 作者多样性统计 |
| `id_map.json` | ID →（权重, 层级, 回复数）映射，抽引用时用它核对 |

## 必读

- `SKILL.md` —— 六步流水线、三件套护城河、引用格式、环境坑
- `canonical-format.md` —— 语料字段与别名全表
- `pipeline.md` —— 流水线细节

## 硬性要求

1. **先看 `dup_dropped`，再信任何规模数字**——抓取端分页游标重叠会产出大量纯重复行，
   不去重会让"评论总数""总赞数"虚高，并让同一条观点被重复计入共识度。
2. **每条带数据的结论必须标引用**：`[源:ID|权重N|层级]`，ID 必须真实出自 `corpus_ccf.csv`。
3. **反例对冲**：每条共识都要配反方论据。语料一片和谐时，必须**主动**去楼中楼与低权重
   长文里开采反例，不能因为"没看到反例"就省略本章。
4. **盲区诚实说明**：主动披露幸存者 / 平台 / 算法 / 时间四类偏差。
5. **交付后必须机验引用**，差集为空才算完成：

```bash
python scripts/verify_citations.py <你的指南.md> corpus_ccf.csv
```

## 交付物

一份 Markdown 深度指南（建议 8 章以上）。建议结构：

> 开场结论 → 认知框架 → 共识 vs 争议 → 反例对冲 → 行动清单 → 盲区说明

---

*本提示词由 comment-distillery v{version} 于 {time} 生成。*
"""


PACK_README_TEMPLATE = """# comment-distillery 蒸馏包

生成时间：{time}　·　工具版本：v{version}

这是一个**开箱即用**的语料包：把它交给任意能读文件的 AI，它就能按 `SKILL.md`
的方法论产出带引用的深度指南。

## 怎么用（三步）

1. 把**整个文件夹**拖进你的 AI 对话（Claude / ChatGPT / Codex / WorkBuddy / Cursor…），
   或者把 `PROMPT.md` 整段粘进对话框，再把 `all_comments.txt` 附上。
2. AI 按 `SKILL.md` 的方法论产出指南。
3. 用引用机验卡一道：差集为空才算交付。

```bash
python scripts/verify_citations.py <你的指南.md> corpus_ccf.csv
```

## 本包含什么

| 文件 | 用途 |
|---|---|
| `PROMPT.md` | **直接粘给 AI 的提示词**（含硬性要求与验收命令） |
| `SKILL.md` | 完整方法论（AI 读它） |
| `all_comments.txt` | 全量易读语料，按权重降序 |
| `low_score_long.txt` | 低权重长文区（真信号） |
| `corpus_ccf.csv` | 规范语料，引用溯源的单一真值源 |
| `stats.json` | 统计口径（**先看 dup_dropped**） |
| `id_map.json` | ID 溯源映射 |
| `canonical-format.md` / `pipeline.md` | 字段规范与流水线说明 |

## 语料概览

{summary}
"""


def _sanitize_name(name: str) -> str:
    """把用户输入的包名清成安全目录名（防路径穿越与非法字符）。"""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", (name or "").strip())
    name = name.strip(" .")
    return name


def _summarize_stats(stats: dict) -> str:
    def g(k, d=0):
        v = stats.get(k, d)
        return v if v is not None else d
    lines = [
        f"- 原始行数：{g('total_raw')}",
        f"- 去重丢弃：**{g('dup_dropped')}**"
        + ("　⚠️ 占比偏高，说明抓取端分页游标发生过重叠，规模数字以下面为准"
           if g('total_raw') and g('dup_dropped') / max(g('total_raw'), 1) > 0.1 else ""),
        f"- 去噪后条数：**{g('total_after_denoise')}**（一级 {g('n_top_level')} / 楼中楼 {g('n_reply')}）",
        f"- 点赞总数：{g('score_sum')}（均值 {g('score_mean')}，最高 {g('score_max')}）",
        f"- 低权重长文条数：{g('n_low_score_long')}",
        f"- 去重作者数：{g('authors_unique')}（其中发过多条 {g('authors_multi')}）",
    ]
    return "\n".join(lines)


def export_package(input_csv, outdir, package_name=None,
                   low_max=8, low_min_len=120, on_log=None, with_glossary=False):
    """一键：原始语料 CSV -> 预处理 -> 蒸馏包目录。

    包内同时含"给人看的说明"与"给 AI 读的语料 + 方法论"，拿到即用。

    on_log(msg) 可选日志回调。
    返回 {pack_dir, files:[...], stats, paths, name}
    """
    log = on_log or (lambda m: print(m))

    src = Path(input_csv)
    if not src.exists():
        raise FileNotFoundError(f"语料 CSV 不存在：{src}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = _sanitize_name(package_name) or f"comment-distillery-pack-{stamp}"
    pack_dir = Path(outdir) / name
    if pack_dir.exists() and any(pack_dir.iterdir()):
        # 同名重跑不能就地覆盖：mkdtemp 式的"复用同名目录"会让上一次的
        # 残留文件跟这一次的产物混在一起，用户分不清哪份是这次的结果。
        # 实测：在包里放一个标记文件，重跑后它仍在 —— 就是这个问题。
        # 这里改名为 <name>-<时间戳>，两次结果各占一个目录，互不污染。
        pack_dir = Path(outdir) / f"{name}-{stamp}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    log(f"[1/4] 预处理语料 → {pack_dir}")
    stats, paths = prepare(str(src), str(pack_dir), low_max, low_min_len)
    log(f"      去重丢弃 {stats.get('dup_dropped', 0)} 行，"
        f"去噪后 {stats.get('total_after_denoise', 0)} 条"
        f"（一级 {stats.get('n_top_level', 0)} / 楼中楼 {stats.get('n_reply', 0)}）")

    log("[2/4] 收录方法论文件")
    copied = []
    sp = skill_path()
    if sp.exists():
        shutil.copyfile(sp, pack_dir / "SKILL.md")
        copied.append("SKILL.md")
    else:
        log("      ⚠️ 未找到 SKILL.md，包内将缺少方法论（AI 产出质量会下降）")
    for rel in RES_DOCS:
        p = resource_root() / rel
        if p.exists():
            shutil.copyfile(p, pack_dir / p.name)
            copied.append(p.name)

    log("[3/4] 生成 PROMPT.md")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    (pack_dir / "PROMPT.md").write_text(
        PROMPT_TEMPLATE.replace("{version}", APP_VERSION).replace("{time}", now),
        encoding="utf-8")

    log("[4/4] 生成 README.md")
    (pack_dir / "README.md").write_text(
        PACK_README_TEMPLATE.replace("{time}", now)
                            .replace("{version}", APP_VERSION)
                            .replace("{summary}", _summarize_stats(stats)),
        encoding="utf-8")

    # 黑话提示（可选，默认关）：
    # 生成代价几乎为零，但它只"提示哪里可能有坑"，不做解释——所以默认关，
    # 需要的人勾一下即可，避免给不需要的人多一个看不懂的文件。
    if with_glossary:
        try:
            from . import glossary as _gl
            gp = _gl.write_glossary(str(pack_dir))
            copied.append("GLOSSARY.md")
            log(f"      已生成黑话提示：{Path(gp).name}"
                "（只提示，不解释；含义未确认时请勿猜）")
        except Exception as e:
            log(f"      ⚠️ 黑话提示生成失败（不影响其余产物）：{e}")

    files = sorted(p.name for p in pack_dir.iterdir() if p.is_file())
    log(f"完成：{pack_dir}（{len(files)} 个文件）")
    return {"pack_dir": str(pack_dir), "files": files, "name": name,
            "stats": stats, "paths": paths, "methodology": copied}


# ────────────────────────────── 自检 ──────────────────────────────

def selfcheck():
    """启动自检：确认随包资源齐全。返回 (ok, [消息...])。

    打包最容易踩的坑就是"漏 --add-data"，症状是运行到一半才报 FileNotFoundError。
    这里在启动时一次性暴露，而不是等用户点了按钮才炸。
    """
    msgs = []
    ok = True
    checks = [
        ("方法论 SKILL.md", RES_SKILL),
        ("预处理脚本", RES_PREP),
        ("引用机验脚本", RES_VERIFY),
        ("数字机验脚本", RES_VERIFYNUM),
        ("规则机验脚本", RES_RULETAGS),
        ("HTML 报告脚本", RES_EMIT),
        ("采集桥接脚本（可选）", RES_CRAWL),
    ]
    for label, rel in checks:
        if (resource_root() / rel).exists():
            msgs.append((True, f"{label}：OK"))
        elif rel == RES_CRAWL:
            msgs.append((True, f"{label}：未随包（仅影响「采集」页）"))
        else:
            ok = False
            msgs.append((False, f"{label}：缺失（{rel}）"))
    return ok, msgs
