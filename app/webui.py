#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具 · 本地 Web 界面（逻辑层）。

为什么要有它（exe 的三宗罪，这个形态一条都不犯）：

    1. 仅 Windows   -> 纯标准库 http.server，Windows / macOS / Linux 同一份代码
    2. SmartScreen 拦截（无签名证书）-> 不打包、不签名，双击一个 .py 或用 -m 启动
    3. 改 SKILL.md 就得重发版（随包资源 = 发版线）-> 读的是仓库当前文件，
       **永远不存在"产物滞后"**

零第三方依赖：http.server / json / threading / webbrowser，全是标准库。
不联网、不上传任何数据——所有计算都在本进程内，语料从不离开本机。

安全边界（本地工具也要有边界，别因为"只是本地"就裸奔）：
    · 默认只监听 127.0.0.1；--lan / --public 时才改绑 0.0.0.0
    · Host / Origin 校验（挡 DNS-rebinding 与跨站表单）
    · 局域网/公开模式改用令牌鉴权（替代本机校验）+ 私网 Host 白名单
    · 路径白名单 + resolve（挡路径穿越与整个磁盘可读）
    · 公开模式额外把文件系统收进单一沙箱并禁用文件选择器
    · 预览页 CSP + sandbox（报告是渲染产物，不当可信脚本执行）

用法：
    python -m app.webui [--port 8756] [--no-browser] [--allow-root DIR]
                        [--lan --token X]    # 局域网：同网段设备可用，功能全开
                        [--public --token X] # 公网部署：收进沙箱，需令牌
