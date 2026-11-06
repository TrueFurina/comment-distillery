#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端冒烟：用假 AI 跑通「蒸馏 → 机验 → 修复 → 报告」，不发真请求。

为什么要这个：真 Key 不能进 CI，而这条链路最容易坏的地方恰恰不是 HTTP，
而是**编排**——幻觉 ID 有没有被喂回模型、修完有没有重新验、未通过时
HTML 有没有被标红。这些用假模型才能稳定复现。

用法：
    python tests/smoke_distill.py            # 期望 PASS
    python tests/smoke_distill.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import core, distill, llm  # noqa: E402

FAKE_MODEL = "fake-1"

# 第一轮故意编两条不存在的 ID；第二轮（修复轮）换成真 ID。
ROUND1 = """# 测试指南

## 一、开场

这是一条真实评论 `[源:c1010|权重58|回复]`。

这条是编的 `[源:c999999999999|权重99|一级]`。

还有一条也是编的 `[源:c888888888888|权重88|回复]`。

## 二、请人工核对

以上引用需人工抽查。
"""

ROUND2 = """# 测试指南

## 一、开场

这是一条真实评论 `[源:c1010|权重58|回复]`。

这条原来编的引用已被删除。

还有一条也删了。

## 二、请人工核对

以上引用需人工抽查。
"""


def fake_chat(messages, cfg, on_delta=None, should_stop=None, retries=2,
              usage_out=None):
    if usage_out is not None:
        # 回填 token 用量，走通"成本可观测"钩子路径（非计费）。
        usage_out.update({"prompt_tokens": 1, "completion_tokens": 1,
                          "total_tokens": 2})
    prompt = messages[-1]["content"]
    if "不存在" in prompt and "校对员" in (messages[0].get("content") or ""):
        return ROUND2
    if on_delta:
        on_delta(ROUND1)
    return ROUND1


def main(argv):
    verbose = "-v" in argv
    fails = []

    def ck(cond, msg):
        print(("  OK   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    print("① 生成蒸馏包（样例语料）")
    tmp = tempfile.mkdtemp(prefix="cd-smoke-")
    pack = core.export_package(str(ROOT / "examples" / "sample_corpus.csv"),
                               tmp, "smoke", on_log=lambda m: None)
    ck(Path(pack["pack_dir"], "corpus_ccf.csv").exists(), "包内有 corpus_ccf.csv")
    ck(Path(pack["pack_dir"], "SKILL.md").exists(), "包内有 SKILL.md（方法论随包）")

    print("② build_prompt 是否真的带上了方法论与硬性规则")
    cfg = dict(llm.DEFAULTS, base_url="http://x/v1", api_key="sk-x",
               model=FAKE_MODEL, configured=True, missing=[])
    msgs = distill.build_prompt(pack["pack_dir"], cfg)
    sys_msg, user_msg = msgs[0]["content"], msgs[1]["content"]
    ck("三件套" in sys_msg or "反例对冲" in sys_msg, "system 里有方法论正文")
    ck("[源:" not in user_msg,
       "user 里没有任何可被机验误判的完整引用标记（示范也不行）")
    ck("dup_dropped" in user_msg, "user 提示先看 dup_dropped")
    ck("前排打卡" in user_msg or "c1001" in user_msg, "user 里带了真实语料")

    print("③ 超长语料降级：应压缩并显式声明省略")
    long_text = "x" * (cfg["max_corpus_chars"] + 5000)
    body, truncated = distill._compact(long_text, cfg["max_corpus_chars"])
    ck(truncated and "省略" in body, "超长时压缩且标注了省略")

    print("④ 跑 distill（假 AI 第一轮编 2 条幻觉）")
    real_chat = llm.chat
    llm.chat = fake_chat
    distill.llm_mod.chat = fake_chat
    try:
        def _verify(guide_path, corpus_csv):
            r = core.verify_guide(guide_path, [corpus_csv])
            return {"cited": len(r.get("cited") or []), "bad": list(r.get("bad") or [])}

        logs = []
        res = distill.distill(str(pack["pack_dir"]), cfg,
                              on_log=logs.append, verify_fn=_verify,
                              max_rounds=2)
        if verbose:
            print("\n".join("      " + x for x in logs))

        ck(res["rounds"] == 2, f"触发了修复轮（rounds={res['rounds']}）")
        ck(res["bad"] == [], f"修复后差集为空（bad={res['bad']}）")
        ck(res["passed"] is True, "passed=True")
        ck(res["cited"] >= 1, f"识别到真实引用（cited={res['cited']}）")

        guide = Path(res["guide_path"])
        ck(guide.exists(), "guide.md 已落盘")
        body = guide.read_text(encoding="utf-8")
        ck("c999999999999" not in body, "幻觉 ID 已从终稿移除")
        ck("c1010" in body, "真引用被保留")

        print("⑤ 出报告：HTML 应显示机验通过")
        html = core.emit_report(str(guide), None,
                                [str(Path(pack["pack_dir"], "corpus_ccf.csv"))])
        h = Path(html["out"]).read_text(encoding="utf-8")
        ck("机验通过" in h and '差集 <span class="n">0' in h,
           "HTML 页首标注机验通过、差集 0")
        ck(h.count('class="cite"') >= 1, "引用角标已渲染")
    finally:
        llm.chat = real_chat
        distill.llm_mod.chat = real_chat

    print("⑥ 未通过时必须拒绝交付（模拟修不动的模型）")
    distill.llm_mod.chat = lambda *a, **k: "# 还是错的\n\n`[源:c777777777777|权重1|一级]`\n"
    try:
        res2 = distill.distill(str(pack["pack_dir"]), cfg,
                              on_log=lambda m: None, verify_fn=_verify,
                              max_rounds=1)
        ck(res2["passed"] is False, "passed=False（修不动就不许说通过）")
        ck(res2["bad"], f"仍报告幻觉清单（{res2['bad']}）")
    finally:
        distill.llm_mod.chat = real_chat

    print("⑥b 机验没过时，上一轮的 report.html 必须被挪开")
    stale_dir = Path(pack["pack_dir"])
    (stale_dir / "report.html").write_text("<html>上一轮的旧报告</html>",
                                           encoding="utf-8")
    import app.webui as _webui
    moved = _webui._stale_report(str(stale_dir))
    ck(bool(moved) and Path(moved).exists(), "旧报告被改名保留（没删）")
    ck(not (stale_dir / "report.html").exists(),
       "原位已空——不会再被误当成本轮产物")

    print("⑦ 未配置 AI 时 core.distill_package 要说人话")
    old = core.llm_status
    core.llm_status = lambda: {"configured": False, "missing": ["api_key"]}
    try:
        real_app_root = core.app_root
        core.app_root = lambda: Path(tempfile.mkdtemp())
        try:
            core.distill_package(pack["pack_dir"])
            ck(False, "未配置时应抛错")
        except RuntimeError as e:
            ck("未配置 AI" in str(e), "报错信息含『未配置 AI』")
    finally:
        core.app_root = real_app_root
        core.llm_status = old

    print()
    if fails:
        print(f"FAIL {len(fails)} 项：")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
