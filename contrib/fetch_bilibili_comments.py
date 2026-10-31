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
import contextlib
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


class StopRequested(Exception):
    """用户请求停止，用来把采集从网络层快速掀翻。

    单独定义而不复用 KeyboardInterrupt：后者在服务线程里会变成一个
    没人接的异常，日志只留一行 traceback，用户以为程序崩了。
    """


def _sleep_cancellable(seconds, should_stop=None, tick=0.1):
    """限速用的 sleep，但能被停止请求打断。

    直接 time.sleep(0.6) 时，用户点「停止」最长要等这 0.6 秒才轮到下一次检查；
    看起来不多，但若限速值被调大、或夹在网络重试里，就会变成"点了停止还在跑"。
    分段睡 + 每次检查，最长响应时间压到 tick 级别。
    """
    end = time.time() + max(0.0, seconds)
    while True:
        left = end - time.time()
        if left <= 0:
            return
        if should_stop and should_stop():
            return
        time.sleep(min(tick, left))


def http_get_json(url, params=None, timeout=20, retries=3, should_stop=None):
    """带重试的 JSON GET。默认强制直连，规避被系统代理污染的 SSL 假死。

    should_stop() 返回 True 时立刻放弃本次重试（抛 StopRequested）。
    翻页动辄几百次请求，用户点了停止不该还得等一次 20 秒超时走完。
    """
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        if should_stop and should_stop():
            raise StopRequested()
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
                _sleep_cancellable(1.0 + attempt * 1.5 + random.uniform(0, 0.5),
                                   should_stop)
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


def get_meta(bvid):
    """取视频元信息里的规模线索，用来在采集前告诉用户"大概要等多久"。

    只读 view 接口的 stat.reply（评论+回复总数）。拿不到就返回空 dict——
    这只是一条体验优化，不该因为它失败就拦住采集。
    """
    try:
        data = http_get_json("https://api.bilibili.com/x/web-interface/view",
                             {"bvid": bvid})
        if data.get("code") != 0:
            return {}
        st = (data.get("data") or {}).get("stat") or {}
        return {"reply": int(st.get("reply") or 0),
                "view": int(st.get("view") or 0),
                "title": ((data.get("data") or {}).get("title") or "")[:60]}
    except Exception:
        return {}


def fetch_main(oid, mode=3, max_pages=0, on_page=None, should_stop=None):
    """拉全部一级评论。返回 list[dict(top-level reply json)]。

    注意：热度排序(mode=3)下点赞数实时变化，游标翻页会在相邻页之间产生重叠，
    同一条评论可能被抓到 2 次（实测 2 万条语料里约 22% 是纯重复行）。这里按
    rpid 去重，保证输出无重复。

    on_page(pages, got)  每翻完一页回调一次。翻页阶段总页数事先未知，
    没有这个回调时上层在这几分钟里**一个字都打不出来**，用户只能干瞪眼看
    一个静止的日志框——这也是"像卡死"的来源之一。

    should_stop()        返回 True 时在下一页之前收手，已抓部分照常返回。
    翻页本身要几分钟，只在外层"每条一级评论之间"检查是不够的：用户点了停止
    却还要干等好几分钟，和不能停没区别。
    """
    out = []
    seen = set()
    nxt = 1
    pages = 0
    while True:
        if should_stop and should_stop():
            print(f"  [stop] 翻页阶段收到停止请求，已取 {len(out)} 条")
            break
        params = sign({"oid": oid, "type": 1, "mode": mode, "next": nxt, "ps": 20})
        try:
            data = http_get_json("https://api.bilibili.com/x/v2/reply/wbi/main", params,
                                 should_stop=should_stop)
        except StopRequested:
            print(f"  [stop] 翻页阶段收到停止请求，已取 {len(out)} 条")
            break
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
        if on_page:
            on_page(pages + 1, len(out))
        cursor = data.get("data", {}).get("cursor", {}) or {}
        if cursor.get("is_end") or cursor.get("next") in (None, 0):
            break
        nxt = cursor.get("next")
        if not nxt or nxt <= 0:
            break
        pages += 1
        if max_pages and pages >= max_pages:
            break
        _sleep_cancellable(random.uniform(0.25, 0.6), should_stop)
    return out


