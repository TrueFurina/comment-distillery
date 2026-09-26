#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具 · tkinter 界面层。

只有本模块依赖 GUI；全部业务逻辑在 app/core.py（可被测试直接导入）。

线程模型
--------
所有耗时操作都在后台线程跑，通过 queue 把
    log / progress / done / error
四类事件送回主线程，主线程用 after() 轮询消费。
**worker 线程绝不触碰任何 tk 控件** —— tkinter 不是线程安全的，
跨线程改控件在 Windows 上会随机崩溃或静默卡死。

零第三方依赖：只用标准库 tkinter。
"""

import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app import core

# ─────────────────────── 配色（与官网同一套色系） ───────────────────────
BG = "#0b1020"
PANEL = "#141b2e"
PANEL2 = "#1d2740"
INK = "#e8eefc"
MUTED = "#8fa3c9"
DIM = "#5d7298"
ACC = "#00e59b"
BLUE = "#38b6ff"
WARN = "#ffb454"
ERR = "#ff6b81"
LINE = "#243149"

UI_FONT = ("Microsoft YaHei UI", 10)
MONO_FONT = ("Consolas", 9)

CSV_TYPES = [("语料 CSV", "*.csv"), ("所有文件", "*.*")]
MD_TYPES = [("Markdown 指南", "*.md"), ("所有文件", "*.*")]


def default_outdir() -> str:
    """默认输出目录：用户主目录下（不写 exe 同目录——安装到 Program Files 会没权限）。"""
    d = Path.home() / "comment-distillery-output"
    return str(d)


def open_in_explorer(path) -> bool:
    p = Path(path)
    target = p if p.is_dir() else p.parent
    if not target.exists():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(str(target))          # noqa: S606 —— Windows 专用
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception:
        return False


def _enable_dpi():
    """Windows 高分屏下让文字不发虚。失败无所谓，只是观感问题。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ─────────────────────────── 后台任务封装 ───────────────────────────

class Task:
    """把后台函数变成事件流：log / progress / done / error。"""

    def __init__(self, fn):
        self.fn = fn
        self.q = queue.Queue()
        self._stop = threading.Event()

    # — 供 worker 调用（线程安全：只往 queue 里塞） —
    def log(self, msg):
        self.q.put(("log", str(msg)))

    def progress(self, done, total, sub=0):
        self.q.put(("progress", (done, total, sub)))

    def stopped(self) -> bool:
        return self._stop.is_set()

    # — 供主线程调用 —
    def request_stop(self):
        self._stop.set()

    def start(self):
        def worker():
            try:
                res = self.fn(self)
                self.q.put(("done", res))
            except Exception as e:                     # noqa: BLE001
                self.q.put(("error", (e, traceback.format_exc())))
        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────── 通用页基类 ───────────────────────────

