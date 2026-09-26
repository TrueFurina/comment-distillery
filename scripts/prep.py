#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / prep.py
预处理脚本：把任意群体文本语料 CSV 变成 AI 易读、可溯源的文本 + 统计 + ID 映射。

零依赖（仅 Python 标准库），跨平台。

用法:
    python prep.py <corpus.csv> [outdir] [--low-max 8] [--low-min-len 120]

产出 (outdir):
    all_comments.txt     - 按权重(score)降序，每条 "[ID | 权重N | 层级 | 复M]\\n内容"
    low_score_long.txt   - 低权重长文（真信号区），供"头部通读 + 精筛"两段式的第二段
    stats.json           - 规模/互动/时间样本/信号词/作者多样性
    id_map.json          - [{id, score, floor, reply}]，抽取阶段的溯源依据

字段名容错：中英文/常见变体自动映射（见 FIELD_ALIASES，完整说明见 docs/canonical-format.md）。
编码容错：utf-8-sig -> gb18030 -> gbk -> utf-8。
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

DEFAULT_LOW_MAX = 8        # 低权重阈值：score <= 此值
DEFAULT_LOW_MIN_LEN = 120  # 长文阈值：字符数 >= 此值
MIN_LEN = 4                # 去噪：正文短于此值直接丢弃

# 噪音词：广告/引流/联系方式（中英）
NOISE_KEYWORDS = [
    "加微信", "微信号", "私聊", "代做", "优惠", "秒到", "加我", "引流", "兼职刷",
    "点击链接", "扫码", "关注公众号", "telegram", "whatsapp", "dm me",
]

# 字段别名表：精确匹配优先，其次子串匹配（子串匹配时跳过 <3 字符的候选，避免 "id" 误命中 "用户id"）
FIELD_ALIASES = {
    "id": ["评论id", "comment_id", "commentid", "cid", "id", "评论编号", "条目id", "item_id"],
    "content": ["评论内容", "content", "text", "内容", "comment", "正文", "message", "body", "回复内容"],
    "score": ["点赞数", "likes", "like", "点赞", "赞", "score", "upvotes", "upvote",
              "赞同数", "赞同", "热度", "stars", "star"],
    "reply": ["回复数", "replies", "reply", "reply_count", "子评论数", "回复"],
    "time": ["发布时间", "时间", "created_at", "datetime", "timestamp", "date", "time", "创建时间"],
    "isrep": ["是否为回复", "is_reply", "isreply", "是否回复", "类型"],
    "uid": ["用户id", "userid", "uid", "author_id", "作者id", "author", "用户", "用户标识"],
    "parent": ["父评论id", "parent_id", "parentid", "父id", "根评论id", "root_id", "root_comment_id"],
    "source": ["source", "来源", "平台", "platform"],
}


def clean(text):
    return (text or "").strip()


def is_noise(text):
    t = text.strip()
    if len(t) < MIN_LEN:
        return True
    if re.fullmatch(r"[\W_]+", t):          # 纯符号 / 纯 emoji
        return True
    if re.fullmatch(r"https?://\S+", t):    # 纯链接
        return True
    low = t.lower()
    for kw in NOISE_KEYWORDS:
        if kw in low:
            return True
    return False


def load_rows(path):
    """编码容错地读取 CSV，返回 (rows, fieldnames)。"""
    last_err = None
    for enc in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                names = list(reader.fieldnames) if reader.fieldnames else []
            return rows, names
        except Exception as e:  # 尝试下一种编码
            last_err = e
            continue
    raise last_err


def map_field(names, key):
    """把逻辑字段映射到实际列名。精确匹配优先，其次子串匹配（候选需 >=3 字符）。"""
    cands = FIELD_ALIASES[key]
    for c in cands:                                   # 1) 精确匹配
        for n in names:
            if n and n.strip().lower() == c.lower():
                return n
    for c in cands:                                   # 2) 子串匹配（保守）
        if len(c) < 3:
            continue
        for n in names:
            if n and c.lower() in n.lower():
                return n
    return None


def to_int(v):
    try:
        return int(re.sub(r"\D", "", str(v or 0)) or 0)
    except Exception:
        return 0