def fetch_sub(oid, root_rpid, max_pages=50, max_retry=4, should_stop=None):
    """拉某条一级评论下的全部子回复。带指数退避重试，避免限流导致整体归零。

    should_stop() 返回 True 时立刻收手，返回已拉到的部分——单条讨论楼也可能
    有几十上百条回复，翻页同样不该无视停止请求。
    """
    out = []
    pn = 1
    while True:
        if should_stop and should_stop():
            break
        params = sign({"oid": oid, "type": 1, "root": root_rpid, "pn": pn, "ps": 20})
        data = None
        for attempt in range(max_retry):
            try:
                data = http_get_json("https://api.bilibili.com/x/v2/reply/reply", params,
                                     should_stop=should_stop)
                break
            except StopRequested:
                return out
            except Exception as e:
                if attempt < max_retry - 1:
                    _sleep_cancellable(2 ** attempt + random.uniform(0, 1), should_stop)
                else:
                    print(f"  [warn] sub root={root_rpid} pn={pn} 网络失败: {e}")
                    return out
        if data is None:
            return out
        code = data.get("code")
        if code != 0:
            # -412/-509 为限流，长休眠后重试；其余直接放弃该根
            if code in (-412, -509):
                _sleep_cancellable(5 + random.uniform(0, 3), should_stop)
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


class _CallbackWriter:
    """把 print 输出按行转给回调。

    用途：fetch_main / fetch_sub 内部用 print 输出告警（限流、翻页失败等）。
    与其去改动这两个算法的每一处 print（回归风险），这里用 redirect_stdout
    把它们的输出统一接进日志回调 —— 算法零改动。

    **必须防重入**：回调本身极可能也会 print（CLI 用法、或任何把日志打到
    控制台的 on_log）。若不设防，print → writer.write → emit → print →
    writer.write … 直接 RecursionError，采集在 1 秒内就崩，而且只在
    "回调会 print" 的用法下复现——Web 界面写日志是进内存列表，恰好躲开，
    属于典型的"换个调用方就炸"。
    """

    def __init__(self, emit):
        self._emit = emit
        self._buf = ""
        self._busy = False

    def write(self, s):
        if s is None:
            return
        if self._busy:
            # 回调正在处理中又产生输出：直接丢弃，避免自激递归
            return
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._safe_emit(line.rstrip())

    def _safe_emit(self, text):
        self._busy = True
        try:
            self._emit(text)
        finally:
            self._busy = False

    def flush(self):
        if self._buf.strip() and not self._busy:
            self._safe_emit(self._buf.rstrip())
        self._buf = ""

    def isatty(self):
        return False


