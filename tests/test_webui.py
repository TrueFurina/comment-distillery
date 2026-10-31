#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地 Web 界面（app/webui.py）的回归测试。

覆盖三类，缺一不可：
    1. 路由能跑通（页面 / hello / fs / job / preview / download）
    2. **安全边界真的拦得住**（Host / Origin / 路径穿越）——这类最容易
       "写的时候想到了、改的时候删掉了"，必须有测试钉住
    3. 端到端：prep → pack → verify → emit 四步真跑一遍

起真实 HTTP 服务（127.0.0.1 + 端口 0 由系统分配），不发外网请求。
"""

import http.client
import json
import os
import re
import shutil
import socket
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import webui  # noqa: E402


def _raw(port, raw: bytes, timeout=6):
    """发一条原始 HTTP 请求，返回响应头+体（用于伪造 Host/Origin）。"""
    buf = b""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.sendall(raw)
            s.settimeout(1.2)
            while True:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    break
                if not d:
                    break
                buf += d
    except OSError:
        pass
    return buf


class WebUIBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 强制关公开模式：unittest 按类名字母序加载，TestPublicMode 可能先于本类运行，
        # 若其复位不彻底会泄漏 _PUBLIC=True 进来。这里兜底。
        webui._PUBLIC = False
        webui._ACCESS_TOKEN = ""
        webui._SANDBOX = None
        webui._LAN = False
        cls.srv, cls.url = webui.serve(port=0, open_browser=False, quiet=True)
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.tmp = Path(tempfile.mkdtemp(prefix="cd-webui-test-"))

        # 隔离 AI 配置：这些测试跑的是"没配 AI"的路径。
        # 不隔离的话，本机一旦填了真 Key，一键就会真的去调模型，
        # 测试从 10 秒变成几分钟，还会因超时假报失败——实测踩过。
        # 用 app_root 打补丁而不是删用户的 llm.json：
        # 删文件属于破坏用户数据，改路径指向只是本进程内的临时视图。
        cls._real_app_root = webui.core.app_root
        cls._stub_root = Path(tempfile.mkdtemp(prefix="cd-stub-root-"))
        webui.core.app_root = lambda: cls._stub_root

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        webui.core.app_root = cls._real_app_root
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ── 小工具 ──
    def get(self, path, raw=False):
        with urllib.request.urlopen(self.base + path, timeout=30) as r:
            b = r.read()
            return (r.status, b) if raw else (r.status, b.decode("utf-8"))

    def getj(self, path):
        st, b = self.get(path, raw=True)
        return st, json.loads(b.decode("utf-8"))

    def post(self, path, obj):
        """POST JSON。4xx/5xx **不抛**——业务语义（如"未知动作 400"）本来就要断言。"""
        req = urllib.request.Request(
            self.base + path, data=json.dumps(obj).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def wait(self, jid, rounds=150):
        for _ in range(rounds):
            st, d = self.getj("/api/job?id=" + urllib.parse.quote(jid))
            if d.get("done"):
                return d
            import time
            time.sleep(0.2)
        self.fail("作业超时未完成")

    def hello(self):
        return self.getj("/api/hello")[1]


# ────────────────────────────── 路由 ──────────────────────────────

class TestRoutes(WebUIBase):
    def test_page_is_self_contained(self):
        st, body = self.get("/")
        self.assertEqual(st, 200)
        # 五个步骤必须在页面上；外链资源一个都不许有
        for m in ("① 采集", "② 预处理", "③ 蒸馏包", "④ 引用机验", "⑤ 出报告"):
            self.assertIn(m, body)
        self.assertNotIn('<script src="http', body)
        self.assertNotIn('<link rel="stylesheet" href="http', body)

    def test_page_csp_header(self):
        with urllib.request.urlopen(self.base + "/", timeout=20) as r:
            self.assertIn("Content-Security-Policy", r.headers)
            self.assertIn("default-src 'none'", r.headers["Content-Security-Policy"])

    def test_hello_reports_selfcheck_and_samples(self):
        h = self.hello()
        self.assertTrue(h["ok"])
        self.assertTrue(h["selfcheck"]["ok"], f"自检未通过：{h['selfcheck']['msgs']}")
        self.assertTrue(h["sample_corpus"], "示例语料未找到")
        self.assertTrue(h["sample_guide"], "示例指南未找到")
        self.assertTrue(h["outdir"])

    def test_fs_lists_directory(self):
        st, d = self.getj("/api/fs?path=" + urllib.parse.quote(str(ROOT / "examples")))
        self.assertEqual(st, 200)
        names = [e["name"] for e in d["entries"]]
        self.assertIn("sample_corpus.csv", names)

    def test_page_panels_match_backend_actions(self):
        """每个后端动作都必须在前端有入口，反之亦然。

        这是"加了一个后端能力却忘了给入口"这类漏项的廉价守卫——
        它不会自己报 bug，只会让功能静默不可达。

        对应关系不要求"一动作一页签"：`distill` 挂在「③ 蒸馏包」页里
        （对已有包补跑 AI），`ai` 是纯设置页、不对应任何后端动作。
        这两条例外集中声明在 webui 里，不靠测试去猜。
        """
        _, body = self.get("/")
        def picks(attr):
            return set(re.findall(r'data-%s="([a-z]+)"' % attr, body))

        actions = set(webui._ACTIONS.keys())
        pane_of = getattr(webui, "UI_PANE_OF", {})
        settings = set(getattr(webui, "UI_SETTINGS_PANES", set()))
        # 每个动作应有的页签 key：默认是自己，声明过映射的按映射
        expect_panes = {pane_of.get(a, a) for a in actions}

        self.assertEqual(picks("run"), actions,
                         "有动作没入口，或有入口没动作")
        self.assertEqual(picks("p"), expect_panes | settings,
                         "data-p 面板与后端动作不一致")
        # 日志/结果框允许动作与页签不同名（同页多动作），但必须落在某个真实存在的页里
        for attr in ("log", "res"):
            got = picks(attr)
            self.assertTrue(set(pane_of.get(x, x) for x in got) <=
                            expect_panes | settings,
                            f"data-{attr} 出现了没有对应页签的动作：{sorted(got - actions)}")

    def test_page_js_references_only_defined_ids(self):
        """JS 里 $('#x') 引用的元素必须在页面里真的存在（防改名后静默失效）。"""
        _, body = self.get("/")
        defined = set(re.findall(r'id="([^"]+)"', body))
        js = re.search(r"<script>(.*?)</script>", body, re.S)
        self.assertIsNotNone(js, "页面应有内联 JS")
        used = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', js.group(1)))
        self.assertEqual(used - defined, set(),
                         f"JS 引用了不存在的元素：{sorted(used - defined)}")

    def test_unknown_route_404(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.get("/nope")
        self.assertEqual(c.exception.code, 404)

    def test_job_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.getj("/api/job?id=nope")
        self.assertEqual(c.exception.code, 404)

    def test_unknown_action_rejected(self):
        st, d = self.post("/api/start", {"action": "rm-rf", "params": {}})
        self.assertEqual(st, 400)
        self.assertIn("未知动作", d["error"])

    def test_malformed_body_rejected(self):
        req = urllib.request.Request(self.base + "/api/start", data=b"{not json",
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(req, timeout=20)
        self.assertEqual(c.exception.code, 400)


# ────────────────────────────── 安全边界 ──────────────────────────────

class TestSecurity(WebUIBase):
    def test_foreign_host_rejected(self):
        buf = _raw(self.port,
                   b"GET / HTTP/1.1\r\nHost: evil.example.com\r\nConnection: close\r\n\r\n")
        self.assertIn(b"403", buf[:64], "非本机 Host 必须被拒")

    def test_foreign_origin_rejected(self):
        body = b'{"action":"prep","params":{}}'
        buf = _raw(self.port,
                   b"POST /api/start HTTP/1.1\r\n"
                   b"Host: 127.0.0.1\r\n"
                   b"Origin: http://evil.example.com\r\n"
                   b"Content-Type: application/json\r\n"
                   b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                   b"Connection: close\r\n\r\n" + body)
        self.assertIn(b"403", buf[:64], "跨站 Origin 必须被拒")

    def test_local_origin_allowed(self):
        body = b'{"action":"prep","params":{"input":"x"}}'
        buf = _raw(self.port,
                   b"POST /api/start HTTP/1.1\r\n"
                   b"Host: 127.0.0.1\r\n"
                   b"Origin: http://127.0.0.1\r\n"
                   b"Content-Type: application/json\r\n"
                   b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                   b"Connection: close\r\n\r\n" + body)
        # 通过 Origin 校验后会走到业务层（找不到文件 -> 400/500 或作业报错），
        # 但绝不能是 403
        self.assertNotIn(b"403", buf[:64])

    def test_path_traversal_rejected(self):
        # 探测串必须「在当前平台上真的位于允许根之外」，否则测到的是 404 不是越权：
        #  · 「..」深链 —— resolve 后越过所有允许根（两大平台都成立）
        #  · home 父目录 —— 必在 home / 仓库 / 系统临时目录之外
        #  · 「C:/Windows/...」这种盘符绝对路径只在 Windows 上成立；POSIX 上它是
        #    相对路径，resolve 后落在仓库内、根本不是穿越——eb15e33 曾把它当
        #    通用探测，CI(Linux) 假红 7 个提交才被发现（2026-10-23 教训）。
        deep = "/".join([".."] * 8) + "/x"
        for bad in (deep, str(Path.home().parent)):
            with self.assertRaises(urllib.error.HTTPError) as c:
                self.getj("/api/fs?path=" + urllib.parse.quote(bad))
            self.assertEqual(c.exception.code, 403, f"应拦截：{bad}")
        if os.name == "nt":
            with self.assertRaises(urllib.error.HTTPError) as c:
                self.getj("/api/fs?path=" + urllib.parse.quote("C:/Windows/System32"))
            self.assertEqual(c.exception.code, 403)

    def test_safe_path_rejects_outside_root(self):
        with self.assertRaises(webui.OutsideRoot):
            webui.safe_path("/".join([".."] * 8) + "/x")
        with self.assertRaises(webui.OutsideRoot):
            webui.safe_path(str(Path.home().parent / "cd-outside"))
        if os.name == "nt":
            with self.assertRaises(webui.OutsideRoot):
                webui.safe_path("C:/Windows/System32/config/SAM")
        with self.assertRaises(webui.OutsideRoot):
            webui.safe_path("")

    def test_safe_path_accepts_inside_root(self):
        p = webui.safe_path(str(ROOT / "examples" / "sample_corpus.csv"))
        self.assertTrue(p.exists())

    def test_preview_is_sandboxed(self):
        h = self.hello()
        guide, corpus = h["sample_guide"], h["sample_corpus"]
        st, d = self.post("/api/start", {"action": "emit", "params": {
            "guide": guide, "corpora": [corpus],
            "out": str(self.tmp / "sec.html"), "no_verify": True}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        with urllib.request.urlopen(
                self.base + "/preview?path=" + urllib.parse.quote(job["result"]["out"]),
                timeout=20) as r:
            csp = r.headers.get("Content-Security-Policy", "")
            self.assertIn("sandbox", csp, "预览页必须沙箱化")
            self.assertNotIn("allow-scripts", csp, "预览页绝不能放行脚本")


# ────────────────────────────── 端到端 ──────────────────────────────

class TestPipeline(WebUIBase):
    def test_auto_one_click(self):
        """一键完成：给一份现成 CSV，应一次产出成品包。"""
        h = self.hello()
        outdir = str(self.tmp / "auto")
        st, d = self.post("/api/start", {"action": "auto", "params": {
            "arg": h["sample_corpus"], "outdir": outdir, "name": "auto-t"}})
        self.assertEqual(st, 200)
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        r = job["result"]
        # 未配置 AI 时，一键应停在"蒸馏包已就绪"（与 v1.7.0 行为一致）；
        # 配了 AI 才会出现"一键到底"的标题。测试环境不碰网络，故走前者。
        self.assertIn("蒸馏包已就绪", r["head"])
        self.assertEqual(r.get("mode"), "pack-only")
        pack = Path(r["kv"]["包目录"])
        self.assertTrue(pack.is_dir(), f"包目录不存在：{pack}")
        for f in ("SKILL.md", "all_comments.txt", "PROMPT.md", "corpus_ccf.csv"):
            self.assertTrue((pack / f).exists(), f"包内缺 {f}")
        self.assertFalse(r.get("aborted", False))

    def test_auto_rejects_empty_arg(self):
        st, d = self.post("/api/start", {"action": "auto",
                                         "params": {"arg": "", "outdir": str(self.tmp)}})
        job = self.wait(d["job"])
        self.assertIsNotNone(job.get("error"))
        self.assertIn("视频链接", job["error"])

    def test_auto_does_not_mix_reruns(self):
        """同名重跑必须各自成目录，不能把上一次的残留混进这一次的包。"""
        h = self.hello()
        outdir = str(self.tmp / "rerun")
        Path(outdir).mkdir(parents=True, exist_ok=True)
        # 预先在同名目录里放个"上一次的残留"
        seed = Path(outdir) / "same" 
        seed.mkdir(parents=True, exist_ok=True)
        (seed / "OLD_MARKER.txt").write_text("from previous run", encoding="utf-8")

        st, d = self.post("/api/start", {"action": "auto", "params": {
            "arg": h["sample_corpus"], "outdir": outdir, "name": "same"}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        pack = Path(job["result"]["kv"]["包目录"])
        self.assertTrue(pack.is_dir())
        self.assertNotEqual(pack, seed,
                            "同名重跑不该复用同一个目录")
        self.assertFalse((pack / "OLD_MARKER.txt").exists(),
                         "新包里混进了上一次的残留文件")

    def test_full_chain(self):
        h = self.hello()
        corpus, guide = h["sample_corpus"], h["sample_guide"]

        # ② 预处理
        outdir = str(self.tmp / "prep")
        st, d = self.post("/api/start", {"action": "prep",
                                         "params": {"input": corpus, "outdir": outdir}})
        self.assertEqual(st, 200)
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        self.assertIn("去噪后", job["result"]["head"])
        self.assertTrue(any(f["name"] == "corpus_ccf.csv"
                            for f in job["result"]["files"]))

        # ③ 蒸馏包
        st, d = self.post("/api/start", {"action": "pack", "params": {
            "input": corpus, "outdir": str(self.tmp / "pack"), "name": "t-pack"}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        self.assertIn("SKILL.md", job["result"]["kv"]["随包方法论"])
        ccf = str(self.tmp / "pack" / "t-pack" / "corpus_ccf.csv")
        self.assertTrue(Path(ccf).exists())

        # ④ 机验 —— 示例指南的引用必须全部命中
        st, d = self.post("/api/start", {"action": "verify",
                                         "params": {"guide": guide, "corpora": [ccf]}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        self.assertEqual(job["result"]["cls"], "ok",
                         "示例指南应当零幻觉：" + str(job["result"].get("bad")))
        self.assertNotEqual(job["result"]["kv"]["引用条数"], "0")

        # ⑤ 报告
        st, d = self.post("/api/start", {"action": "emit", "params": {
            "guide": guide, "corpora": [ccf], "out": str(self.tmp / "report.html")}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        r = job["result"]
        self.assertEqual(r["cls"], "ok")
        self.assertTrue(Path(r["out"]).exists())
        self.assertIn("幻觉 0", r["verdict"])

    def test_missing_corpus_is_reported_not_crashed(self):
        h = self.hello()
        st, d = self.post("/api/start", {"action": "verify",
                                         "params": {"guide": h["sample_guide"], "corpora": []}})
        self.assertEqual(st, 200)   # 作业能起
        job = self.wait(d["job"])
        self.assertIsNotNone(job.get("error"))
        self.assertIn("语料", job["error"])

    def test_missing_file_is_reported(self):
        st, d = self.post("/api/start", {"action": "prep", "params": {
            "input": str(self.tmp / "does-not-exist.csv"), "outdir": str(self.tmp / "x")}})
        job = self.wait(d["job"])
        self.assertIsNotNone(job.get("error"))
        self.assertEqual(job["status"], "error")

    def test_emit_without_corpus_warns(self):
        h = self.hello()
        st, d = self.post("/api/start", {"action": "emit", "params": {
            "guide": h["sample_guide"], "corpora": [],
            "out": str(self.tmp / "noverify.html")}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        # 无语料 -> 没跑机验 -> 必须告警，不能假装通过
        self.assertEqual(job["result"]["cls"], "warn")
        self.assertIn("未跑机验", job["result"]["verdict"])


# ────────────────────────────── 公开托管模式 ──────────────────────────────

class TestPublicMode(unittest.TestCase):
    """公开模式的安全边界必须钉死——这是"部署成在线平台"的前提。

    公开模式：令牌鉴权（替代本机 Host/Origin）+ 文件限制在沙箱 + 关文件选择器。
    本类是定义顺序里的最后一组，setUpClass 开公开模式、tearDownClass 复位，
    不污染 TestRoutes/TestSecurity/TestPipeline（它们跑在本地模式）。
    """

    TOKEN = "public-test-token-xyz"

    @classmethod
    def setUpClass(cls):
        cls.sandbox = tempfile.mkdtemp(prefix="cd-pub-")
        webui.set_public(cls.TOKEN, cls.sandbox)
        cls.srv, cls.url = webui.serve(port=0, open_browser=False, quiet=True, host="127.0.0.1")
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        webui._PUBLIC = False               # 直接复位（set_public 永远置 True，不能用于复位）
        webui._ACCESS_TOKEN = ""
        webui._SANDBOX = None
        shutil.rmtree(cls.sandbox, ignore_errors=True)

    def _raw_auth(self, auth):
        head = (b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                + (b"Authorization: Bearer " + auth.encode() + b"\r\n" if auth else b"")
                + b"Connection: close\r\n\r\n")
        return _raw(self.port, head)

    def test_page_without_token_rejected(self):
        self.assertIn(b"401", self._raw_auth("")[:64], "公开模式无令牌必须 401")

    def test_wrong_token_rejected(self):
        self.assertIn(b"401", self._raw_auth("wrong")[:64], "错误令牌必须 401")

    def test_page_with_token_allowed(self):
        self.assertIn(b"200", self._raw_auth(self.TOKEN)[:64], "正确令牌应放行")

    def test_fs_disabled_in_public(self):
        req = urllib.request.Request(
            self.base + "/api/fs",
            headers={"Authorization": "Bearer " + self.TOKEN})
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(c.exception.code, 403, "公开模式必须禁用文件选择器")

    def test_only_sandbox_accessible(self):
        # 公开模式 allowed_roots 只有沙箱；仓库示例语料不在沙箱内 -> OutsideRoot
        with self.assertRaises(webui.OutsideRoot):
            webui.safe_path(str(ROOT / "examples" / "sample_corpus.csv"))

    def test_auto_forces_sandbox_output(self):
        """一键流程在公开模式下必须把产物收进沙箱，不能采信用户给的目录。

        实测过的坏法：`_do_auto` 里 `_PUBLIC` 分支直接 Path(p["outdir"])，
        完全跳过 safe_path —— 公开部署时只要构造一个 outdir 就能写出沙箱。
        """
        import inspect
        src = inspect.getsource(webui._do_auto)
        self.assertIn("base = _SANDBOX", src,
                      "公开模式下 base 必须强制为沙箱")
        self.assertNotIn('Path(p.get("outdir"))', src,
                         "不得直接采信用户提供的 outdir")

    def test_hello_reports_public_mode(self):
        req = urllib.request.Request(
            self.base + "/api/hello",
            headers={"Authorization": "Bearer " + self.TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        self.assertEqual(d["mode"], "public")
        self.assertTrue(d["outdir"])


# ────────────────────────────── 局域网模式 ──────────────────────────────

class TestLanMode(unittest.TestCase):
    """局域网模式：令牌鉴权 + 私网 Host 白名单 + **保留文件选择器/完整文件系统**。

    与公开模式的关键区别：_api_fs 不 403、allowed_roots 给默认全量（不是沙箱）。
    本类在定义序里最后一组，setUpClass 开局域网模式、tearDownClass 复位，
    不污染前面几组（它们跑在本地/公开模式）。
    """

    TOKEN = "lan-test-token-xyz"

    @classmethod
    def setUpClass(cls):
        webui.set_lan(cls.TOKEN)
        cls.srv, cls.url = webui.serve(port=0, open_browser=False, quiet=True, host="127.0.0.1")
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        webui._LAN = False                    # 直接复位（set_lan 永远置 True，不能用于复位）
        webui._ACCESS_TOKEN = ""
        webui._SANDBOX = None

    def _raw(self, auth, host="127.0.0.1"):
        head = (b"GET / HTTP/1.1\r\nHost: " + host.encode() + b"\r\n"
                + (b"Authorization: Bearer " + auth.encode() + b"\r\n" if auth else b"")
                + b"Connection: close\r\n\r\n")
        return _raw(self.port, head)

    def test_page_without_token_rejected(self):
        self.assertIn(b"401", self._raw("")[:64], "局域网模式无令牌必须 401")

    def test_wrong_token_rejected(self):
        self.assertIn(b"401", self._raw("wrong")[:64], "错误令牌必须 401")

    def test_page_with_token_allowed(self):
        self.assertIn(b"200", self._raw(self.TOKEN)[:64], "正确令牌应放行")

    def test_fs_enabled_in_lan(self):
        # 关键区别：局域网模式保留文件选择器（公开模式这里应 403）
        q = "/api/fs?path=" + urllib.parse.quote(str(ROOT / "examples"))
        req = urllib.request.Request(
            self.base + q, headers={"Authorization": "Bearer " + self.TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        self.assertIn("entries", d)
        self.assertIn("sample_corpus.csv", [e["name"] for e in d["entries"]])

    def test_full_roots_accessible(self):
        # 局域网模式不收沙箱：仓库示例语料可达（公开模式下这里会 OutsideRoot）
        p = webui.safe_path(str(ROOT / "examples" / "sample_corpus.csv"))
        self.assertTrue(p.exists())

    def test_private_host_accepted(self):
        # 用私网 IP 作 Host 应被接受（证明同网段设备能用 IP 访问）
        self.assertIn(b"200", self._raw(self.TOKEN, host="172.16.222.99")[:64],
                      "私网 Host 必须放行")

    def test_foreign_host_rejected(self):
        # 外域 Host 仍要挡（DNS-rebinding / 跨站）
        self.assertIn(b"403", self._raw(self.TOKEN, host="evil.example.com")[:64],
                      "外域 Host 必须被拒")

    def test_hello_reports_lan_mode(self):
        req = urllib.request.Request(
            self.base + "/api/hello",
            headers={"Authorization": "Bearer " + self.TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        self.assertEqual(d["mode"], "lan")
        self.assertTrue(d["outdir"])


# ────────────────────────────── 「界面能真的用」回归 ──────────────────────────────
#
# 这一组钉住的是 2026-10-27 实测出来的 7 个 bug。它们的共同特征是：
# **纯逻辑测试全绿，真实点开界面却完全不能用**。所以断言都尽量贴近
# 用户看得见的那一层（CSP 头、按钮文案、错误话术、返回的文件链接）。

class TestUsableInBrowser(WebUIBase):
    def test_csp_allows_fetch_to_self(self):
        """页面按钮全靠 fetch 调 /api/*；CSP 缺 connect-src 会让整站点了没反应。"""
        with urllib.request.urlopen(self.base + "/", timeout=20) as r:
            csp = r.headers["Content-Security-Policy"]
        self.assertIn("connect-src", csp,
                      "CSP 必须显式放行 connect-src，否则 fetch 被拦截、界面全瘫")
        self.assertTrue("'self'" in csp or "127.0.0.1" in csp, csp)

    def test_default_tab_matches_visible_pane(self):
        """默认高亮的页签必须和默认显示的面板是同一个。"""
        st, body = self.get("/")
        self.assertEqual(st, 200)
        # 页签高亮来自 buildTabs()，面板可见性来自 HTML 的 hidden 属性；
        # 两者若各写一份常量就必然漂移，这里直接盯构建方式。
        self.assertIn('$(".pane:not([hidden])")', body,
                      "默认页签应按首个可见面板推导，不能写死索引")

    def test_output_fields_are_files_not_dirs(self):
        """c_out / e_out 是文件路径，不能被预填成目录。"""
        st, body = self.get("/")
        self.assertIn('cOut.value = h.outdir + "\\\\comments.csv"', body)
        self.assertIn('eOut.value = h.outdir + "\\\\report.html"', body)
        # 不再有一刀切的后缀选择器去批量预填目录名（注释里提到不算）
        for line in body.splitlines():
            code = line.split("//")[0]
            self.assertNotIn('input[id$="_out"]', code,
                             "不该再用后缀一刀切预填——会把目录填进文件名位置")

    def test_setbusy_restores_original_label(self):
        """任务结束后按钮必须还原成原文案，不能卡在「运行中…」。"""
        st, body = self.get("/")
        self.assertIn("if (!b.dataset.label) b.dataset.label = b.textContent.trim();", body,
                      "原件标签要在改写前存，否则存下的就是「运行中…」")

    def test_emit_returns_downloadable_file(self):
        """⑤ 报告生成后必须给出可点的文件，否则用户以为没出结果。"""
        h = self.hello()
        out = str(self.tmp / "r.html")
        st, d = self.post("/api/start", {"action": "emit", "params": {
            "guide": h["sample_guide"], "corpora": [h["sample_corpus"]], "out": out}})
        job = self.wait(d["job"])
        self.assertIsNone(job.get("error"), job.get("error"))
        files = job["result"].get("files") or []
        self.assertTrue(files, "报告已生成却没返回文件列表，界面点不开也下不了")
        self.assertTrue(any(f["path"] == out for f in files), files)

    def test_directory_as_output_rejected_early(self):
        """把目录填成输出文件 -> 立刻给可读错误，而不是跑完几百秒再崩。"""
        h = self.hello()
        st, d = self.post("/api/start", {"action": "crawl", "params": {
            "arg": "BV1o74y6XEcM", "out": str(self.tmp), "roots_only": True}})
        job = self.wait(d["job"], rounds=60)
        self.assertIsNotNone(job.get("error"), "目录当输出文件必须被拦下")
        self.assertIn("目录", job["error"])
        self.assertNotIn("PermissionError", job["error"],
                         "要给人话，不要甩 PermissionError")

    def test_crawl_progress_callback_arity(self):
        """采集进度回调必须吃满 (done, total, subs) —— 少一个形参就会在
        抓完几千条之后抛 TypeError，用户白等。这里直接打真身，不发网络请求。"""
        import inspect
        from app import webui
        sig = inspect.signature(webui._do_crawl)
        src = inspect.getsource(webui)
        self.assertIn("def on_progress(done, total, subs=0)", src,
                      "webui 的 on_progress 必须接 3 个参数（与 contrib.crawl 约定一致）")
        # 再确认上游确实是三参调用，防止有人反向"修"错边
        from contrib import fetch_bilibili_comments as fbc
        csig = inspect.signature(fbc.crawl)
        self.assertIn("on_progress", csig.parameters)
        # fetch_main 要支持翻页进度，否则前几分钟日志一片空白
        self.assertIn("on_page", inspect.signature(fbc.fetch_main).parameters)

    def test_second_instance_does_not_hijack_port(self):
        """端口被占时必须换端口，而不是两个进程共享同一端口。"""
        import socket
        from app.webui import build_server
        # 先占一个空闲端口，模拟"已经有一个实例在跑"
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        busy = probe.getsockname()[1]
        probe.listen(1)
        try:
            if os.name == "nt":
                with self.assertRaises(OSError,
                                       msg="Windows 上第二个实例不得抢到同一端口"):
                    build_server("127.0.0.1", busy).server_close()
            else:
                # POSIX 下 SO_REUSEADDR 语义不同（只放行 TIME_WAIT）：
                # 这里只要求"不静默共享"，绑定失败或换端口都算对。
                try:
                    build_server("127.0.0.1", busy).server_close()
                except OSError:
                    pass
        finally:
            probe.close()


class TestCancelAndCallbacks(WebUIBase):
    """停止链路 + 采集回调的回归。

    这三条都是 2026-10-27 实测才暴露的，且全都**只在特定调用方式下复现**：
    递归那条要 on_log 自己也 print，丢数据那条要"翻页阶段被叫停"——
    正常路径跑一百遍都是绿的。
    """

    def test_callback_writer_survives_printing_log(self):
        """on_log 自己 print 时不得自激递归（否则采集 1 秒就崩）。"""
        import io
        import contextlib
        from contrib.fetch_bilibili_comments import _CallbackWriter

        hits = []

        def on_log(msg):
            hits.append(msg)
            print("echo: " + msg)   # 关键：回调又把输出打回 stdout

        w = _CallbackWriter(on_log)
        with contextlib.redirect_stdout(w):
            print("hello")
            print("world")
        w.flush()
        self.assertIn("hello", "".join(hits))
        self.assertIn("world", "".join(hits))

    def test_fetch_main_stops_mid_pagination_and_keeps_data(self):
        """翻页阶段叫停：已抓到的必须留下，不能"抓了 N 条写出 0 条"。"""
        import inspect
        from contrib import fetch_bilibili_comments as fbc
        sig = inspect.signature(fbc.fetch_main)
        self.assertIn("should_stop", sig.parameters)
        self.assertIn("should_stop", inspect.signature(fbc.fetch_sub).parameters)

        src = inspect.getsource(fbc.crawl)
        # 翻页已停时，mains 里的数据要照常进 rows（不能第一轮就被 break 掉）
        self.assertIn("翻页阶段已停止", src)
        self.assertIn("and not stopped", src)

    def test_job_can_be_cancelled(self):
        """Web 端要真能停：没有 /api/cancel，用户只能干等几分钟。"""
        from app import webui
        jid = webui._new_job()
        self.assertTrue(webui._cancel(jid))
        self.assertTrue(webui._should_stop(jid))
        webui._finish(jid)
        d = webui._job(jid)
        self.assertEqual(d["status"], "cancelled")
        # 已结束的作业不能再取消
        self.assertFalse(webui._cancel(jid))

    def test_cancel_route_exists(self):
        st, d = self.post("/api/cancel", {"job": "no-such-job"})
        self.assertEqual(st, 200)
        self.assertFalse(d["ok"])

    def test_cancelled_result_is_warn_not_ok(self):
        """半截语料的头不能是"✓ 抓到"，必须是"已停止"并说明不是完整语料。"""
        from app import webui
        raw = {"bv": "BV1x", "n_top": 370, "n_sub": 10, "n_total": 380,
               "out_csv": "", "stopped": True}
        r = webui._shape("crawl", raw, None, lambda m: None)
        self.assertEqual(r["cls"], "warn")
        self.assertIn("已停止", r["head"])
        self.assertIn("不是完整语料", r["kv"]["合计"])
        self.assertIn("半截", r["next"])

    def test_stop_keeps_partial_csv_downloadable(self):
        """停止后必须把已抓到的 CSV 交出去，否则抓了半天拿不到手。

        实测踩过：停止时 pack_dir 为空、files 也为空，用户手里有 631 行语料
        却没有任何入口可取——日志里有个路径文字，界面上点不了。
        """
        from app import webui
        csvp = str(self.tmp / "partial.csv")
        Path(csvp).write_text("id,content\nc1,x\n", encoding="utf-8")
        raw = {"steps": [("采集", "279 条（中途停止）")], "aborted": True,
               "pack_dir": "", "files": [csvp], "partial_csv": csvp}
        r = webui._shape("auto", raw, None, lambda m: None)
        self.assertEqual(r["cls"], "warn")
        names = [f["name"] for f in (r.get("files") or [])]
        self.assertIn("partial.csv", names, "已抓到的 CSV 必须出现在可下载列表里")
        self.assertEqual(r["kv"].get("已保留"), csvp)

    def test_stop_button_only_on_long_step(self):
        """停止按钮要只出现在会跑几分钟的那一步，且默认隐藏。"""
        with urllib.request.urlopen(self.base + "/", timeout=20) as r:
            body = r.read().decode("utf-8")
        self.assertIn('data-stop="crawl"', body)
        self.assertIn("hidden", body.split('data-stop="crawl"')[1][:30])
        self.assertIn("async function stop(a)", body)


if __name__ == "__main__":
    unittest.main()
