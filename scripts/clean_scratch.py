#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全清理 output/ 与 out/ 下的调试残留。

背景（2026-11-02 事故）
------------------------
上一轮会话把 `output/` 整体判为「scratch 陈旧产物」并移入归档目录，
连带带走了 5 份已交付的蒸馏报告与 `报告索引.html`。
`output/` 被 .gitignore 忽略，git 里没有备份，**报告差点永久丢失**。

根因不是「手滑」，而是**没有把「哪些能删」写成代码**。
本脚本把这条规则固化成白名单 + 保护名单：

- 只有命中 SAFE_PATTERNS 的条目才会被删；
- 命中 PROTECTED_PATTERNS 的条目永远不删，即使显式点名；
- 默认 dry-run，必须加 `--yes` 才真正删除；
- 删除前打印将删/将保留的完整清单。

用法
----
    python scripts/clean_scratch.py                # 预演（不删任何东西）
    python scripts/clean_scratch.py --yes          # 执行
    python scripts/clean_scratch.py --root output  # 只清 output/
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
from pathlib import Path

# ── 可以删：调试 / 冒烟 / 临时 ──────────────────────────────────────────
SAFE_PATTERNS = [
    "e2e*", "dbg*", "debug*", "tmp*", "temp*", "test*", "smoke*",
    "ctl", "p13*", "ui-final", "ui_*", "_probe*", "__pycache__",
    "*.tmp", "*.log", "*.bak",
]

# ── 永远不删：交付物 / 数据 / 索引 ──────────────────────────────────────
PROTECTED_PATTERNS = [
    "distill-*",          # 蒸馏包（report.html + guide.md + 标题命名副本 + stats.json）
    "报告索引*.html",      # 报告总入口
    "index.html",         # 兼容英文名
    "prep-*",             # 预处理产物，重跑成本高
    "comments-*.csv",     # 原始语料，重新采集不等于同一批数据
    "all_comments.*",
    "corpus*",
    "id_map.json",
    "README.md",          # 本目录的防护说明
    ".writable",          # 应用写权限探针
    "_backup",            # 备份快照目录
]

DIRS = ["output", "out"]


def matches(name: str, patterns) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def classify(name: str) -> str:
    """返回 protected / safe / keep。"""
    if matches(name, PROTECTED_PATTERNS):
        return "protected"
    if matches(name, SAFE_PATTERNS):
        return "safe"
    return "keep"


def scan(root: Path):
    """返回 [(path, verdict)]，只看 root 的直接子项。"""
    items = []
    if not root.is_dir():
        return items
    for p in sorted(root.iterdir()):
        items.append((p, classify(p.name)))
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="安全清理 output/ 与 out/ 的调试残留")
    ap.add_argument("--yes", action="store_true", help="真正执行删除（默认只预演）")
    ap.add_argument("--root", default=None, help="只处理指定目录，如 output / out")
    ap.add_argument("--project", default=None, help="项目根（默认取本脚本上级）")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve() if args.project else Path(__file__).resolve().parent.parent
    targets = [args.root] if args.root else DIRS

    total_safe = total_protected = 0
    plan = []

    for d in targets:
        root = project / d
        items = scan(root)
        if not items:
            print(f"[跳过] {root} 不存在或为空")
            continue
        print(f"\n=== {root} ===")
        for p, verdict in items:
            mark = {"protected": "🔒 保护", "safe": "🗑  可删", "keep": "·  保留"}[verdict]
            print(f"  {mark}  {p.name}")
            if verdict == "safe":
                total_safe += 1
                plan.append(p)
            elif verdict == "protected":
                total_protected += 1

    print("\n" + "─" * 58)
    print(f"可删 {total_safe} 项 | 受保护 {total_protected} 项")

    if total_safe == 0:
        print("没有可清理的条目。")
        return 0

    if not args.yes:
        print("\n这是预演（dry-run），未删除任何文件。")
        print("确认无误后执行：  python scripts/clean_scratch.py --yes")
        return 0

    failed = []
    for p in plan:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            print(f"  已删 {p}")
        except Exception as e:  # noqa: BLE001
            failed.append((p, e))
            print(f"  [X] {p}: {type(e).__name__}: {e}")

    if failed:
        print(f"\n{len(failed)} 项删除失败。")
        return 1
    print(f"\n完成，共删除 {len(plan)} 项。受保护的 {total_protected} 项未被触碰。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
