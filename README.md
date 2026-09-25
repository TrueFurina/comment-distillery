# comment-distillery · 评论蒸馏器

> **把一堆群体文本，炼成一份有据可查的行动指南。**
> Turn a pile of crowd text into an evidence-cited action guide.

[![CI](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml/badge.svg)](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success.svg)](#快速开始)

---

## 这是什么

一个 **Agent Skill + 零依赖工具链**，把**一群人对同一议题的自发文本**，蒸馏成**带引用溯源的、可行动的认知结构**。

输入：评论区导出、问卷开放题、访谈逐字稿、产品反馈、Issue 讨论、弹幕……任何"一群人七嘴八舌"的文本集合。
输出：一份厚 Markdown 指南——**认知框架 + 共识 vs 争议 + 反例对冲 + 引用溯源 + 行动清单 + 盲区诚实说明**。

**它不是**：爬虫、情感饼图、词云、舆情仪表盘。

---

## 为什么又要造一个轮子？

因为这条赛道的三层里，前两层已经卷完了，第三层几乎没人做深：

```
L1 采集            L2 统计摘要            L3 建设性综合
─────────────────  ────────────────────  ────────────────────────
MediaCrawler (6万★)  情感分布 / 词云 /      认知框架 + 共识vs争议
BilibiliCrawler      高频主题 / 几句金句    + 反例对冲 + 引用溯源
bbc-skill            …然后就没有然后了      + 行动清单 + 盲区说明
                                           ★ 这里
```

现有工具停在**「告诉你大家什么情绪」**。但真正值钱的问题是：

- 大家**共识**了什么？分歧在哪？**反方最强的论据是什么**？
- 哪条结论背后有 200 个人撑腰，哪条只是嗓门大？
- 我**接下来该做什么**？我可能会**错在哪**？

这些没人系统性地做。本项目补这一跳，且**只做这一跳**——采集和分析统计交给成熟生态，我们不重复造轮子。

### 与已有工具的区别

| 维度 | 现有 L1/L2 工具 | comment-distillery |
|---|---|---|
| 输出 | 仪表盘 / 饼图 / 摘要 | **厚 Markdown 指南** |
| 核心动作 | 统计频次、算情感 | 聚类 → **抽认知框架** → 共识 vs 争议 → **反例对冲** → 行动清单 → **盲区说明** |
| 可验证性 | 结论无出处 | **每条结论可溯源到具体条目 ID** |
| 立场 | 单向呈现（高赞说什么就是什么） | **强制反例对冲**，不输出一边倒 |
| 诚实性 | 只报结论 | **强制披露四类盲区** |
| 依赖 | 一堆重库 | **零依赖，纯标准库** |
| 平台耦合 | 绑定单一平台 | **平台中立**，可被任意 agent 读取 |

---

## 三件套护城河

这是本项目和"又一个摘要工具"的分水岭，**任何情况下不砍**：

1. **反例对冲** —— 每条共识必须配反方论据。在实测中，这条机制真实生效过：某次楼中楼补齐后，有 **4 条子回复直接推翻了基于顶层评论得出的结论**。
2. **引用溯源** —— 每条带数据的结论后附 `[源:条目ID|权重N|层级]`。指南从"AI 总结"变成"有依据的群体洞察"。
3. **盲区诚实说明** —— 主动披露**幸存者偏差、平台/人群偏差、权重算法偏差、时间切片偏差**。误读比不信更危险。

---

## 快速开始

**零依赖，不需要 `pip install`。** 只要 Python 3.8+。

```bash
git clone https://github.com/TrueFurina/comment-distillery.git
cd comment-distillery

# 1) 预处理：语料 CSV -> 按权重排序的可读文本 + 统计 + ID 映射
python scripts/prep.py examples/sample_corpus.csv out/

# 2) 通读 out/all_comments.txt（这一步是 AI 的活，不是脚本的活）

# 3) 写完指南后，强制机验引用真实性（防止幻觉引用）
python scripts/verify_citations.py 你的指南.md examples/sample_corpus.csv
```

`prep.py` 产出：

| 文件 | 用途 |
|---|---|
| `all_comments.txt` | 按权重降序、每条带 `[ID \| 权重N \| 层级 \| 复M]`，供通读 |
| `low_score_long.txt` | **低权重长文**——真信号区（见下方"反直觉发现"） |
| `stats.json` | 规模 / 互动 / 作者多样性 / 时间样本 / 信号词 |
| `id_map.json` | `id → 权重/层级/回复数`，**溯源的依据** |

---

## 反直觉发现：高权重 ≠ 高信号

这是本项目在真实语料上反复验证的一条铁律，也是 `low_score_long.txt` 存在的原因：

> 群体文本里，**最高分往往被零信息量的"最大公约数"占据**——词义科普、玩梗、附和、形式吐槽（用词/口音/长相/标题句式）。**真正的认知框架常藏在低分长文里。**

**实测实例**（某视频 5052 条评论）：

| 排名 | 权重 | 内容 | 性质 |
|---|---|---|---|
| 第 1 名 | **12317** | 「discouraged 是泄气的意思」 | 零信息量词义科普 |
| 藏在长尾 | **4** | 两层 discouraged 的关键区分 | ★ 全篇最重要的认知框架 |
| 藏在长尾 | **2** | 「优绩是手中的工具，优绩主义是需要被拆解的信仰」 | ★ 最锋利的一句 |

所以正确读法是**两段式**：先按权重降序通读头部锚定情绪基调，**再用脚本筛"低权重长文"捞真信号**。两头都不能漏。

---

## 支持的语料域

同一套流水线，换的只是输入：

| 域 | 典型来源 |
|---|---|
| 社区评论区 | B站、YouTube、Reddit、知乎、小红书、微博 |
| 用户研究 | 问卷开放题、访谈逐字稿、焦点小组 |
| 产品反馈 | 应用商店评论、NPS 反馈、客服工单 |
| 开源社区 | GitHub Issue / PR 讨论、Discourse |
| 团队协作 | 会议纪要、群聊记录、复盘文档 |
| 学术质性 | 开放式问卷、田野笔记、二手文本 |
| 直播弹幕 | 弹幕流、直播评论 |

**共性抽象**：一群人对同一议题（或同一刺激）产生的、尚未结构化整理的文本集合。符合这个抽象就适用；不符合（单人日记、纯客观数据）不要硬套。

---

## 统一格式（Canonical Corpus Format）

任何来源归一成同一张表，下游流水线完全一致：

```csv
id,text,parent_id,is_reply,score,reply_count,created_at,author_id,source
```

| 字段 | 语义 | 必需 |
|---|---|---|
| `id` | 唯一标识（溯源锚点） | ✅ |
| `text` | 正文 | ✅ |
| `score` | 群体认可度（赞/赞同/upvotes）—— **不是真值** | 推荐 |
| `reply_count` | 被回复数（用于筛讨论型深水区） | 推荐 |
| `parent_id` / `is_reply` | 层级结构 | 可选 |
| `created_at` | 时间（切片偏差分析） | 可选 |
| `author_id` | 作者（**产出中不得外泄**） | 可选 |
| `source` | 来源标记（多语料合并时区分） | 可选 |

**只要 `id` + `text` 两列就能跑**，其余字段有则更准。字段名容错，中英文/常见变体自动映射——完整的别名表见 [`docs/canonical-format.md`](docs/canonical-format.md)。

> 平台中立不等于"写一堆平台适配器"，而是**把差异关在输入层**，让核心流水线保持单一。

### 语料从哪来？——本项目不做采集

采集是一个独立且成熟的生态，本项目**刻意不重复造**。按语料域选现成工具，导出后对齐上面的格式即可：

| 平台 | 现成工具（截至 2026-09） |
|---|---|
| B站 | BilibiliCrawler（桌面 GUI）、MediaCrawler、本仓库 `contrib/` |
| YouTube | youtube-comment-downloader（MIT，免 API Key）、youtube-comment-suite（GUI） |
| Reddit | PRAW / URS（走官方 API；Pushshift 与 `.json` 端点已不可用） |
| 小红书·抖音·快手·微博·贴吧·知乎 | MediaCrawler（⚠️ **非商用许可**） |
| 多平台（agent-native） | Agent-Reach |

**选型前务必看两张表**：许可证差异（MediaCrawler 是明确非商用）与法律风险（Reddit 已在 2025 年就未授权抓取提起诉讼）。
完整的工具对比、风险提示与"任意工具 → 本项目格式"的映射方法，见 [`docs/collecting.md`](docs/collecting.md)。

---

## 6 步流水线

```
1 接入 Ingest      拿到 CCF CSV
        ↓
2 预处理 Prep      prep.py → 排序文本 + 统计 + ID 映射
        ↓
3 通读聚类        逐条真读（不是只看统计）→ 主题聚类 / 标注共识·争议·独立观点
        ↓
4 框架抽取        反例对冲 + 引用溯源 + 盲区说明（三件套）
        ↓
5 结构化输出      深度版（默认）/ 标准版 / 极简版
        ↓
6 验证 Verify     ⚠️ verify_citations.py 强制机验，差集必须为空
```

**第 6 步是硬门，不是建议。** 原因见下。

---

## 关于幻觉引用：我们抓过自己

写完长篇指南后，我们用脚本把指南里所有引用的 ID 与原始语料做差集比对——**在 96 条引用中揪出了 1 条根本不存在的 ID**。

那条 ID 格式完全正确（`c` + 12 位数字）、看起来毫无破绽，但语料里没有。如果没有机验，它会以"有出处"的样子永久留在文档里。

所以：

```bash
python scripts/verify_citations.py guide.md corpus.csv      # 退出码非 0 即为不合格
```

> **诚实的降级方式是减少引用条数，绝不是保留一个"看起来对"的 ID。**

---

## 在 Agent 里使用

`SKILL.md` 是**平台中立**的——不写死任何 agent 专属工具调用，Claude Code / Codex / Cursor / WorkBuddy / 自研 agent 都能直接读取执行。

```bash
# 以 Claude Code / 兼容 skills 的 agent 为例：放到 skills 目录即可
cp -r comment-distillery ~/.claude/skills/     # 路径按你的 agent 调整
```

然后直接说：*"用 comment-distillery 分析这份评论 CSV"* / *"把这些问卷开放题整理成指南"*。

---

## 目录结构

```
comment-distillery/
├── SKILL.md                 # ★ 核心：给 agent 读的完整技能说明
├── README.md / README.en.md # 人读的说明
├── docs/
│   ├── canonical-format.md  # 统一语料格式 + 字段别名全表
│   ├── collecting.md        # 语料从哪来：各平台现成采集工具对照
│   ├── domains.md           # 各语料域的适配指南
│   ├── pipeline.md          # 6 步流水线详解
│   └── compliance.md        # 合规与伦理边界
├── scripts/
│   ├── prep.py              # 预处理（零依赖）
│   └── verify_citations.py  # 引用真实性机验（强制质量门）
├── contrib/                 # ⚠️ 可选采集桥接，非核心、无支持
│   ├── README.md
│   └── fetch_bilibili_comments.py
├── examples/
│   └── sample_corpus.csv    # 合成示例语料（不含任何真实用户数据）
└── tests/                   # 回归测试（CI 自动跑）
```

---

## 合规与伦理（必读）

本项目的定位天然比采集类工具更干净——**没有反爬代码、不碰登录态、不提供绕过风控的选项**，因此可以直接 MIT 开源、可被企业采用。

但使用者仍需遵守：

- **用途**：仅限个人学习研究；**禁止**商业舆情监控、批量用户画像。
- **著作权**：原始文本归原作者与平台所有；产出仅为观点提炼，**不得二次分发原始语料**。
- **隐私**：产出中不得出现可识别个人身份的信息（真实姓名、账号、联系方式、精确位置）。
- **采集**：遵守目标平台服务条款与 `robots`；本项目**不提供任何绕过平台限制的选项**。

详见 [`docs/compliance.md`](docs/compliance.md)。

---

## 路线图

- [x] **v1** — 6 步流水线、深度版默认、引用溯源、反例对冲、盲区说明、引用机验
- [x] **v1.1** — 场景升维：从"评论"扩为"任何群体文本"，统一语料格式 CCF
- [ ] **v1.2** — 更多语料域的适配示例（问卷 / 访谈 / 工单）
- [ ] **v2** — 跨语料聚合（同一议题的多来源合并分析）
- [ ] **v2** — 真·人工校验 loop（关键结论的交互式确认）

---

## 贡献

欢迎 issue 与 PR——尤其是**新的语料域适配示例**和**真实的踩坑记录**。见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

提交前请确保：

```bash
python -m pytest tests/ -v
```

---

## License

[MIT](LICENSE) © 2026 comment-distillery contributors
