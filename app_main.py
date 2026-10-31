#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具入口。

同一个入口服务多种运行方式：

    python app_main.py                 # 源码运行（打开窗口）
    pyinstaller app_main.py            # 打包 exe（见 scripts/build_exe.py）
    comment-distillery.exe --selfcheck     # 随包资源自检（不开窗口，用退出码汇报）
    comment-distillery.exe --selftest-gui  # 构建完整窗口→自动关闭（验证 GUI 真能起来）
    comment-distillery.exe --version

为什么入口放在仓库根而不是 app/ 里：PyInstaller 只把**入口脚本所在目录**加进
sys.path；入口若放在 app/ 内部，`from app.gui import ...` 就找不到 app 包。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _emit(lines, report=None):
    """窗口模式下 sys.stdout 可能是 None（print 会静默丢弃），
    因此自检结果同时支持落盘，便于 CI / 打包后核验。"""
    text = "\n".join(lines) + "\n"
    try:
        if sys.stdout is not None:
            sys.stdout.write(text)
            sys.stdout.flush()
    except Exception:
        pass
    if report:
        try:
            Path(report).write_text(text, encoding="utf-8")
        except Exception:
            pass


def _fatal(msg):
    _emit([msg])
    try:
        import tkinter.messagebox as mb
        mb.showerror("启动失败", msg)
    except Exception:
        pass
    return 1


def _selftest_run(core, outdir, report):
    """端到端自检：用随包样例语料真跑一遍「预处理 → 打包 → 引用机验」。

    这是冻结打包最该验的一环：PyInstaller 把脚本当**数据**塞进 _MEIPASS，
    再由 app/core.py 用 importlib 加载执行。只做 import 检查证明不了这条链路通 ——
    必须真的跑一遍，否则会出现"exe 能开窗、一点按钮就报错"。
    """
    import tempfile
    lines = []
    ok = True

    # `--selftest-run` 的参数是**输出目录**，但极易被误传成 BV 号
    # （文档里写 <dir>，人却习惯照抄 `--selftest-run BV1xxx`）。
    # 早先的写法会静默把 BV 号当目录名建到 cwd，留下一个 `BV1xxx/` 垃圾目录。
    # 这里认出"不像路径"的值就直接说清楚，别猜。
    if outdir:
        looks_like_path = any(c in outdir for c in ("\\", "/")) or outdir in (".", "..") \
            or Path(outdir).suffix != ""
        if not looks_like_path:
            lines.append(f"FAIL --selftest-run 需要的是**输出目录**，不是 BV 号：{outdir}")
            lines.append("     用法：--selftest-run <输出目录>，或直接省略该参数（会用临时目录）")
            _emit(lines, report=report)
            return 1

    outdir = outdir or tempfile.mkdtemp(prefix="cd-selftest-")
    try:
        root = core.resource_root()
        sample = root / "examples" / "sample_corpus.csv"
        guide = root / "examples" / "sample_guide.md"
        lines.append(f"资源根: {root}")
        lines.append(f"输出到: {outdir}")

        if not sample.exists():
            lines.append(f"FAIL 缺少随包样例语料: {sample}")
            ok = False
        else:
            res = core.export_package(str(sample), str(outdir), "selfcheck",
                                      on_log=lambda m: lines.append("  " + m))
            need = {"PROMPT.md", "README.md", "SKILL.md",
                    "corpus_ccf.csv", "all_comments.txt", "stats.json"}
            missing = sorted(need - set(res["files"]))
            if missing:
                lines.append(f"FAIL 蒸馏包缺少: {missing}")
                ok = False
            else:
                lines.append(f"OK   蒸馏包 {len(res['files'])} 个文件已生成")

            if guide.exists():
                v = core.verify_guide(str(guide), [str(sample)])
                lines.append(f"OK   引用机验：{len(v['cited'])} 条引用 / "
                             f"{len(v['bad'])} 条幻觉")
                if v["bad"]:
                    lines.append(f"FAIL 样例指南出现幻觉引用: {v['bad']}")
                    ok = False
            else:
                lines.append("FAIL 缺少随包样例指南")
                ok = False
    except Exception as e:
        import traceback
        lines.append("FAIL 端到端执行抛异常: " + repr(e))
        lines.extend("  " + ln for ln in traceback.format_exc().splitlines()[-5:])
        ok = False

    lines.append("SELFTEST-RUN " + ("PASS" if ok else "FAIL"))
    _emit(lines, report=report)
    return 0 if ok else 1


def _utf8_stdout():
    """把 stdout/stderr 切到 UTF-8，并在异常时降级而不是崩。

    为什么放在 main() 最前面统一做：Windows 控制台默认 GBK，任何一处
    `print("⚡ …")` / `print("✓ …")` 都会抛 UnicodeEncodeError 把整个启动打死。
    这个坑已经踩到第三次（build_exe 自己修过、webui.main 修过、现在
    gui.smoke_test 又踩），说明"各处自觉加"不可靠 —— 入口一次性兜住。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv=None):
    _utf8_stdout()
    args = list(sys.argv[1:] if argv is None else argv)

    def opt(name):
        """取 `--report <path>` 之类的值；后面紧跟另一个开关时视为缺省。"""
        if name in args:
            i = args.index(name)
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                return args[i + 1]
        return None

    try:
        import tkinter  # noqa: F401  仅探测可用性
    except ImportError as e:
        return _fatal(
            "启动失败：当前 Python 缺少 tkinter。\n"
            "Windows 官方 Python 自带 tkinter；若使用裁剪过的解释器，"
            "请安装 python3-tk 后重试。\n"
            f"原始错误：{e}"
        )

    from app import core

    if "--version" in args:
        _emit([f"comment-distillery {core.APP_VERSION}"])
        return 0

    if "--selfcheck" in args:
        ok, msgs = core.selfcheck()
        lines = [("OK   " if g else "FAIL ") + m for g, m in msgs]
        lines.append(f"resource_root = {core.resource_root()}")
        lines.append("SELFCHECK " + ("PASS" if ok else "FAIL"))
        _emit(lines, report=opt("--report"))
        return 0 if ok else 1

    if "--selftest-run" in args:
        return _selftest_run(core, opt("--selftest-run"), opt("--report"))

    # exe 入口也要能起本地 Web 界面：源码用户走 `python -m app --web`，
    # 而 exe 只有 app_main 这一个入口，不接这个开关就等于 exe 用户永远
    # 只能用 tkinter（换机器 / 远程用就没法子了）。
    if "--web" in args or "-w" in args:
        from app.webui import main as webui_main
        rest = [a for a in args if a not in ("--web", "-w")]
        return webui_main(rest)

    from app.gui import main as gui_main, smoke_test

    if "--selftest-gui" in args:
        rc = smoke_test()
        info = list(getattr(smoke_test, "info", []))
        _emit(info + [f"SELFTEST-GUI {'PASS' if rc == 0 else 'FAIL'}"],
              report=opt("--report"))
        return rc

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
