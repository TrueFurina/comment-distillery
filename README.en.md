# comment-distillery

> **Turn a pile of crowd text into an evidence-cited action guide.**

[![CI](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml/badge.svg)](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success.svg)](#quick-start)

**[中文文档](README.md)** · English

---

## What it is

An **Agent Skill + zero-dependency toolchain** that distills **a crowd's unstructured text about one topic** into an **evidence-cited, actionable cognitive structure**.

**Input** — comment exports, open-ended survey answers, interview transcripts, product feedback, issue threads, live-chat logs… any pile of "many people talking about the same thing".
**Output** — a thick Markdown guide: **frameworks + consensus vs. disagreement + counter-example hedging + citation provenance + action checklist + honest blind-spot disclosure**.

**It is not** a scraper, a sentiment pie chart, a word cloud, or a dashboard.

---

## What the output actually looks like

Excerpt from [`examples/sample_guide.md`](examples/sample_guide.md) (**synthetic corpus**: 26 items → 23 after denoising). Three things to notice: **every claim traces back to a concrete item**, **every consensus is paired with a counter-example**, and **it discloses where it might be wrong**.

```markdown
### Topic A: Is the learning curve a design flaw?

**Consensus side**
> "Beginners have to grasp three abstract concepts before their first
>  command runs. For non-technical users that's a walk-away-level
>  barrier." [src:c1006|score7|root]

**Counter-example hedge**
> "A steep curve isn't bad design. Much of the complexity in pro tools
>  is forced by real requirements. Hiding it just means users hit it
>  later — it doesn't disappear." [src:c1010|score58|reply]

Note: the most important framing in the whole thread has 2 points,
while the highest-scored item (842) is "lol first". That is the
"high score != high signal" problem, in the wild.
```

**Action checklist (excerpt)**

| When | Action |
|---|---|
| This week | Decide whether you're asking "worth learning?" or "worth switching?" — the answers can be opposites `[src:c1020\|score2\|root]` |
| This month | Assess maintainer sustainability (response latency, commit-frequency trend), not just the feature list `[src:c1012\|score4\|root]` |

**The blind spots it states about itself**

> - **Score bias**: score = what's easiest to upvote, not what most people agree with.
> - **Sample bias**: 23 items carry no statistical representativeness.
> - **Data nature**: synthetic — contains no real user content.

> Every `[src:…]` above is machine-checked against the corpus by `verify_citations.py` — **a non-empty diff blocks delivery**. That gate has caught 2 hallucinated citations in our own guides.

---

## Why another wheel?

Because this space has three layers, the first two are saturated, and the third is barely explored:

```
L1 Collection        L2 Summary              L3 Constructive synthesis
──────────────────   ─────────────────────   ───────────────────────────
MediaCrawler (60k★)  sentiment / word cloud  frameworks + consensus vs. debate
BilibiliCrawler      top topics / quotes     + counter-examples + citations
bbc-skill            …and that's it          + action checklist + blind spots
                                             ★ here
```

Existing tools stop at **"here's what everyone feels."** The questions that actually pay off are:

- What do people **agree** on? Where do they **split**? **What's the strongest opposing argument?**
- Which conclusion has 200 people behind it, and which one is just loud?
- **What should I do next?** Where am I **most likely to be wrong**?

Nobody does this systematically. This project does exactly this one jump — and *only* this jump. Collection and statistics are left to the mature ecosystem.

### How it differs

| Dimension | Existing L1/L2 tools | comment-distillery |
|---|---|---|
| Output | Dashboard / pie chart / summary | **Thick Markdown guide** |
| Core action | Count frequencies, score sentiment | Cluster → **extract frameworks** → consensus vs. debate → **counter-example hedging** → action checklist → **blind-spot disclosure** |
| Verifiability | Claims without sources | **Every claim traceable to a concrete item ID** |
| Stance | One-sided (the top comment wins) | **Mandatory counter-examples**; never one-sided |
| Honesty | Conclusions only | **Mandatory disclosure of four bias types** |
| Dependencies | Heavy stack | **Zero dependencies, stdlib only** |
| Platform coupling | Tied to one platform | **Platform-neutral**; readable by any agent |

---

## The three pillars

These separate this project from "yet another summarizer" — **never to be cut**:

1. **Counter-example hedging** — every stated consensus must carry the strongest opposing evidence. This has fired for real: after deep-reply threads were fetched, **4 replies directly overturned conclusions drawn from top-level comments alone**.
2. **Citation provenance** — every data-backed claim ends with `[src:item_id|weight:N|level]`. The guide becomes *a sourced insight from a crowd*, not *an AI summary*.
3. **Honest blind-spot disclosure** — survivorship bias, platform/population bias, ranking-algorithm bias, temporal-slice bias. Misreading is more dangerous than disbelief.

---

## Quick start

### Install into your agent (one command)

```bash
npx skills add TrueFurina/comment-distillery
```

Works with Claude Code / Cursor / Codex / Windsurf / Copilot and 40+ other agents (`vercel-labs/skills` resolves the install path automatically). Browse without installing: `npx skills add TrueFurina/comment-distillery --list`.

### Or use the scripts directly

**Zero dependencies — no `pip install` needed.** Python 3.8+ is enough.

```bash
git clone https://github.com/TrueFurina/comment-distillery.git
cd comment-distillery

# 1) Preprocess: corpus CSV -> ranked readable text + stats + id map
python scripts/prep.py examples/sample_corpus.csv out/

# 2) Read out/all_comments.txt (this is the AI's job, not the script's)

# 3) After writing the guide, hard-verify citation authenticity
python scripts/verify_citations.py your_guide.md examples/sample_corpus.csv
```

`prep.py` produces:

| File | Purpose |
|---|---|
| `all_comments.txt` | Ranked by weight, each item tagged `[ID \| weight \| level \| replies]` |
| `low_score_long.txt` | **Low-weight long-form** — the real signal zone (see below) |
| `stats.json` | scale / engagement / author diversity / time samples / signal phrases |
| `id_map.json` | `id → weight/level/replies`, **the basis for provenance** |

---

## Counter-intuitive finding: weight ≠ signal

Verified repeatedly on real corpora, and the reason `low_score_long.txt` exists:

> The highest-scored item is often occupied by **zero-information lowest-common-denominator content** — terminology explainers, memes, agreement, form complaints (wording / accent / looks / title phrasing). **The real cognitive frameworks hide in low-score long-form items.**

**Measured example** (5,052 comments on one video):

| Rank | Weight | Content | Nature |
|---|---|---|---|
| #1 | **12,317** | "discouraged means dispirited" | Zero-information explainer |
| Long tail | **4** | The key distinction between two layers of failure | ★ Most important framework in the whole corpus |
| Long tail | **2** | "Merit is a tool; meritocracy is a belief to be dismantled" | ★ Sharpest line |

So read in **two passes**: top-down through the head to anchor the emotional tone, **then script-filter the low-weight long-form** to mine real signal. Miss neither end.

---

## Supported corpora

Same pipeline, different input:

| Domain | Typical sources |
|---|---|
| Community comments | Bilibili, YouTube, Reddit, Zhihu, Xiaohongshu, Weibo |
| User research | Open-ended survey answers, interview transcripts, focus groups |
| Product feedback | App store reviews, NPS feedback, support tickets |
| Open source | GitHub issue / PR threads, Discourse |
| Team collaboration | Meeting notes, group-chat logs, retrospectives |
| Qualitative research | Open questionnaires, field notes, secondary text |
| Live chat / danmaku | Bullet-chat streams, live comments |

**Shared abstraction**: an unstructured collection of text produced by many people around one topic (or one stimulus). If it fits, the pipeline applies. If it doesn't (a single person's diary, purely objective data), don't force it.