def crawl(arg, out_csv, roots_only=False, on_log=None, on_progress=None, should_stop=None):
    """抓取 B 站视频评论并写 CSV —— CLI 与桌面 GUI 共用的单一入口。

    arg           BV 号或视频链接
    out_csv       输出 CSV 路径（utf-8-sig；列名与 prep.py 的字段别名对齐）
    roots_only    True = 只抓一级评论（规避子回复限流，快而稳）
    on_log(msg)   日志回调，默认 print
    on_progress(done, total, subs)  进度回调
    should_stop() 返回 True 时在两条一级评论之间优雅停止，已抓部分仍会正常写出

    返回 {bv, oid, n_top, n_sub, n_total, out_csv, stopped}
    无法解析 BV、或 view 接口失败时抛 RuntimeError。
    """
    log = on_log or (lambda m: print(m))
    writer = _CallbackWriter(log)

    bv = extract_bv(arg)
    if not bv:
        raise RuntimeError("无法从输入解析 BV 号（示例：BV1xx411c7mD 或 https://www.bilibili.com/video/BV.../）")
    oid = get_aid(bv)
    log(f"解析: {bv} -> aid {oid}")

    log("拉取一级评论（翻页中，这条最花时间）…")
    meta = get_meta(bv)
    if meta.get("reply"):
        # 实测：约 20 条主楼/页、每页 ~1 秒；主楼大约占总评论数的一半。
        # 先说清"大概几分钟"，用户才不会以为程序死了。
        # 实测校准（BV1o74y6XEcM，10,631 条 / 主楼 4,942 / 子回复 5,129）：
        #   只要主楼 213s（翻页）；含楼中楼 677s。估时按这两个锚点线性外推。
        est_pages = max(1, meta["reply"] / 2 / 20)
        paging_min = est_pages / 60.0                 # ≈ 50 页/分钟
        # 含楼中楼时，子回复约占 2/3 的墙钟时间（实测 677s 里 464s 在拉子回复）
        est_min = max(1, round(paging_min if roots_only else paging_min * 3.1))
        mode_txt = "只要主楼" if roots_only else "含楼中楼"
        log(f"该视频评论区共 {meta['reply']:,} 条（{mode_txt}），"
            f"预计翻 ~{int(est_pages)} 页、全程约 {est_min} 分钟；"
            "中途可点「停止」，已抓到的会保留")
    with contextlib.redirect_stdout(writer):
        mains = fetch_main(oid, mode=3,
                           on_page=lambda pages, got: log(
                               f"翻页 {pages} 页，累计 {got} 条主楼"),
                           should_stop=should_stop)
    writer.flush()
    log(f"一级评论数: {len(mains)}")
    if on_progress:
        on_progress(0, len(mains), 0)

    rows = []  # csv 行 dict
    total_sub = 0
    last_log = [time.time()]
    # 翻页阶段被打断也算 stopped：否则界面会拿半截语料报"✓ 抓到 N 条"
    stopped = bool(should_stop and should_stop())
    if stopped:
        # 翻页阶段就停了：mains 是**已经抓好**的那部分，必须全部写出去。
        # 早先这里直接进 for 循环、第一轮又撞上 should_stop，结果是
        # "抓了 1298 条、写出 0 条"——停止变成了白跑，比不能停更气人。
        log(f"翻页阶段已停止，保留已抓到的 {len(mains)} 条主楼并写出")
    for idx, r in enumerate(mains, 1):
        if should_stop and should_stop() and not stopped:
            stopped = True
            log(f"收到停止请求：已完成 {idx - 1}/{len(mains)} 条一级评论，正在写出已抓取的部分…")
            break
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
        rcount = r.get("rcount", 0)
        if roots_only:
            # 只抓一级评论模式：跳过子回复，规避限流、快速拿到观点主体
            if on_progress and (idx % 5 == 0 or idx == len(mains)):
                on_progress(idx, len(mains), total_sub)
            continue
        if stopped:
            # 用户已经喊停：只把主楼写完，不再去拉子回复。
            # 子回复是逐楼串行请求（每条约 1~2 秒），停下后还继续拉，
            # 等于"点了停止又跑了两分钟"，比不提供停止更让人恼火。
            if on_progress and idx == len(mains):
                on_progress(idx, len(mains), total_sub)
            continue
        # 拉子回复（仅讨论型楼中楼 rcount>=3，避免海量无效请求触发限流雪崩）
        if rcount and rcount >= 3:
            with contextlib.redirect_stdout(writer):
                subs = fetch_sub(oid, rpid, should_stop=should_stop)
            writer.flush()
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
            # 每条根之间随机休眠，平滑限速（可被停止请求打断）
            _sleep_cancellable(random.uniform(0.15, 0.5), should_stop)
        if on_progress and (idx % 5 == 0 or idx == len(mains)):
            on_progress(idx, len(mains), total_sub)
        # 按时间节流而不是按条数：含楼中楼时每条要 2~3 秒，"每 50 条"就是
        # 两分半才打一行，日志框照样像死了一样。
        if time.time() - last_log[0] >= 3.0:
            last_log[0] = time.time()
            log(f"进度 {idx}/{len(mains)} 条一级，已拉子回复 {total_sub} 条")

    # 写 CSV (utf-8-sig 让 Excel 正确显示中文)
    cols = ["评论ID", "根评论ID", "是否为回复", "评论内容", "点赞数", "回复数", "时间", "父评论ID", "用户ID"]
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    log(f"完成: 共 {len(rows)} 条 (一级 {sum(1 for x in rows if x['是否为回复'] == '否')} + 子回复 {total_sub}) -> {out_csv}")
    return {
        "bv": bv,
        "oid": oid,
        "n_top": sum(1 for x in rows if x["是否为回复"] == "否"),
        "n_sub": total_sub,
        "n_total": len(rows),
        "out_csv": out_csv,
        "stopped": stopped,
    }


def utf8_stdout():
    """stdout/stderr 切 UTF-8：Windows 控制台可能是 cp1252，print 中文会
    UnicodeEncodeError（实测 GitHub windows runner 因此整步失败）。
    桌面工具走 log 回调、不经 stdout，故只影响 CLI 用法。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    utf8_stdout()
    if len(sys.argv) < 2:
        print("用法: python fetch_bilibili_comments.py <BV号或链接> [out.csv] [--roots-only]")
        sys.exit(1)
    arg = sys.argv[1]
    out_csv = "bilibili_comments.csv"
    roots_only = False
    for extra in sys.argv[2:]:
        if extra == "--roots-only":
            roots_only = True
        else:
            out_csv = extra

    try:
        crawl(arg, out_csv, roots_only=roots_only)
    except RuntimeError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
