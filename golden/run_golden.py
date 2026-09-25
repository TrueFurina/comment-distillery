#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / golden / run_golden.py
跑分器 —— 编排：加载场景 → 取回复 → 判分 → 汇总 → 报告落盘。

三种模式：
  1) 离线判分（推荐，不绑定任何 CLI / 模型）
       python golden/run_golden.py --replies <dir>
     目录内每个场景的回复存为 <dir>/<case_id>.txt。缺失的场景记为 no_reply，
     **不计入总分**（避免"没跑"被静默当成 0 分）。

  2) 基线自测（场景集与 baseline 回复是否自洽）
       python golden/run_golden.py --baseline
     baseline 回复应当拿满分；拿不到说明场景设计或 baseline 写错了。

  3) 变异验证（判分器本身是否有效）
       python golden/run_golden.py --self-test
     对每个场景构造"故意违反"的变异体，验证分数必须下降（红线类必须归 0）。
     **变异体还能拿满分 = 判分器无效**，脚本以退出码 1 报错。

零依赖，仅标准库。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import graders  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent
RESULTS_DIR = GOLDEN_DIR / "results"
BASELINE_DIR = GOLDEN_DIR / "replies" / "baseline"


def collect_replies(cases, replies_dir):
    """返回 dict: case_id -> 文本。缺失的不进 dict。"""
    out = {}
    d = Path(replies_dir)
    for c in cases:
        p = d / f"{c['id']}.txt"
        if p.exists():
            out[c["id"]] = p.read_text(encoding="utf-8")
    return out


def run(cases, replies, base_dir=None):
    results, missing = [], []
    for c in cases:
        if c["id"] not in replies:
            missing.append(c["id"])
            continue
        results.append(graders.grade(c, replies[c["id"]], base_dir))
    return results, missing


def build_report(results, missing, mode, extra=None):
    agg = graders.aggregate(results)
    rep = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": mode,
        "total": agg["total"],
        "by_category": agg["by_category"],
        "n_cases": agg["n_cases"],
        "red_line_cases": agg["red_line_cases"],
        "no_reply": missing,
        "cases": [{"id": r["id"], "category": r["category"], "weight": r["weight"],
                   "score": r["score"], "passed": r["passed"], "total": r["total"],
                   "red_lines": r["red_lines"]} for r in results],
    }
    if extra:
        rep.update(extra)
    return rep


def save_report(rep, out_dir=None):
    d = Path(out_dir) if out_dir else RESULTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    name = f"{rep['mode']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p = d / name
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def print_report(rep):
    print(f"\n=== golden 跑分（{rep['mode']}）===")
    print(f"总分: {rep['total']} / 100   场景数: {rep['n_cases']}")
    for k, v in rep["by_category"].items():
        print(f"  {k:16s} {v['score']:6.1f}  ({v['cases']} 个场景)")
    if rep["red_line_cases"]:
        print(f"  ⚠️ 命中红线: {rep['red_line_cases']}")
    if rep["no_reply"]:
        print(f"  ⚪ 无回复（未计入）: {rep['no_reply']}")
    print("\n--- 明细 ---")
    for c in rep["cases"]:
        flag = "❌" if c["red_lines"] else ("✅" if c["score"] == 5 else "⚠️")
        print(f"  {flag} {c['id']:34s} {c['score']}/5  ({c['passed']}/{c['total']} 规则)")


# ── 变异验证 ──────────────────────────────────────────────────────────
def build_mutants(case, baseline):
    """
    从 baseline 派生"故意违反"的变异体。
    返回 [(label, mutated_text, expect)]，expect ∈ {"drop"（必须低于满分）, "zero"（必须 0 分）}
    """
    e = case.get("expect", {})
    mutants = []

    for kw in e.get("must_contain", []):
        if kw in baseline:
            mutants.append((f"删除 must_contain 关键词「{kw}」",
                            baseline.replace(kw, ""), "drop"))
    any_kws = e.get("must_contain_any") or []
    if any_kws:
        m = baseline
        for k in any_kws:
            m = m.replace(k, "")
        if m != baseline:
            mutants.append(("删除 must_contain_any 全部候选词", m, "drop"))
    for kw in e.get("must_not_contain", []):
        mutants.append((f"插入红线词「{kw}」", baseline + f"\n{kw}\n", "zero"))
    if e.get("citation_real"):
        m, n = re.subn(r"\[源\s*[:：]\s*([^\]\|｜\s,，;；\\]+)", "[源:c9999999", baseline, count=1)
        if n:
            mutants.append(("把首条引用 ID 替换为不存在的 c9999999", m, "zero"))
    # 注：regex_* 规则的变异无法通用构造（不知道该删哪段文本才能让它不命中），
    # 统一由 self_test() 记为 skipped，不在此处伪造变异体。
    return mutants


