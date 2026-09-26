#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 comment-distillery 桌面 exe（PyInstaller）。

用法（须在**已安装 PyInstaller** 的解释器里运行）:

    python scripts/build_exe.py              # 单文件 GUI（发布用）
    python scripts/build_exe.py --console    # 带控制台窗口（排障用）
    python scripts/build_exe.py --onedir     # 目录版（启动更快、便于排障）
    python scripts/build_exe.py --clean      # 先清 build/dist
    python scripts/build_exe.py --verify     # 核验产物内资源与仓库是否逐项一致

本机构建环境（一次性，路径随你放）:

    py -3.13 -m venv <某处>/venv313
    <某处>/venv313/Scripts/python.exe -m pip install pyinstaller

⚠️ 用**带 tkinter** 的解释器建 venv：GUI 与打包都依赖它。
   （某些精简发行版 / 托管环境的 Python 不带 tkinter，实测 import 报
     `ModuleNotFoundError: No module named 'tkinter'`。本脚本会先探测再构建。）

打包后**必须**真实启动一次再宣称成功 —— "装上了 ≠ 能用"：

    dist\\comment-distillery.exe --selfcheck       # 随包资源是否齐全
    dist\\comment-distillery.exe --selftest-gui    # 真建窗口、真跑事件循环

零第三方依赖是**运行时**承诺；PyInstaller 只存在于构建期，不进入产物逻辑。
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "comment-distillery"

