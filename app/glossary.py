#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黑话/梗预检索（可选步骤）：给蒸馏前补一层"这人到底在说什么"。

## 为什么需要它

评论区的黑话会直接影响语义判断，而这类误判**机验抓不到**——引用 ID 全真，
只是理解错了。实测例子：一条评论写"勒夫有节目效果跟勒夫是出有什么矛盾吗"，
其中"是出"是"是畜"的输入法漏字（V 圈把 MCN 老板称"畜"是常用贬称）。
不懂这个梗，就会把整句读成病句或错别字，进而误判说话人的立场。

## 它做什么 / 不做什么

- 做：抽取**高频且可疑**的术语（圈内黑话、缩写、疑似错别字），
  生成一份"待解释清单"，随蒸馏包一起交给 AI；
- 不做：不自动上网查、不猜词义、不把猜测写进指南。
  猜测必须由用户在**可选的联网步骤**里触发（默认关闭）。

职责边界很重要：本步骤只负责**指出哪里可能有坑**，不负责填坑。
填错了比不填更糟——一个错的梗义会让整章论证跑偏，而且没有任何机验能发现。

零第三方依赖，仅标准库。
"""

import json
import re
from collections import Counter
from pathlib import Path

# 中文停用词与常规词：不当作"黑话候选"。刻意很短，只挡掉最明显的。
_STOP = set("""
的 了 是 在 有 和 就 都 而 及 与 着 或 一个 没有 我们 你们 他们 这个 那个 什么 怎么 为什么
可以 不是 还是 就是 但是 所以 因为 如果 虽然 已经 自己 现在 时候 问题 东西 事情 这样 那样
感觉 觉得 知道 认为 应该 可能 一定 真的 其实 然后 而且 虽然 不过 只是 还有 这么 那么
""".split())

CJK = re.compile(r"[\u4e00-\u9fff]{2,6}")
ALNUM = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,10}")


def _load_texts(pack_dir):
    p = Path(pack_dir) / "all_comments.txt"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("["):      # 跳过 [ID | 权重 | ...] 行
            continue
        out.append(line)
    return out


def candidates(pack_dir, min_count=3, top=40):
    """抽候选黑话：出现 ≥min_count 次、非停用词、长度 2–6 的词与英文缩写。

    这只是**候选**，不是词表。真黑话需要人来确认——脚本不做判断。
    """
    texts = _load_texts(pack_dir)
    if not texts:
        return {"terms": [], "note": "无可读语料"}

    cjk, alnum = Counter(), Counter()
    for t in texts:
        for w in CJK.findall(t):
            if w not in _STOP:
                cjk[w] += 1
        for w in ALNUM.findall(t):
            alnum[w.lower()] += 1

    terms = []
    for w, c in cjk.most_common(200):
        if c >= min_count:
            terms.append({"term": w, "count": c, "kind": "zh"})
    for w, c in alnum.most_common(100):
        if c >= max(2, min_count):
            terms.append({"term": w, "count": c, "kind": "en"})

    terms.sort(key=lambda x: -x["count"])
    return {"terms": terms[:top], "total_texts": len(texts),
            "note": "候选词，需人工确认哪些是真黑话"}


# 圈内缩写/黑话的高频嫌疑词。不追求全，只覆盖"不懂就一定读错"的那批。
JARGON_HINTS = {
    "v": "虚拟主播（VTuber）的简称；'V圈'=虚拟主播圈子",
    "皮套": "虚拟形象/虚拟主播本人（含贬义色彩）",
    "中之人": "皮套背后的真人演员",
    "同接": "同时在线观看人数（concurrent viewers）",
    "舰长": "B站直播间付费订阅档位（低于提督/总督）",
    "提督": "B站直播间较高档付费订阅",
    "总督": "B站直播间最高档付费订阅",
    "sc": "Super Chat，B站付费醒目留言",
    "爆米": "付费/打赏（米=钱）",
    "圈米": "赚粉丝的钱",
    "老头": "给主播大额打赏的中老年男性观众（圈内贬称）",
    "留子": "留学生（常被视为高付费群体）",
    "低气压": "主播情绪低落、对观众冷淡甚至发脾气的状态",
    "娘念": "用女性化声线念弹幕/台词",
    "训粉": "主播训斥粉丝",
    "热水器": "以软色情/擦边方式吸引流量",
    "转生": "换号或换皮重开直播",
    "毕业": "主播停止活动/退役",
    "塌房": "公众形象崩塌（私德/言行丑闻）",
    "开盒": "人肉搜索、曝光真实身份",
    "底边": "规模极小、几乎没人看的主播",
    "二游": "二次元风格手游",
    "虚环": "腾讯的虚拟主播题材企划/游戏",
    "cdd": "腾讯旗下虚拟偶像团队相关（评论区用法）",
    "tx": "腾讯（Tencent）的圈内缩写",
    "府": "指 MCN 老板'乐府'及其公会",
    "杏": "hololive（'Hololive'的圈内谐音简称）",
    "bu": "B站用户（Bilibili User）",
    "dd": "看多个主播的观众（'谁都推'）",
}

# 近音/形近但**语义会读错**的替换。只收真正会导致误判的，
# 不收"同一对象的两种叫法"（如 乐府/勒夫、炫狗/炫神）——那不是错字，
# 标出来只会让 AI 以为原文有问题。
HOMOPHONE_PAIRS = [
    ("是出", "是畜"),   # 实测：贬称"畜"被输入法打成"出"，按字面读就是病句
    ("虚幻", "虚环"),   # 把企划名写成"虚幻"，容易被误当成"虚幻引擎"
]

# 同一对象的多种称呼：不是错字，是圈内别称。单列出来，避免误报。
ALIAS_GROUPS = [
    ["乐府", "勒夫", "府子", "斧子", "府"],
    ["炫神", "炫狗", "选购"],
    ["虚环", "虚幻"],   # 注意：与上面的 HOMOPHONE_PAIRS 重叠时，以别名优先
    ["hololive", "杏", "holo"],
]


def scan_hints(pack_dir):
    """扫出语料里实际出现的黑话与可疑写法。只看"出现过的"，不做推断。"""
    texts = _load_texts(pack_dir)
    blob = "\n".join(texts)
    low = blob.lower()

    found = []
    for k, v in JARGON_HINTS.items():
        n = low.count(k)
        if n:
            found.append({"term": k, "count": n, "meaning": v})

    # 别名组里出现过的，先登记，避免被当成错字误报
    alias_seen = set()
    for grp in ALIAS_GROUPS:
        for a in grp:
            if low.count(a.lower()):
                alias_seen.add(a)
                alias_seen.add(a.lower())

    odd = []
    for a, b in HOMOPHONE_PAIRS:
        if a in blob and a not in alias_seen:
            odd.append({"seen": a, "likely": b,
                        "note": f"「{a}」可能是「{b}」的同音/形近写法（需按上下文确认）"})

    # 单条里连续重复同一**汉字**≥3（键盘/输入法打滑的典型痕迹）。
    # 限定汉字：数字/字母重复（如"1000""000"）通常是正常写法，不是打滑。
    for t in texts:
        for m in re.finditer(r"([\u4e00-\u9fff])\1{2,}", t):
            odd.append({"seen": m.group(0), "likely": "",
                        "note": f"疑似输入重复：{m.group(0)}（原文：{t[:40]}…）"})

    aliases = [g for g in ALIAS_GROUPS if any(a in blob for a in g)]

    return {"jargon": sorted(found, key=lambda x: -x["count"]), "odd": odd[:20],
            "aliases": aliases, "n_texts": len(texts)}


def glossary_md(pack_dir, extra_notes=None, min_count=3, top=40):
    """生成 GLOSSARY.md：黑话候选 + 可疑写法 + 人工补充的释义。"""
    h = scan_hints(pack_dir)
    info = candidates(pack_dir, min_count=min_count, top=top)

    L = ["# 术语与黑话提示（可选参考）", "",
         "> 由 comment-distillery 自动生成。**只提示，不做断言**。",
         "> 用途：避免把圈内黑话按字面读、把谐音错字当病句。",
         "> 原则：不确定的词**不要猜**，正文里标注「此处术语含义未确认」即可。",
         ""]

    if extra_notes:
        L += ["## 已知释义（人工提供，可直接采用）", ""]
        for k, v in extra_notes.items():
            L.append(f"- **{k}**：{v}")
        L.append("")

    L += [f"## 本语料出现的圈内术语（共 {h['n_texts']} 条语料）", ""]
    if h["jargon"]:
        L += ["| 词 | 次数 | 含义 |", "|---|---|---|"]
        for j in h["jargon"]:
            L.append(f"| `{j['term']}` | {j['count']} | {j['meaning']} |")
    else:
        L.append("（未命中内置词表）")
    L.append("")

    if h.get("aliases"):
        L += ["## 同一对象的多种叫法（不是错字）", "",
              "下列词在语料里混用，指同一对象。**不要**当成错别字或不同主体：", ""]
        for g in h["aliases"]:
            L.append("- " + " / ".join(f"`{x}`" for x in g))
        L.append("")

    L += ["## 可疑写法（可能被误读）", ""]
    if h["odd"]:
        for o in h["odd"]:
            L.append(f"- {o['note']}")
    else:
        L.append("（未发现明显可疑写法）")
    L.append("")

    L += ["## 高频候选词（未收录，自行判断）", "",
          f"出现 ≥{min_count} 次、但不在内置词表里的词：", ""]
    known = {j["term"] for j in h["jargon"]}
    rest = [t for t in info["terms"] if t["term"].lower() not in known][:25]
    if rest:
        L.append("、".join(f"`{t['term']}`×{t['count']}" for t in rest))
    else:
        L.append("（无）")
    L += ["", "## 给蒸馏者的三条纪律", "",
          "1. **宁可留空，不要编释义。** 一个错的梗义会让整章论证跑偏，且没有机验能发现。",
          "2. 遇到明显错别字（如把贬称写成同音字），正文注明「原文如此」，不要静默改正。",
          "3. 术语影响结论时，说明「若该词义为 A 则结论成立，为 B 则不成立」。"]
    return "\n".join(L) + "\n"


def write_glossary(pack_dir, extra_notes=None, min_count=3, top=40):
    p = Path(pack_dir) / "GLOSSARY.md"
    p.write_text(glossary_md(pack_dir, extra_notes, min_count, top),
                 encoding="utf-8")
    return str(p)
