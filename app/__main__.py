#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python -m app 入口。"""

import sys


def _fail(msg):
    try:
        sys.stderr.write(msg)
    except Exception:
        pass
    return 1


def main():
    try:
        from app.gui import main as gui_main
    except ImportError as e:
        return _fail(
            "启动失败：当前 Python 缺少 tkinter。\n"
            "Windows 官方 Python 自带 tkinter；若使用裁剪过的解释器，"
            "请安装 python3-tk 后重试。\n"
            f"原始错误：{e}\n"
        )
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
