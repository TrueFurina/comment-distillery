#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端：起真服务 → 用 HTTP 走完「一键」，核对产物与页面文案。

与 tests/smoke_distill.py 的分工：
- smoke_distill 在同一进程里直接调函数，验**编排逻辑**；
- 本脚本起真实 HTTP 服务、按前端的调用顺序发请求，验**接线**——
  路由有没有注册、作业能不能推进、结果结构前端认不认得。

    python tests/e2e_web.py            # 期望 PASS
"""

import json
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import webui  # noqa: E402

FAKE_PORT = 8911


def start_fake_ai():
    sys.path.insert(0, str(ROOT / "tests"))
    import fake_openai_server as F
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", FAKE_PORT), F.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def start_app():
    srv = webui.build_server("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def post(port, path, payload):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=30) as r:
        return json.loads(r.read().decode())


def wait_job(port, jid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = get(port, f"/api/job?id={jid}")
        if d.get("done"):
            return d
        time.sleep(0.3)
    raise TimeoutError(f"作业 {jid} 超时（{timeout}s）")


def main():
    fails = []

    def ck(cond, msg):
        print(("  OK   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    fake = start_fake_ai()
    srv, port = start_app()
    tmp = Path(tempfile.mkdtemp(prefix="cd-e2e-"))

    # ⚠️ 把 app_root 指向临时目录：**绝不能**让测试写用户真实的 llm.json。
    # 踩过一次：测试末尾调 save_llm_config("","","") 清空配置，把用户刚填好的
    # base_url/model 一起抹掉了（Key 还在，于是变成一份半残配置）。
    # 隔离后，测试怎么写都只影响 tmp。
    _real_root = webui.core.app_root
    _test_root = Path(tempfile.mkdtemp(prefix="cd-e2e-root-"))
    webui.core.app_root = lambda: _test_root
    try:
        # 指向假网关（写在临时 root 里）
        webui.core.save_llm_config(f"http://127.0.0.1:{FAKE_PORT}/v1",
                                   "sk-e2e-fake", "fake-model")

        print("① /api/llm 应报告已配置")
        st = get(port, "/api/llm")
        ck(st.get("configured") is True, "configured=True")
        ck("sk-e2e-fake" not in json.dumps(st), "响应里不含 Key 明文")

        print("② /api/llm/test 应连通")
        r = post(port, "/api/llm/test", {})
        ck(r.get("ok") is True, f"ok=True（{r.get('error', '')}）")

        print("③ 一键：应一路跑到报告")
        job = post(port, "/api/start", {"action": "auto", "params": {
            "arg": str(ROOT / "examples" / "sample_corpus.csv"),
            "outdir": str(tmp), "name": "e2e"}})
        ck(bool(job.get("job")), "拿到 job id")
        d = wait_job(port, job["job"])
        ck(d.get("error") is None, f"无错误（{d.get('error')}）")
        res = d.get("result") or {}
        logs = "\n".join(d.get("log") or [])
        ck(res.get("mode") == "full", f"mode=full（实际 {res.get('mode')}）")
        ck("🎉" in (res.get("head") or ""), f"标题是一键到底：{res.get('head')}")
        ck("幻觉 0" in json.dumps(res, ensure_ascii=False) or
           "差集为空" in json.dumps(res, ensure_ascii=False),
           "结果里写明差集为空")

        print("④ 修复轮真的跑过（第一轮编了 2 条假 ID）")
        ck("2 条幻觉引用" in logs, "日志里记录了检出的幻觉引用")
        ck("✅ 通过" in logs, "日志里记录了修复后通过")

        pack = Path(res.get("kv", {}).get("包目录", ""))
        ck(pack.is_dir(), f"包目录存在：{pack}")
        rep = pack / "report.html"
        ck(rep.exists(), "report.html 已生成")
        h = rep.read_text(encoding="utf-8", errors="replace")
        ck("机验通过" in h, "报告页首标注机验通过")
        ck("c424242424242" not in h, "幻觉 ID 未进入报告")
        ck((pack / "guide.md").exists(), "guide.md 已落盘")

        print("⑤ 结果结构前端认不认得（关键字段齐不齐）")
        for k in ("cls", "head", "kv", "files", "next"):
            ck(k in res, f"result.{k} 存在")
        ck(res.get("kv", {}).get("报告"), "kv 里带报告路径，前端能一键打开")

        print("⑥ 未配置 AI 时应退化，不许报错")
        webui.core.save_llm_config("", "", "")   # 清空
        import os
        for k in ("CD_LLM_API_KEY", "CD_LLM_MODEL", "CD_LLM_BASE_URL"):
            os.environ.pop(k, None)
        job2 = post(port, "/api/start", {"action": "auto", "params": {
            "arg": str(ROOT / "examples" / "sample_corpus.csv"),
            "outdir": str(tmp / "noai"), "name": "noai"}})
        d2 = wait_job(port, job2["job"])
        r2 = d2.get("result") or {}
        ck(d2.get("error") is None, "没配 AI 不算失败")
        ck(r2.get("mode") == "pack-only", f"mode=pack-only（实际 {r2.get('mode')}）")
        ck("蒸馏包已就绪" in (r2.get("head") or ""), f"标题：{r2.get('head')}")
        ck(Path(r2.get("kv", {}).get("包目录", "")).is_dir(), "包仍然产出")
        print("      next =", (r2.get("next") or "")[:100])
    finally:
        webui.core.app_root = _real_root
        try:
            srv.shutdown()
            fake.shutdown()
        except Exception:
            pass

    print()
    if fails:
        print(f"FAIL {len(fails)} 项：")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
