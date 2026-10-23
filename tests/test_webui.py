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
        cls.srv, cls.url = webui.serve(port=0, open_browser=False, quiet=True)
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.tmp = Path(tempfile.mkdtemp(prefix="cd-webui-test-"))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
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
        """前端五块面板与后端五个动作必须一一对应。

        这是"加了一个后端能力却忘了给入口"这类漏项的廉价守卫——
        它不会自己报 bug，只会让功能静默不可达。
        """
        _, body = self.get("/")
        def picks(attr):
            return set(re.findall(r'data-%s="([a-z]+)"' % attr, body))
        self.assertEqual(picks("run"), set(webui._ACTIONS.keys()))
        for attr in ("log", "res", "p"):
            self.assertEqual(picks(attr), set(webui._ACTIONS.keys()),
                             f"data-{attr} 面板与后端动作不一致")

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
        # 注意：允许根含用户家目录，故「仓库两级之上」未必越权（仓库在家目录下时两级之上仍在家里）。
        # 改用「家目录两级之上」作为必定越权的动态用例，跨平台稳健，不依赖仓库摆放位置。
        above_home = str(Path.home().parent.parent)
        for bad in ("C:/Windows/System32", "/etc", above_home):
            with self.assertRaises(urllib.error.HTTPError) as c:
                self.getj("/api/fs?path=" + urllib.parse.quote(bad))
            self.assertEqual(c.exception.code, 403, f"应拦截：{bad}")

    def test_safe_path_rejects_outside_root(self):
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

    def test_hello_reports_public_mode(self):
        req = urllib.request.Request(
            self.base + "/api/hello",
            headers={"Authorization": "Bearer " + self.TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        self.assertEqual(d["mode"], "public")
        self.assertTrue(d["outdir"])


if __name__ == "__main__":
    unittest.main()
