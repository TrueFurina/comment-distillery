#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python -m app 入口。

    python -m app           # 桌面窗口（tkinter）
    python -m app --web     # 本地 Web 界面（纯标准库，跨平台，免打包）
"""

import sys


def _fail(msg):
    try:
        sys.stderr.write(msg)
    except Exception:
        pass
    return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    web = any(a in ("--web", "-w") for a in argv)
    rest = [a for a in argv if a not in ("--web", "-w")]

    if web:
        from app.webui import main as webui_main
        return webui_main(rest)

    try:
        from app.gui import main as gui_main
    except ImportError as e:
        return _fail(
            "启动失败：当前 Python 缺少 tkinter。\n"
            "Windows 官方 Python 自带 tkinter；若使用裁剪过的解释器，"
            "请安装 python3-tk 后重试。\n"
            f"原始错误：{e}\n\n"
            "或者改用不需要 tkinter 的本地 Web 界面：\n"
            "    python -m app --web\n"
        )
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