---

## Canonical Corpus Format

Normalize any source into one table; everything downstream is identical:

```csv
id,text,parent_id,is_reply,score,reply_count,created_at,author_id,source
```

| Field | Meaning | Required |
|---|---|---|
| `id` | Unique identifier (provenance anchor) | ✅ |
| `text` | Body text | ✅ |
| `score` | Group endorsement (likes / upvotes) — **not ground truth** | recommended |
| `reply_count` | Reply count (used to find discussion threads) | recommended |
| `parent_id` / `is_reply` | Hierarchy | optional |
| `created_at` | Time (temporal-bias analysis) | optional |
| `author_id` | Author (**must never leak into output**) | optional |
| `source` | Source tag (when merging corpora) | optional |

**`id` + `text` alone is enough to run.** Field names are fuzzy-matched with CN/EN aliases — full table in [`docs/canonical-format.md`](docs/canonical-format.md).

> Platform neutrality isn't "writing a pile of adapters" — it's **confining the differences to the input layer** and keeping the core pipeline singular.

### Where does the corpus come from? — we don't collect it

Collection is its own mature ecosystem, and this project deliberately **does not rebuild it**. Pick an existing tool per platform, then map its export to the format above:

| Platform | Existing tools (as of 2026-09) |
|---|---|
| Bilibili | BilibiliCrawler (GUI), MediaCrawler, this repo's `contrib/` |
| YouTube | youtube-comment-downloader (MIT, no API key), youtube-comment-suite (GUI) |
| Reddit | PRAW / URS (official API; Pushshift and `.json` endpoints are dead) |
| Xiaohongshu · Douyin · Kuaishou · Weibo · Tieba · Zhihu | MediaCrawler (⚠️ **non-commercial license**) |
| Many platforms (agent-native) | Agent-Reach |