# 随包资源：(源路径, 包内目标目录)。漏任何一条都会让 exe 运行到一半报错，
# 因此 app/core.py 的 selfcheck() 会在启动时一次性把它们检出来。
#
# ⚠️ 只列**运行期真正需要**的文件，不要图省事整目录塞进来：
#   ① 整目录会把只是构建期用的脚本（如本文件）也打进产物，产物里出现陈旧副本；
#   ② 而一旦 build_exe.py 变了，产物就"过期"，形成"改脚本→产物过期→重建→又变"的循环。
#     （本文件与 make_icon.py 属构建期，**故意不打包**。）
ADD_DATA = [
    ("SKILL.md", "."),
    ("docs/canonical-format.md", "docs"),
    ("docs/pipeline.md", "docs"),
    ("scripts/prep.py", "scripts"),
    ("scripts/verify_citations.py", "scripts"),
    ("scripts/check_rule_tags.py", "scripts"),
    ("contrib/fetch_bilibili_comments.py", "contrib"),
    ("contrib/README.md", "contrib"),
    ("examples/sample_corpus.csv", "examples"),
    ("examples/sample_guide.md", "examples"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_icon() -> Path | None:
    """图标缺失就地生成（PNG/ICO 都用标准库手写，不引入 Pillow）。"""
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        return icon
    mk = ROOT / "scripts" / "make_icon.py"
    if mk.exists():
        print("[icon] 未找到图标，先执行 scripts/make_icon.py 生成…")
        subprocess.run([sys.executable, str(mk)], cwd=ROOT, check=False)
    return icon if icon.exists() else None


def verify_pack(exe: Path) -> int:
    """核验产物内随包资源与**仓库当前版本**逐项一致（防"陈旧副本"）。

    为什么需要它：exe 里打包的是资源**快照**。改了 SKILL.md / 脚本后若忘了重建，
    产物外表毫无异样、自检照样 PASS（自检只看"文件在不在"，不看"是不是最新"），
    但用户导出的蒸馏包里带的就是过期方法论。这是最隐蔽的一类漂移。

    返回 0 = 一致；1 = 有差异；2 = 无法核验。
    """
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        print("[FAIL] --verify 需要 PyInstaller（读取产物归档）。", file=sys.stderr)
        return 2
    if not exe.exists():
        print(f"[FAIL] 产物不存在: {exe}", file=sys.stderr)
        return 2

    reader = CArchiveReader(str(exe))
    toc = [n.replace("\\", "/") for n in reader.toc]

    def digest(arc_name):
        # toc 里存的是反斜杠形式，找原始名
        orig = next(n for n in reader.toc if n.replace("\\", "/") == arc_name)
        return hashlib.sha256(reader.extract(orig)).hexdigest()

    bad, checked = [], 0
    for src, dst in ADD_DATA:
        p = ROOT / src
        if not p.exists():
            print(f"[warn] 源文件不存在，跳过核验：{src}")
            continue
        arc = p.name if dst in (".", "") else f"{dst}/{p.name}"
        if arc not in toc:
            bad.append(f"产物内缺少 {arc}")
            continue
        got = digest(arc)
        want = hashlib.sha256(p.read_bytes()).hexdigest()
        checked += 1
        if got != want:
            bad.append(f"{arc} 与仓库不一致（产物 {got[:12]} / 仓库 {want[:12]}）")

    # 反向检查：产物里不该出现构建期脚本（整目录打包会把它们塞进来）
    leaked = [n for n in toc
              if n.endswith((".py",)) and any(
                  n.startswith(f"{d}/") for d in ("scripts", "contrib"))
              and Path(n).name not in {Path(s).name for s, _ in ADD_DATA}]
    if leaked:
        bad.append(f"产物内混入了非运行期脚本（整目录打包的迹象）：{sorted(leaked)}")

    print(f"\n[verify] 逐项比对 {checked}/{len(ADD_DATA)} 个随包资源")
    if bad:
        print("[FAIL] 产物与仓库不一致，请重建后再发布：", file=sys.stderr)
        for b in bad:
            print("  - " + b, file=sys.stderr)
        return 1
    print("[OK] 产物内随包资源与仓库当前版本逐项一致，无陈旧副本。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="打包 comment-distillery 桌面 exe")
    ap.add_argument("--console", action="store_true", help="保留控制台窗口（排障用）")
    ap.add_argument("--onedir", action="store_true", help="目录版而非单文件")
    ap.add_argument("--clean", action="store_true", help="构建前清理 build/dist")
    ap.add_argument("--verify", action="store_true",
                    help="核验现有产物内资源与仓库是否逐项一致（不构建）")
    ap.add_argument("--exe", default=None, help="--verify 时指定产物路径")
    args = ap.parse_args(argv)

    if args.verify:
        exe = Path(args.exe) if args.exe else ROOT / "dist" / f"{NAME}.exe"
        if not exe.exists():
            exe = exe.with_suffix("")           # 非 Windows 平台无 .exe 后缀
        return verify_pack(exe)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[FAIL] 当前解释器没有 PyInstaller。\n"
              f"  解释器: {sys.executable}\n"
              "  安装:   <该解释器> -m pip install pyinstaller\n"
              "  提示:   建议用独立的 3.13 构建 venv，别污染运行环境。",
              file=sys.stderr)
        return 2

    # tkinter 是运行期 GUI 依赖，缺它打包出来的 exe 也是废的 —— 提前失败，
    # 别等 PyInstaller 跑完几分钟再报一句看不懂的错。
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("[FAIL] 当前解释器没有 tkinter，打出来的 exe 打开即崩。\n"
              f"  解释器: {sys.executable}\n"
              "  换一个自带 tkinter 的 Python（官方安装包默认包含；\n"
              "  部分精简版/托管环境会裁掉）重建 venv 后重试。",
              file=sys.stderr)
        return 2

    if args.clean:
        for d in ("build", "dist"):
            p = ROOT / d
            if p.exists():
                shutil.rmtree(p)
                print(f"[clean] 已删除 {p}")

    sep = os.pathsep                                   # Windows ';' / POSIX ':'
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir" if args.onedir else "--onefile",
        "--console" if args.console else "--windowed",
        "--name", NAME,
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--paths", str(ROOT),
    ]
    icon = ensure_icon()
    if icon:
        cmd += ["--icon", str(icon)]
    else:
        print("[warn] 未能生成图标，产物将使用默认图标")

    for src, dst in ADD_DATA:
        p = ROOT / src
        if not p.exists():
            print(f"[warn] 随包资源缺失，跳过：{src}", file=sys.stderr)
            continue
        # ⚠️ 必须传绝对路径：一旦用了 --specpath，PyInstaller 会把 --add-data 的相对
        #    路径按 spec 所在目录解析（实测报 "Unable to find build/SKILL.md"）。
        cmd += ["--add-data", f"{p}{sep}{dst}"]

    cmd.append("app_main.py")

    print("[build] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    if rc != 0:
        print(f"[FAIL] PyInstaller 退出码 {rc}", file=sys.stderr)
        return rc

    if args.onedir:
        exe = ROOT / "dist" / NAME / f"{NAME}.exe"
    else:
        exe = ROOT / "dist" / f"{NAME}.exe"
    if not exe.exists():
        # 非 Windows 平台没有 .exe 后缀
        alt = exe.with_suffix("")
        exe = alt if alt.exists() else exe

    if not exe.exists():
        print("[FAIL] 构建声称成功，但产物不存在 —— 不要相信没有产物的成功。",
              file=sys.stderr)
        return 3

    size_mb = exe.stat().st_size / (1 << 20)
    print(f"\n[OK] 产物: {exe}")
    print(f"     体积: {size_mb:.1f} MB")
    print(f"     SHA256: {sha256(exe)}")
    print("\n下一步（务必都跑一遍再宣称成功）：")
    print(f"     {exe.name} --selfcheck")
    print(f"     {exe.name} --selftest-gui")
    print(f"     {exe.name} --selftest-run <dir>")
    print(f"     python {Path(__file__).name} --verify      # 资源是否与仓库逐项一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
