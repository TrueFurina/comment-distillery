#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery · 蒸馏编排（BYO-AI 时才被调用）。

把"用户自己拿 AI 写指南"这件事自动化，但不改变它的性质：

    prompt = 仓库当前 SKILL.md（方法论） + 语料 + 硬性要求
             ↓  用户自己填的 endpoint/key
          指南 markdown
             ↓  verify_citations（既有脚本，不另写判据）
          差集 = 空 ? 交付 : 带着幻觉 ID 清单再修一轮（最多 N 轮）

关键设计取舍：

1. **方法论永远读磁盘上的 SKILL.md**，不在这里复制一份。否则二进制里会
   固化一个旧版本方法论，而用户以为自己在用最新规则——这正是本项目
   最不能接受的"口径漂移"。
2. **引用机验不是"顺便跑一下"**，而是闸门：差集非空就把幻觉 ID 喂回给模型
   让它改，改不动就**拒绝交付 HTML**（可以降级交 markdown，但必须标注未通过）。
   不做这一步的话，一键出报告等于批量生产不可验证的文档。
3. **不替用户决定"哪条结论对"**。这里只保证引用真实、结构齐全，不评判观点。

零第三方依赖，仅标准库。
"""

import json
import re
import time
from pathlib import Path

from . import llm as llm_mod

# 语料过长时的分卷阈值：单次请求塞不完就分块摘要，再合并。
# 这里的 120k 字符不是模型的硬上限，而是"再大就容易中途断流/超时"的工程值。
CHUNK_CHARS = 120000

STRUCTURE_HINT = """# 结构要求（8 章以上）

0. 开场结论（5 条以内，每条一句话能被引用）
1. 语料与读法（规模、口径、你怎么读的；诚实披露未读部分）
2. 口径与规模（先看 dup_dropped；数字以去重后为准）
3. 认知框架（把这个议题的底层机制抽象成 2-4 个互相咬合的环节）
4. 争议一（双方各自举证，写成"反方/正方"，不要替读者站队）
5. 争议二（同上；若语料只有一场真争议，这一章改成"被忽略的第三种声音"）
6. 反例对冲（每条共识配一条**逆向因果**反例，不是"也有例外"）
7. 可操作手册（按人群分册，每个动作必须有语料出处；写不出的不许编）
8. 盲区说明（幸存者/平台/算法/时间四类，逐条披露，说明它如何影响本文结论）
9. 元方法论（这份语料为什么能挖出东西、怎么复用、哪个尝试失败了）
10. 请人工核对的关键结论（3-5 条承重点 + 各自核对方式）
附录：方法与校验（语料规模、通读方式、引用机验命令）"""

HARD_RULES = """# 硬性要求（违反任一即为不合格）

1. **先看 dup_dropped，再信任何规模数字。** 不为 0 就说明上游有重复行，
   全文数字口径一律以去重后为准，并在正文说明。
2. **每条带数据的结论必须标引用**。写法是：一对英文方括号，里面依次是
   "源" 字、冒号、条目 ID、竖线、权重数字、竖线、层级（一级/回复）。
   例：一条权重 150 的一级评论，其标记形如 源:c316322377792 外加方括号。
   ID 必须逐字来自 `corpus_ccf.csv`，**不许凭印象补写**。
   引用少而真 > 多而假。宁可少写一条结论，也不要编一个"看起来对"的 ID。
3. **反例对冲**：每条共识都要配反方论据。找反例时优先找**逆向因果**
   （"这个相关性会不会是反的"），而不是"也有例外"——后者不削弱规律。
   语料一片和谐时，必须主动去楼中楼与低权重长文里开采，不能因为
   "没看到反例"就省略本章。
4. **权重不是可信度**。最高赞往往是零信息量的梗。要显式指出
   "高赞≠高信号"在本语料中的具体表现（举真实数字）。
5. **盲区诚实说明**：主动披露幸存者 / 平台人群 / 算法（点赞） / 时间四类偏差，
   并说明各自如何影响本文结论。