**Check two things before choosing**: license terms (MediaCrawler is explicitly non-commercial) and legal exposure (Reddit filed complaints over unauthorized scraping in 2025).
Full comparison, risk notes, and the "any tool → our format" mapping are in [`docs/collecting.md`](docs/collecting.md).

---

## The 6-step pipeline

```
1 Ingest        obtain the CCF CSV
      ↓
2 Prep          prep.py -> ranked text + stats + id map
      ↓
3 Read & Cluster  read every item (not just stats) -> cluster, tag consensus/debate
      ↓
4 Synthesize    counter-examples + provenance + blind spots (the three pillars)
      ↓
5 Emit          deep (default) / standard / minimal
      ↓
6 Verify        ⚠️ verify_citations.py — the diff set MUST be empty
```

**Step 6 is a hard gate, not advice.**

---

## On hallucinated citations: we caught our own

After writing a long guide, we diffed every cited ID against the corpus — and **caught 1 non-existent ID out of 96 citations**.

It was perfectly formatted (`c` + 12 digits), looked flawless, but did not exist. Without machine verification it would have stayed in the document looking "sourced" forever.

```bash
python scripts/verify_citations.py guide.md corpus.csv     # non-zero exit = fail
```

> **An honest downgrade is fewer citations — never a "looks-right" ID.**

---

## Using it inside an agent

`SKILL.md` is **platform-neutral** — no agent-specific tool calls are hardcoded, so Claude Code / Codex / Cursor / WorkBuddy / your own agent can all read and execute it.

```bash
cp -r comment-distillery ~/.claude/skills/     # adjust path to your agent
```

Then just say: *"analyze this comment CSV with comment-distillery"*.

---

## Layout

