#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 output/ 下的交付物快照到 output/_backup/<时间戳>/。

为什么需要它
------------
`output/` 被 .gitignore 忽略（合规：不得二次分发原始语料），所以
`distill-*/` 与 `报告索引.html` **从来没有进过版本库**。
2026-11-02 一次「清理 scratch」就把 5 份报告整体搬走，git 里无任何备份可回滚。

本脚本提供**本地可逆快照**：删除/清理之前跑一次，任何误操作都能拷回。

用法
----
    python scripts/backup_reports.py                  # 快照到 output/_backup/<ts>/
    python scripts/backup_reports.py --list           # 列出已有快照
    python scripts/backup_reports.py --keep 5         # 只保留最近 5 份
    python scripts/backup_reports.py --restore <ts>   # 从指定快照拷回 output/
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
import time
from pathlib import Path

# 需要备份的交付物
PATTERNS = [
    "distill-*",
    "报告索引*.html",
    "prep-*",
    "comments-*.csv",
]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def collect(src: Path):
    if not src.is_dir():
        return []
    out = []
    for p in sorted(src.iterdir()):
        if p.name == "_backup":
            continue
        if any(fnmatch.fnmatch(p.name, pat) for pat in PATTERNS):
            out.append(p)
    return out


def backup(project: Path, keep: int | None) -> int:
    src = project / "output"
    items = collect(src)
    if not items:
        print(f"[!] {src} 下没有可备份的交付物。")
        print("    若报告还没恢复，先双击项目根的 恢复报告.bat。")
        return 1

    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = src / "_backup" / ts
    dst.mkdir(parents=True, exist_ok=True)

    total = 0
    for p in items:
        target = dst / p.name
        try:
            if p.is_dir():
                shutil.copytree(p, target)
                n = sum(1 for _ in p.rglob("*") if _.is_file())
            else:
                shutil.copy2(p, target)
                n = 1
            total += n
            print(f"  ✓ {p.name}  ({n} 个文件)")
        except Exception as e:  # noqa: BLE001
            print(f"  [X] {p.name}: {type(e).__name__}: {e}")
            return 1

    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())
    print(f"\n快照完成: {dst}")
    print(f"  条目 {len(items)} 个 / 文件 {total} 个 / {size/1024/1024:.1f} MB")

    if keep is not None:
        prune(project, keep)
    return 0


def list_snapshots(project: Path):
    root = project / "output" / "_backup"
    if not root.is_dir():
        print("还没有任何快照。")
        return 0
    snaps = sorted([d for d in root.iterdir() if d.is_dir()], reverse=True)
    if not snaps:
        print("还没有任何快照。")
        return 0
    print(f"共 {len(snaps)} 份快照（新的在前）：")
    for d in snaps:
        n = sum(1 for f in d.rglob("*") if f.is_file())
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        dirs = [x.name for x in d.iterdir() if x.is_dir() and x.name.startswith("distill-")]
        print(f"  {d.name}  {n} 文件 / {size/1024/1024:.1f} MB  包含 {len(dirs)} 个蒸馏包")
    return 0


def prune(project: Path, keep: int):
    root = project / "output" / "_backup"
    if not root.is_dir():
        return
    snaps = sorted([d for d in root.iterdir() if d.is_dir()], reverse=True)
    for old in snaps[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        print(f"  已清理旧快照 {old.name}")


def restore(project: Path, ts: str):
    root = project / "output" / "_backup"
    src = root / ts
    if not src.is_dir():
        print(f"[X] 找不到快照: {src}")
        print("    用 --list 查看可用快照。")
        return 1
    dst = project / "output"
    count = 0
    for p in src.iterdir():
        target = dst / p.name
        if target.exists():
            print(f"  ! 已存在，跳过 {p.name}")
            continue
        if p.is_dir():
            shutil.copytree(p, target)
        else:
            shutil.copy2(p, target)
        count += 1
        print(f"  ✓ 恢复 {p.name}")
    print(f"\n完成，恢复 {count} 项到 {dst}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="备份/恢复 output/ 下的交付物")
    ap.add_argument("--list", action="store_true", help="列出已有快照")
    ap.add_argument("--restore", metavar="TS", help="从指定时间戳快照恢复")
    ap.add_argument("--keep", type=int, default=None, help="备份后只保留最近 N 份快照")
    ap.add_argument("--project", default=None, help="项目根（默认取本脚本上级）")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve() if args.project else project_root()

    if args.list:
        return list_snapshots(project)
    if args.restore:
        return restore(project, args.restore)
    return backup(project, args.keep)


if __name__ == "__main__":
    sys.exit(main())