6. **涉及法律、医疗、金融事实的争议，只记录"评论区主张"，不做真伪判断**，
   并标注"本指南未核实"。
7. **凡做了转述而非直引之处，必须显式标注**（"按：此为转述"）。
8. **遇到圈内黑话或疑似错别字，先看包内 `GLOSSARY.md`，再决定怎么读。**
   不确定含义时**不要猜**，直接写「此处术语含义未确认」；明显错字注明「原文如此」，
   不要静默改正。**这条最容易出错且机验查不到**——引用 ID 是真的，理解错了照样算对。
9. 不要在正文里"展示引用格式"（比如写一段完整可用的示范标记做说明）——
   机验会把它当成真引用去语料里查，查不到就报幻觉。要说明规则时，
   把标记拆开用文字描述，别让它成为一段可被解析的完整标记。
"""


def _read(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def _compact(text, limit):
    """超长时保留头尾。头是最高赞（基调），尾是长尾（真信号）。"""
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.6)
    tail = limit - head
    return (text[:head]
            + f"\n\n……（此处省略 {len(text) - limit} 字符，完整语料见 corpus_ccf.csv）……\n\n"
            + text[-tail:]), True


def build_prompt(pack_dir, cfg, corpus_text=None):
    """组装 messages。语料过长时自动降级为"节选 + 明示省略"。"""
    pack = Path(pack_dir)
    skill = pack / "SKILL.md"
    stats = pack / "stats.json"
    corpus_csv = pack / "corpus_ccf.csv"

    methodology = _read(skill) if skill.exists() else ""
    raw = corpus_text if corpus_text is not None else (
        _read(pack / "all_comments.txt") if (pack / "all_comments.txt").exists() else "")

    # 黑话提示（可选）：有就带上，没有不影响任何流程。
    gloss = ""
    gp = pack / "GLOSSARY.md"
    if gp.exists():
        gloss = ("\n\n—— 术语与黑话提示（由工具生成，只作参考；不确定的词不要猜）——\n\n"
                 + _read(gp))

    limit = int(cfg.get("max_corpus_chars") or CHUNK_CHARS)
    body, truncated = _compact(raw, limit)

    st = {}
    if stats.exists():
        try:
            st = json.loads(_read(stats))
        except Exception:
            st = {}
    stat_line = ("原始 {total_raw} 行 / 去重丢弃 {dup_dropped} / 去噪后 {n} 条"
                 "（一级 {tl} · 楼中楼 {rp}）/ 赞合计 {ss}").format(
        total_raw=st.get("total_raw", "?"), dup_dropped=st.get("dup_dropped", "?"),
        n=st.get("total_after_denoise", "?"), tl=st.get("n_top_level", "?"),
        rp=st.get("n_reply", "?"), ss=st.get("score_sum", "?"))

    sys_msg = (
        "你是 comment-distillery 的执行者。你唯一的任务：把一批真实评论语料，"
        "蒸馏成一份带可机验引用、含反例对冲与盲区披露的深度指南。\n\n"
        "你会被一道机器检查卡住：文中所有 `[源:ID|...]` 里的 ID 都会与语料 ID 全集"
        "求差集，**差集必须为空**。编造 ID 会被打回重写。\n\n"
        "—— 以下是本项目的完整方法论，必须遵守 ——\n\n" + methodology
    )

    user_msg = (
        f"# 语料\n\n统计口径：{stat_line}\n\n"
        + ("⚠️ 语料过长，以下为**节选**（保留高赞头部与长尾）；"
           "被省略的部分确实存在，不要声称读了全文。\n\n" if truncated else
           "以下为全量语料。\n\n")
        + "```\n" + body + "\n```\n"
        + gloss + "\n\n"
        + HARD_RULES + "\n\n" + STRUCTURE_HINT + "\n\n"
        + f"语料 ID 全集共 {_count_ids(corpus_csv)} 个，全部在 corpus_ccf.csv 里。\n"
        + "直接输出 Markdown 全文，不要解释你在做什么，不要包 ``` 围栏。"
    )
    return [{"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg}]


def _count_ids(csv_path):
    try:
        import csv as _csv
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            return sum(1 for _ in _csv.DictReader(f))
    except Exception:
        return "?"


def repair_prompt(guide_text, bad_ids, corpus_csv, num_issues=None):
    """把幻觉 ID / 数字矛盾拎出来让模型自改——只改这两类，不许重写全文。"""
    num_issues = list(num_issues or [])
    ids = "\n".join(f"- {i}" for i in bad_ids[:80])
    more = "" if len(bad_ids) <= 80 else f"\n（另有 {len(bad_ids) - 80} 条未列出）"
    nums = "\n".join(f"- {i}" for i in num_issues[:40]) if num_issues else "（无）"

    # 把语料的真实统计直接给出来，避免模型二次算错
    stats = _corpus_stats(corpus_csv)

    parts = []
    if bad_ids:
        parts.append(f"A. 引用了 {len(bad_ids)} 个**语料中不存在**的 ID：\n\n{ids}{more}")
    if num_issues:
        parts.append(f"B. 有 {len(num_issues)} 处**数字算错**（下面已给出正确值）：\n\n{nums}")
    body = "\n\n".join(parts) if parts else "（无需修复）"

    return [
        {"role": "system",
         "content": "你是校对员。只做两件事：把不存在的引用 ID 换成语料里真实存在的 ID（或删掉），"
                    "把算错的数字改成正确值。不改观点、不改结构、不删章节。输出修正后的完整 Markdown。"},
        {"role": "user",
         "content": (
             f"{body}\n\n"
             f"语料真实统计（以此为准，不要再自己数）：\n{stats}\n\n"
             "处理规则：\n"
             "1. 不存在的 ID：换成真 ID（含正确权重与层级）；找不到就删掉该引用标记；"
             "整句只靠它支撑则删整句；\n"
             "2. 数字错误：直接改成上面给出的正确值，不要重算、不要改口径；\n"
             "3. 不许新编任何 ID；不许把 ID 改成相近数字来凑；\n"
             "4. 其余文字一字不动。\n\n"
             "—— 指南原文 ——\n\n" + guide_text
         )},
    ]


def _corpus_stats(corpus_csv):
    """给修复轮用的权威统计，避免模型二次算错。"""
    try:
        import csv as _csv
        with open(corpus_csv, encoding="utf-8-sig", newline="") as f:
            rows = list(_csv.DictReader(f))
        sc = []
        for r in rows:
            for k in ("score", "like", "赞", "点赞"):
                if k in r:
                    try:
                        sc.append(int(float(r[k] or 0)))
                    except Exception:
                        pass
                    break
        if not sc:
            return f"- 语料条数：{len(rows)}（读不到赞数列）"
        lines = [f"- 语料条数：{len(sc)}",
                 f"- 赞合计：{sum(sc)}",
                 f"- 均值：{sum(sc)/len(sc):.2f}",
                 f"- 最高：{max(sc)}",
                 f"- 中位数：{sorted(sc)[len(sc)//2]}"]
        for k in (5, 8, 10):
            sub = [s for s in sc if s <= k]
            pct = sum(sub) / sum(sc) * 100 if sum(sc) else 0
            lines.append(f"- 权重≤{k}：{len(sub)} 条，赞合计 {sum(sub)}，占全部赞 {pct:.1f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"（统计生成失败：{e}）"


def distill(pack_dir, cfg, on_log=None, on_delta=None, should_stop=None,
            verify_fn=None, max_rounds=None):
    """跑完"AI 写指南 → 机验 → 修复 → 再验"。

    verify_fn(guide_path, corpus_csv) -> {"cited": int, "bad": [ids...]}
    由调用方注入（core 里绑到 scripts/verify_citations.py），避免本模块
    反向依赖 core，保持可单测。

    返回 {"guide_path", "rounds", "cited", "bad", "passed", "elapsed"}
    """
    log = on_log or (lambda m: None)
    pack = Path(pack_dir)
    corpus = pack / "corpus_ccf.csv"
    if not corpus.exists():
        raise FileNotFoundError(f"蒸馏包里没有 corpus_ccf.csv：{pack}")

    rounds_cap = int(max_rounds if max_rounds is not None
                     else cfg.get("max_repair_rounds", 2))
    t0 = time.time()

    log(f"④ 蒸馏：调用 {cfg.get('model')} 生成指南"
        f"（方法论来自包内 SKILL.md，{len(_read(pack / 'SKILL.md')) if (pack / 'SKILL.md').exists() else 0} 字符）…")
    if on_delta:
        on_delta("\n--- AI 输出开始 ---\n")
    text = llm_mod.chat(build_prompt(pack, cfg), cfg,
                        on_delta=on_delta, should_stop=should_stop)
    text = llm_mod.strip_fence(text)
    if on_delta:
        on_delta("\n--- AI 输出结束 ---\n")

    guide = pack / "guide.md"
    guide.write_text(text, encoding="utf-8")
    log(f"   初稿 {len(text)} 字符 → {guide.name}")

    cited, bad, rnd, numfails = 0, [], 0, []
    nums_ok = False   # 数字复算是否真的执行过（False 时不许宣称数字无误）
    if verify_fn:
        for rnd in range(1, rounds_cap + 1):
            if should_stop and should_stop():
                log("   已停止：跳过后续修复轮")
                break
            log(f"⑤ 机验（第 {rnd} 轮）：引用与语料 ID 求差集…")
            v = verify_fn(str(guide), str(corpus))
            cited, bad = int(v.get("cited", 0)), list(v.get("bad") or [])
            # 「没有 num_issues」≠「数字都对」：core._verify() 在复算抛异常时
            # 会写 num_issues=[] 并附 num_error，空列表看起来像「没发现问题」，
            # 于是这里照样打印「数字复算无误」——真实假绿。
            v = v or {}
            num_err = str(v.get("num_error") or "").strip()
            nums_ok = ("num_issues" in v) and not num_err
            numfails = list(v.get("num_issues") or [])
            if not bad and not numfails:
                if nums_ok:
                    log(f"   ✅ 通过：{cited} 条引用，幻觉 0；数字复算无误")
                else:
                    log(f"   ✅ 引用通过：{cited} 条引用，幻觉 0")
                    log("   ⚠️ 数字复算未执行"
                        + (f"（{num_err}）" if num_err else "（校验器未返回 num_issues）")
                        + "，本次不宣称「数字无误」")
                break
            if bad:
                log(f"   ❌ {len(bad)} 条幻觉引用：{', '.join(bad[:6])}"
                    + ("…" if len(bad) > 6 else ""))
            if numfails:
                log(f"   ❌ {len(numfails)} 处数字矛盾：" + "；".join(numfails[:3]))
            if rnd == rounds_cap:
                break
            log(f"   让 AI 修第 {rnd} 轮（只改引用/数字，不动观点）…")
            fixed = llm_mod.chat(repair_prompt(text, bad, corpus, numfails), cfg,
                                 on_delta=None, should_stop=should_stop)
            text = llm_mod.strip_fence(fixed)
            guide.write_text(text, encoding="utf-8")
            log(f"   修正稿 {len(text)} 字符，已覆盖 {guide.name}")

    elapsed = round(time.time() - t0, 1)
    passed = (not bad and not numfails) if verify_fn else None
    if verify_fn and passed:
        tail = "数字复算无误" if nums_ok else "数字复算未执行（不宣称数字无误）"
        log(f"④⑤ 完成（{elapsed}s）：{cited} 条引用全部可溯源，{tail}")
    elif verify_fn and not passed:
        parts = []
        if bad:
            parts.append(f"{len(bad)} 条幻觉引用")
        if numfails:
            parts.append(f"{len(numfails)} 处数字矛盾")
        log(f"④⑤ 完成（{elapsed}s）但**未通过机验**：仍有 " + "、".join(parts or ["未知问题"])
            + "。该指南可以看，但不能算已验证交付。")

    return {"guide_path": str(guide), "rounds": rnd, "cited": cited,
            "bad": bad, "num_issues": numfails, "passed": passed,
            "elapsed": elapsed}