def run(input_path, outdir, low_max=DEFAULT_LOW_MAX, low_min_len=DEFAULT_LOW_MIN_LEN):
    """执行完整预处理，返回 (stats, paths)。

    单一实现：CLI(main) 与桌面 GUI(app/core.py) 共用同一条逻辑，
    避免"两套实现各自漂移"——本项目对数字漂移零容忍。

    paths 键: all_comments / low_score_long / stats / id_map
    """
    os.makedirs(outdir, exist_ok=True)

    rows, names = load_rows(input_path)
    f_id = map_field(names, "id")
    f_content = map_field(names, "content")
    f_score = map_field(names, "score")
    f_reply = map_field(names, "reply")
    f_time = map_field(names, "time")
    f_isrep = map_field(names, "isrep")
    f_uid = map_field(names, "uid")
    f_source = map_field(names, "source")

    if not f_content:
        print(f"[warn] 未识别到正文列。实际列名: {names}", file=sys.stderr)

    recs = []
    for i, r in enumerate(rows):
        c = clean(r.get(f_content) if f_content else "")
        if not c:
            continue
        cid = clean(r.get(f_id)) if f_id else ""
        if not cid:
            cid = f"r{i}"
        isrep = str(r.get(f_isrep) if f_isrep else "").strip().lower() in (
            "1", "true", "yes", "是", "回复", "子",
        )
        recs.append({
            "id": cid,
            "content": c,
            "score": to_int(r.get(f_score) if f_score else 0),
            "reply": to_int(r.get(f_reply) if f_reply else 0),
            "time": clean(r.get(f_time) if f_time else ""),
            "floor": "回复" if isrep else "一级",
            "uid": clean(r.get(f_uid) if f_uid else ""),
            "source": clean(r.get(f_source) if f_source else ""),
        })

    raw = len(recs)

    # ---- 去重 ----
    # 抓取端分页游标重叠会产出「同 ID、同内容、同赞数」的完全重复行（实测某 2 万条
    # 语料中约 22% 的行是纯重复）。不去重会让「评论总数」「总赞数」虚高，并让同一条
    # 观点被重复计入共识度——后者对「高赞即共识」的判断是致命的。
    seen_ids = set()
    deduped = []
    dup_dropped = 0
    for x in recs:
        if x["id"] in seen_ids:
            dup_dropped += 1
            continue
        seen_ids.add(x["id"])
        deduped.append(x)
    recs = deduped

    recs = [x for x in recs if not is_noise(x["content"])]
    recs.sort(key=lambda x: -x["score"])

    # ---- 全量易读文本 ----
    txt_path = os.path.join(outdir, "all_comments.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for x in recs:
            f.write(f"[{x['id']} | 权重{x['score']} | {x['floor']} | 复{x['reply']}]\n{x['content']}\n\n")

    # ---- 低权重长文（真信号区）----
    low_long = [x for x in recs
                if x["score"] <= low_max and len(x["content"]) >= low_min_len]
    low_long.sort(key=lambda x: -len(x["content"]))
    low_path = os.path.join(outdir, "low_score_long.txt")
    with open(low_path, "w", encoding="utf-8") as f:
        f.write(f"# 低权重长文（权重<={low_max} 且 字数>={low_min_len}），按字数降序，共 {len(low_long)} 条\n\n")
        for x in low_long:
            f.write(f"[{x['id']} | 权重{x['score']} | {x['floor']} | 复{x['reply']}]\n{x['content']}\n\n")

    # ---- 统计 ----
    n = len(recs)
    score_sum = sum(x["score"] for x in recs)
    top = sorted(recs, key=lambda x: -x["score"])[:20]
    cn = re.findall(r"[一-鿿]{2,4}", "".join(x["content"] for x in recs))
    phrases = [w for w, _ in collections.Counter(cn).most_common(40)]
    uids = [x["uid"] for x in recs if x["uid"]]
    n_sub = sum(1 for x in recs if x["floor"] == "回复")
    stats = {
        "total_raw": raw,
        "dup_dropped": dup_dropped,
        "total_after_denoise": n,
        "n_top_level": n - n_sub,
        "n_reply": n_sub,
        "score_sum": score_sum,
        "score_mean": round(score_sum / n, 2) if n else 0,
        "score_max": max((x["score"] for x in recs), default=0),
        "reply_sum": sum(x["reply"] for x in recs),
        "n_low_score_long": len(low_long),
        "authors_unique": len(set(uids)),
        "authors_multi": sum(1 for _, c in collections.Counter(uids).items() if c > 1),
        "time_sample": [x["time"] for x in recs if x["time"]][:5],
        "top20": [{"id": x["id"], "score": x["score"], "floor": x["floor"],
                   "content": x["content"][:120]} for x in top],
        "top_phrases": phrases,
        # 兼容旧字段名，避免下游脚本断裂
        "like_sum": score_sum,
        "like_mean": round(score_sum / n, 2) if n else 0,
        "like_max": max((x["score"] for x in recs), default=0),
    }
    stats_path = os.path.join(outdir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # ---- ID 映射（溯源）----
    map_path = os.path.join(outdir, "id_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump([{"id": x["id"], "score": x["score"], "floor": x["floor"],
                    "reply": x["reply"]} for x in recs],
                  f, ensure_ascii=False, indent=2)

    # ---- 规范语料 CSV（Canonical Corpus Format）----
    # 下游（蒸馏包导出 / 引用机验 / 跨语料合并）都以它为单一真值源，
    # 不必再各自去猜原始 CSV 的列名与脏值。
    ccf_path = os.path.join(outdir, "corpus_ccf.csv")
    ccf_cols = ["id", "content", "score", "reply", "time", "floor", "uid", "source"]
    with open(ccf_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ccf_cols)
        w.writeheader()
        for x in recs:
            w.writerow({k: x[k] for k in ccf_cols})

    return stats, {
        "all_comments": txt_path,
        "low_score_long": low_path,
        "stats": stats_path,
        "id_map": map_path,
        "corpus_ccf": ccf_path,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="comment-distillery 预处理")
    ap.add_argument("input", help="语料 CSV 路径")
    ap.add_argument("outdir", nargs="?", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--low-max", type=int, default=DEFAULT_LOW_MAX,
                    help=f"低权重阈值，score<=此值视为低权重（默认 {DEFAULT_LOW_MAX}）")
    ap.add_argument("--low-min-len", type=int, default=DEFAULT_LOW_MIN_LEN,
                    help=f"长文阈值，字符数>=此值视为长文（默认 {DEFAULT_LOW_MIN_LEN}）")
    args = ap.parse_args(argv)

    stats, out = run(args.input, args.outdir, args.low_max, args.low_min_len)
    print(f"OK raw={stats['total_raw']} denoised={stats['total_after_denoise']} "
          f"(一级{stats['n_top_level']}/回复{stats['n_reply']}) "
          f"score_sum={stats['score_sum']} low_long={stats['n_low_score_long']}\n"
          f"   -> {out['all_comments']}\n   -> {out['low_score_long']}\n"
          f"   -> {out['stats']}\n   -> {out['id_map']}")


if __name__ == "__main__":
    main()