class RunTab(ttk.Frame):
    """标题 + 表单区 +（进度 + 日志 + 运行按钮）的通用页。"""

    def __init__(self, master, title, hint, run_label="开始", supports_stop=False):
        super().__init__(master, style="Card.TFrame")
        self.task = None
        self._build_head(title, hint)
        self.fields = ttk.Frame(self, style="Card.TFrame")
        self.fields.pack(fill="x", padx=22, pady=(0, 10))
        self._build_footer(run_label, supports_stop)

    # — 骨架 —
    def _build_head(self, title, hint):
        box = ttk.Frame(self, style="Card.TFrame")
        box.pack(fill="x", padx=22, pady=(18, 12))
        ttk.Label(box, text=title, style="H1.TLabel").pack(anchor="w")
        ttk.Label(box, text=hint, style="Muted.TLabel", wraplength=940,
                  justify="left").pack(anchor="w", pady=(4, 0))

    def _build_footer(self, run_label, supports_stop):
        foot = ttk.Frame(self, style="Card.TFrame")
        foot.pack(fill="both", expand=True, padx=22, pady=(0, 18))

        prog = ttk.Frame(foot, style="Card.TFrame")
        prog.pack(fill="x", pady=(0, 8))
        self.pbar = ttk.Progressbar(prog, mode="determinate", maximum=100,
                                    style="Horizontal.TProgressbar")
        self.pbar.pack(side="left", fill="x", expand=True)
        self.plabel = tk.Label(prog, text="", bg=PANEL, fg=DIM, font=MONO_FONT)
        self.plabel.pack(side="left", padx=(10, 0))

        self.logbox = tk.Text(foot, height=13, bg="#0a0f1c", fg=MUTED,
                              insertbackground=INK, relief="flat", wrap="word",
                              font=MONO_FONT, padx=12, pady=10,
                              highlightthickness=1, highlightbackground=LINE)
        self.logbox.pack(fill="both", expand=True)
        self.logbox.tag_configure("ok", foreground=ACC)
        self.logbox.tag_configure("warn", foreground=WARN)
        self.logbox.tag_configure("err", foreground=ERR)
        self.logbox.tag_configure("info", foreground=MUTED)
        self.logbox.tag_configure("hi", foreground=INK)
        sb = ttk.Scrollbar(foot, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=sb.set)
        sb.place(relx=1.0, rely=0, relheight=1.0, anchor="ne", x=-2)
        self.logbox.configure(state="disabled")

        btns = ttk.Frame(foot, style="Card.TFrame")
        btns.pack(fill="x", pady=(12, 0))
        self.run_btn = ttk.Button(btns, text=run_label, style="Primary.TButton",
                                  command=self._start)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(btns, text="停止", style="Ghost.TButton",
                                   command=self._stop, state="disabled")
        if supports_stop:
            self.stop_btn.pack(side="left", padx=(8, 0))
        self.extra = ttk.Frame(btns, style="Card.TFrame")
        self.extra.pack(side="left", padx=(8, 0))

    # — 表单行助手 —
    def path_row(self, label, var, mode="open", filetypes=None, width=12):
        f = ttk.Frame(self.fields, style="Card.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text=label, style="Field.TLabel", width=width,
                  anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=var, style="Field.TEntry").pack(
            side="left", fill="x", expand=True)

        def browse():
            if mode == "dir":
                p = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
            elif mode == "save":
                p = filedialog.asksaveasfilename(
                    filetypes=filetypes or CSV_TYPES,
                    defaultextension=".csv",
                    initialfile=Path(var.get()).name or "comments.csv")
            else:
                p = filedialog.askopenfilename(filetypes=filetypes or CSV_TYPES)
            if p:
                var.set(p)

        ttk.Button(f, text="浏览…", style="Ghost.TButton",
                   command=browse).pack(side="left", padx=(8, 0))
        return f

    def spin_row(self, label, var, frm, to, width=12):
        f = ttk.Frame(self.fields, style="Card.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text=label, style="Field.TLabel", width=width,
                  anchor="w").pack(side="left")
        ttk.Spinbox(f, from_=frm, to=to, textvariable=var, width=8,
                    style="TSpinbox").pack(side="left")
        return f

    def entry_row(self, label, var, width=12):
        f = ttk.Frame(self.fields, style="Card.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text=label, style="Field.TLabel", width=width,
                  anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=var, style="Field.TEntry").pack(
            side="left", fill="x", expand=True)
        return f

    # — 日志 —
    def log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.logbox.configure(state="normal")
        self.logbox.insert("end", f"[{ts}] {msg}\n", tag)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def clear_log(self):
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")

    # — 运行控制 —
    def _start(self):
        if self.task is not None:
            return
        try:
            work = self.build_work()
        except ValueError as e:
            messagebox.showwarning("参数不完整", str(e))
            return
        self.clear_log()
        self.task = Task(work)
        self._set_running(True)
        self.pbar.configure(value=0)
        self.plabel.configure(text="")
        self.task.start()
        self.after(60, self._pump)

    def _stop(self):
        if self.task is not None:
            self.task.request_stop()
            self.log("已请求停止：会在当前这条评论处理完后停下，已抓取的部分仍会写出。", "warn")

    def _set_running(self, running):
        self.run_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    def _pump(self):
        if self.task is None:
            return
        try:
            while True:
                kind, payload = self.task.q.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "progress":
                    done, total, sub = payload
                    if total:
                        self.pbar.configure(maximum=total, value=done)
                        self.plabel.configure(text=f"{done}/{total} · 楼中楼 {sub}")
                elif kind == "done":
                    self.task = None
                    self._set_running(False)
                    self.on_done(payload)
                    return
                elif kind == "error":
                    exc, tb = payload
                    self.task = None
                    self._set_running(False)
                    self.log(f"失败：{exc}", "err")
                    for line in tb.strip().splitlines()[-4:]:
                        self.log("  " + line, "err")
                    self.set_status("失败", ERR)
                    messagebox.showerror("任务失败", f"{type(exc).__name__}: {exc}")
                    return
        except queue.Empty:
            pass
        self.after(80, self._pump)

    # — 由子类实现 —
    def build_work(self):
        raise NotImplementedError

    def on_done(self, result):
        raise NotImplementedError

    def set_status(self, text, color=DIM):
        app = self.winfo_toplevel()
        if hasattr(app, "set_status"):
            app.set_status(text, color)


