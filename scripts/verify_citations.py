#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / verify_citations.py
引用真实性机验 —— 本项目的强制质量门。

背景：LLM 在写长指南时会生成"看似合理但实际不存在"的引用 ID（幻觉引用）。
这些 ID 格式完全正确、肉眼无法分辨，唯一可靠的发现方式是机器比对差集。

用法:
    python verify_citations.py <guide.md> <corpus.csv> [more.csv ...] [--field 评论ID] [--pattern REGEX]

规则:
    指南中被引用的 ID 必须全部存在于语料 ID 全集；差集为空才允许交付（退出码 0），
    否则打印所有幻觉 ID 并退出码 1。

引用识别:
    1) 结构化标记：[源:ID ...]  /  [源:ID|权重N|...]  —— 首选，取第一个分隔符前的 ID
    2) 兜底扫描：--pattern 指定的正则（默认同时尝试常见形态 c\\d{6,} 与纯长数字）

零依赖，仅标准库。
"""
import argparse
import csv
import os
import re
import sys

# 与 prep.py 保持一致的字段别名（只取 ID 相关）
ID_ALIASES = ["评论id", "comment_id", "commentid", "cid", "id", "评论编号", "条目id", "item_id"]

DEFAULT_PATTERNS = [r"c\d{6,}", r"\b\d{8,}\b"]


def load_ids(path, field=None):
    """读取语料 CSV 的全部 ID（编码容错）。

    field 显式给出时优先按该列名取；否则走别名自动识别。
    （注：--field 曾是空转参数——解析了却从未传下来，2026-09-26 修复。）
    """
    last_err = None
    for enc in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                names = list(reader.fieldnames) if reader.fieldnames else []
                col = None
                if field:                                 # 0) 显式指定优先
                    for n in names:
                        if n and n.strip().lower() == field.strip().lower():
                            col = n
                            break
                for c in ID_ALIASES:                      # 1) 精确优先
                    if col:
                        break
                    for n in names:
                        if n and n.strip().lower() == c.lower():
                            col = n
                            break
                if not col:                               # 2) 子串兜底
                    for c in ID_ALIASES:
                        if len(c) < 3:
                            continue
                        for n in names:
                            if n and c.lower() in n.lower():
                                col = n
                                break
                        if col:
                            break
                ids = set()
                if col:
                    for r in reader:
                        v = str(r.get(col, "")).strip()
                        if v:
                            ids.add(v)
                return ids, col
        except Exception as e:
            last_err = e
            continue
    raise last_err


def extract_cited(text, patterns):
    """从指南文本中抽取被引用的 ID 集合。"""
    cited = set()
    # 1) 结构化标记 [源:ID ...] —— 取 "源:" 后到第一个分隔符之间的内容
    #    字符类需排除反斜杠：markdown 表格内竖线必须转义，写作 [源:c123\|权重7\|一级]，
    #    若不排除会捕获到 "c123\"（多一个反斜杠）而误判为幻觉引用。
    for m in re.finditer(r"\[源\s*[:：]\s*([^\]\|｜\s,，;；\\]+)", text):
        cited.add(m.group(1).strip().strip("\\"))
    # 2) 兜底正则
    for p in patterns:
        for m in re.finditer(p, text):
            cited.add(m.group(0))
    return cited


def run(guide, corpora, field=None, patterns=None):
    """执行引用机验，返回结果 dict（不打印、不退出进程）。

    单一实现：CLI(main) 与桌面 GUI(app/core.py) 共用。
    返回键:
        real       语料 ID 全集(set)
        cited      指南中被引用的 ID 集合(set)
        bad       幻觉引用（有序 list）
        per_corpus [{path, n, col}]
        contexts   {pid: 上下文片段}
        patterns   实际生效的兜底正则
    文件不存在时抛 FileNotFoundError（由调用方决定怎么呈现）。
    """
    for c in corpora:
        if not os.path.exists(c):
            raise FileNotFoundError(f"语料不存在: {c}")
    if not os.path.exists(guide):
        raise FileNotFoundError(f"指南不存在: {guide}")

    real = set()
    per_corpus = []
    for c in corpora:
        ids, col = load_ids(c, field)
        real |= ids
        per_corpus.append({"path": c, "n": len(ids), "col": col})

    text = open(guide, encoding="utf-8").read()
    pats = patterns if patterns else DEFAULT_PATTERNS
    cited = extract_cited(text, pats)
    bad = sorted(i for i in cited if i not in real)

    contexts = {}
    for b in bad:
        m = re.search(re.escape(b), text)
        if m:
            s = max(0, m.start() - 60)
            contexts[b] = text[s:m.end() + 60].replace("\n", " ")

    return {
        "guide": guide,
        "real": real,
        "cited": cited,
        "bad": bad,
        "per_corpus": per_corpus,
        "contexts": contexts,
        "patterns": pats,
        "field": field,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="引用真实性机验（幻觉引用检测）")
    ap.add_argument("guide", help="待验的指南 markdown")
    ap.add_argument("corpora", nargs="+", help="一个或多个语料 CSV（引用必须来自它们的并集）")
    ap.add_argument("--field", default=None, help="指定语料中的 ID 列名（默认自动识别）")
    ap.add_argument("--pattern", action="append", default=None,
                    help="自定义兜底 ID 正则，可重复；默认 c\\d{6,} 与 \\b\\d{8,}\\b")
    args = ap.parse_args(argv)

    try:
        res = run(args.guide, args.corpora, args.field, args.pattern)
    except FileNotFoundError as e:
        print(f"[ERR] {e}", file=sys.stderr)
        return 2

    for c in res["per_corpus"]:
        print(f"[ok] {os.path.basename(c['path'])}: {c['n']} ids (列: {c['col']})")

    print(f"\n语料 ID 全集: {len(res['real'])}")
    print(f"指南引用 ID  : {len(res['cited'])}")
    print(f"幻觉引用     : {len(res['bad'])}")

    if res["bad"]:
        print("\n=== ❌ 幻觉引用（指南中引用了不存在于语料的 ID）===")
        for b in res["bad"]:
            ctx = res["contexts"].get(b)
            print(f"  {b}  … {ctx} …" if ctx else f"  {b}")
        print("\n请把这些 ID 替换为语料中真实存在的条目，或删除该条引用后重跑本脚本。")
        print("诚实的降级方式是减少引用条数，绝不是保留一个『看起来对』的 ID。")
        return 1

    print("\n=== ✅ 通过：所有引用均可在语料中溯源 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
