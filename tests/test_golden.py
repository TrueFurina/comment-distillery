#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comment-distillery / tests / test_golden.py
golden 评估集的回归测试（CI 自动跑）。

本文件的核心不是"能跑通"，而是**判分器真的能扣分**：
测试全绿不等于有效——必须证明"故意违反的回复会被扣分"，否则整套评估是自欺。
因此包含变异验证的元测试。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "golden"))

import graders          # noqa: E402
import run_golden       # noqa: E402

CASES = REPO_ROOT / "golden" / "cases"
BASELINE = REPO_ROOT / "golden" / "replies" / "baseline"


class TestCaseSet(unittest.TestCase):
    def test_all_cases_load(self):
        cases = graders.load_cases(CASES)
        self.assertGreaterEqual(len(cases), 8)

    def test_four_categories_present(self):
        cats = {c["category"] for c in graders.load_cases(CASES)}
        self.assertEqual(cats, {"citation", "coverage", "counterevidence", "layering"})

    def test_every_case_has_rules_and_rationale(self):
        for c in graders.load_cases(CASES):
            with self.subTest(case=c["id"]):
                self.assertTrue(c["expect"], f"{c['id']} 无任何判定规则")
                self.assertTrue(c.get("rationale"), f"{c['id']} 缺理由说明")
                self.assertTrue(c.get("source"), f"{c['id']} 缺出处")

    def test_every_case_has_baseline_reply(self):
        for c in graders.load_cases(CASES):
            with self.subTest(case=c["id"]):
                self.assertIsNotNone(graders.load_baseline_reply(c["id"], BASELINE),
                                     f"{c['id']} 缺 baseline 回复")


class TestBaseline(unittest.TestCase):
    def test_baseline_scores_100(self):
        cases = graders.load_cases(CASES)
        replies = {c["id"]: graders.load_baseline_reply(c["id"], BASELINE) for c in cases}
        results, missing = run_golden.run(cases, replies)
        self.assertEqual(missing, [])
        rep = run_golden.build_report(results, missing, "baseline")
        self.assertEqual(rep["total"], 100.0)
        self.assertEqual(rep["red_line_cases"], [])


class TestGraderEffectiveness(unittest.TestCase):
    """判分器有效性：变异体必须被扣分。"""

    def test_self_test_passes(self):
        st = run_golden.self_test(graders.load_cases(CASES), BASELINE)
        self.assertTrue(st["ok"], f"判分器无效: {st['failures']}")
        self.assertGreaterEqual(st["mutants_checked"], 20)

    def test_hallucinated_id_scores_zero(self):
        """手工变异：把真实引用换成不存在的 ID，citation 场景必须归 0。"""
        cases = {c["id"]: c for c in graders.load_cases(CASES)}
        case = cases["citation-provenance"]
        base = graders.load_baseline_reply(case["id"], BASELINE)
        mutated = base.replace("[源:c1002", "[源:c9999999")
        r = graders.grade(case, mutated)
        self.assertEqual(r["score"], 0)
        self.assertTrue(any("幻觉引用" in str(x) for x in r["red_lines"]))

    def test_missing_citation_marker_scores_below_full(self):
        cases = {c["id"]: c for c in graders.load_cases(CASES)}
        case = cases["citation-provenance"]
        base = graders.load_baseline_reply(case["id"], BASELINE)
        mutated = base.replace("[源:", "（出处:")
        r = graders.grade(case, mutated)
        self.assertLess(r["score"], graders.MAX_SCORE)


class TestNoReplyHandling(unittest.TestCase):
    def test_missing_replies_not_counted_as_zero(self):
        """没跑的场景不能静默当 0 分——必须单列。"""
        cases = graders.load_cases(CASES)
        replies = {c["id"]: graders.load_baseline_reply(c["id"], BASELINE)
                   for c in cases if c["category"] != "layering"}
        results, missing = run_golden.run(cases, replies)
        rep = run_golden.build_report(results, missing, "replies")
        self.assertEqual(sorted(rep["no_reply"]),
                         sorted(c["id"] for c in cases if c["category"] == "layering"))
        # 剩余场景仍应满分——说明缺失项没有拉低总分（而不是被当成 0 分混入）
        self.assertEqual(rep["total"], 100.0)

    def test_empty_replies_dir_errors(self):
        with tempfile.TemporaryDirectory() as d:
            cases = graders.load_cases(CASES)
            results, _ = run_golden.run(cases, run_golden.collect_replies(cases, d))
            self.assertEqual(results, [])


class TestAggregation(unittest.TestCase):
    def test_weighted_total_math(self):
        results = [
            {"id": "a", "category": "x", "weight": 3, "score": 5,
             "passed": 1, "total": 1, "red_lines": []},
            {"id": "b", "category": "x", "weight": 1, "score": 0,
             "passed": 0, "total": 1, "red_lines": [("m", "x")]},
        ]
        agg = graders.aggregate(results)
        self.assertEqual(agg["total"], round(100.0 * (15 + 0) / (15 + 5), 1))
        self.assertEqual(agg["red_line_cases"], ["b"])

    def test_report_is_json_serializable(self):
        cases = graders.load_cases(CASES)
        replies = {c["id"]: graders.load_baseline_reply(c["id"], BASELINE) for c in cases}
        results, missing = run_golden.run(cases, replies)
        rep = run_golden.build_report(results, missing, "baseline")
        json.dumps(rep, ensure_ascii=False)     # 不可序列化会抛异常


if __name__ == "__main__":
    unittest.main()
