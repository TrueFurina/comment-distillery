#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 cookies_paste.txt 里的完整 Cookie 串写进 publish_config.local.json。

用法：
  1. 在 DevTools → Network → 刷新站点 → 复制任意请求的 `Cookie:` 请求头值
     （这一整串含 HttpOnly 登录态，分隔符是标准 ; ）
  2. 把三段分别写进 cookies_paste.txt，每行一个平台：
        csdn=<完整 Cookie 串>
        bilibili=<完整 Cookie 串>
        zhihu=<完整 Cookie 串>
  3. 运行：py scripts/apply_cookies.py
  脚本会校验关键登录态是否齐全，并写配置。

cookies_paste.txt 已被 .gitignore 屏蔽，不会入库。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "publish_config.local.json")
PASTE_PATH = os.path.join(ROOT, "cookies_paste.txt")

# 各平台「没有它就等于没登录」的必备 key
REQUIRED = {
    "csdn": ["UserToken"],
    "bilibili": ["SESSDATA", "bili_jct"],
    "zhihu": ["z_c0"],
}


def _cookie_keys(cookie: str):
    return {p.split("=", 1)[0].strip() for p in cookie.split(";") if "=" in p}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # 回退：从 publish.py 取默认配置
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cd_pub", os.path.join(ROOT, "scripts", "publish.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.default_config()


def main():
    if not os.path.exists(PASTE_PATH):
        print(f"找不到 {PASTE_PATH}")
        print("请先按脚本顶部说明创建该文件，每行一个平台：csdn=... / bilibili=... / zhihu=...")
        return 1

    cfg = load_config()
    pasted = {}
    with open(PASTE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print(f"  跳过无法解析的行：{line[:40]}...")
                continue
            plat, val = line.split("=", 1)
            plat = plat.strip().lower()
            val = val.strip()
            if plat in REQUIRED:
                pasted[plat] = val
            else:
                print(f"  忽略未知平台：{plat}（仅支持 csdn/bilibili/zhihu）")

    if not pasted:
        print("cookies_paste.txt 里没有任何 csdn/bilibili/zhihu 条目。")
        return 1

    all_ok = True
    for plat, cookie in pasted.items():
        keys = _cookie_keys(cookie)
        cfg.setdefault(plat, {})
        cfg[plat]["cookie"] = cookie
        cfg[plat]["enabled"] = True
        if plat == "zhihu":
            # 适配器优先用 cookie 里的 _xsrf，这里顺手同步配置字段
            for k in keys:
                if k == "_xsrf":
                    cfg[plat]["xsrf"] = _cookie_val(cookie, "_xsrf")
        missing = [k for k in REQUIRED[plat] if k not in keys]
        status = "OK" if not missing else f"缺登录态 {missing}"
        if missing:
            all_ok = False
        print(f"  {plat:9} 写入 {len(keys)} 个 key -> {status}")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {CONFIG_PATH}")
    if all_ok:
        print("✅ 三个平台登录态齐全，可直接跑：py scripts/publish.py <指南.md> --platform all")
    else:
        print("⚠️ 仍有平台缺登录态，发布会 401/404 或落本地草稿；请补齐对应 Cookie 串后重跑本脚本。")
    return 0


def _cookie_val(cookie, key):
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(f"{key}="):
            return part[len(key) + 1:]
    return ""


if __name__ == "__main__":
    sys.exit(main())
