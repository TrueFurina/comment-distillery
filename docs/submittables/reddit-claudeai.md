# r/ClaudeAI 成稿

> 发帖位置：<https://www.reddit.com/r/ClaudeAI/>（Create Post → 标题+正文，正文直接贴 Markdown）
> 不要改写口吻；主动交代局限是刻意的，不是谦虚。

## 标题（原样复制）

```
I built a skill that turns comment sections into evidence-cited guides — and it caught its own hallucinated citations
```

## 正文（原样复制）

````markdown
**The hook:** we had an LLM write long citation-heavy analyses from comment-section data. The hallucinated citation IDs it produced were *format-perfect* — correct prefix, plausible length, right position in the sentence. Nobody could tell by reading. We only found them by scripting a set-difference against the corpus IDs: they simply didn't exist. This happened **twice** (1 in 96 citations, then 1 in 103), in both cases a single wrong digit deep in an index.

That bug is why this project exists.

**What it is:** [comment-distillery](https://github.com/TrueFurina/comment-distillery) — a Claude skill (MIT, zero third-party dependencies, pure stdlib) that distills a pile of crowd comments into a structured guide with: cited evidence for every claim, **mandatory counter-evidence** for every consensus, and an explicit "what we might be wrong about" section.

```bash
npx skills add TrueFurina/comment-distillery
```

There's also a Windows GUI exe (11 MB, no install, no API key) that handles collection → preprocessing → exporting a "distillation pack" (corpus + SKILL.md + paste-ready prompt). The distillation itself stays with your model: [site](https://truefurina.github.io/comment-distillery/) · [Release](https://github.com/TrueFurina/comment-distillery/releases/latest).

**3 design decisions that came from real failures, not taste:**

1. **Citation verification is a hard gate, not a suggestion.** `verify_citations.py` extracts every ID the guide cites and set-differences it against the corpus. Non-empty difference = the guide doesn't ship. The honest fallback is fewer citations, never a "plausible-looking" ID.

2. **Counter-evidence is mandatory.** We caught real consensus distortion: after deduplicating, 22% of one crawl (4,501 of 20,399 rows) were exact duplicates — the same opinion counted multiple times inflates "highly-liked = consensus" judgments. That's not a cosmetic bug, it's a wrong-conclusion generator.

3. **Reply threads are required, not optional.** On one video, fetching 6,724 nested replies forced us to revise 3 conclusions from the main thread. Counter-arguments, professional corrections, fact-checks — they live almost exclusively in the replies.

**What it is NOT (the honest part):**

- The verification gate checks citation *existence* and format. It does **not** check whether a conclusion is *correct*. A conclusion with a real citation but wrong reasoning passes every gate. This is written in `docs/retrospective.md` §7, not buried.
- All real-world corpora so far are from a single platform (Bilibili). Cross-platform validity is untested.
- Most rules are single-battle evidence; they're tagged as such and kept out of the "iron laws" section until replicated. There's a golden test set (8 cases / 4 categories, 31 mutation-tested graders) that currently measures *form and traceability*, not reasoning quality.

**The interesting meta-lesson:** across all our failures, the pattern was the same — using a proxy metric as a substitute for ground truth (like-count ↔ approval, text length ↔ thought, ID format ↔ citation validity, row count ↔ corpus size). Every one of those broke in a measurable way on ~47k real comments.

**Ask:** not stars. If you've worked on grounded synthesis from crowd text (L3-style: consensus + counter-evidence + blind spots), I'd genuinely like to hear how you handle the "conclusion is cited-but-wrong" problem. That's the gate we haven't solved.
````

## 发后备注（不贴进帖子）

- 最佳发帖时间：北京时间 20:00–24:00（北美上午）。
- 预期质疑与回答口径：
  - 「为什么只有 B 站」→ 已在正文局限段交代；回答时补一句「管道与平台解耦，采集器是 contrib 可选件，欢迎 PR 其他平台的桥接」。
  - 「这不就是总结器」→ 引正文第 1、2 点（机验门 + 反例强制）。
- 若被 Mod 删除：记录到 `docs/submittables/README.md` 状态列，**不换号重发**。