def self_test(cases, baseline_dir=None):
    baseline_dir = Path(baseline_dir) if baseline_dir else BASELINE_DIR
    failures, checked, skipped = [], 0, []
    per_case = []

    for c in cases:
        base_txt = graders.load_baseline_reply(c["id"], baseline_dir)
        if base_txt is None:
            failures.append(f"{c['id']}: 缺少 baseline 回复")
            per_case.append({"id": c["id"], "status": "no_baseline"})
            continue
        base_res = graders.grade(c, base_txt)
        if base_res["score"] != graders.MAX_SCORE:
            failures.append(
                f"{c['id']}: baseline 未拿满分（{base_res['score']}/5，"
                f"未过规则 {[d for d in base_res['details'] if not d[2]]}）")
            per_case.append({"id": c["id"], "status": "baseline_not_full",
                             "score": base_res["score"]})
            continue

        mutants = build_mutants(c, base_txt)
        if not mutants:
            skipped.append(c["id"])
        for label, mutated, expect in mutants:
            checked += 1
            r = graders.grade(c, mutated)
            if expect == "zero" and r["score"] != 0:
                failures.append(f"{c['id']}: 变异「{label}」应归 0，实得 {r['score']}")
            elif expect == "drop" and r["score"] >= graders.MAX_SCORE:
                failures.append(f"{c['id']}: 变异「{label}」应扣分，仍得满分")
        per_case.append({"id": c["id"], "status": "ok", "mutants": len(mutants)})

    for c in cases:
        if any(k in c.get("expect", {}) for k in ("regex_must_hit", "regex_must_not_hit")):
            skipped.append(f"{c['id']}（含 regex 规则，变异未自动构造）")

    return {"ok": not failures, "failures": failures,
            "mutants_checked": checked, "skipped": sorted(set(skipped)),
            "per_case": per_case}


def compare(a_path, b_path):
    a = json.load(open(a_path, encoding="utf-8"))
    b = json.load(open(b_path, encoding="utf-8"))
    ma = {c["id"]: c["score"] for c in a["cases"]}
    mb = {c["id"]: c["score"] for c in b["cases"]}
    rows = []
    for k in sorted(set(ma) | set(mb)):
        sa, sb = ma.get(k), mb.get(k)
        if sa is None or sb is None:
            continue
        if sa != sb:
            rows.append((k, sa, sb))
    print(f"\n=== 对比 ===")
    print(f"  {os.path.basename(a_path)}: {a['total']}")
    print(f"  {os.path.basename(b_path)}: {b['total']}")
    print(f"  总分变化: {round(b['total'] - a['total'], 1)}")
    if rows:
        print("  逐场景变化（负数为回归）:")
        for k, sa, sb in rows:
            mark = "🔻回归" if sb < sa else "🔺改善"
            print(f"    {mark}  {k:34s} {sa} → {sb}")
    else:
        print("  逐场景无变化")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="golden 跑分器（离线判分 / 基线自测 / 变异验证）")
    ap.add_argument("--replies", help="存放 agent 回复的目录（<case_id>.txt）")
    ap.add_argument("--baseline", action="store_true", help="用内置 baseline 回复跑分")
    ap.add_argument("--self-test", action="store_true", help="变异验证：判分器是否真的能扣分")
    ap.add_argument("--cases", default=None, help="场景目录（默认 golden/cases）")
    ap.add_argument("--out", default=None, help="报告输出目录（默认 golden/results）")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="对比两份报告")
    ap.add_argument("--no-save", action="store_true", help="不落盘，仅打印")
    args = ap.parse_args(argv)

    if args.compare:
        return compare(*args.compare)

    cases = graders.load_cases(args.cases)

    if args.self_test:
        st = self_test(cases)
        print(f"\n=== 变异验证 ===")
        print(f"  检查变异体: {st['mutants_checked']} 个")
        if st["skipped"]:
            print(f"  跳过（无法自动构造变异）: {st['skipped']}")
        if st["ok"]:
            print("  ✅ 全部变异体均被正确扣分——判分器有效")
            return 0
        print("  ❌ 判分器无效，以下变异体未被扣分：")
        for f in st["failures"]:
            print(f"    - {f}")
        return 1

    if args.baseline:
        replies = {c["id"]: t for c in cases
                   if (t := graders.load_baseline_reply(c["id"])) is not None}
        mode = "baseline"
    elif args.replies:
        replies = collect_replies(cases, args.replies)
        mode = "replies"
    else:
        ap.error("需指定 --replies / --baseline / --self-test / --compare 之一")
        return 2

    results, missing = run(cases, replies)
    if not results:
        print("[ERR] 没有任何场景拿到回复，无法跑分。", file=sys.stderr)
        return 2

    rep = build_report(results, missing, mode)
    print_report(rep)
    if not args.no_save:
        p = save_report(rep, args.out)
        print(f"\n报告已落盘: {p}")
    return 0 if not rep["red_line_cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