# ─────────────────────────── ① 采集 ───────────────────────────

class CrawlTab(RunTab):
    def __init__(self, master):
        super().__init__(
            master,
            "① 采集 · 从视频链接拿评论",
            "粘贴 B 站视频链接或 BV 号，自动完成 WBI 签名、翻页、楼中楼子回复拉取，"
            "输出与预处理脚本对齐的 CSV。\n"
            "提示：楼中楼是「辩论层」——反例与纠错几乎只在这里。追求速度可勾选「只抓一级评论」。",
            run_label="开始采集", supports_stop=True)

        self.var_url = tk.StringVar()
        self.var_out = tk.StringVar(value=str(Path(default_outdir()) / "comments.csv"))
        self.var_roots = tk.BooleanVar(value=False)

        self.entry_row("视频链接 / BV", self.var_url)
        self.path_row("保存为", self.var_out, mode="save", filetypes=CSV_TYPES)

        f = ttk.Frame(self.fields, style="Card.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text="", style="Field.TLabel", width=12).pack(side="left")
        ttk.Checkbutton(f, text="只抓一级评论（不发子回复请求，规避限流）",
                        variable=self.var_roots).pack(side="left")

        ttk.Button(self.extra, text="打开所在文件夹", style="Ghost.TButton",
                   command=lambda: open_in_explorer(self.var_out.get())).pack(side="left")

    def build_work(self):
        url = self.var_url.get().strip()
        out = self.var_out.get().strip()
        if not url:
            raise ValueError("请填写视频链接或 BV 号。")
        if not out:
            raise ValueError("请指定保存路径。")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        roots = self.var_roots.get()

        def work(t):
            self.set_status("采集中…", BLUE)
            t.log("开始采集（内置随机限速，请勿高频使用）")
            res = core.crawl_comments(
                url, out, roots_only=roots,
                on_log=t.log, on_progress=t.progress, should_stop=t.stopped)
            return res

        return work

    def on_done(self, res):
        if res.get("stopped"):
            self.log(f"已停止。已写出 {res['n_total']} 条 → {res['out_csv']}", "warn")
        else:
            self.log(f"采集完成：{res['n_total']} 条"
                     f"（一级 {res['n_top']} / 楼中楼 {res['n_sub']}）", "ok")
        self.log(f"输出：{res['out_csv']}", "hi")
        self.log("下一步：切到「② 预处理」，把这个 CSV 变成 AI 易读的语料。", "info")
        self.set_status("采集完成", ACC)


# ─────────────────────────── ② 预处理 ───────────────────────────

class PrepTab(RunTab):
    def __init__(self, master):
        super().__init__(
            master,
            "② 预处理 · 把 CSV 变成 AI 易读语料",
            "编码容错读取 → 按 ID 去重 → 去噪 → 按权重降序 → 导出规范语料、易读文本、"
            "低权重长文、统计与 ID 映射。\n"
            "去重是硬需求：抓取端分页游标重叠会产生大量纯重复行，不去重会让规模与共识度双双虚高。",
            run_label="开始预处理")

        self.var_in = tk.StringVar()
        self.var_out = tk.StringVar(value=str(Path(default_outdir()) / "prep"))
        self.var_low = tk.IntVar(value=8)
        self.var_len = tk.IntVar(value=120)

        self.path_row("语料 CSV", self.var_in, filetypes=CSV_TYPES)
        self.path_row("输出目录", self.var_out, mode="dir")
        self.spin_row("低权重阈值", self.var_low, 0, 1000)
        self.spin_row("长文阈值", self.var_len, 20, 10000)

        ttk.Button(self.extra, text="打开输出目录", style="Ghost.TButton",
                   command=lambda: open_in_explorer(self.var_out.get())).pack(side="left")

    def build_work(self):
        src = self.var_in.get().strip()
        out = self.var_out.get().strip()
        if not src or not Path(src).exists():
            raise ValueError("请选择一个存在的语料 CSV。")
        if not out:
            raise ValueError("请指定输出目录。")

        def work(t):
            self.set_status("预处理中…", BLUE)
            t.log(f"读取 {src}")
            stats, paths = core.prepare(src, out, self.var_low.get(), self.var_len.get())
            return stats, paths

        return work

    def on_done(self, result):
        stats, paths = result
        raw = stats.get("total_raw", 0)
        dup = stats.get("dup_dropped", 0)
        n = stats.get("total_after_denoise", 0)

        self.log(f"原始行数   {raw}", "hi")
        if dup:
            pct = dup / raw * 100 if raw else 0
            tag = "warn" if pct > 10 else "info"
            extra = "  ← 抓取端游标重叠，规模数字以去重后为准" if pct > 10 else ""
            self.log(f"去重丢弃   {dup}（{pct:.1f}%）{extra}", tag)
        else:
            self.log("去重丢弃   0", "ok")
        self.log(f"去噪后条数 {n}（一级 {stats.get('n_top_level', 0)}"
                 f" / 楼中楼 {stats.get('n_reply', 0)}）", "ok")
        self.log(f"点赞总数   {stats.get('score_sum', 0)}"
                 f"（均值 {stats.get('score_mean', 0)}，最高 {stats.get('score_max', 0)}）", "info")
        self.log(f"低权重长文 {stats.get('n_low_score_long', 0)} 条"
                 f"（权重≤{self.var_low.get()} 且字数≥{self.var_len.get()}）", "info")
        self.log(f"去重作者   {stats.get('authors_unique', 0)}"
                 f"（发过多条 {stats.get('authors_multi', 0)}）", "info")
        self.log("", "info")
        for k, v in paths.items():
            self.log(f"→ {k:16s} {v}", "hi")
        self.log("下一步：切到「③ 导出蒸馏包」一键打包，或直接用它微调。", "info")
        self.set_status("预处理完成", ACC)


# ─────────────────────────── ③ 导出蒸馏包 ───────────────────────────

class PackTab(RunTab):
    def __init__(self, master):
        super().__init__(
            master,
            "③ 导出蒸馏包 · 一键拿给 AI 用",
            "输入原始语料 CSV，一步完成「预处理 + 打包」：产出一个开箱即用的文件夹，"
            "里面既有给 AI 读的语料与方法论，也有可直接粘贴的提示词。\n"
            "要不要 API Key？不需要 —— 蒸馏由你自己选的那个 AI 来完成。",
            run_label="导出蒸馏包")

        self.var_in = tk.StringVar()
        self.var_out = tk.StringVar(value=default_outdir())
        self.var_name = tk.StringVar(value="")
        self.var_low = tk.IntVar(value=8)
        self.var_len = tk.IntVar(value=120)

        self.path_row("语料 CSV", self.var_in, filetypes=CSV_TYPES)
        self.path_row("导出到目录", self.var_out, mode="dir")
        self.entry_row("包名（可空）", self.var_name)
        self.spin_row("低权重阈值", self.var_low, 0, 1000)
        self.spin_row("长文阈值", self.var_len, 20, 10000)

        self.btn_open = ttk.Button(self.extra, text="打开包目录", style="Ghost.TButton",
                                   state="disabled", command=self._open_pack)
        self.btn_open.pack(side="left")
        self._pack_dir = None

    def _open_pack(self):
        if self._pack_dir:
            open_in_explorer(self._pack_dir)

    def build_work(self):
        src = self.var_in.get().strip()
        out = self.var_out.get().strip()
        if not src or not Path(src).exists():
            raise ValueError("请选择一个存在的语料 CSV。")
        if not out:
            raise ValueError("请指定导出目录。")
        Path(out).mkdir(parents=True, exist_ok=True)
        name = self.var_name.get().strip() or None
        low, ln = self.var_low.get(), self.var_len.get()

        def work(t):
            self.set_status("导出蒸馏包…", BLUE)
            return core.export_package(src, out, name, low, ln, on_log=t.log)

        return work

    def on_done(self, res):
        self._pack_dir = res["pack_dir"]
        self.btn_open.configure(state="normal")
        self.log(f"蒸馏包已就绪：{res['pack_dir']}", "ok")
        self.log("包含文件：", "info")
        for f in res["files"]:
            self.log(f"  · {f}", "hi")
        self.log("", "info")
        self.log("怎么用：把整个文件夹拖进你的 AI（或把 PROMPT.md 粘进对话框 + 附上 "
                 "all_comments.txt），它就会按 SKILL.md 产出指南。", "info")
        self.log("拿到指南后回到「④ 引用校验」卡一道——差集为空才算交付。", "info")
        self.set_status("蒸馏包导出完成", ACC)


# ─────────────────────────── ④ 引用校验 ───────────────────────────

class VerifyTab(RunTab):
    def __init__(self, master):
        super().__init__(
            master,
            "④ 引用校验 · 卡住幻觉引用",
            "AI 写长指南时会生成「格式完全正确、但语料里根本不存在」的引用 ID —— "
            "肉眼无法分辨，唯一可靠的发现方式是机器比对差集。\n"
            "差集必须为空才允许交付。诚实的降级方式是减少引用条数，"
            "绝不是保留一个『看起来对』的 ID。",
            run_label="开始校验")

        self.var_guide = tk.StringVar()
        self.var_corpora = tk.StringVar()
        self._corpora = []

        self.path_row("指南 Markdown", self.var_guide, filetypes=MD_TYPES)

        f = ttk.Frame(self.fields, style="Card.TFrame")
        f.pack(fill="x", pady=4)
        ttk.Label(f, text="语料 CSV", style="Field.TLabel", width=12,
                  anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=self.var_corpora, style="Field.TEntry").pack(
            side="left", fill="x", expand=True)
        ttk.Button(f, text="选择…", style="Ghost.TButton",
                   command=self._pick_corpora).pack(side="left", padx=(8, 0))

        ttk.Button(self.extra, text="校验随包 SKILL.md", style="Ghost.TButton",
                   command=self._check_skill).pack(side="left")

    def _pick_corpora(self):
        ps = filedialog.askopenfilenames(filetypes=CSV_TYPES)
        if ps:
            self._corpora = list(ps)
            self.var_corpora.set(" ｜ ".join(Path(p).name for p in ps))

    def _check_skill(self):
        res = core.check_skill()
        self.clear_log()
        self.log(f"文件：{res['path']}", "info")
        self.log(f"条目总数 {res['checked']}   带标记 {res['tagged']}   "
                 f"裸铁律 {len(res['errors'])}", "hi")
        if res["errors"]:
            for e in res["errors"]:
                self.log("  " + e, "err")
            self.set_status("发现裸铁律", ERR)
        else:
            self.log("通过：全部规则条目均带溯源标记。", "ok")
            self.set_status("SKILL.md 检查通过", ACC)

    def build_work(self):
        guide = self.var_guide.get().strip()
        if not guide or not Path(guide).exists():
            raise ValueError("请选择一个存在的指南 Markdown。")
        corpora = self._corpora or [p.strip() for p in
                                    self.var_corpora.get().split("｜") if p.strip()]
        if not corpora:
            raise ValueError("请选择至少一个语料 CSV。")

        def work(t):
            self.set_status("校验中…", BLUE)
            t.log(f"指南：{guide}")
            for c in corpora:
                t.log(f"语料：{c}")
            return core.verify_guide(guide, corpora)

        return work

    def on_done(self, res):
        for c in res["per_corpus"]:
            self.log(f"读取 {Path(c['path']).name}：{c['n']} 个 ID"
                     f"（列：{c['col']}）", "info")
        self.log("", "info")
        self.log(f"语料 ID 全集 {len(res['real'])}", "hi")
        self.log(f"指南引用 ID  {len(res['cited'])}", "hi")
        bad = res["bad"]
        if bad:
            self.log(f"幻觉引用     {len(bad)}", "err")
            self.log("", "info")
            for b in bad:
                self.log(f"  {b}", "err")
                ctx = res["contexts"].get(b)
                if ctx:
                    self.log(f"      … {ctx} …", "warn")
            self.log("", "info")
            self.log("请把这些 ID 换成语料里真实存在的条目，或删掉该条引用后重跑。", "warn")
            self.set_status(f"发现 {len(bad)} 个幻觉引用", ERR)
        else:
            self.log("幻觉引用     0 —— 全部引用均可在语料中溯源。", "ok")
            self.set_status("引用校验通过", ACC)


# ─────────────────────────── ⑤ 关于 ───────────────────────────

class AboutTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame")
        self.app = app

        box = ttk.Frame(self, style="Card.TFrame")
        box.pack(fill="both", expand=True, padx=22, pady=20)

        ttk.Label(box, text="关于", style="H1.TLabel").pack(anchor="w")
        ttk.Label(box, text="comment-distillery 把一群人对同一议题的自发文本，"
                            "蒸馏成一份带认知框架、共识与争议、反例对冲、引用溯源、"
                            "行动清单与盲区说明的深度指南。",
                  style="Muted.TLabel", wraplength=900, justify="left").pack(
            anchor="w", pady=(6, 16))

        info = [
            ("工具版本", f"v{core.APP_VERSION}"),
            ("运行方式", "已打包 exe" if core.is_frozen() else "源码运行"),
            ("Python", sys.version.split()[0]),
            ("资源根", str(core.resource_root())),
            ("输出目录", default_outdir()),
        ]
        grid = ttk.Frame(box, style="Card.TFrame")
        grid.pack(anchor="w", fill="x")
        for i, (k, v) in enumerate(info):
            ttk.Label(grid, text=k, style="Field.TLabel", width=12,
                      anchor="w").grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(grid, text=v, bg=PANEL, fg=INK, font=MONO_FONT,
                     anchor="w").grid(row=i, column=1, sticky="w", pady=2)

        ttk.Label(box, text="随包自检", style="H2.TLabel").pack(anchor="w", pady=(20, 6))
        self.check_box = tk.Text(box, height=7, bg="#0a0f1c", fg=MUTED, relief="flat",
                                 font=MONO_FONT, padx=12, pady=10, wrap="word",
                                 highlightthickness=1, highlightbackground=LINE)
        self.check_box.pack(fill="x")
        self.check_box.tag_configure("ok", foreground=ACC)
        self.check_box.tag_configure("err", foreground=ERR)

        btns = ttk.Frame(box, style="Card.TFrame")
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text="重新自检", style="Ghost.TButton",
                   command=self.run_check).pack(side="left")
        ttk.Button(btns, text="打开输出目录", style="Ghost.TButton",
                   command=lambda: open_in_explorer(default_outdir())).pack(
            side="left", padx=(8, 0))
        ttk.Button(btns, text="项目主页", style="Ghost.TButton",
                   command=lambda: self._open("https://github.com/TrueFurina/comment-distillery")
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="方法论 SKILL.md", style="Ghost.TButton",
                   command=lambda: self._open(core.skill_path())).pack(
            side="left", padx=(8, 0))

        self.run_check()

    def _open(self, target):
        t = str(target)
        try:
            if t.startswith("http"):
                import webbrowser
                webbrowser.open(t)
            else:
                os.startfile(t) if sys.platform == "win32" else subprocess.Popen(
                    ["open" if sys.platform == "darwin" else "xdg-open", t])
        except Exception as e:
            messagebox.showinfo("打开失败", str(e))

    def run_check(self):
        ok, msgs = core.selfcheck()
        self.check_box.configure(state="normal")
        self.check_box.delete("1.0", "end")
        for good, m in msgs:
            self.check_box.insert("end", ("  ✓ " if good else "  ✗ ") + m + "\n",
                                  "ok" if good else "err")
        self.check_box.insert("end",
                              "\n自检结论：" + ("资源齐全，功能可用。" if ok
                                          else "有资源缺失，部分功能不可用。") + "\n",
                              "ok" if ok else "err")
        self.check_box.configure(state="disabled")
        self.app.set_status("自检通过" if ok else "自检发现缺失", ACC if ok else ERR)


