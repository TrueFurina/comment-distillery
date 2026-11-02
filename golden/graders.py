#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / golden / graders.py
判分器 —— 按规则类型给单个场景的 agent 回复打分。

设计要点（照搬 AGI-Distiller 的 golden 三分离原则，格式改为 JSON 以适应本项目的零依赖约束）：
  - 场景集是纯数据（golden/cases/*.json），可增删，不含逻辑；
  - 判分器只做判分，不关心回复是谁产生的；
  - 跑分器（run_golden.py）负责编排与落盘。

规则类型（每条规则独立计 1 分，红线命中则整场景 0 分）：
  must_contain        全部关键词必须出现
  must_contain_any    至少一个关键词出现
  must_not_contain    红线：任一禁词出现即整场景 0 分
  regex_must_hit      全部正则必须命中
  regex_must_not_hit  红线：任一正则命中即 0 分
  citation_real       引用机验：回复中被引用的 ID 必须全部存在于语料（复用 scripts/verify_citations.py）
  files_must_exist    相对 base_dir 的产物必须存在
  files_must_not_exist 红线：禁区产物不得存在
  inference_quality  推断质量判分（软扣分，无红线）：边界意识 / 盲区披露 / 数字锚定。
                     抓住"引用真实但推理空泛 / 过度泛化 / 无盲区意识 / 数字无来源"的回复，
                     弥补原评估集只判形式与可溯源的局限（golden/README.md 已知局限 #3）。

零依赖，仅标准库。
"""
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_citations as vc  # noqa: E402  复用引用机验，不重写

CASES_DIR = Path(__file__).resolve().parent / "cases"
REPLIES_BASELINE_DIR = Path(__file__).resolve().parent / "replies" / "baseline"

MAX_SCORE = 5

# ── 推断质量判分（inference_quality）───────────────────────────────────
# 设计意图：原评估集只能卡"形式与可溯源"（golden/README.md 已知局限 #3）——一条
# "引用真实但推理空泛 / 过度泛化 / 无盲区意识"的回复能拿满分。这里补一套**结构信号**
# 级的推断质量判分，全部软扣分、无红线，避免误伤真正高质量但措辞不同的指南。
# 这些是启发式（不调用模型），属"质量提示"而非"质量证明"，和整套评估集的定位一致。

# 边界 / 适用范围意识：好结论从不假装普适，会锚定到"这批样本"。
SCOPE_MARKERS = [
    "在这批样本", "在这批评论", "在这份语料", "本批", "本次采集",
    "样本中", "在我们的样本里", "这批数据", "针对本采集", "本批评论",
    "在本次", "本采集",
]

# 盲区 / 局限披露：好推断会明确"我没覆盖什么 / 不能推广到哪"。
BLIND_SPOT_MARKERS = [
    "局限", "盲区", "不代表", "未必普适", "无法推断", "样本偏差",
    "未涵盖", "不能推广", "谨慎看待", "存疑", "需注意", "不代表全部",
    "受样本限制", "未必适用", "不意味着", "不应推广",
]

# 数字锚定：若出现百分比，必须锚定到样本量 / 来源，防止无来源的精确数字。
ANCHOR_MARKERS = [
    "样本", "条评论", "条样本中", "基于", "据本批", "采集自", "语料中",
    "在这", "条数据", "本批的", "条评论中",
]

PERCENT_RE = re.compile(r"\d+(\.\d+)?\s*%")

# 数字比例主张：阿拉伯百分比 + 中文比例词（六成 / 三分之一 / 一半 / 百分之三十 等）。
# 统一视为"数字比例主张"，出现即必须锚定来源——补上 anchor_percentages 只认 '%'
# 漏掉中文比例词的口子（"约六成""三分之一的用户"同样是事实风险来源）。
NUMERIC_CLAIM_RE = re.compile(
    r"\d+(\.\d+)?\s*%"        # 31.9%
    r"|百分之\d+"              # 百分之三十
    r"|[一二两三四五六七八九]成"  # 六成 / 三成
    r"|三分之[一二]"             # 三分之一
    r"|三分之二"                # 三分之二
    r"|四分之三"                # 四分之三
    r"|一半"                   # 一半
)


def load_cases(cases_dir=None):
    """加载全部场景（cases/*.json，每文件一个数组）。按 category + id 排序保证稳定。"""
    d = Path(cases_dir) if cases_dir else CASES_DIR
    cases = []
    for p in sorted(d.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):          # 兼容单场景文件
            data = [data]
        for c in data:
            c.setdefault("weight", 1)
            c.setdefault("expect", {})
            c["_file"] = p.name
            cases.append(c)
    cases.sort(key=lambda c: (c.get("category", ""), c.get("id", "")))
    return cases


def _check_text_rules(expect, text):
    """返回 (passed, total, red_line_hits, detail_lines)。"""
    passed = 0
    total = 0
    red = []
    detail = []

    for kw in expect.get("must_contain", []):
        total += 1
        ok = kw in text
        passed += 1 if ok else 0
        detail.append(("must_contain", kw, ok, False))

    any_kws = expect.get("must_contain_any") or []
    if any_kws:
        total += 1
        ok = any(k in text for k in any_kws)
        passed += 1 if ok else 0
        detail.append(("must_contain_any", " | ".join(any_kws), ok, False))

    for kw in expect.get("must_not_contain", []):
        total += 1
        hit = kw in text
        if hit:
            red.append(("must_not_contain", kw))
            detail.append(("must_not_contain", kw, False, True))
        else:
            passed += 1
            detail.append(("must_not_contain", kw, True, False))

    for pat in expect.get("regex_must_hit", []):
        total += 1
        ok = re.search(pat, text) is not None
        passed += 1 if ok else 0
        detail.append(("regex_must_hit", pat, ok, False))

    for pat in expect.get("regex_must_not_hit", []):
        total += 1
        hit = re.search(pat, text) is not None
        if hit:
            red.append(("regex_must_not_hit", pat))
            detail.append(("regex_must_not_hit", pat, False, True))
        else:
            passed += 1
            detail.append(("regex_must_not_hit", pat, True, False))

    return passed, total, red, [d for d in detail if d]


def _check_files(expect, base_dir):
    passed = 0
    total = 0
    red = []
    detail = []
    for rel in expect.get("files_must_exist", []):
        total += 1
        ok = (Path(base_dir) / rel).exists()
        passed += 1 if ok else 0
        detail.append(("files_must_exist", rel, ok, False))
    for rel in expect.get("files_must_not_exist", []):
        total += 1
        hit = (Path(base_dir) / rel).exists()
        if hit:
            red.append(("files_must_not_exist", rel))
            detail.append(("files_must_not_exist", rel, False, True))
        else:
            passed += 1
            detail.append(("files_must_not_exist", rel, True, False))
    return passed, total, red, detail


def _check_citation(expect, text):
    """引用机验：差集必须为空。复用 verify_citations，不重写逻辑。"""
    spec = expect.get("citation_real")
    if not spec:
        return 0, 0, [], []
    corpus = spec.get("corpus")
    corpus_path = Path(corpus)
    if not corpus_path.is_absolute():
        corpus_path = REPO_ROOT / corpus
    if not corpus_path.exists():
        return 0, 1, [("citation_real", f"corpus 不存在: {corpus}")], [
            ("citation_real", f"corpus 不存在: {corpus}", False, False)]

    real, _ = vc.load_ids(str(corpus_path))
    patterns = spec.get("patterns", vc.DEFAULT_PATTERNS)
    cited = vc.extract_cited(text, patterns)
    bad = sorted(i for i in cited if i not in real)
    total = 1
    if bad:
        return 0, total, [("citation_real", f"幻觉引用 {bad}")], [
            ("citation_real", f"幻觉引用: {', '.join(bad)}", False, True)]
    return total, total, [], [("citation_real", f"{len(cited)} 条引用全部可溯源", True, False)]


def _check_inference_quality(expect, text):
    """推断质量判分：边界意识 / 盲区披露 / 数字锚定。

    返回 (passed, total, red, detail)。**全部软扣分、无红线**——不命中只是
    扣该子项分，不归零，以容忍真实高质量但措辞不同的指南（规避已知局限 #1 的误伤）。
    """
    spec = expect.get("inference_quality")
    if not spec:
        return 0, 0, [], []
    passed, total, red, detail = 0, 0, [], []

    # ① 边界 / 适用范围意识
    if spec.get("min_scope_markers"):
        total += 1
        n = sum(1 for m in SCOPE_MARKERS if m in text)
        if n >= spec["min_scope_markers"]:
            passed += 1
            detail.append(("inference_quality", f"边界意识标记×{n}（≥{spec['min_scope_markers']}）", True, False))
        else:
            detail.append(("inference_quality",
                           f"边界意识标记不足（{n}/{spec['min_scope_markers']}）——结论可能过度泛化", False, False))

    # ② 盲区 / 局限披露
    if spec.get("require_blind_spot"):
        total += 1
        hit = any(m in text for m in BLIND_SPOT_MARKERS)
        if hit:
            passed += 1
            detail.append(("inference_quality", "盲区/局限披露存在", True, False))
        else:
            detail.append(("inference_quality", "缺盲区/局限披露——未说明适用范围与不足", False, False))

    # ③ 数字锚定：出现数字比例（阿拉伯% 或中文比例词）则必须锚定来源
    if spec.get("anchor_percentages"):
        total += 1
        if NUMERIC_CLAIM_RE.search(text) is None:
            passed += 1
            detail.append(("inference_quality", "无数字比例，数字锚定自动通过", True, False))
        else:
            anchored = any(m in text for m in ANCHOR_MARKERS)
            if anchored:
                passed += 1
                detail.append(("inference_quality", "数字比例已锚定来源", True, False))
            else:
                detail.append(("inference_quality", "含数字比例但未锚定来源——可能是无来源的精确数字", False, False))
    return passed, total, red, detail


def grade(case, reply_text, base_dir=None):
    """
    给单个场景打分，返回 dict：
      score      0-5（红线命中为 0）
      passed/total  规则通过数
      red_lines  [(rule_type, evidence)]  命中的红线
      details    [(rule_type, target, ok, is_red)]
    """
    expect = case.get("expect", {})
    p1, t1, r1, d1 = _check_text_rules(expect, reply_text)
    p2, t2, r2, d2 = _check_citation(expect, reply_text)
    p3, t3, r3, d3 = _check_files(expect, base_dir or REPO_ROOT)
    p4, t4, r4, d4 = _check_inference_quality(expect, reply_text)

    passed, total = p1 + p2 + p3 + p4, t1 + t2 + t3 + t4
    red = r1 + r2 + r3 + r4
    details = d1 + d2 + d3 + d4

    if red:
        score = 0
    elif total == 0:
        score = MAX_SCORE          # 无规则的场景视为通过（场景设计问题由 self-test 兜住）
    else:
        score = round(MAX_SCORE * passed / total)

    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "weight": case.get("weight", 1),
        "score": score,
        "passed": passed,
        "total": total,
        "red_lines": red,
        "details": details,
    }


def aggregate(results):
    """加权百分制：Σ(score×weight) / Σ(5×weight) × 100。"""
    num = sum(r["score"] * r["weight"] for r in results)
    den = sum(MAX_SCORE * r["weight"] for r in results)
    total = round(100.0 * num / den, 1) if den else 0.0
    by_cat = {}
    for r in results:
        c = by_cat.setdefault(r["category"], {"num": 0, "den": 0, "n": 0})
        c["num"] += r["score"] * r["weight"]
        c["den"] += MAX_SCORE * r["weight"]
        c["n"] += 1
    cats = {k: {"score": round(100.0 * v["num"] / v["den"], 1) if v["den"] else 0.0,
                "cases": v["n"]}
            for k, v in sorted(by_cat.items())}
    return {"total": total, "by_category": cats,
            "n_cases": len(results),
            "red_line_cases": [r["id"] for r in results if r["red_lines"]]}


def load_baseline_reply(case_id, baseline_dir=None):
    d = Path(baseline_dir) if baseline_dir else REPLIES_BASELINE_DIR
    p = d / f"{case_id}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None


if __name__ == "__main__":
    # 自检：打印全部场景与其规则数，便于人工核对场景集是否退化
    for c in load_cases():
        e = c["expect"]
        n = sum(len(e.get(k, [])) for k in
                ("must_contain", "must_not_contain", "regex_must_hit", "regex_must_not_hit",
                 "files_must_exist", "files_must_not_exist")) \
            + (1 if e.get("must_contain_any") else 0) + (1 if e.get("citation_real") else 0)
        iq = e.get("inference_quality")
        if iq:
            n += sum(1 for k in ("min_scope_markers", "require_blind_spot", "anchor_percentages") if iq.get(k))
        print(f"{c['category']:16s} {c['id']:34s} weight={c['weight']} rules={n}")
