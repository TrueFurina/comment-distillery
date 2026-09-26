#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具 · 逻辑层（无 GUI 依赖）。

四条能力，全部**委托**给仓库已有脚本，不另立实现：

    采集     -> contrib/fetch_bilibili_comments.py :: crawl()
    预处理   -> scripts/prep.py                    :: run()
    引用机验 -> scripts/verify_citations.py        :: run()
    规则机验 -> scripts/check_rule_tags.py         :: check()

为什么坚持委托而不重写：本项目对"数字漂移 / 口径漂移"零容忍。
只要有两套实现，就一定会分叉——CLI 修了 bug 而 exe 里还是旧的。
本层可以被任何前端复用（tkinter / CLI / 未来 webview），也可被测试直接导入。

零第三方依赖，仅标准库。
"""

import importlib.util
import re
import shutil
import sys
import time
from pathlib import Path

APP_VERSION = "1.0.0"

# 随包资源相对路径（打包时需由 scripts/build_exe.py 的 --add-data 收进来）
RES_SKILL = "SKILL.md"
RES_DOCS = ("docs/canonical-format.md", "docs/pipeline.md")
RES_PREP = "scripts/prep.py"
RES_VERIFY = "scripts/verify_citations.py"
RES_RULETAGS = "scripts/check_rule_tags.py"
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


def _ruletags_mod():
    return _load("cd_ruletags", RES_RULETAGS)


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
                   low_max=8, low_min_len=120, on_log=None):
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
        ("规则机验脚本", RES_RULETAGS),
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
