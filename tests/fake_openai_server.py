#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地假 AI 网关：让端到端冒烟不花真钱、不依赖外网。

它只实现 /v1/chat/completions 两条路径（流式与非流式），行为刻意模仿
一个"会犯错的模型"：第一轮编两条不存在的 ID，被要求校对时改好。
正好用来验证「机验 → 修复 → 再验」这条闸门真的会拦。

    python tests/fake_openai_server.py 8899
"""

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROUND_BAD = """# 冒烟指南

## 一、这场讨论在吵什么

有真实依据的一条 `[源:c1010|权重58|回复]`。

手滑编出来的一条 `[源:c424242424242|权重42|一级]`。

## 二、反例对冲

另一条也是编的 `[源:c555555555555|权重5|回复]`。

## 三、盲区

样本很小，不能外推。
"""

ROUND_GOOD = """# 冒烟指南

## 一、这场讨论在吵什么

有真实依据的一条 `[源:c1010|权重58|回复]`。

原来那条编的引用已删除。

## 二、反例对冲

另一条也已删除。

## 三、盲区

样本很小，不能外推。
"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        msgs = body.get("messages") or []
        sys_txt = (msgs[0].get("content") or "") if msgs else ""
        usr_txt = (msgs[-1].get("content") or "") if msgs else ""

        asking_repair = "校对员" in sys_txt
        text = ROUND_GOOD if asking_repair else ROUND_BAD

        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(0, len(text), 120):
                chunk = {"choices": [{"delta": {"content": text[i:i + 120]}}]}
                self.wfile.write(b"data: " + json.dumps(chunk, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        out = json.dumps({"choices": [{"message": {"content": text}}]},
                         ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"fake openai on http://127.0.0.1:{port}/v1", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
