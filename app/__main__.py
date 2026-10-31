#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python -m app 入口。

    python -m app                    # 桌面窗口（tkinter）
    python -m app --web              # 本地 Web 界面（纯标准库，跨平台，免打包）
    python -m app --selfcheck        # 随包资源自检（不开窗口）
    python -m app --selftest-gui     # 建窗→自动关，验证 GUI 真能起来
    python -m app --selftest-run <BV|链接>   # 端到端跑一次真实流水线

``--web`` 只影响 Web 分支；其余开关一律转交给 app_main，**不能再自己吞掉**。
早先这里只认 ``--web``，把其它参数全当"多余"丢掉、直接开图形界面，
于是 ``-m app --selftest-gui`` 变成"打开一个真窗口然后永远不退"——
打包冒烟与 CI 都卡在这里，还得靠 Ctrl+C 收场。
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

    if web:
        rest = [a for a in argv if a not in ("--web", "-w")]
        from app.webui import main as webui_main
        return webui_main(rest)

    # 桌面 / 自检 / 端到端等开关由 app_main 统一裁决（单一入口，避免两套解析）
    try:
        from app_main import main as app_main
    except ImportError as e:      # 打包后 app_main 可能不在包内，退回本地实现
        return _gui_only(argv, e)
    return app_main(argv)


def _gui_only(argv, import_err):
    """兜底：只有 app 包时的最小可用路径。"""
    if any(a.startswith("--selftest") or a == "--selfcheck" for a in argv):
        return _fail(
            "该自检开关需要 app_main.py 在场（它负责调度各子命令）。\n"
            f"导入失败：{import_err}\n"
            "直接运行：python app_main.py " + " ".join(argv) + "\n")
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