# ─────────────────────────── 主窗口 ───────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"comment-distillery v{core.APP_VERSION} · 评论蒸馏工具箱")
        self.configure(bg=BG)
        self.geometry("1080x760")
        self.minsize(940, 660)

        _setup_style(self)
        self._build_header()
        self._build_statusbar()
        self._build_notebook()
        self.set_status("就绪")

    def _build_header(self):
        head = tk.Frame(self, bg=PANEL, height=76)
        head.pack(fill="x", side="top")
        head.pack_propagate(False)
        inner = tk.Frame(head, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=22)
        tk.Label(inner, text="◈", bg=PANEL, fg=ACC,
                 font=("Segoe UI Symbol", 22)).pack(side="left", padx=(0, 12))
        box = tk.Frame(inner, bg=PANEL)
        box.pack(side="left")
        tk.Label(box, text="comment-distillery", bg=PANEL, fg=INK,
                 font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        tk.Label(box, text="把一群人的评论，蒸馏成一份带引用的深度指南",
                 bg=PANEL, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        tk.Label(inner, text=f"v{core.APP_VERSION}", bg=PANEL, fg=DIM,
                 font=MONO_FONT).pack(side="right")
        tk.Frame(self, bg=LINE, height=1).pack(fill="x", side="top")

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL, height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status = tk.Label(bar, text="", bg=PANEL, fg=DIM,
                                font=("Microsoft YaHei UI", 9), anchor="w")
        self._status.pack(side="left", padx=22)
        tk.Label(bar, text="零第三方依赖 · 仅标准库", bg=PANEL, fg=DIM,
                 font=("Microsoft YaHei UI", 9)).pack(side="right", padx=22)

    def _build_notebook(self):
        nb = ttk.Notebook(self, style="TNotebook")
        nb.pack(fill="both", expand=True, padx=14, pady=12)
        self.tabs = {
            "crawl": CrawlTab(nb),
            "prep": PrepTab(nb),
            "pack": PackTab(nb),
            "verify": VerifyTab(nb),
            "about": AboutTab(nb, self),
        }
        nb.add(self.tabs["crawl"], text="① 采集")
        nb.add(self.tabs["prep"], text="② 预处理")
        nb.add(self.tabs["pack"], text="③ 导出蒸馏包")
        nb.add(self.tabs["verify"], text="④ 引用校验")
        nb.add(self.tabs["about"], text="关于")

    def set_status(self, text, color=DIM):
        try:
            self._status.configure(text=text, fg=color)
        except Exception:
            pass


def _setup_style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=PANEL, foreground=INK, fieldbackground=PANEL2,
                 bordercolor=LINE, lightcolor=PANEL2, darkcolor=PANEL2,
                 troughcolor=PANEL2, focuscolor=ACC, font=UI_FONT)
    st.configure("Card.TFrame", background=PANEL)
    st.configure("TLabel", background=PANEL, foreground=INK)
    st.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
    st.configure("Field.TLabel", background=PANEL, foreground=MUTED)
    st.configure("H1.TLabel", background=PANEL, foreground=INK,
                 font=("Microsoft YaHei UI", 15, "bold"))
    st.configure("H2.TLabel", background=PANEL, foreground=ACC,
                 font=("Microsoft YaHei UI", 10, "bold"))
    st.configure("Field.TEntry", fieldbackground=PANEL2, foreground=INK,
                 insertcolor=INK, bordercolor=LINE, padding=6)
    st.map("Field.TEntry", fieldbackground=[("focus", PANEL2)],
           bordercolor=[("focus", ACC)])
    st.configure("TButton", background=PANEL2, foreground=INK,
                 bordercolor=LINE, padding=(12, 7), relief="flat")
    st.map("TButton", background=[("active", LINE)], bordercolor=[("active", ACC)])
    st.configure("Primary.TButton", background=ACC, foreground="#04120c",
                 font=("Microsoft YaHei UI", 10, "bold"), padding=(18, 9))
    st.map("Primary.TButton",
           background=[("active", "#00c88a"), ("disabled", "#26343a")],
           foreground=[("disabled", DIM)])
    st.configure("Ghost.TButton", padding=(9, 6))
    st.configure("TCheckbutton", background=PANEL, foreground=MUTED)
    st.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", INK)])
    st.configure("TSpinbox", fieldbackground=PANEL2, foreground=INK,
                 arrowcolor=MUTED, bordercolor=LINE, padding=4)
    st.configure("TNotebook", background=BG, bordercolor=LINE, tabmargins=(2, 8, 2, 0))
    st.configure("TNotebook.Tab", background=BG, foreground=MUTED,
                 padding=(20, 10), font=("Microsoft YaHei UI", 10))
    st.map("TNotebook.Tab", background=[("selected", PANEL)],
           foreground=[("selected", ACC)])
    st.configure("Horizontal.TProgressbar", background=ACC, troughcolor=PANEL2,
                 bordercolor=PANEL2, lightcolor=ACC, darkcolor=ACC, thickness=8)


def main():
    _enable_dpi()
    app = App()
    app.mainloop()
    return 0


def smoke_test(hold_ms=1500):
    """构建完整窗口、跑一小段真实事件循环、自动关闭。

    用途：打包后的冒烟验证。只做 import 检查证明不了什么 —— 必须让
    tkinter 真的初始化、所有控件真的构造一遍、事件循环真的转起来，
    才能说"这个 exe 能用"。任何一处控件参数写错都会在这里抛异常。
    """
    _enable_dpi()
    app = App()
    app.after(hold_ms, app.destroy)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
