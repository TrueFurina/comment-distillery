#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / contrib —— 「桥接」抓取脚本（纯标准库，零第三方依赖）。

⚠️ 本文件位于 contrib/，属于**非核心、可选、不在官方支持范围**的便利件。
   comment-distillery 的核心范围是 L3（把已有的群体文本蒸馏成指南），
   不包含采集。这个脚本只是让「只有视频链接、没有 CSV」的用户能快速上手。
   更推荐使用成熟采集工具（MediaCrawler / BilibiliCrawler / 平台导出）。
   使用者需自行承担合规责任，详见 contrib/README.md 与 docs/compliance.md。

定位：SKILL.md 主推用成熟采集工具导出 CSV。
本脚本是给「在用 agent 的人」的备选桥接——直接丢 BV 号/链接，
自动完成 WBI 签名、翻页、子回复拉全，输出与 prep.py 对齐的 CSV。

用法:
    python fetch_bilibili_comments.py <BV号或视频链接> [out.csv] [--roots-only]
    python fetch_bilibili_comments.py BV1xx411c7mD
    python fetch_bilibili_comments.py "https://www.bilibili.com/video/BV1o74y6XEcM/"

    --roots-only  只抓一级评论，跳过楼中楼子回复。
                  经验：子回复接口极易触发限流(-412/-509)，一旦被限流整体进度会
                  长期停滞；而一级评论才是有实质观点的主体。追求时效与稳定性时用它。

输出 CSV 列: 评论ID,根评论ID,是否为回复,评论内容,点赞数,回复数,时间,父评论ID,用户ID
（与 BilibiliCrawler 导出格式对齐，可直接喂 prep.py）

