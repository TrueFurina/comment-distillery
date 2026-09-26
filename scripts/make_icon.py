#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成桌面应用图标 assets/icon.ico。

为什么手写 ICO 而不是装 Pillow：本项目对"零第三方依赖"是有承诺的，
构建链路也不该引入 Pillow 这种几十 MB 的重依赖。PNG 用标准库 zlib 就能编，
ICO 只是个简单容器 —— 顺带把图标也变成可复现、可 diff 的产物。

用法:
    python scripts/make_icon.py            # 生成 assets/icon.ico
"""

import os
import struct
import sys
import zlib
from pathlib import Path


def utf8_stdout():
    """stdout/stderr 切 UTF-8：Windows 控制台可能是 cp1252，print 中文会
    UnicodeEncodeError（实测 GitHub windows runner 因这一步直接构建失败）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"

# 与 app/gui.py、官网 同一套配色
BG_TOP = (11, 16, 32)
BG_BOT = (26, 36, 58)
ACC = (0, 229, 155)
BLUE = (56, 182, 255)
SIZES = [16, 24, 32, 48, 64, 128, 256]


def _rounded_bg(size, x, y):
    """圆角矩形底：返回 (r,g,b,a) 或 None（在圆角外）。"""
    r = size * 0.22
    cx = min(max(x, r), size - 1 - r)
    cy = min(max(y, r), size - 1 - r)
    dx, dy = x - cx, y - cy
    if dx * dx + dy * dy > r * r:
        return None
    t = y / max(size - 1, 1)
    return (int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
            int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
            int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t),
            255)


def _diamond(size, x, y):
    """中央菱形（与界面上那个 ◈ 同构），沿对角线从绿渐变到蓝，边缘抗锯齿。"""
    cx = cy = (size - 1) / 2.0
    u = (x - cx) / (size * 0.5)
    v = (y - cy) / (size * 0.5)
    d = abs(u) + abs(v)                      # 曼哈顿距离：菱形等值线
    half = 0.62
    if d > half + 0.14:
        return None
    # 抗锯齿：在 half ~ half+0.14 之间线性淡出
    a = 1.0 if d <= half else max(0.0, (half + 0.14 - d) / 0.14)
    t = min(max((u + v) * 0.5 + 0.5, 0.0), 1.0)
    r = int(ACC[0] + (BLUE[0] - ACC[0]) * t)
    g = int(ACC[1] + (BLUE[1] - ACC[1]) * t)
    b = int(ACC[2] + (BLUE[2] - ACC[2]) * t)
    return (r, g, b, int(a * 255))


def render(size):
    """返回 RGBA 像素行序列（raw，未压缩）。"""
    rows = []
    for y in range(size):
        row = bytearray([0])                 # PNG filter type 0
        for x in range(size):
            px = _rounded_bg(size, x, y)
            if px is None:
                row += bytes((0, 0, 0, 0))
                continue
            dia = _diamond(size, x, y)
            if dia is None:
                row += bytes(px)
                continue
            r, g, b, a = dia
            inv = (255 - a) / 255.0
            row += bytes((int(r * a / 255 + px[0] * inv),
                          int(g * a / 255 + px[1] * inv),
                          int(b * a / 255 + px[2] * inv), 255))
        rows.append(bytes(row))
    return b"".join(rows)


def png_bytes(size):
    """把一个尺寸渲染成 PNG 字节（纯标准库：zlib + crc32）。"""
    raw = render(size)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def main():
    utf8_stdout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images = [(s, png_bytes(s)) for s in SIZES]

    # ICO 容器：ICONDIR + N × ICONDIRENTRY + 各图像数据
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size        # 256 在 ICO 里用 0 表示
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                               len(data), offset)
        blobs += data
        offset += len(data)

    OUT.write_bytes(header + entries + blobs)
    print(f"OK -> {OUT}  ({OUT.stat().st_size / 1024:.1f} KB, {len(images)} 个尺寸)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
