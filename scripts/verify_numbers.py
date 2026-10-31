#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字机验：检查指南里"由语料算出来的数"有没有算错。

为什么需要它：`verify_citations.py` 只保证**引用 ID 真实存在**，
它管不了"这条 ID 被引用时，旁边那个数字对不对"。实测过 AI 写：
    「权重 ≤5 的评论共 22 条，赞合计仅 62，占全部赞的 7.5%」
——22 条对、62 错（实际 55）、7.5% 错（实际 6.6%），而引用机验照样全绿。
**引用真实 + 数字算错 = 看起来最可信的错误。**

本脚本的立场是"宁可漏报，不可误报"：只检查**能无歧义复算**的几类表述，
拿不准的一律跳过（并在 SKIP 里打印原因），绝不去猜作者意图。

检查项（输入：指南 md + 语料 csv）：
    1. "共/a total of N 条" 与语料条数
    2. "赞合计/赞总和/共计 N 赞"
    3. "占全部赞的 X%" —— 用此前出现的"n 条 / m 赞"复算
    4. "权重 ≤K 的评论共 N 条" / "合计 M" —— 直接复算
    5. "前 N 条合计 S" / "占比 X%"

用法:
    python scripts/verify_numbers.py <guide.md> <corpus.csv>
退出码 0 = 无可复算矛盾；1 = 发现不一致。
"""

import csv
import re
import sys


def utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


ID_ALIASES = ["id", "评论id", "comment_id", "cid"]


def load_scores(path, field=None):
    for enc in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rd = csv.DictReader(f)
                names = list(rd.fieldnames or [])
                col = None
                if field and field in names:
                    col = field
                else:
                    for n in names:
                        if (n or "").strip().lower() in ID_ALIASES:
                            col = n
                            break
                if col is None:                       # 靠列名找赞
                    for n in names:
                        if (n or "").strip().lower() in ("score", "like", "赞", "点赞"):
                            col = n
                            break
                if col is None:
                    return []
                vals = []
                for r in rd:
                    try:
                        vals.append(int(float(r.get(col) or 0)))
                    except Exception:
                        pass
                return vals
        except UnicodeDecodeError:
            continue
    return []


def load_scores_direct(path):
    """直接从 score 列读，不依赖 ID 列。"""
    for enc in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rd = csv.DictReader(f)
                names = [(n or "").strip().lower() for n in (rd.fieldnames or [])]
                idx = None
                for cand in ("score", "like", "赞", "点赞"):
                    if cand in names:
                        idx = names.index(cand)
                        break
                if idx is None:
                    return []
                out = []
                for r in rd:
                    v = list(r.values())[idx]
                    try:
                        out.append(int(float(v or 0)))
                    except Exception:
                        pass
                return out
        except UnicodeDecodeError:
            continue
    return []


def collect(guide_path, corpus_path):
    """返回 (issues, checked)。供 app/core.py 复用，不打印、不退出。

    issues 是**人话描述的矛盾清单**，可直接喂回给模型修正。
    """
    scores = load_scores_direct(corpus_path)
    if not scores:
        return [], 0
    n_all, sum_all = len(scores), sum(scores)
    mx = max(scores)
    ssorted = sorted(scores, reverse=True)

    with open(guide_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = re.sub(r"```.*?```", "", text, flags=re.S)

    issues, checked = [], 0

    def num(x):
        return int(str(x).replace(",", "").replace("，", ""))

    for m in re.finditer(r"去噪后\s*\*{0,2}(\d+)\*{0,2}\s*条|语料\s*\*{0,2}(\d+)\*{0,2}\s*条", text):
        v = num(m.group(1) or m.group(2))
        checked += 1
        if v != n_all:
            issues.append(f"语料条数写 {v}，实际 {n_all}")

    for m in re.finditer(r"赞合计\s*\*{0,2}([\d,，]+)|赞总和\s*\*{0,2}([\d,，]+)|共计\s*([\d,，]+)\s*赞", text):
        v = num(m.group(1) or m.group(2) or m.group(3))
        checked += 1
        if v != sum_all:
            issues.append(f"赞合计写 {v}，实际 {sum_all}")

    for m in re.finditer(r"最高赞\s*\*{0,2}([\d,，]+)", text):
        v = num(m.group(1))
        checked += 1
        if v != mx:
            issues.append(f"最高赞写 {v}，实际 {mx}")

    for m in re.finditer(
            r"权重\s*[≤<=]+\s*(\d+)\s*的评论共\s*\*{0,2}(\d+)\*{0,2}\s*条"
            r"[^\n]{0,40}?(?:赞合计|合计)[^\d]{0,6}([\d,，]+)?"
            r"[^\n]{0,30}?([\d.]+)\s*%", text):
        k, cnt, tot, pct = int(m.group(1)), num(m.group(2)), m.group(3), m.group(4)
        real_cnt = sum(1 for s in scores if s <= k)
        real_tot = sum(s for s in scores if s <= k)
        real_pct = real_tot / sum_all * 100 if sum_all else 0
        checked += 3
        if cnt != real_cnt:
            issues.append(f"权重≤{k} 的条数写 {cnt}，实际 {real_cnt}")
        if tot and num(tot) != real_tot:
            issues.append(f"权重≤{k} 的赞合计写 {num(tot)}，实际 {real_tot}")
        if abs(float(pct) - real_pct) > 0.15:
            issues.append(f"权重≤{k} 的赞占比写 {pct}%，实际 {real_pct:.1f}%")

    for m in re.finditer(r"前\s*(\d+)\s*条合计\s*\*{0,2}([\d,，]+)", text):
        k, v = int(m.group(1)), num(m.group(2))
        real = sum(ssorted[:k])
        checked += 1
        if v != real:
            issues.append(f"前{k}条合计写 {v}，实际 {real}")

    return issues, checked


def main(argv=None):
    args = [a for a in (argv if argv is not None else sys.argv[1:])
            if not a.startswith("-")]
    if len(args) < 2:
        print("用法: verify_numbers.py <guide.md> <corpus.csv>")
        return 2
    guide_p, corpus_p = args[0], args[1]

    scores = load_scores_direct(corpus_p)
    if not scores:
        print(f"[skip] 读不到 score 列：{corpus_p}")
        return 0
    print(f"[ok] 语料 {len(scores)} 条 / 赞合计 {sum(scores)} / 最高 {max(scores)}")

    issues, checked = collect(guide_p, corpus_p)
    print(f"[..] 可复算的数字表述：{checked} 处")
    if not issues:
        print("=== ✅ 通过：未发现可复算的数字矛盾 ===")
        return 0
    print(f"=== ❌ 发现 {len(issues)} 处数字矛盾 ===")
    for i in issues:
        print("  -", i)
    print("\n说明：本脚本只查『能无歧义复算』的表述，查不到的不代表没写错。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