"""

import ipaddress
import json
import mimetypes
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app import core
from app.webui_page import PAGE_HTML

DEFAULT_PORT = 8756
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# 私网 Host 白名单：局域网模式（--lan）下，Host / Origin 必须落在这类地址上，
# 既放开「用服务器私网 IP 访问」，又守住 DNS-rebinding（拒绝 evil.com 之类外域 Host）。
try:
    _HOSTNAME = socket.gethostname().lower()
except Exception:
    _HOSTNAME = ""

def _host_allowed(h):
    if not h:
        return False
    if h in _LOCAL_HOSTS:
        return True
    if _HOSTNAME and h == _HOSTNAME:
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local

# ── 公开托管模式 ──────────────────────────────────────────────────────
# 默认关闭。开启后：绑定 0.0.0.0 + 令牌鉴权（替代本机 Host/Origin 校验）+
# 文件系统收进单一沙箱（并禁用文件选择器），使本工具可被部署成"粘贴链接就能用"的
# 在线平台——对标的就是 vreport.tri4t.xyz 那种"填链接一键"形态。
# 关键：蒸馏（LLM）那一步仍不内置——公开模式同样 BYO-AI，不破「不内置 LLM」铁律。
_PUBLIC = False
_ACCESS_TOKEN = ""
_SANDBOX = None
_LAN = False
_DEMO = False


def set_public(token, sandbox, demo=False):
    """进入公开托管模式。sandbox 为空则取 <cwd>/out/public。

    demo=True 时跳过令牌校验：托管平台的代理会注入 Authorization 头，
    空令牌的「开放访问」会被令牌闸门误拦成 401。仅用于公开演示部署，
    沙箱与路径白名单仍然生效。
    """
    global _PUBLIC, _ACCESS_TOKEN, _SANDBOX, _DEMO
    _PUBLIC = True
    _ACCESS_TOKEN = token or ""
    _DEMO = demo
    _SANDBOX = (Path(sandbox).resolve() if sandbox
                else (Path.cwd() / "out" / "public").resolve())
    _SANDBOX.mkdir(parents=True, exist_ok=True)


def set_lan(token):
    """进入局域网模式：绑定 0.0.0.0 + 令牌鉴权 + 私网 Host 白名单。

    与公开模式的关键区别：**保留文件选择器与完整文件系统**（不收进沙箱），
    让可信内网里的任意设备能走完整闭环（含把 AI 成品导回 ④ 引用机验 / ⑤ 出报告）。
    铁律不变：不内置 LLM，蒸馏仍 BYO-AI。
    """
    global _LAN, _ACCESS_TOKEN
    _LAN = True
    _ACCESS_TOKEN = token or ""

# 前端动作 -> 是否需要语料白名单校验的入参键
_EXTRA_ROOTS = set()


# ────────────────────────────── 路径白名单 ──────────────────────────────

def allowed_roots():
    """可访问的根目录集合。

    默认：用户主目录 + 当前工作目录 + 系统临时目录 + 仓库根（读示例语料）。
    刻意**不包含**整个磁盘——本地工具也不是"任意路径可读"的许可证。
    公开模式下：只允许沙箱目录（防公网用户读服务器任意文件）。
    """
    if _PUBLIC and _SANDBOX:
        return [_SANDBOX]
    roots = []
    # 程序目录必须可写：默认输出根就在那儿（打包后 resource_root 是临时解包目录，
    # 不等于程序目录，所以这里要单独加 app_root）。
    for p in (Path.home(), Path.cwd(), Path(tempfile.gettempdir()),
              core.resource_root(), core.app_root()):
        try:
            roots.append(p.resolve())
        except Exception:
            pass
    roots.extend(_EXTRA_ROOTS)
    # 去重并保持顺序
    seen, out = set(), []
    for r in roots:
        k = str(r).lower()
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def add_root(path):
    """追加一个允许根（--allow-root）。"""
    try:
        _EXTRA_ROOTS.add(Path(path).resolve())
    except Exception:
        pass


class OutsideRoot(Exception):
    pass


def safe_path(raw, must_exist=False, allow_missing_parent=False):
    """把外部传入的路径收进白名单内。

    resolve() 先吃掉 `..` 与符号链接，再逐个根做 is_relative_to —— 顺序反了就白给。
    """
    if not raw:
        raise OutsideRoot("路径为空")
    try:
        p = Path(raw).expanduser().resolve()
    except Exception as e:
        raise OutsideRoot(f"路径无法解析：{raw}（{e}）")
    for root in allowed_roots():
        try:
            p.relative_to(root)
        except ValueError:
            continue
        if must_exist and not p.exists():
            raise FileNotFoundError(f"路径不存在：{p}")
        return p
    if allow_missing_parent:
        # 「另存为」允许指向尚不存在的父目录下的新文件：校验父目录
        par = p.parent
        for root in allowed_roots():
            try:
                par.relative_to(root)
                return p
            except ValueError:
                continue
    raise OutsideRoot(
        f"路径不在允许范围内：{p}\n允许的根："
        + "、".join(str(r) for r in allowed_roots()[:3]) + " …"
        "（需要别的目录时用 --allow-root DIR 追加）")


# ────────────────────────────── 作业调度 ──────────────────────────────

_JOBS = {}
_JOB_LOCK = threading.Lock()
_JOB_SEQ = [0]


def _new_job():
    _JOB_SEQ[0] += 1
    jid = f"j{_JOB_SEQ[0]}-{int(time.time() * 1000) % 100000}"
    with _JOB_LOCK:
        _JOBS[jid] = {"id": jid, "done": False, "status": "running",
                      "log": [], "result": None, "error": None,
                      "cancel": False}
    return jid


def _job(jid):
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if not j:
            return None
        return {"id": j["id"], "done": j["done"], "status": j["status"],
                "log": list(j["log"]), "result": j["result"], "error": j["error"],
                "cancelled": bool(j.get("cancel"))}


def _log(jid, msg):
    ts = time.strftime("%H:%M:%S")
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if j is not None:
            j["log"].append(f"[{ts}] {msg}")


def _cancel(jid):
    """请求中止一个作业。真正的"停"由执行体在每个可中断点自查。"""
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if j is None:
            return False
        if j["done"]:
            return False
        j["cancel"] = True
        j["log"].append(f"[{time.strftime('%H:%M:%S')}] 收到停止请求，正在收尾…")
        return True


def _should_stop(jid):
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        return bool(j and j.get("cancel"))


def _finish(jid, result=None, error=None):
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if j is not None:
            j["done"] = True
            if error:
                j["status"] = "error"
            elif j.get("cancel"):
                j["status"] = "cancelled"
            else:
                j["status"] = "ok"
            j["result"] = result
            j["error"] = error


def start_job(action, params):
    """起一个后台作业，立即返回 job id。"""
    jid = _new_job()
    t = threading.Thread(target=_worker, args=(jid, action, params), daemon=True)
    t.start()
    return jid


# ────────────────────────────── 各动作的真正执行体 ──────────────────────────────

def _as_file_target(raw, what="输出文件"):
    """把一个用户填的路径判定为「可写的文件路径」。

    为什么要单独拦一把：界面里「输出目录」和「输出文件」长得很像，
    用户（或旧版默认值）很容易把目录填进文件名位置。不拦的话，
    真正写盘时才会抛 PermissionError / IsADirectoryError，
    而且是在跑完几百秒采集之后才抛——最气人的那种失败。
    """
    p = Path(raw)
    if p.exists() and p.is_dir():
        raise ValueError(
            f"{what}填的是目录：{p}\n"
            f"这里需要的是一个文件路径，例如 {p}\\comments.csv")
    if not p.suffix:
        raise ValueError(
            f"{what}没有扩展名：{p}\n"
            f"请补上文件名，例如 {p}\\comments.csv")
    return p


def _pub_out(name, default):
    """公开模式：把输出路径收进沙箱（只取文件名，杜绝任意写）。"""
    base = (name or "").strip()
    base = Path(base).name or default
    p = _SANDBOX / base
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _pub_in(name, default):
    """公开模式：输入必须已在沙箱内（取文件名查存在的文件）。"""
    base = (name or "").strip()
    base = Path(base).name or default
    p = _SANDBOX / base
    if not p.exists():
        raise FileNotFoundError(f"公开模式下找不到：{base}（请在沙箱内操作）")
    return p


def _files_of(d):
    """把目录或文件路径列表 -> 前端 files 结构。"""
    out = []
    for p in d:
        p = Path(p)
        if p.exists() and p.is_file():
            out.append({"name": p.name, "path": str(p), "size": p.stat().st_size})
    return out


def _do_crawl(p, log):
    arg = (p.get("arg") or "").strip()
    if not arg:
        raise ValueError("请填视频链接或 BV 号")
    if _PUBLIC:
        out_p = _pub_out(p.get("out"), "comments.csv")
    else:
        out = (p.get("out") or "").strip()
        if not out:
            raise ValueError("请填输出 CSV 路径")
        out_p = _as_file_target(safe_path(out, allow_missing_parent=True), "输出 CSV")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    roots_only = bool(p.get("roots_only"))

    last = [0]
    def on_progress(done, total, subs=0):
        """采集进度回调。

        签名必须与 contrib.crawl 的约定一致：on_progress(done, total, subs)。
        这里少写一个形参曾导致 ① 采集跑满 3 分钟后必崩（TypeError），
        用户白等一场——所以形参顺序与默认值都与上游对齐，不再各写一套。
        """
        step = max(50, int(total / 20) if total else 50)   # 大约 20 条进度线
        if total and (done - last[0] >= step or done >= total):
            last[0] = done
            tail = f"，楼中楼 {_fmt(subs)} 条" if subs else ""
            log(f"进度 {_fmt(done)}/{_fmt(total)} 条主楼{tail}")

    res = core.crawl_comments(arg, str(out_p), roots_only=roots_only,
                              on_log=log, on_progress=on_progress,
                              should_stop=p.get("_should_stop"))
    return res, out_p


def _do_prep(p, log):
    if _PUBLIC:
        src = _pub_in(p.get("input"), "comments.csv")
        outdir = _SANDBOX
    else:
        src = safe_path(p.get("input"), must_exist=True)
        outdir = safe_path(core.outdir_or_default(p.get("outdir")),
                           allow_missing_parent=True)
    outdir.mkdir(parents=True, exist_ok=True)
    stats, paths = core.prepare(str(src), str(outdir),
                                int(p.get("low_max") or 8),
                                int(p.get("low_min_len") or 120))
    return (stats, paths), outdir


def _do_pack(p, log):
    if _PUBLIC:
        src = _pub_in(p.get("input"), "comments.csv")
        outdir = _SANDBOX
    else:
        src = safe_path(p.get("input"), must_exist=True)
        outdir = safe_path(core.outdir_or_default(p.get("outdir")),
                           allow_missing_parent=True)
    res = core.export_package(str(src), str(outdir), p.get("name") or None,
                              int(p.get("low_max") or 8),
                              int(p.get("low_min_len") or 120),
                              on_log=log,
                              with_glossary=bool(p.get("with_glossary")))
    return res, Path(res["pack_dir"])


def _do_verify(p, log):
    if _PUBLIC:
        guide = _pub_in(p.get("guide"), "guide.md")
        corpora = [str(_pub_in(c, "comments.csv")) for c in (p.get("corpora") or [])]
    else:
        guide = safe_path(p.get("guide"), must_exist=True)
        corpora = [str(safe_path(c, must_exist=True)) for c in (p.get("corpora") or [])]
    if not corpora:
        raise ValueError("至少给一份语料 CSV——没有语料就无从判断引用是否真实")
    log("抽取引用并与语料真实 ID 求差集…")
    res = dict(core.verify_guide(str(guide), corpora, p.get("field") or None))
    # 数字复算：抓"引用全真但算错"的那一类
    nums, checked = [], 0
    try:
        mod = core._verify_num_mod()
        for c in corpora:
            got, n = mod.collect(str(guide), str(c))
            nums += list(got or [])
            checked += n
        log(f"数字复算：检查 {checked} 处可复算表述，矛盾 {len(nums)} 处")
    except Exception as e:
        log(f"数字复算跳过（{type(e).__name__}: {e}）")
    res["num_issues"] = nums
    res["num_checked"] = checked
    return res, None


def _do_emit(p, log):
    if _PUBLIC:
        guide = _pub_in(p.get("guide"), "guide.md")
        corpora = [str(_pub_in(c, "comments.csv")) for c in (p.get("corpora") or [])]
        out_p = _pub_out(p.get("out"), "report.html")
    else:
        guide = safe_path(p.get("guide"), must_exist=True)
        corpora = [str(safe_path(c, must_exist=True)) for c in (p.get("corpora") or [])]
        out = p.get("out")
        out_p = _as_file_target(safe_path(out, allow_missing_parent=True),
                                "输出 HTML") if out else None
    log("渲染中…")
    res = core.emit_report(str(guide), str(out_p) if out_p else None,
                           corpora or None, None,
                           p.get("title") or None, p.get("subtitle") or None,
                           bool(p.get("no_verify")))
    return res, Path(res["out"])


def _do_auto(p, log):
    """一键：采集 → 预处理 → 蒸馏包 →（配了 AI 就）指南 → 机验 → 报告。

    "一键"的终点取决于用户是否配了 AI，这个分叉由 core.finish_after_pack
    统一决定，本函数只负责把前段产物交出去。**不内置 LLM 仍然成立**：
    配了也只是用用户自己的 endpoint 与 Key，工具不捆绑模型、不代付。

    参数：
        arg         BV 号或视频链接（也接受现成 CSV 路径，那样跳过采集）
        outdir      输出根目录（每一步在下面建自己的子目录）
        name        可选，包名
        roots_only  只抓主楼（默认 True：快 3 倍）
        low_max / low_min_len  预处理阈值
    """
    import time as _t

    arg = (p.get("arg") or "").strip()
    if not arg:
        raise ValueError("请填视频链接、BV 号，或一份现成的 CSV 路径")

    # 公开模式只能写沙箱，绝不能直接采信用户给的目录（否则可越出沙箱）。
    if _PUBLIC:
        base = _SANDBOX
        base.mkdir(parents=True, exist_ok=True)
    else:
        base = safe_path(core.outdir_or_default(p.get("outdir")),
                         allow_missing_parent=True)
        base.mkdir(parents=True, exist_ok=True)

    stamp = _t.strftime("%Y%m%d-%H%M%S")
    name = (p.get("name") or "").strip() or f"distill-{stamp}"
    low_max = int(p.get("low_max") or 8)
    low_min_len = int(p.get("low_min_len") or 120)
    roots_only = bool(p.get("roots_only", True))
    stop = p.get("_should_stop")

    steps = []
    csv_path = None

    # ① 采集（输入已是 CSV 就跳过——很多人手头本来就有语料）
    looks_csv = arg.lower().endswith(".csv")
    if looks_csv:
        cand = (Path(_SANDBOX, Path(arg).name) if _PUBLIC
                else safe_path(arg, must_exist=True))
        if not cand.exists():
            raise FileNotFoundError(f"找不到 CSV：{cand}")
        csv_path = cand
        log(f"① 跳过采集：直接使用现成语料 {csv_path.name}")
        steps.append(("采集", "跳过（用现成 CSV）"))
    else:
        log("① 采集：开始抓评论…")
        if _PUBLIC:
            out_csv = base / f"comments-{stamp}.csv"
        else:
            out_csv = _as_file_target(base / f"comments-{stamp}.csv", "输出 CSV")
        out_csv.parent.mkdir(parents=True, exist_ok=True)

        last = [0]

        def on_progress(done, total, subs=0):
            step = max(50, int(total / 20) if total else 50)
            if total and (done - last[0] >= step or done >= total):
                last[0] = done
                tail = f"，楼中楼 {_fmt(subs)} 条" if subs else ""
                log(f"   进度 {_fmt(done)}/{_fmt(total)} 条主楼{tail}")

        res = core.crawl_comments(arg, str(out_csv), roots_only=roots_only,
                                  on_log=log, on_progress=on_progress,
                                  should_stop=stop)
        csv_path = out_csv
        steps.append(("采集", f"{_fmt(res.get('n_total', 0))} 条"
                             + ("（中途停止）" if res.get("stopped") else "")))
        if res.get("stopped"):
            log("   采集中途被停止：用已抓到的部分继续，结论覆盖度会打折")

    if stop and stop():
        log("已停止：采集中断，后续步骤不再执行。")
        # 停止也要交出已抓到的 CSV：不然用户抓了几百条，界面上却无处可取。
        keep = str(csv_path) if Path(csv_path).exists() else ""
        if keep:
            log(f"   已保留：{keep}")
        return {"steps": steps, "aborted": True, "pack_dir": "",
                "files": [keep] if keep else [], "partial_csv": keep}, base

    # ② 预处理
    log("② 预处理：去重、去噪、按权重排序…")
    prep_dir = base / f"prep-{stamp}"
    prep_dir.mkdir(parents=True, exist_ok=True)
    stats, paths = core.prepare(str(csv_path), str(prep_dir), low_max, low_min_len)
    n_after = stats.get("total_after_denoise", 0)
    log(f"   去噪后 {_fmt(n_after)} 条"
        f"（一级 {_fmt(stats.get('n_top_level', 0))} / 楼中楼 {_fmt(stats.get('n_reply', 0))}）")
    steps.append(("预处理", f"去噪后 {_fmt(n_after)} 条"))

    if stop and stop():
        log("已停止：预处理完成，不再打包。")
        return {"steps": steps, "aborted": True, "pack_dir": "",
                "prep_dir": str(prep_dir)}, base

    # ③ 蒸馏包
    log("③ 打包：语料 + 方法论 + 提示词…")
    pack = core.export_package(str(csv_path), str(base), name, low_max, low_min_len,
                               on_log=log,
                               with_glossary=bool(p.get("with_glossary")))
    steps.append(("蒸馏包", f"{len(pack.get('files', []))} 个文件"))
    log(f"   包目录：{pack['pack_dir']}")

    out = {
        "steps": steps,
        "aborted": False,
        "pack_dir": pack.get("pack_dir", ""),
        "prep_dir": str(prep_dir),
        "csv": str(csv_path),
        "n_after": n_after,
        "files": pack.get("files", []),
        "name": name,
        "mode": "pack-only",
    }

    # ④⑤ 交给 core.finish_after_pack —— "一键"的语义只在那里定义一次，
    #     Web 与 GUI 共用，避免两边各写一套导致"同一操作、两种结局"。
    fin = core.finish_after_pack(pack["pack_dir"], on_log=log, should_stop=stop)
    out.update({k: fin.get(k) for k in
                ("mode", "ai", "ai_error", "distill", "report", "stale_report")
                if k in fin})
    return out, Path(pack["pack_dir"])


def _stale_report(pack_dir):
    """保留旧名以兼容既有调用；实现只有一处（core）。"""
    return core._stale_report(pack_dir)


def _do_distill(p, log):
    """对已生成的蒸馏包补跑 AI 蒸馏（不重跑采集/预处理）。"""
    if _PUBLIC:
        pack_dir = _pub_in(p.get("pack_dir"), "")
    else:
        pack_dir = safe_path(p.get("pack_dir"), must_exist=True)
    if not pack_dir or not Path(pack_dir).is_dir():
        raise ValueError("请填蒸馏包目录（含 corpus_ccf.csv 的那一层）")
    res = core.distill_package(str(pack_dir), on_log=log,
                               should_stop=p.get("_should_stop"))
    return res, Path(res["guide_path"])


# 一个页签可能挂多个动作（「③ 蒸馏包」页里还有"只跑 AI 蒸馏"）；
# 「AI 设置」是纯设置页，不对应任何后端动作。这两条例外集中声明，
# 由 tests/test_webui.py 的 test_page_panels_match_backend_actions 守住。
UI_PANE_OF = {"distill": "pack"}
UI_SETTINGS_PANES = {"ai"}

_ACTIONS = {"crawl": _do_crawl, "prep": _do_prep, "pack": _do_pack,
            "verify": _do_verify, "emit": _do_emit, "auto": _do_auto,
            "distill": _do_distill}


def _llm_probe():
    """发一条最小请求验证连通性。返回里**绝不含 Key 明文**。"""
    from app import llm as llm_mod
    cfg = llm_mod.load_config(core.app_root())
    if not cfg.get("configured"):
        return {"ok": False, "error": llm_mod.describe(cfg),
                "status": core.llm_status()}
    t0 = time.time()
    try:
        txt = llm_mod.chat(
            [{"role": "user", "content": "只回复两个字：可用"}], cfg, retries=0)
        return {"ok": True, "elapsed": round(time.time() - t0, 1),
                "reply": llm_mod.redact(txt)[:80],
                "status": core.llm_status()}
    except Exception as e:
        return {"ok": False, "error": llm_mod.redact(e)[:400],
                "status": core.llm_status()}

def _worker(jid, action, params):
    def log(m):
        _log(jid, str(m))

    # 把「本作业是否被要求停止」注入参数，执行体在可中断点自查。
    # 采集一步动辄几分钟，没有这个就只能等它自己跑完。
    params = dict(params or {})
    params["_should_stop"] = (lambda: _should_stop(jid))

    try:
        fn = _ACTIONS.get(action)
        if not fn:
            raise ValueError(f"未知动作：{action}")
        raw, where = fn(params, log)
        if _should_stop(jid):
            log("已停止：以下为已抓取到的部分，不是完整结果。")
        _finish(jid, _shape(action, raw, where, log))
    except FileNotFoundError as e:
        log(f"✗ {e}")
        _finish(jid, None, f"找不到文件：{e}")
    except OutsideRoot as e:
        log(f"✗ {e}")
        _finish(jid, None, str(e))
    except Exception as e:
        log(f"✗ {type(e).__name__}: {e}")
        _finish(jid, None, f"{type(e).__name__}: {e}")


# ────────────────────────────── 结果整形（后端只给事实，不给情绪） ──────────────────────────────

def _fmt(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _shape(action, raw, where, log):
    if action == "crawl":
        stopped = bool(raw.get("stopped"))
        return {
            "cls": "warn" if stopped else "ok",
            "head": (f"⏹ 已停止，留下 {_fmt(raw.get('n_total', 0))} 条" if stopped
                     else f"✓ 抓到 {_fmt(raw.get('n_total', 0))} 条"),
            "kv": {"视频": raw.get("bv", ""),
                   "主楼 / 楼中楼": f"{_fmt(raw.get('n_top', 0))} / {_fmt(raw.get('n_sub', 0))}",
                   "合计": _fmt(raw.get("n_total", 0)) + ("（中途停止，不是完整语料）" if stopped else ""),
                   "输出": raw.get("out_csv", "")},
            "files": _files_of([raw.get("out_csv", "")]),
            "next": ("这次是半截语料，可以直接往下跑 ②，但结论覆盖度会打折；"
                     "要全量就重跑一次并等它跑完。" if stopped else ""),
        }

    if action == "prep":
        s = raw[0]
        dup = s.get("dup_dropped", 0) or 0
        tot = s.get("total_raw", 0) or 0
        warn = "　⚠️ 占比偏高，抓取端分页重叠过，规模数字以去噪后为准" if tot and dup / max(tot, 1) > 0.1 else ""
        return {
            "cls": "warn" if warn else "ok",
            "head": f"✓ 去噪后 {_fmt(s.get('total_after_denoise', 0))} 条",
            "kv": {"原始行数": _fmt(tot),
                   "去重丢弃": _fmt(dup) + warn,
                   "去噪后条数": _fmt(s.get("total_after_denoise", 0)) +
                                f"（一级 {_fmt(s.get('n_top_level', 0))} / 楼中楼 {_fmt(s.get('n_reply', 0))}）",
                   "点赞总数": f"{_fmt(s.get('score_sum', 0))}（均值 {s.get('score_mean', 0)}，最高 {_fmt(s.get('score_max', 0))}）",
                   "低权重长文": _fmt(s.get("n_low_score_long", 0)),
                   "去重作者数": f"{_fmt(s.get('authors_unique', 0))}（发过多条 {_fmt(s.get('authors_multi', 0))}）",
                   "输出目录": str(where)},
            "files": _files_of(list(raw[1].values()) if isinstance(raw[1], dict) else []),
            "next": "下一步：③ 导出蒸馏包（把语料 + 方法论打包给 AI）",
        }

    if action == "pack":
        st = raw.get("stats", {})
        miss = [x for x in ("SKILL.md",) if x not in (raw.get("methodology") or [])]
        return {
            "cls": "warn" if miss else "ok",
            "head": f"✓ 蒸馏包已导出（{len(raw.get('files', []))} 个文件）" + ("　⚠️ 缺方法论" if miss else ""),
            "kv": {"包目录": raw.get("pack_dir", ""),
                   "文件数": str(len(raw.get("files", []))),
                   "去噪后条数": _fmt(st.get("total_after_denoise", 0)),
                   "低权重长文": _fmt(st.get("n_low_score_long", 0)),
                   "随包方法论": "、".join(raw.get("methodology") or []) or "（无）"},
            "files": _files_of([str(where / f) for f in raw.get("files", [])]),
            "next": ("已配 AI：在本页填包目录点「只跑 AI 蒸馏」即可直接出指南；"
                     "或把包目录拖进任意 AI。拿到指南后回到 ④ 机验 → ⑤ 出报告"
                     if core.llm_status().get("configured") else
                     "把整个包目录拖进任意 AI → 拿到 Markdown 指南 → 回到 ④ 机验 → ⑤ 出报告。"
                     "想全自动：先去「🤖 AI 设置」填 endpoint / Key / 模型名。"),
        }

    if action == "verify":
        bad = list(raw.get("bad") or [])
        nums = list(raw.get("num_issues") or [])
        if bad or nums:
            parts = []
            if bad:
                parts.append(f"{len(bad)} 条幻觉引用")
            if nums:
                parts.append(f"{len(nums)} 处数字矛盾")
            return {
                "cls": "err",
                "head": "✗ " + "、".join(parts) + "，不得交付",
                "verdict": "❌ " + "；".join(parts) + "——按质量门不得交付。",
                "bad": bad, "num_issues": nums,
                "kv": {**{k: v for k, v in {
                    "引用条数": _fmt(len(raw.get("cited") or [])),
                    "语料 ID 数": _fmt(len(raw.get("real") or [])),
                    "幻觉引用": _fmt(len(bad)),
                    "数字矛盾": _fmt(len(nums)),
                    "可复算表述": _fmt(raw.get("num_checked", 0)),
                }.items()}},
            }
        return {
            "cls": "ok",
            "head": "✓ 差集为空，可交付",
            "verdict": (f"❌ 检出 <b>{len(bad)}</b> 条幻觉引用——按质量门不得交付。"
                        if bad else
                        f"✅ 引用 {_fmt(len(raw.get('cited') or []))} 条，"
                        f"全部命中语料 {_fmt(len(raw.get('real') or []))} 个 ID，<b>差集为空</b>。"),
            "bad": bad,
            "kv": {"引用条数": _fmt(len(raw.get("cited") or [])),
                   "语料 ID 数": _fmt(len(raw.get("real") or [])),
                   "幻觉引用": _fmt(len(bad)),
                   "数字复算": f"{_fmt(raw.get('num_checked', 0))} 处，矛盾 0",
                   "语料明细": "；".join(
                       f"{Path(c['path']).name}（{_fmt(c['n'])} ids，列 {c['col']}）"
                       for c in (raw.get("per_corpus") or []))},
        }

    if action == "emit":
        v = raw.get("verify") or {}
        bad = list(v.get("bad") or [])
        if not v.get("ran"):
            verdict = "⚠️ 未跑机验（没填语料），信任条缺失——建议补上语料重跑"
            cls = "warn"
        elif bad:
            verdict = f"❌ 机验差集非空（{len(bad)} 条幻觉）——报告已生成但<b>不得交付</b>"
            cls = "err"
        else:
            verdict = (f"✅ 机验通过：引用 {_fmt(v.get('cited', 0))} 条 / 语料 "
                       f"{_fmt(v.get('real', 0))} ids / <b>幻觉 0</b>")
            cls = "ok"
        return {
            "cls": cls, "head": "✓ 报告已生成" + ("　⚠️ 见下方" if cls != "ok" else ""),
            "verdict": verdict,
            "out": raw.get("out", ""),
            "kv": {"输出文件": raw.get("out", ""),
                   "体积": f"{_fmt(raw.get('bytes', 0))} 字节",
                   "标题": raw.get("title", ""),
                   "章节数": _fmt(len(raw.get("headings") or [])),
                   "引用条目": _fmt(len(raw.get("cites") or [])),
                   "机验": (f"引用 {_fmt(v.get('cited', 0))} / 语料 {_fmt(v.get('real', 0))} / 幻觉 {_fmt(len(bad))}"
                            if v.get("ran") else "未跑（无语料）")},
            # 少了这一行，界面只剩一串路径文字、点不开也下不了——
            # 报告明明生成了，用户却以为没出结果。
            "files": _files_of([raw.get("out", "")]),
        }

    if action == "auto":
        st = raw.get("steps") or []
        aborted = bool(raw.get("aborted"))
        done_txt = "　".join(f"{k}：{v}" for k, v in st)
        kv = {"包名": raw.get("name", ""),
              "包目录": raw.get("pack_dir", ""),
              "去噪后条数": _fmt(raw.get("n_after", 0)),
              "三步": done_txt}
        if raw.get("pack_dir"):
            files = _files_of([str(Path(raw["pack_dir"]) / f)
                               for f in (raw.get("files") or [])])
        else:
            # 未完成时没有包，但可能有已抓到的 CSV —— 要能把链接给出去
            files = _files_of(raw.get("files") or [])
        if aborted:
            kept = raw.get("partial_csv") or raw.get("prep_dir") or ""
            kv["已保留"] = kept
            return {"cls": "warn", "head": "⏹ 已停止（未走完三步）",
                    "kv": kv, "files": files,
                    "next": ("上面是已经拿到的部分，可以直接接着跑 ②；"
                              "要完整包就重跑一次并等它跑完。" if kept else
                              "要完整包就重跑一次并等它跑完。")}
        mode = raw.get("mode", "pack-only")
        d = raw.get("distill") or {}
        rep = (raw.get("report") or {}).get("out", "")
        if rep:
            kv["报告"] = rep
            files = _files_of([rep]) + files
        if d.get("guide_path"):
            files = _files_of([d["guide_path"]]) + files
            kv["指南"] = d["guide_path"]
            kv["引用 / 幻觉"] = f"{d.get('cited', 0)} / {len(d.get('bad') or [])}"

        if mode == "full":
            return {"cls": "ok", "head": "🎉 一键到底：报告已生成并通过机验",
                    "kv": kv, "files": files,
                    "verdict": (f"✅ 引用 {_fmt(d.get('cited', 0))} 条，差集为空。"
                                f"修复轮 {d.get('rounds', 0)} 轮，耗时 {d.get('elapsed', 0)}s。"
                                "直接打开上面的 report.html 就能交付。"),
                    "mode": mode,
                    "next": "想换个模型再跑一遍？改「🤖 AI 设置」里的模型名后重跑即可。"}

        if mode == "guide-unverified":
            return {"cls": "warn", "head": "⚠️ 指南生成了，但机验没过，未出报告",
                    "kv": kv, "files": files, "bad": list(d.get("bad") or []),
                    "verdict": (f"❌ 残留 {len(d.get('bad') or [])} 条幻觉引用。"
                                "按质量门，差集非空的指南不能当交付物。"),
                    "mode": mode,
                    "next": ("打开 guide.md，把报错列出的 ID 换成语料里真实存在的条目；"
                             "或再重跑一次让 AI 修一轮。")}

        extra = ""
        if raw.get("ai_error"):
            extra = "　⚠️ AI 蒸馏失败，已退回只出包"
        return {
            "cls": "warn" if raw.get("ai_error") else "ok",
            "head": "✓ 蒸馏包已就绪" + extra,
            "kv": kv, "files": files,
            "mode": mode,
            "verdict": ("AI 调用失败：" + str(raw.get("ai_error"))[:400]
                        if raw.get("ai_error") else ""),
            "next": ("没配置 AI，所以只出到蒸馏包。把上面这个包目录拖进任意 AI"
                     "（或把 PROMPT.md 粘进对话框 + 附上 all_comments.txt），"
                     "它就会按 SKILL.md 写出带引用的指南；拿到指南后再回到 ④ 卡一道引用。"
                     "想全自动：去「🤖 AI 设置」填 endpoint / Key / 模型名后重跑。"),
        }

    if action == "distill":
        bad = list(raw.get("bad") or [])
        passed = raw.get("passed")
        cls = "ok" if passed else ("err" if passed is False else "warn")
        if passed:
            head = f"✓ 指南已生成并通过机验（{raw.get('cited', 0)} 条引用）"
            verdict = (f"✅ 引用 {_fmt(raw.get('cited', 0))} 条全部命中语料，差集为空。"
                       f"修复轮 {raw.get('rounds', 0)} 轮，耗时 {raw.get('elapsed', 0)}s。")
        elif passed is False:
            head = "⚠️ 指南已生成，但机验未通过"
            verdict = (f"❌ 仍有 <b>{len(bad)}</b> 条幻觉引用。这份 markdown 可以看，"
                       f"但<b>不算已验证交付</b>——按质量门不得对外发布。")
        else:
            head = "✓ 指南已生成（未跑机验）"
            verdict = "未注入机验函数，无法判断引用真伪。"
        return {
            "cls": cls, "head": head, "verdict": verdict, "bad": bad,
            "kv": {"指南文件": raw.get("guide_path", ""),
                   "引用条数": _fmt(raw.get("cited", 0)),
                   "幻觉引用": _fmt(len(bad)),
                   "修复轮数": str(raw.get("rounds", 0)),
                   "耗时": f"{raw.get('elapsed', 0)} 秒"},
            "files": _files_of([raw.get("guide_path", "")]),
            "next": ("下一步：⑤ 出 HTML 报告（用这份 guide.md + 包内 corpus_ccf.csv）。"
                     if passed else
                     "建议手动把幻觉 ID 换成真实条目后重跑机验；或再让 AI 修一轮。"),
        }

    if action == "full":
        st = raw.get("steps") or []
        mode = raw.get("mode", "")
        kv = {"包名": raw.get("name", ""),
              "包目录": raw.get("pack_dir", ""),
              "去噪后条数": _fmt(raw.get("n_after", 0)),
              "各步": "　".join(f"{k}：{v}" for k, v in st)}
        pack_dir = raw.get("pack_dir") or ""
        files = _files_of([str(Path(pack_dir) / f)
                           for f in (raw.get("files") or [])]) if pack_dir else []
        d = raw.get("distill") or {}
        if d.get("guide_path"):
            files += _files_of([d["guide_path"]])
        if (raw.get("report") or {}).get("out"):
            files += _files_of([raw["report"]["out"]])
            kv["报告"] = raw["report"]["out"]

        if mode == "full":
            return {"cls": "ok", "head": "🎉 一键到底：报告已生成并通过机验",
                    "kv": kv, "files": files,
                    "verdict": (f"✅ 引用 {_fmt(d.get('cited', 0))} 条，差集为空。"
                                f"直接打开上面的 report.html 就能交付。"),
                    "next": "想换个模型再跑一遍？改「AI 设置」里的模型名后重跑即可。"}
        if mode == "guide-unverified":
            return {"cls": "warn", "head": "⚠️ 指南生成了，但机验没过，未出报告",
                    "kv": kv, "files": files,
                    "verdict": (f"❌ 残留 {len(d.get('bad') or [])} 条幻觉引用。"
                                "按质量门，差集非空的指南不能当交付物。"),
                    "next": ("打开 guide.md，把报错列出的 ID 换成语料里真实存在的条目；"
                             "或重跑一次让 AI 再修一轮。")}
        # pack-only
        extra = ("　⚠️ AI 蒸馏失败，已退回只出包" if raw.get("ai_error") else "")
        out = {"cls": "warn" if raw.get("ai_error") else "ok",
               "head": "✓ 蒸馏包已就绪" + extra,
               "kv": kv, "files": files,
               "next": ("没配置 AI，所以只出到蒸馏包。把包目录拖进任意 AI 即可拿到指南；"
                        "想全自动出报告，去「AI 设置」填 endpoint / Key / 模型名后重跑。")}
        if raw.get("ai_error"):
            out["verdict"] = "AI 调用失败：" + str(raw["ai_error"])[:400]
        return out

    return {"cls": "ok", "head": "✓ 完成", "kv": {}}


# ────────────────────────────── HTTP ──────────────────────────────

_MIME = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8", ".csv": "text/csv; charset=utf-8",
    ".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "comment-distillery/1.0"

    # ── 基础 ──
    def log_message(self, fmt, *args):
        # 默认会把每条请求打到 stderr，本地工具没必要吵
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8",
              extra=None, method=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if method != "HEAD" and body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _err(self, code, msg):
        self._json({"error": msg}, code)

    def _local_only(self):
        """Host / Origin 校验——本地服务也要挡 DNS-rebinding。"""
        host = (self.headers.get("Host") or "").strip()
        h = host.rsplit(":", 1)[0].strip("[]").lower()
        if h not in _LOCAL_HOSTS:
            self._err(403, f"拒绝非本机访问：{host}")
            return False
        origin = self.headers.get("Origin")
        if origin:
            try:
                oh = urllib.parse.urlsplit(origin).hostname or ""
            except Exception:
                oh = ""
            if oh.lower() not in _LOCAL_HOSTS:
                self._err(403, "跨站请求被拒绝")
                return False
        return True

    def _request_token(self):
        """从 Authorization: Bearer / X-Access-Token / ?token= 取公开模式令牌。"""
        auth = self.headers.get("Authorization") or ""
        if auth[:7].lower() == "bearer ":
            return auth[7:].strip()
        t = self.headers.get("X-Access-Token")
        if t:
            return t
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        return (q.get("token") or [""])[0]

    def _gate(self):
        """三种模式统一入口：
        本地模式 -> 本机 Host/Origin 校验；公开模式 -> 令牌；局域网模式 -> 私网 Host + 令牌。"""
        if _PUBLIC:
            if _DEMO:
                return True
            return self._token_gate("公开模式需要访问令牌")
        if _LAN:
            return self._lan_only()
        return self._local_only()

    def _token_gate(self, msg):
        tok = self._request_token()
        if tok != _ACCESS_TOKEN:
            self._err(401, msg)
            return False
        return True

    def _lan_only(self):
        """局域网模式：Host/Origin 必须落私网/回环，且必须带正确令牌。"""
        host = (self.headers.get("Host") or "").strip()
        h = host.rsplit(":", 1)[0].strip("[]").lower()
        if not _host_allowed(h):
            self._err(403, f"拒绝非私网访问：{host}（局域网模式只接受私网/回环地址）")
            return False
        tok = self._request_token()
        if tok != _ACCESS_TOKEN:
            self._err(401, "局域网模式需要访问令牌")
            return False
        origin = self.headers.get("Origin")
        if origin:
            try:
                oh = urllib.parse.urlsplit(origin).hostname or ""
            except Exception:
                oh = ""
            if not _host_allowed(oh.lower()):
                self._err(403, "跨站请求被拒绝")
                return False
        return True

    # ── 路由 ──
    def do_GET(self):
        if not self._gate():
            return
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path

        if path in ("/", "/index.html"):
            # connect-src 'self' 不能少：页面上的按钮全靠 fetch 调 /api/*。
            # default-src 'none' 会连 fetch 一起掐断（CSP 的 default-src 兜底
            # 包含 connect-src），结果就是界面画得好好的、点任何按钮都毫无反应，
            # 控制台只留一行 blocked——这是最像「程序坏了」的坏法。
            self._send(200, PAGE_HTML, "text/html; charset=utf-8",
                       {"Content-Security-Policy":
                        "default-src 'none'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; img-src data:; "
                        "connect-src 'self' http://127.0.0.1:* http://localhost:*"})
            return

        if path == "/api/hello":
            ok, msgs = core.selfcheck()
            root = core.resource_root()
            sample_corpus = root / "examples" / "sample_corpus.csv"
            sample_guide = root / "examples" / "sample_guide.md"
            self._json({
                "ok": True, "version": core.APP_VERSION,
                "mode": ("public" if _PUBLIC else ("lan" if _LAN else "local")),
                "outdir": (str(_SANDBOX) if _PUBLIC else str(core.default_outdir())),
                "roots": [str(r) for r in allowed_roots()],
                "selfcheck": {"ok": ok, "msgs": [list(m) for m in msgs]},
                "sample_corpus": str(sample_corpus) if sample_corpus.exists() else "",
                "sample_guide": str(sample_guide) if sample_guide.exists() else "",
            })
            return

        if path == "/api/fs":
            self._api_fs(q)
            return

        if path == "/api/llm":
            st = core.llm_status()
            if _PUBLIC:
                st = dict(st, configured=False,
                          describe="公开模式不读取本机 AI 配置")
            # 用量摘要（可观测，非计费）：随配置一起返回，AI 设置页展示。
            try:
                from app import llm as _llm_mod
                st["usage"] = _llm_mod.usage_summary()
            except Exception:
                st["usage"] = {}
            self._json(st)
            return

        if path == "/api/job":
            jid = (q.get("id") or [""])[0]
            j = _job(jid)
            if not j:
                return self._err(404, "作业不存在")
            return self._json(j)

        if path == "/preview":
            self._serve_file((q.get("path") or [""])[0], inline=True)
            return

        if path == "/download":
            self._serve_file((q.get("path") or [""])[0], inline=False)
            return

        self._err(404, "未找到：" + path)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if not self._gate():
            return
        u = urllib.parse.urlsplit(self.path)
        if u.path not in ("/api/start", "/api/cancel",
                          "/api/llm", "/api/llm/test"):
            return self._err(404, "未找到：" + u.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as e:
            return self._err(400, f"请求体解析失败：{e}")

        if u.path == "/api/cancel":
            jid = body.get("job") or ""
            ok = _cancel(jid)
            return self._json({"ok": ok, "job": jid})

        if u.path == "/api/llm":
            # 只写配置，不触网：避免"填完就要等一个超时才知道 Key 错了"。
            # 想验证连通性请调 /api/llm/test。
            if _PUBLIC:
                return self._err(403, "公开模式不允许在本机写 AI 配置")
            try:
                r = core.save_llm_config(
                    body.get("base_url", ""),
                    body.get("api_key", ""),
                    body.get("model", ""),
                    body.get("timeout") or 600,
                    body.get("max_corpus_chars") or 120000)
                return self._json({"ok": True, **r})
            except Exception as e:
                return self._err(500, f"保存失败：{e}")

        if u.path == "/api/llm/test":
            if _PUBLIC:
                return self._err(403, "公开模式不允许测试本机凭证")
            try:
                return self._json(_llm_probe())
            except Exception as e:
                return self._json({"ok": False, "error": str(e)[:400]})

        action = body.get("action")
        if action not in _ACTIONS:
            return self._err(400, f"未知动作：{action}")
        try:
            jid = start_job(action, body.get("params") or {})
        except Exception as e:
            return self._err(500, f"启动失败：{e}")
        self._json({"ok": True, "job": jid})

    # ── 具体实现 ──
    def _api_fs(self, q):
        if _PUBLIC:
            return self._err(403, "公开模式不提供文件选择器")
        raw = (q.get("path") or [""])[0]
        try:
            d = safe_path(raw) if raw else Path.home().resolve()
        except OutsideRoot as e:
            return self._err(403, str(e))
        if d.is_file():
            d = d.parent
        if not d.is_dir():
            return self._err(404, f"不是目录：{d}")
        dirs, fils = [], []
        try:
            for e in sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    if e.is_dir():
                        dirs.append({"name": e.name, "path": str(e),
                                     "is_dir": True, "size": None})
                    else:
                        fils.append({"name": e.name, "path": str(e),
                                     "is_dir": False, "size": e.stat().st_size})
                except OSError:
                    continue
        except PermissionError:
            return self._err(403, f"没有权限读取：{d}")
        parent = d.parent if d.parent != d else None
        self._json({"path": str(d), "parent": str(parent) if parent else "",
                    "entries": dirs + fils})

    def _serve_file(self, raw, inline):
        try:
            p = safe_path(raw, must_exist=True)
        except OutsideRoot as e:
            return self._err(403, str(e))
        except FileNotFoundError as e:
            return self._err(404, str(e))
        if not p.is_file():
            return self._err(404, f"不是文件：{p}")
        ctype = _MIME.get(p.suffix.lower(),
                          mimetypes.guess_type(p.name)[0] or "application/octet-stream")
        if isinstance(ctype, str) and "charset" not in ctype.lower() and ctype.startswith("text"):
            ctype += "; charset=utf-8"
        extra = {}
        if inline:
            # 报告是渲染产物：给它 CSP + 禁脚本的 sandbox，不当可信页面执行
            extra["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:")
            extra["Content-Disposition"] = "inline"
            extra["X-Frame-Options"] = "SAMEORIGIN"
            if p.suffix.lower() in (".html", ".htm"):
                extra["Content-Security-Policy"] += "; sandbox allow-same-origin"
        else:
            fn = urllib.parse.quote(p.name)
            extra["Content-Disposition"] = f"attachment; filename*=UTF-8''{fn}"
        try:
            data = p.read_bytes()
        except OSError as e:
            return self._err(500, f"读取失败：{e}")
        self._send(200, data, ctype, extra)


def build_server(host="127.0.0.1", port=DEFAULT_PORT):
    """建服务器（不 serve_forever）。port=0 由系统分配，便于测试。

    Windows 上一定要关掉 allow_reuse_address：SO_REUSEADDR 在 Windows 的语义
    是「允许别的进程再绑同一个端口」，于是第二个实例能悄无声息地跟旧实例
    共用 8756 —— 用户以为重启了新版本，浏览器连到的还是旧进程（改完不生效），
    两个实例还各自持有一份作业表。Linux/macOS 上该选项无此副作用，保留即可。
    """
    srv_cls = ThreadingHTTPServer
    if os.name == "nt":
        class _NoReuseServer(ThreadingHTTPServer):
            allow_reuse_address = False
        srv_cls = _NoReuseServer
    return srv_cls((host, port), Handler)


def serve(port=DEFAULT_PORT, open_browser=True, host="127.0.0.1", quiet=False):
    """起服务。返回 (server, url)。调用方负责 shutdown()。"""
    srv = None
    if port:
        try:
            srv = build_server(host, port)
        except OSError:
            srv = None
            if not quiet:
                print(f"端口 {port} 已被占用（可能有另一个实例在跑），改用系统分配的空闲端口。")
    if srv is None:
        srv = build_server(host, 0)          # 端口被占就交给系统分配
    real = srv.server_address[1]
    url = f"http://127.0.0.1:{real}/"
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    if not quiet:
        print("comment-distillery 本地界面已启动：" + url)
        print("（只监听 127.0.0.1，不联网、不上传数据。Ctrl+C 结束）")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return srv, url


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        prog="python -m app.webui",
        description="启动本地 Web 界面（纯标准库，跨平台，免打包）")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("PORT") or DEFAULT_PORT),
                    help=f"端口（默认 {DEFAULT_PORT}；也读 PORT 环境变量，便于托管平台注入）")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--allow-root", action="append", default=[], metavar="DIR",
                    help="追加一个允许访问的根目录（可重复）")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（默认 127.0.0.1；公开模式会自动改 0.0.0.0）")
    ap.add_argument("--public", action="store_true",
                    help="公开托管模式：绑定 0.0.0.0 + 令牌鉴权（替代本机校验），文件限制在沙箱")
    ap.add_argument("--demo", action="store_true",
                    help="公开演示模式：等价 --public 但不校验令牌（托管平台会注入 Authorization 头，"
                         "空令牌的开放访问会被误拦）；沙箱与路径白名单仍生效")
    ap.add_argument("--lan", action="store_true",
                    help="局域网模式：绑定 0.0.0.0 + 令牌鉴权 + 私网 Host 白名单，保留文件选择器（功能全开）")
    ap.add_argument("--token", default="",
                    help="公开/局域网模式访问令牌（建议长随机串；必须配合 --public 或 --lan）")
    ap.add_argument("--public-dir", default="",
                    help="公开模式文件系统沙箱目录（默认 <cwd>/out/public）")
    args = ap.parse_args(argv)

    if args.demo:
        args.public = True
        args.token = ""

    for r in args.allow_root:
        add_root(r)

    if args.public and args.lan:
        print("⚠️ --public 与 --lan 互斥，同时给出时按公开模式处理（沙箱 + 禁用文件选择器）")
    if args.public:
        if not args.token:
            print("⚠️ 公开模式未设 --token：任何能访问该端口的人都能直接使用"
                  "（演示用；正式部署请设令牌）")
        set_public(args.token, args.public_dir or None, demo=args.demo)
        args.host = "0.0.0.0"
        # 公开 demo：把示例语料复制进沙箱。否则 /api/hello 给出的样例路径在沙箱外，
        # 前端点「用示例」时 /api/start 按沙箱内的 basename 查找会 404。
        try:
            import shutil

            _ex = core.resource_root() / "examples"
            if _ex.is_dir() and _SANDBOX is not None:
                for _n in ("sample_corpus.csv", "sample_guide.md"):
                    _src = _ex / _n
                    if _src.is_file():
                        shutil.copy2(_src, _SANDBOX / _n)
        except Exception as _e:  # noqa: BLE001 - 示例缺失不应阻断启动
            print(f"⚠️ 公开模式复制示例语料失败（不影响启动）：{_e}")
    elif args.lan:
        if not args.token:
            print("⚠️ 局域网模式必须提供 --token，否则同网段任何人都能直接用本服务")
        set_lan(args.token)
        args.host = "0.0.0.0"

    # 控制台编码先兜底：Windows 默认 GBK 下 print('✓') 会直接抛
    # UnicodeEncodeError 把整个启动打死（exe 无控制台时甚至看不到原因）。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ok, msgs = core.selfcheck()
    for good, m in msgs:
        print(("  ✓ " if good else "  ✗ ") + m)
    if not ok:
        print("\n自检未通过：缺少随包资源，界面里对应功能会失败。")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        if _PUBLIC:
            print(f"\n🔓 公开模式：监听 {args.host}，能访问该端口者凭 --token 即可使用（文件限制在沙箱）。")
        elif _LAN:
            print(f"\n🌐 局域网模式：监听 {args.host}，同网段设备凭 --token 即可访问（保留文件选择器，功能全开）。")
        else:
            print(f"\n⚠️ 监听 {args.host} 会把本服务暴露到网络，且 Host 校验将拒绝外部请求。")

    srv, url = serve(args.port, open_browser=not args.no_browser, host=args.host)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
