# r/LocalLLaMA 成稿

> 发帖位置：<https://www.reddit.com/r/LocalLLaMA/>（与 r/ClaudeAI 那篇**间隔至少 1 天**）
> 该社区对「不联网、不装包、不花钱」敏感；对营销味零容忍。

## 标题（原样复制）

```
I built a zero-dependency comment-mining toolkit (pure stdlib, no API keys) — it exports a corpus + prompt pack you can distill with any local model
```

## 正文（原样复制）

````markdown
**Short version:** [comment-distillery](https://github.com/TrueFurina/comment-distillery) is an MIT-licensed, pure-stdlib Python toolkit (3 scripts + a tkinter GUI) that takes a comment section, cleans it, and exports a "distillation pack": a deduplicated corpus + a rulebook (SKILL.md) + a paste-ready prompt. You then hand the pack to **whatever model you run** — local via ollama/llama.cpp, or an API if you prefer. The toolkit never needs a key and never calls an LLM.

```bash
npx skills add TrueFurina/comment-distillery   # agent use
# or: download the 11 MB single-file exe (no install, no Python needed)
```

[Site](https://truefurina.github.io/comment-distillery/) · [Release](https://github.com/TrueFurina/comment-distillery/releases/latest)

**Why split it this way:** the analysis is the part that benefits from your model of choice; the *collect-clean-verify* part is boring deterministic work that shouldn't depend on any provider. Keeping them separate also means the methodology (SKILL.md) is versioned in a repo, not frozen inside a binary — the exe always points at the current repo version.

**Why pure stdlib, seriously:** everything is `urllib` + `csv` + `json`. `pip install` isn't in the pipeline at all. 61 tests run on Python 3.10–3.13 in CI. This came from a real failure: an isolated venv broke on a setuptools source-build mid-upgrade, and that one incident made us commit to zero runtime dependencies. It also means you can read every line before running it.

**What the pipeline does:**

1. Collect comments (top-level + nested replies) — plain HTTP with WBI signing, dedup by comment ID, polite pacing.
2. Preprocess: encoding-tolerant load → dedup → denoise → weight by engagement → export stats (`dup_dropped`, per-ID map for provenance).
3. Verify: after your model writes its guide, `verify_citations.py` set-differences every cited ID against the corpus. Hallucinated citations = non-empty difference = the guide doesn't ship. We caught format-perfect hallucinated IDs twice this way (1/96 and 1/103 citations) — reading would never have caught them.
4. A golden eval set (8 cases / 4 categories, 31 mutation-tested graders) checks the graders themselves.

**Honest limitations (from the repo's own retrospective):**

- Verification covers citation *existence* and format only — a conclusion can be cited-but-wrongly-reasoned and pass. Unsolved, documented, not hidden.
- Real-world corpora so far are Bilibili-only; other platforms are untested (the collector is a separate optional module).
- The pack/prompt is model-agnostic by construction, but we've run distillation with hosted models, not yet benchmarked against local ones. If you run it with a local model, I'd like to hear how the rulebook holds up.

**Ask:** if you mine text with local models, I'm specifically interested in whether the "citation verification + mandatory counter-evidence" gates hold up as a harness for weaker models — does forcing evidence discipline improve output, or just make hallucination more pedantic? Repo and all battle notes (47k real comments, 5 overturned assumptions) are in the links.
````

## 发后备注（不贴进帖子）

- 与 r/ClaudeAI 那篇至少隔 1 天，避免被认成同一波 self-promo。
- 若有人问「模型无关的 pack 到底怎么用」：回答「导出的文件夹里有 corpus CSV、SKILL.md（方法论规则）和 PROMPT.md（可直接粘的提示词），粘给你本地模型或任意 agent 即可」，不展开营销。
- 本地模型实测数据（如果有人回了实测结果）记录到 `docs/distribution.md` §3 维护提醒。
