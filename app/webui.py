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
    · 只监听 127.0.0.1
    · Host / Origin 校验（挡 DNS-rebinding 与跨站表单）
    · 路径白名单 + resolve（挡路径穿越与整个磁盘可读）
    · 预览页 CSP + sandbox（报告是渲染产物，不当可信脚本执行）

用法：
    python -m app.webui [--port 8756] [--no-browser] [--allow-root DIR]
"""

import json
import mimetypes
import os
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

# ── 公开托管模式 ──────────────────────────────────────────────────────
# 默认关闭。开启后：绑定 0.0.0.0 + 令牌鉴权（替代本机 Host/Origin 校验）+
# 文件系统收进单一沙箱（并禁用文件选择器），使本工具可被部署成"粘贴链接就能用"的
# 在线平台——对标的就是 vreport.tri4t.xyz 那种"填链接一键"形态。
# 关键：蒸馏（LLM）那一步仍不内置——公开模式同样 BYO-AI，不破「不内置 LLM」铁律。
_PUBLIC = False
_ACCESS_TOKEN = ""
_SANDBOX = None


def set_public(token, sandbox):
    """进入公开托管模式。sandbox 为空则取 <cwd>/out/public。"""
    global _PUBLIC, _ACCESS_TOKEN, _SANDBOX
    _PUBLIC = True
    _ACCESS_TOKEN = token or ""
    _SANDBOX = (Path(sandbox).resolve() if sandbox
                else (Path.cwd() / "out" / "public").resolve())
    _SANDBOX.mkdir(parents=True, exist_ok=True)

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
    for p in (Path.home(), Path.cwd(), Path(tempfile.gettempdir()),
              core.resource_root()):
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
                      "log": [], "result": None, "error": None}
    return jid


def _job(jid):
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if not j:
            return None
        return {"id": j["id"], "done": j["done"], "status": j["status"],
                "log": list(j["log"]), "result": j["result"], "error": j["error"]}


def _log(jid, msg):
    ts = time.strftime("%H:%M:%S")
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if j is not None:
            j["log"].append(f"[{ts}] {msg}")


def _finish(jid, result=None, error=None):
    with _JOB_LOCK:
        j = _JOBS.get(jid)
        if j is not None:
            j["done"] = True
            j["status"] = "error" if error else "ok"
            j["result"] = result
            j["error"] = error


def start_job(action, params):
    """起一个后台作业，立即返回 job id。"""
    jid = _new_job()
    t = threading.Thread(target=_worker, args=(jid, action, params), daemon=True)
    t.start()
    return jid


# ────────────────────────────── 各动作的真正执行体 ──────────────────────────────

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
        out_p = safe_path(out, allow_missing_parent=True)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    roots_only = bool(p.get("roots_only"))

    last = [0]
    def on_progress(done, total):
        if total and done - last[0] >= 200:
            last[0] = done
            log(f"已抓 {done}")

    res = core.crawl_comments(arg, str(out_p), roots_only=roots_only,
                              on_log=log, on_progress=on_progress)
    return res, out_p


def _do_prep(p, log):
    if _PUBLIC:
        src = _pub_in(p.get("input"), "comments.csv")
        outdir = _SANDBOX
    else:
        src = safe_path(p.get("input"), must_exist=True)
        outdir = safe_path(p.get("outdir") or str(Path.home() / "comment-distillery-output"),
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
        outdir = safe_path(p.get("outdir") or str(Path.home() / "comment-distillery-output"),
                           allow_missing_parent=True)
    res = core.export_package(str(src), str(outdir), p.get("name") or None,
                              int(p.get("low_max") or 8),
                              int(p.get("low_min_len") or 120),
                              on_log=log)
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
    res = core.verify_guide(str(guide), corpora, p.get("field") or None)
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
        out_p = safe_path(out, allow_missing_parent=True) if out else None
    log("渲染中…")
    res = core.emit_report(str(guide), str(out_p) if out_p else None,
                           corpora or None, None,
                           p.get("title") or None, p.get("subtitle") or None,
                           bool(p.get("no_verify")))
    return res, Path(res["out"])


_ACTIONS = {"crawl": _do_crawl, "prep": _do_prep, "pack": _do_pack,
            "verify": _do_verify, "emit": _do_emit}


def _worker(jid, action, params):
    def log(m):
        _log(jid, str(m))

    try:
        fn = _ACTIONS.get(action)
        if not fn:
            raise ValueError(f"未知动作：{action}")
        raw, where = fn(params, log)
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
        return {
            "cls": "ok", "head": f"✓ 抓到 {_fmt(raw.get('n_total', 0))} 条",
            "kv": {"视频": raw.get("bv", ""),
                   "主楼 / 楼中楼": f"{_fmt(raw.get('n_top', 0))} / {_fmt(raw.get('n_sub', 0))}",
                   "合计": _fmt(raw.get("n_total", 0)) + ("（已中断）" if raw.get("stopped") else ""),
                   "输出": raw.get("out_csv", "")},
            "files": _files_of([raw.get("out_csv", "")]),
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
            "next": "把整个包目录拖进任意 AI → 拿到 Markdown 指南 → 回到 ④ 机验 → ⑤ 出报告",
        }

    if action == "verify":
        bad = list(raw.get("bad") or [])
        return {
            "cls": "err" if bad else "ok",
            "head": ("✗ 差集非空，不得交付" if bad else "✓ 差集为空，可交付"),
            "verdict": (f"❌ 检出 <b>{len(bad)}</b> 条幻觉引用——按质量门不得交付。"
                        if bad else
                        f"✅ 引用 {_fmt(len(raw.get('cited') or []))} 条，"
                        f"全部命中语料 {_fmt(len(raw.get('real') or []))} 个 ID，<b>差集为空</b>。"),
            "bad": bad,
            "kv": {"引用条数": _fmt(len(raw.get("cited") or [])),
                   "语料 ID 数": _fmt(len(raw.get("real") or [])),
                   "幻觉引用": _fmt(len(bad)),
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
        }

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
        """公开模式用令牌鉴权；本地模式用本机 Host/Origin 校验。"""
        if not _PUBLIC:
            return self._local_only()
        tok = self._request_token()
        if tok != _ACCESS_TOKEN:
            self._err(401, "公开模式需要访问令牌")
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
            self._send(200, PAGE_HTML, "text/html; charset=utf-8",
                       {"Content-Security-Policy":
                        "default-src 'none'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; img-src data:"})
            return

        if path == "/api/hello":
            ok, msgs = core.selfcheck()
            root = core.resource_root()
            sample_corpus = root / "examples" / "sample_corpus.csv"
            sample_guide = root / "examples" / "sample_guide.md"
            self._json({
                "ok": True, "version": core.APP_VERSION,
                "mode": "public" if _PUBLIC else "local",
                "outdir": str(_SANDBOX) if _PUBLIC else str(Path.home() / "comment-distillery-output"),
                "roots": [str(r) for r in allowed_roots()],
                "selfcheck": {"ok": ok, "msgs": [list(m) for m in msgs]},
                "sample_corpus": str(sample_corpus) if sample_corpus.exists() else "",
                "sample_guide": str(sample_guide) if sample_guide.exists() else "",
            })
            return

        if path == "/api/fs":
            self._api_fs(q)
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
        if u.path != "/api/start":
            return self._err(404, "未找到：" + u.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as e:
            return self._err(400, f"请求体解析失败：{e}")
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
        extra = {"X-Content-Type-Options": "nosniff"}
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
    """建服务器（不 serve_forever）。port=0 由系统分配，便于测试。"""
    return ThreadingHTTPServer((host, port), Handler)


def serve(port=DEFAULT_PORT, open_browser=True, host="127.0.0.1", quiet=False):
    """起服务。返回 (server, url)。调用方负责 shutdown()。"""
    srv = None
    if port:
        try:
            srv = build_server(host, port)
        except OSError:
            srv = None
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
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"端口（默认 {DEFAULT_PORT}；被占用则自动换一个）")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--allow-root", action="append", default=[], metavar="DIR",
                    help="追加一个允许访问的根目录（可重复）")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（默认 127.0.0.1；公开模式会自动改 0.0.0.0）")
    ap.add_argument("--public", action="store_true",
                    help="公开托管模式：绑定 0.0.0.0 + 令牌鉴权（替代本机校验），文件限制在沙箱")
    ap.add_argument("--token", default="",
                    help="公开模式访问令牌（建议长随机串；必须配合 --public）")
    ap.add_argument("--public-dir", default="",
                    help="公开模式文件系统沙箱目录（默认 <cwd>/out/public）")
    args = ap.parse_args(argv)

    for r in args.allow_root:
        add_root(r)

    if args.public:
        if not args.token:
            print("⚠️ 公开模式必须提供 --token，否则任何人都无法访问本服务")
        set_public(args.token, args.public_dir or None)
        args.host = "0.0.0.0"

    ok, msgs = core.selfcheck()
    for good, m in msgs:
        print(("  ✓ " if good else "  ✗ ") + m)
    if not ok:
        print("\n自检未通过：缺少随包资源，界面里对应功能会失败。")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        if _PUBLIC:
            print(f"\n🔓 公开模式：监听 {args.host}，能访问该端口者凭 --token 即可使用本服务。")
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
