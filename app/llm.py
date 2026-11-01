#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery · 用户自带 AI 的最小客户端（BYO-AI）。

**这不是"内置 LLM"**，请勿混为一谈：

- 不内置任何模型、不捆绑任何 Key、不代理任何额度；
- 只用**用户自己填的** OpenAI 兼容 endpoint + Key 发一次 HTTP 请求；
- 未配置时本模块完全不被调用，工具行为与 v1.7.0 逐字一致。

因此「不内置 LLM」这条铁律仍然成立：工具本身依旧零成本、零密钥、
方法论依旧引用仓库当前的 `SKILL.md`——它只是多了一条"你愿意把 Key 给我，
我就顺手把 ④⑤ 也跑完"的可选路径。

配置来源（优先级从高到低）：

1. 环境变量  CD_LLM_BASE_URL / CD_LLM_API_KEY / CD_LLM_MODEL  ← 推荐：不落盘、不随项目走
2. 配置文件  <程序目录>/llm.json（明文，仅本机；已被 .gitignore 忽略，不上库）
3. 都没有 → is_configured() 为 False，一键流程停在蒸馏包

环境变量优先于同名字段；**建议把 Key 放环境变量**（尤其多人/共享机），
llm.json 仅作为单用户本机的便利兜底。两者都不需要时，一键只到蒸馏包。

llm.json 形如：

    {
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-...",
      "model": "deepseek-chat",
      "max_corpus_chars": 120000,
      "timeout": 600
    }