```
comment-distillery/
├── SKILL.md                 # ★ core: the full skill spec an agent reads
├── README.md / README.en.md
├── ROADMAP.md               # long-term plan (with exit criteria)
├── docs/
│   ├── canonical-format.md  # corpus format + full alias table
│   ├── collecting.md        # where corpora come from: per-platform tools
│   ├── domains.md           # adaptation guide per domain
│   ├── pipeline.md          # pipeline in detail
│   ├── retrospective.md     # ★ 7-run retrospective: 5 corrections, quantified heuristics, gates
│   ├── rule-provenance.md   # ★ provenance: which run validated which rule; 1-run evidence = "pending"
│   ├── overturned.md        # ★ overturned claims log (incl. what would overturn them again)
│   ├── distribution.md      # distribution playbook (copy-paste PR / post drafts)
│   └── compliance.md        # compliance & ethics
├── scripts/
│   ├── prep.py              # preprocessing (zero deps)
│   ├── verify_citations.py  # citation verification (hard gate)
│   └── check_rule_tags.py   # no "bare rules" gate for SKILL.md (with mutation self-test)
├── golden/                  # test set: 8 cases / 4 categories — did it actually get better?
│   ├── README.md
│   ├── cases/               # scenarios (pure data, JSON)
│   ├── graders.py           # grader
│   ├── run_golden.py        # runner: offline scoring / baseline / mutation test
│   └── replies/baseline/    # ideal replies (should score full marks)
├── contrib/                 # ⚠️ optional collection bridge; not core, unsupported
│   ├── README.md
│   └── fetch_bilibili_comments.py
├── examples/
│   └── sample_corpus.csv    # synthetic example (no real user data)
├── cases/                   # ★ seven real-world runs (artifacts only)
│   ├── README.md            # read first: directory numbering ≠ run numbering
│   ├── 01…04/               # runs 1–4: real corpus → deep-dive guide
│   ├── 05-mustwatch-math/   # runs 6+7: 15-chapter guide + 10-chapter addendum (3 claims corrected)
│   └── notes/               # design notes: rationale / open-source sprint roadmap
└── tests/                   # regression tests (run in CI)
```

> `cases/` ships **artifacts only** (the guides + design docs, 9 md files / 277 KB).
> Raw corpora and pipeline intermediates are **not published**, per [`docs/compliance.md`](docs/compliance.md) §2
> ("do not redistribute raw corpora").

---

## Compliance & ethics

By design this project is cleaner than collection tools — **no anti-bot code, no credentials, no rate-limit bypass** — so it can be MIT-licensed and adopted by companies.

Users must still:

- **Purpose**: personal study & research only; **no** commercial sentiment monitoring or bulk profiling.
- **Copyright**: original text belongs to its authors and the platform; output is opinion distillation only — **do not redistribute raw corpora**.
- **Privacy**: output must not contain personally identifiable information.
- **Collection**: respect platform ToS and `robots`; **no rate-limit bypass is provided**.

See [`docs/compliance.md`](docs/compliance.md).

---

## Roadmap

- [x] **v1** — 6-step pipeline, deep-by-default, provenance, counter-examples, blind spots, citation gate
- [x] **v1.1** — domain generalization: from "comments" to "any crowd text"; Canonical Corpus Format
- [x] **field validation** (7 runs / ~45k items) — the reply-layer (nested comments) study: 21,100 items on one video, and the supplement volume corrected 3 conclusions of the main guide
- [x] **v1.3** — golden test set: 8 cases / 4 categories, baseline scores 100, and 31 mutants prove the grader actually deducts (see [`golden/README.md`](golden/README.md))
- [ ] **v2** — adaptation examples for more domains (surveys / interviews / tickets)
- [ ] **v2** — cross-corpus aggregation (merge multiple sources on one topic)
- [ ] **v2** — real human-in-the-loop verification

Full plan with exit criteria: [`ROADMAP.md`](ROADMAP.md).
Methodology distilled from 7 runs: [`docs/retrospective.md`](docs/retrospective.md).

---

## Contributing

Issues and PRs welcome — especially **new domain adaptation examples** and **real-world pitfall notes**. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

```bash
python -m pytest tests/ -v
```

---

## License

[MIT](LICENSE) © 2026 comment-distillery contributors
