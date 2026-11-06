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

1. 环境变量  CD_LLM_BASE_URL / CD_LLM_API_KEY / CD_LLM_MODEL  ← 唯一的环境变量契约
2. 配置文件  llm.json（明文，仅本机；已被 .gitignore 忽略，不上库）
   - **位置跟用户走，不跟程序走**：优先 `<用户配置目录>/comment-distillery/llm.json`
     （Windows 为 `%APPDATA%`，其他平台为 `$XDG_CONFIG_HOME` 或 `~/.config`）。
   - 旧版本把它写在 `<程序目录>/llm.json`（源码=仓库根、exe=exe 目录，两处会割裂，
     换目录/换机器就丢）。现在读取时**回退**到程序目录以兼容存量；写入**总是**
     落到用户配置目录（保存即完成迁移，无需手工搬）。
   - 测试隔离注入点：`CD_LLM_CONFIG_DIR` 环境变量指向临时目录时优先使用，
     避免测试读写用户真实配置。
3. 都没有 → is_configured() 为 False，一键流程停在蒸馏包

**为什么不自动读取 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` 这类"通用"环境变量？**
因为那会劫持环境里可能用于别处的 Key，并悄悄把"没配 AI"变成"已配 AI"，
破坏"只出蒸馏包"这条稳定契约。工具只认自己的显式命名空间 `CD_LLM_*`——
想用 DeepSeek / OpenAI，把 Key 显式填进 `CD_LLM_API_KEY`（或 `llm.json`）即可，
干净、不意外、不越界。

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

# 配置目录的环境变量注入点：测试用它隔离到临时目录，避免读写用户真实配置。
CONFIG_DIR_ENV = "CD_LLM_CONFIG_DIR"


def user_config_dir() -> Path:
    """用户级配置目录（跟人走，不跟程序走）。

    - Windows：%APPDATA%/comment-distillery（如 C:/Users/x/AppData/Roaming/...）
    - 其他：$XDG_CONFIG_HOME/comment-distillery 或 ~/.config/comment-distillery
    这是 XDG 惯例；项目纪律"产物不写用户主目录"只管**产物**（default_outdir），
    配置与产物是两回事——配置是用户私产（含 Key），理应跟用户走。
    """
    env = os.environ.get(CONFIG_DIR_ENV)
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "comment-distillery"

# 默认值只在与"用户已配置"同时成立时才生效
DEFAULTS = {
    # base_url / model 这里故意留空：只有真正来自 env / 文件时才算"已填"，
    # 否则会被 _REQUIRED 判为缺失 → 正确报告未配置，而不是拿占位值假装已配。
    "base_url": "",
    "model": "",
    "max_corpus_chars": 120000,
    "timeout": 600,
    "max_repair_rounds": 2,
    "temperature": 0.3,
    "seed": None,   # 设置后请求尽量确定，便于复现与审计
}

_REQUIRED = ("base_url", "api_key", "model")


def config_path(app_root) -> Path:
    """**读取**用的配置路径：优先用户配置目录，回退程序目录（兼容存量）。

    旧版本把 llm.json 写在程序目录（源码=仓库根、exe=exe 目录），两处割裂。
    这里保留回退，让换了目录/机器的存量配置仍能被读到；写入一律走
    write_config_path()（用户配置目录），保存即完成迁移。
    """
    user = user_config_dir() / CONFIG_NAME
    if user.exists():
        return user
    legacy = Path(app_root) / CONFIG_NAME
    if legacy.exists():
        return legacy
    return user


def write_config_path() -> Path:
    """**写入**用的配置路径：始终用户配置目录（跟人走）。"""
    return user_config_dir() / CONFIG_NAME


def redact(text) -> str:
    """把 sk-xxx / 长随机串抹掉，任何要落日志的地方都必须先过这里。"""
    s = str(text or "")
    s = re.sub(r"(sk-[A-Za-z0-9_\-]{6,})", "sk-***", s)
    s = re.sub(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([^\s\"',}]{8,})", r"\1***", s)
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1***", s)
    return s


def load_config(app_root) -> dict:
    """读配置并归一。未配置完整时返回 {"configured": False, ...}。

    来源优先级：CD_LLM_* 环境变量 > llm.json。详见模块 docstring。
    """
    cfg = dict(DEFAULTS)
    sources = []          # 记录实际命中的来源，供 UI 展示

    p = config_path(app_root)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if v not in (None, ""):
                        cfg[k] = v
                sources.append("file")
        except Exception as e:
            return {"configured": False, "source": "file-broken",
                    "error": f"llm.json 解析失败：{e}", "path": str(p)}

    # CD_LLM_* 环境变量（唯一的环境变量契约，覆盖文件）
    env_map = {"CD_LLM_BASE_URL": "base_url",
               "CD_LLM_API_KEY": "api_key",
               "CD_LLM_MODEL": "model"}
    for env, key in env_map.items():
        v = os.environ.get(env)
        if v:
            cfg[key] = v
            sources.append(env)

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
    cfg["source"] = "+".join(sources) if sources else "none"
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


def chat(messages, cfg, on_delta=None, should_stop=None, retries=2,
         usage_out=None):
    """调用 /chat/completions，返回纯文本。

    on_delta(str) 提供时走流式（SSE），否则一次性返回。
    should_stop() 返回 True 时中止。
    usage_out(dict) 提供时，非流式响应里的 usage 字段（token 用量）会填充进去，
    供调用方做成本台账；流式多数网关不返回 usage，此时保持空 dict。
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
                if usage_out is not None:
                    u = data.get("usage") if isinstance(data, dict) else None
                    if isinstance(u, dict):
                        usage_out.update(u)
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


# ────────────────────────── 成本台账（可观测） ──────────────────────────

USAGE_NAME = "llm-usage.jsonl"


def usage_path() -> Path:
    """用法台账位置：与配置同目录（跟用户走），追加式 JSONL。"""
    return user_config_dir() / USAGE_NAME


def log_usage(entry, usage_path_override=None):
    """追加一条用法记录（不覆盖）。entry 为 dict；失败静默（台账不阻断蒸馏）。

    记录字段：ts / model / phase / prompt_chars / completion_chars /
              prompt_tokens / completion_tokens / total_tokens
    台账是**本地可观测**，不是计费依据——工具不代付、不估单价。
    """
    try:
        import time as _time
        p = Path(usage_path_override) if usage_path_override else usage_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        e = dict(entry)
        e.setdefault("ts", _time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except Exception:
        pass


def usage_summary(usage_path_override=None) -> dict:
    """汇总台账：次数 / 累计 token / 累计字符（读不到或为空返回零值）。"""
    p = Path(usage_path_override) if usage_path_override else usage_path()
    n = p_tok = c_tok = p_chars = c_chars = 0
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                n += 1
                p_tok += int(e.get("prompt_tokens") or 0)
                c_tok += int(e.get("completion_tokens") or 0)
                p_chars += int(e.get("prompt_chars") or 0)
                c_chars += int(e.get("completion_chars") or 0)
        except Exception:
            pass
    return {"calls": n, "prompt_tokens": p_tok, "completion_tokens": c_tok,
            "total_tokens": p_tok + c_tok,
            "prompt_chars": p_chars, "completion_chars": c_chars}