零第三方依赖，仅标准库。Key 不落日志、不回显、不进产物。
"""

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_NAME = "llm.json"

# 默认值只在与"用户已配置"同时成立时才生效
DEFAULTS = {
    "base_url": "https://api.openai.com/v1",
    "model": "",
    "max_corpus_chars": 120000,
    "timeout": 600,
    "max_repair_rounds": 2,
    "temperature": 0.3,
    "seed": None,   # 设置后请求尽量确定，便于复现与审计
}

_REQUIRED = ("base_url", "api_key", "model")


def config_path(app_root) -> Path:
    return Path(app_root) / CONFIG_NAME


def redact(text) -> str:
    """把 sk-xxx / 长随机串抹掉，任何要落日志的地方都必须先过这里。"""
    s = str(text or "")
    s = re.sub(r"(sk-[A-Za-z0-9_\-]{6,})", "sk-***", s)
    s = re.sub(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([^\s\"',}]{8,})", r"\1***", s)
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1***", s)
    return s


def load_config(app_root) -> dict:
    """读配置并归一。未配置完整时返回 {"configured": False, ...}。"""
    cfg = dict(DEFAULTS)
    src = "none"

    p = config_path(app_root)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if v not in (None, ""):
                        cfg[k] = v
                src = "file"
        except Exception as e:
            return {"configured": False, "source": "file-broken",
                    "error": f"llm.json 解析失败：{e}", "path": str(p)}

    env_map = {"CD_LLM_BASE_URL": "base_url",
               "CD_LLM_API_KEY": "api_key",
               "CD_LLM_MODEL": "model"}
    for env, key in env_map.items():
        v = os.environ.get(env)
        if v:
            cfg[key] = v
            src = "env" if src == "none" else "file+env"

    for k in ("max_corpus_chars", "timeout", "max_repair_rounds", "temperature"):
        try:
            cfg[k] = type(DEFAULTS[k])(cfg[k])
        except Exception:
            cfg[k] = DEFAULTS[k]

    cfg["base_url"] = str(cfg.get("base_url") or "").rstrip("/")
    cfg["api_key"] = str(cfg.get("api_key") or "")
    cfg["model"] = str(cfg.get("model") or "")
    missing = [k for k in _REQUIRED if not cfg.get(k)]
    cfg["configured"] = not missing
    cfg["missing"] = missing
    cfg["source"] = src
    cfg["path"] = str(p)
    return cfg


def describe(cfg) -> str:
    """给人看的一行状态，**不含 Key**。"""
    if not cfg.get("configured"):
        miss = "、".join(cfg.get("missing") or [])
        return f"未配置 AI（缺 {miss}）→ 一键只到蒸馏包"
    return f"已配置 AI：{cfg.get('model')} @ {cfg.get('base_url')}"


# ────────────────────────────── HTTP ──────────────────────────────

def _opener(no_proxy=False):
    """默认走系统代理（用户可能在公司网/翻墙环境）。

    `CD_NO_PROXY=1` 时强制直连——与采集端踩过的坑同源：系统代理失效后
    urllib 仍会沿用注册表里的设置，表现为"连得上但一直假死"。
    """
    if no_proxy or os.environ.get("CD_NO_PROXY") == "1":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _ctx():
    """通信用独立的 SSLContext。

    ⚠️ 证书校验**不关**（本地自签 endpoint 请自配 SSL_CERT_FILE）。
    ⚠️ `OpenerDirector.open()` 不接受 `context=` 关键字（那是 `urlopen()`
       的私有参数），传了会 TypeError——实测踩过，且只在真发请求时暴露。
       正确做法是把 context 绑到 HTTPSHandler 上。
    """
    return ssl.create_default_context()


def _https_opener(no_proxy=False):
    o = _opener(no_proxy)
    o.add_handler(urllib.request.HTTPSHandler(context=_ctx()))
    return o


def chat(messages, cfg, on_delta=None, should_stop=None, retries=2):
    """调用 /chat/completions，返回纯文本。

    on_delta(str) 提供时走流式（SSE），否则一次性返回。
    should_stop() 返回 True 时中止。
    """
    if not cfg.get("configured"):
        raise RuntimeError("未配置 AI：" + describe(cfg))

    url = cfg["base_url"] + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg.get("temperature", 0.3),
        "stream": bool(on_delta),
    }
    # seed 只在显式配置时下发：部分 OpenAI 兼容网关遇未知字段会直接 400，
    # 而部分网关会忽略 seed——两种情况都不能假装「已复现」。
    if cfg.get("seed") not in (None, ""):
        try:
            payload["seed"] = int(cfg["seed"])
        except Exception:
            payload["seed"] = cfg["seed"]
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + cfg["api_key"],
    }

    last_err = None
    for attempt in range(retries + 1):
        if should_stop and should_stop():
            raise RuntimeError("已停止")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with _https_opener().open(req, timeout=cfg.get("timeout", 600)) as r:
                if on_delta:
                    return _read_stream(r, on_delta, should_stop)
                data = json.loads(r.read().decode("utf-8", "replace"))
                return _text_of(data)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            # 4xx 里只有 429 值得重试；401/403/404 重试只是浪费用户时间
            if e.code in (400, 401, 403, 404):
                raise RuntimeError(
                    f"AI 接口返回 {e.code}：{redact(detail) or e.reason}\n"
                    f"　检查 base_url / model 名 / Key 是否匹配（当前 {cfg['model']}）"
                )
            last_err = f"HTTP {e.code}：{redact(detail) or e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {redact(e)}"

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("AI 调用失败（已重试）：" + str(last_err))


def _text_of(data) -> str:
    try:
        ch = data["choices"][0]
        msg = ch.get("message") or {}
        c = msg.get("content")
        if isinstance(c, list):                       # 少数网关给分段数组
            c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
        if c:
            return str(c)
        if ch.get("text"):
            return str(ch["text"])
        if ch.get("finish_reason") == "length":
            raise RuntimeError(
                "输出被 max_tokens 截断且没有内容，请调大模型输出上限后重试")
        raise RuntimeError("响应里没有 content")
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("响应结构不认识：" + redact(json.dumps(data)[:300]))


def _read_stream(resp, on_delta, should_stop):
    buf, out = b"", []
    for raw in resp:
        if should_stop and should_stop():
            raise RuntimeError("已停止")
        buf += raw
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line or not line.startswith(b"data:"):
                continue
            chunk = line[5:].strip()
            if chunk == b"[DONE]":
                continue
            try:
                obj = json.loads(chunk.decode("utf-8", "replace"))
            except Exception:
                continue
            for ch in obj.get("choices") or []:
                piece = (ch.get("delta") or {}).get("content")
                if piece:
                    out.append(piece)
                    on_delta(piece)
    text = "".join(out)
    if not text:
        raise RuntimeError("流式响应为空（该网关可能不支持 stream，请改用非流式）")
    return text


def strip_fence(text: str) -> str:
    """模型习惯把整篇 markdown 包进 ```markdown ... ```，剥掉外层围栏。"""
    s = (text or "").strip()
    m = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", s, re.S)
    if m:
        return m.group(1).strip() + "\n"
    return s
