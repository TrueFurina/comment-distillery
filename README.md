# comment-distillery · 评论蒸馏器

> **把一堆群体文本，炼成一份有据可查的行动指南。**
> Turn a pile of crowd text into an evidence-cited action guide.

[![CI](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml/badge.svg)](https://github.com/TrueFurina/comment-distillery/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success.svg)](#快速开始)

**三条入口，按你的习惯挑一条：**

| 你是 | 做什么 |
|---|---|
| 不想碰命令行 | **⬇ [下载 Windows 桌面工具](https://github.com/TrueFurina/comment-distillery/releases/latest)**（~11 MB · 免安装 · **连 Python 都不用装**） |
| 已经在用 AI Agent | `npx skills add TrueFurina/comment-distillery`（Claude Code / Cursor / Codex / Copilot 等 40+ 家） |
| 想看它到底产出什么 | **[🌐 官网](https://truefurina.github.io/comment-distillery/)** · 或直接读下面的[真实产出节选](#真实产出长什么样) |

---

## 这是什么

一个 **Agent Skill + 零依赖工具链**，把**一群人对同一议题的自发文本**，蒸馏成**带引用溯源的、可行动的认知结构**。

输入：评论区导出、问卷开放题、访谈逐字稿、产品反馈、Issue 讨论、弹幕……任何"一群人七嘴八舌"的文本集合。
输出：一份厚 Markdown 指南——**认知框架 + 共识 vs 争议 + 反例对冲 + 引用溯源 + 行动清单 + 盲区诚实说明**。

**它不是**：爬虫、情感饼图、词云、舆情仪表盘。

---

## 真实产出长什么样

下面是 [`examples/sample_guide.md`](examples/sample_guide.md) 的节选（**合成语料**：26 条 → 去噪后 23 条）。看三件事：**每条结论可回溯到具体条目**、**每条共识都配反例**、**结尾主动交代自己哪里可能错**。

```markdown
### 议题 A：学习成本是不是设计缺陷

**共识侧**
> 「新手要先理解三个抽象概念才能跑起来第一条命令，这个门槛对非
>   专业用户是劝退级别的」 [源:c1006|权重7|一级]

**反例对冲**
> 「门槛高不等于设计差，很多专业工具的复杂度是被真实需求逼出来
>   的。把复杂度藏起来只是推给用户更晚发现，而不是真的消失了」
>   [源:c1010|权重58|回复]

💡 那条最关键的框架只有 2 分，而权重最高（842）的是「前排打卡哈哈哈」
   —— 这正是「高权重 ≠ 高信号」的现场证据。
```

**行动清单（节选）**

| 时间 | 行动 |
|---|---|
| 本周 | 先明确你要回答的是"值不值得学"还是"值不值得换"——两个问题的答案可以完全相反 `[源:c1020\|权重2\|一级]` |
| 本月 | 评估维护者可持续性（响应周期、提交频率趋势），别只看功能表 `[源:c1012\|权重4\|一级]` |

**它主动交代的盲区**

> - **权重偏差**：权重 = 最易被点赞的表达，不是最多人认同的立场。
> - **规模偏差**：23 条样本不构成任何统计意义上的代表性。
> - **数据性质**：合成数据，不含任何真实用户内容。

> 上面每一个 `[源:…]` 都由 `verify_citations.py` 与语料全集做差集机验——**差集非空就不许交付**。我们靠这一步在自己产出的指南里抓到过 2 次幻觉引用。

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

> 官网：<https://truefurina.github.io/comment-distillery/>

### 一、桌面工具（Windows，图形界面）

不想碰命令行就用这个：

**[⬇ 下载 comment-distillery.exe](https://github.com/TrueFurina/comment-distillery/releases/latest)** —— 约 11 MB，单文件免安装。

四个页签依次走完：

| 页签 | 干什么 |
|---|---|
| **① 采集** | B 站链接 → 评论（含楼中楼）→ CSV；支持中途停止，已抓部分照常写出 |
| **② 预处理** | 去重 / 去噪 / 统计；**先看 `dup_dropped` 再信任何规模数字** |
| **③ 导出蒸馏包** | 一键打包成一个文件夹：语料 + 方法论 + 可直接粘贴的 `PROMPT.md` |
| **④ 引用校验** | 幻觉引用差集检测 —— 差集非空就不许交付 |

**蒸馏那一步交给你自己选的那个 AI**（Claude / ChatGPT / Codex / WorkBuddy…），所以**不需要任何 API Key**，也不产生调用成本；方法论永远跟你手上那份 `SKILL.md` 一致，不会过期。

> exe 未做代码签名，首次运行 Windows SmartScreen 会拦截，点「更多信息 → 仍要运行」即可（属正常现象，非病毒）。
> 想自己构建：`python scripts/make_icon.py && python scripts/build_exe.py`。

### 二、装进你的 Agent（一条命令）

```bash
npx skills add TrueFurina/comment-distillery
```

兼容 Claude Code / Cursor / Codex / Windsurf / Copilot 等 40+ agent（由 `vercel-labs/skills` 自动解析安装位置）。只想看不装：`npx skills add TrueFurina/comment-distillery --list`。

### 三、直接用脚本（零依赖）

**零依赖，不需要 `pip install`。** 只要 Python 3.10+。

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
| `corpus_ccf.csv` | **规范语料**（Canonical Corpus Format）—— 引用机验与跨语料合并的单一真值源 |

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
├── ROADMAP.md               # 长期规划（含验收门槛与停止条件）
├── app_main.py              # 桌面工具入口（源码运行 / PyInstaller 打包共用）
├── app/                     # ★ 桌面工具（tkinter，零第三方依赖）
│   ├── core.py              #   逻辑层：委托调用 scripts/ 与 contrib/，无 GUI 依赖
│   └── gui.py               #   界面层：唯一接触 GUI 的模块
├── site/index.html          # 官网（单文件静态页，GitHub Pages 发布）
├── assets/icon.ico          # 应用图标（由 scripts/make_icon.py 标准库手写生成）
├── docs/
│   ├── canonical-format.md  # 统一语料格式 + 字段别名全表
│   ├── collecting.md        # 语料从哪来：各平台现成采集工具对照
│   ├── domains.md           # 各语料域的适配指南
│   ├── pipeline.md          # 6 步流水线详解
│   ├── retrospective.md     # ★ 七战沉淀：五次方法论修正 + 量化判据 + 交付质量门
│   ├── rule-provenance.md   # ★ 规则溯源：每条规则的验证战次，单战证据标「待复现」
│   ├── overturned.md        # ★ 被推翻结论台账（含"什么证据会再次推翻它"）
│   ├── engineering-pitfalls.md  # 维护/构建本仓库才会踩的坑（不进打包产物）
│   ├── distribution.md      # 分发作战清单（PR 文案 / 帖子草稿，可直接复制）
│   └── compliance.md        # 合规与伦理边界
├── scripts/
│   ├── prep.py              # 预处理（零依赖）
│   ├── verify_citations.py  # 引用真实性机验（强制质量门）
│   ├── check_rule_tags.py   # 机验 SKILL.md 无「裸铁律」（带变异验证）
│   ├── check_doc_consistency.py  # 文档一致性机验：版本口径 / Release tag / 站点数字 / 规则计数 / 中英对等（带变异验证）
│   ├── build_exe.py         # 打包桌面 exe（PyInstaller，仅构建期依赖）
│   └── make_icon.py         # 标准库手写 ICO 生成器（不引入 Pillow）
├── golden/                  # 评估集：8 场景 / 4 类，判「改规则后是否变强」
│   ├── README.md
│   ├── cases/               # 场景集（纯数据 JSON）
│   ├── graders.py           # 判分器
│   ├── run_golden.py        # 跑分器：离线判分 / 基线 / 变异验证
│   └── replies/baseline/    # 理想回复（应拿满分）
├── contrib/                 # ⚠️ 可选采集桥接，非核心、无支持
│   ├── README.md
│   └── fetch_bilibili_comments.py
├── examples/
│   └── sample_corpus.csv    # 合成示例语料（不含任何真实用户数据）
├── cases/                   # ★ 七战实战档案（**仅产物层**）
│   ├── README.md            # 先读这个：目录编号 ≠ 战次编号
│   ├── 01…04/               # 第 1–4 战：真实语料 → 深度指南
│   ├── 05-mustwatch-math/   # 第 6+7 战：正卷 15 章 + 增补卷 10 章（含 3 处结论修正）
│   └── notes/               # 设计留档：方案论述 / 开源冲刺路线图
└── tests/                   # 回归测试 61 项（CI 自动跑）
```

> `cases/` **只放产出**（各战指南 + 设计文档，共 9 个 md / 277 KB）。
> 原始语料与流水线中间产物按 [`docs/compliance.md`](docs/compliance.md) §2「不得二次分发原始语料」**不公开**。

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
- [x] **实战**（七战 / 约 4.5 万条）— 辩论层（楼中楼）补抓实证：单视频 21,100 条，增补卷修正正卷 3 处结论
- [x] **v1.3** — golden 评估集：8 场景 / 4 类，baseline 100 分，31 个变异体验证判分器有效（见 [`golden/README.md`](golden/README.md)）
- [x] **v1.4** — 交付形态：Windows 桌面 exe（采集→预处理→导出蒸馏包→引用校验）+ 官网（`site/`）
- [ ] **v2** — 更多语料域的适配示例（问卷 / 访谈 / 工单）
- [ ] **v2** — 跨语料聚合（同一议题的多来源合并分析）
- [ ] **v2** — 真·人工校验 loop（关键结论的交互式确认）

完整规划（含每阶段验收门槛与停止条件）见 [`ROADMAP.md`](ROADMAP.md)；
七战方法论沉淀（五次修正、7 条量化判据、交付质量门 G1–G7）见 [`docs/retrospective.md`](docs/retrospective.md)。

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