合规: 仅个人学习研究; 内置随机限速; 不提供任何绕过风控的选项。
"""

import sys
import os
import re
import json
import time
import gzip
import hashlib
import urllib.request
import urllib.parse
import csv
import random

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# WBI 混淆表
MIXIN_ENC = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
             33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
             26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
             20, 34, 44, 52]

# BV -> av 表
BV_TABLE = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
BV_TR = {BV_TABLE[i]: i for i in range(58)}
BV_S = [11, 10, 3, 8, 4, 6]
BV_XOR = 177451812
BV_ADD = 8728348608


def bv2av(bv):
    bv = bv.strip()
    # 算法用完整 12 位串（含 BV 前缀）索引，故不去除前缀
    if not bv.upper().startswith("BV"):
        bv = "BV" + bv
    h = 0
    for i in range(6):
        h += (BV_TR[bv[BV_S[i]]] ^ BV_XOR) * (58 ** i)
    return h - BV_ADD


# 强制直连 opener：绕开 Windows 注册表系统代理（Clash 等失效代理会污染
# urllib 默认的 getproxies()，表现为 SSL: UNEXPECTED_EOF_WHILE_READING 假死）。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_get_json(url, params=None, timeout=20, retries=3):
    """带重试的 JSON GET。默认强制直连，规避被系统代理污染的 SSL 假死。"""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with _OPENER.open(req, timeout=timeout) as r:
                data = r.read()
                enc = r.headers.get("Content-Encoding", "")
                if enc.lower() == "gzip":
                    data = gzip.decompress(data)
                return json.loads(data.decode("utf-8"))
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1.0 + attempt * 1.5 + random.uniform(0, 0.5))
    raise last


_wbi_cache = {}


def get_mixin_key():
    if "key" in _wbi_cache:
        return _wbi_cache["key"]
    nav = http_get_json("https://api.bilibili.com/x/web-interface/nav")
    wbi = nav.get("data", {}).get("wbi_img", {})
    img = wbi.get("img_url", "").split("/")[-1].split(".")[0]
    sub = wbi.get("sub_url", "").split("/")[-1].split(".")[0]
    raw = img + sub
    key = "".join(raw[MIXIN_ENC[i]] for i in range(64))[:32]
    _wbi_cache["key"] = key
    return key


def sign(params):
    key = get_mixin_key()
    params = dict(params)
    params["wts"] = int(time.time())
    items = sorted(params.items(), key=lambda kv: kv[0])
    query = urllib.parse.urlencode(items)
    params["w_rid"] = hashlib.md5((query + key).encode()).hexdigest()
    return params


def extract_bv(arg):
    m = re.search(r"BV[0-9A-Za-z]+", arg)
    return m.group(0) if m else None


def get_aid(bvid):
    """通过官方 view 接口取 aid（避免 bv2av 算法版本错配）。"""
    data = http_get_json("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid})
    if data.get("code") != 0:
        raise RuntimeError(f"view 接口失败 code={data.get('code')} msg={data.get('message')}")
    return int(data["data"]["aid"])


def fetch_main(oid, mode=3, max_pages=0):
    """拉全部一级评论。返回 list[dict(top-level reply json)]。

    注意：热度排序(mode=3)下点赞数实时变化，游标翻页会在相邻页之间产生重叠，
    同一条评论可能被抓到 2 次（实测 2 万条语料里约 22% 是纯重复行）。这里按
    rpid 去重，保证输出无重复。
    """
    out = []
    seen = set()
    nxt = 1
    pages = 0
    while True:
        params = sign({"oid": oid, "type": 1, "mode": mode, "next": nxt, "ps": 20})
        try:
            data = http_get_json("https://api.bilibili.com/x/v2/reply/wbi/main", params)
        except Exception as e:
            print(f"  [warn] main page {nxt} failed: {e}")
            break
        if data.get("code") != 0:
            print(f"  [warn] main code={data.get('code')} msg={data.get('message')}")
            break
        replies = data.get("data", {}).get("replies") or []
        if not replies:
            break
        fresh = 0
        for r in replies:
            rp = r.get("rpid")
            if rp in seen:
                continue
            seen.add(rp)
            out.append(r)
            fresh += 1
        if fresh == 0:
            # 整页都是重复 → 游标已重叠打滑，继续翻只会空转
            print("  [warn] 整页重复，提前结束翻页")
            break
        cursor = data.get("data", {}).get("cursor", {}) or {}
        if cursor.get("is_end") or cursor.get("next") in (None, 0):
            break
        nxt = cursor.get("next")
        if not nxt or nxt <= 0:
            break
        pages += 1
        if max_pages and pages >= max_pages:
            break
        time.sleep(random.uniform(0.25, 0.6))
    return out


def fetch_sub(oid, root_rpid, max_pages=50, max_retry=4):
    """拉某条一级评论下的全部子回复。带指数退避重试，避免限流导致整体归零。"""
    out = []
    pn = 1
    while True:
        params = sign({"oid": oid, "type": 1, "root": root_rpid, "pn": pn, "ps": 20})
        data = None
        for attempt in range(max_retry):
            try:
                data = http_get_json("https://api.bilibili.com/x/v2/reply/reply", params)
                break
            except Exception as e:
                if attempt < max_retry - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                else:
                    print(f"  [warn] sub root={root_rpid} pn={pn} 网络失败: {e}")
                    return out
        if data is None:
            return out
        code = data.get("code")
        if code != 0:
            # -412/-509 为限流，长休眠后重试；其余直接放弃该根
            if code in (-412, -509):
                time.sleep(5 + random.uniform(0, 3))
                continue
            return out
        replies = data.get("data", {}).get("replies") or []
        if not replies:
            break
        out.extend(replies)
        cursor = data.get("data", {}).get("cursor", {}) or {}
        if cursor.get("is_end"):
            break
        pn += 1
        if pn > max_pages:
            break
        time.sleep(random.uniform(0.2, 0.5))
    return out


def fmt_time(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
    except Exception:
        return str(ts)


def main():
    if len(sys.argv) < 2:
        print("用法: python fetch_bilibili_comments.py <BV号或链接> [out.csv]")
        sys.exit(1)
    arg = sys.argv[1]
    out_csv = "bilibili_comments.csv"
    roots_only = False
    for extra in sys.argv[2:]:
        if extra == "--roots-only":
            roots_only = True
        else:
            out_csv = extra

    bv = extract_bv(arg)
    if not bv:
        print("无法从输入解析 BV 号")
        sys.exit(1)
    oid = get_aid(bv)
    print(f"解析: {bv} -> aid {oid}")

    print("拉取一级评论...")
    mains = fetch_main(oid, mode=3)
    print(f"  一级评论数: {len(mains)}")

    rows = []  # csv 行 dict
    total_sub = 0
    for idx, r in enumerate(mains, 1):
        rpid = r.get("rpid")
        member = r.get("member", {}) or {}
        rows.append({
            "评论ID": f"c{rpid}",
            "根评论ID": f"c{rpid}",
            "是否为回复": "否",
            "评论内容": (r.get("content", {}) or {}).get("message", ""),
            "点赞数": r.get("like", 0),
            "回复数": r.get("rcount", 0),
            "时间": fmt_time(r.get("ctime")),
            "父评论ID": "",
            "用户ID": member.get("mid", ""),
        })
        # 拉子回复（仅讨论型楼中楼 rcount>=3，避免海量无效请求触发限流雪崩）
        rcount = r.get("rcount", 0)
        if roots_only:
            # 只抓一级评论模式：跳过子回复，规避限流、快速拿到观点主体
            continue
        if rcount and rcount >= 3:
            subs = fetch_sub(oid, rpid)
            total_sub += len(subs)
            for s in subs:
                sm = s.get("member", {}) or {}
                rows.append({
                    "评论ID": f"c{s.get('rpid')}",
                    "根评论ID": f"c{rpid}",
                    "是否为回复": "是",
                    "评论内容": (s.get("content", {}) or {}).get("message", ""),
                    "点赞数": s.get("like", 0),
                    "回复数": s.get("rcount", 0),
                    "时间": fmt_time(s.get("ctime")),
                    "父评论ID": f"c{r.get('parent', rpid)}",
                    "用户ID": sm.get("mid", ""),
                })
            # 每条根之间随机休眠，平滑限速
            time.sleep(random.uniform(0.15, 0.5))
        if idx % 50 == 0:
            print(f"  进度: {idx}/{len(mains)} 条一级, 已拉子回复 {total_sub}")

    # 写 CSV (utf-8-sig 让 Excel 正确显示中文)
    cols = ["评论ID", "根评论ID", "是否为回复", "评论内容", "点赞数", "回复数", "时间", "父评论ID", "用户ID"]
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"完成: 共 {len(rows)} 条 (一级 {len(mains)} + 子回复 {total_sub}) -> {out_csv}")


if __name__ == "__main__":
    main()
