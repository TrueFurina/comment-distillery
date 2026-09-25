# 语料采集：用现成工具，别自己写

> **本项目不做采集。** 采集是一个独立且高度成熟的生态（多平台、反爬对抗、登录态维护、频繁失效）。
> 本项目的价值在采集**之后**的那一跳：把语料炼成有据可查的行动指南。
>
> 本文件的作用是：让你能**按语料域找到当下可用的采集工具**，并把它的输出对齐到
> [Canonical Corpus Format（CCF）](canonical-format.md)。

---

## 0. 为什么把采集层划出去

三个理由，都不是洁癖：

1. **维护成本不对等。** 采集端要跟着平台签名算法 / 风控策略变，几个月就失效一轮（下文的实例可以印证）。把这类代码放进本仓库，会让"零依赖、MIT、可长期复用"的核心资产被外部变化拖垮。
2. **合规风险不对等。** 采集端的风险（ToS 冲突、登录态、平台诉讼）远高于综合端。混在一起会让企业用户无法使用本仓库——而"企业敢用"恰恰是本项目相对采集类项目的独有资格。
3. **生态已经足够好。** 见下表：7 平台、16 平台、单平台专项，都已经有人做到生产级且仍在活跃维护。

所以本仓库只提供 `contrib/fetch_bilibili_comments.py` 作为**可选桥接**（见 `contrib/README.md`，非核心、无支持），其余场景一律**推荐用成熟工具导出，再喂给 `prep.py`**。

---

## 1. 按平台的现成工具（截至 2026-09，star 数为当时量级）

| 平台 | 工具 | 形态 | 评论能力 | 许可 / 风险 | 备注 |
|---|---|---|---|---|---|
| **B站** | [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | CLI/WebUI，Playwright | 一级 + **二级评论** | ⚠️ **非商用许可** | 多平台龙头，2026-09 仍在活跃提交 |
| **B站** | [BilibiliCrawler](https://github.com/Yi-luo-hua/BilibiliCrawler) | Tauri 桌面 GUI | 评论 + 子评论 | 见仓库 | 免装 Python，含 LLM 舆论分析与 MCP |
| **B站** | `contrib/fetch_bilibili_comments.py`（本仓库） | 纯标准库 CLI | 一级 + 楼中楼 | 见 `contrib/README.md` | 零依赖，`--roots-only` 可只取一级 |
| **YouTube** | [youtube-comment-downloader](https://github.com/egbertbouman/youtube-comment-downloader) | CLI + 库 | 评论（含回复） | MIT | ~1.3k★，免 API Key，JSON/CSV 输出 |
| **YouTube** | [youtube-comment-suite](https://github.com/mattwright324/youtube-comment-suite) | Java 桌面 GUI | 视频/播放列表/频道级归档 | MIT | ~320★，SQLite 归档 + 搜索，适合非开发者 |
| **Reddit** | PRAW | Python 库 | 评论树 | 需遵 Reddit API 条款 | 官方 API 封装，最可靠的地基 |
| **Reddit** | URS | CLI（基于 PRAW） | 评论 | 同上 | 命令行封装 |
| **小红书 / 抖音 / 快手 / 微博 / 贴吧 / 知乎** | MediaCrawler | CLI/WebUI | 帖子 + 评论 + 二级评论 | ⚠️ **非商用许可** | 一个工具覆盖 6 个平台 |
| **Twitter/X · Reddit · YouTube · GitHub · B站 · 小红书 等（约 16 个）** | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) | **Agent-native CLI** | 以"读 + 搜"为主，**评论能力需自行核实** | 见仓库 LICENSE | 面向 AI Agent 设计（含 SKILL.md、`doctor --json`） |

**关于 Agent-Reach 的一段提醒**：它的定位和我们最接近（都是给 agent 用的、跨平台的能力层），但两者是**互补而非竞争**——它解决"agent 怎么读到平台内容"，我们解决"读到之后怎么炼成认知"。另外它大量依赖**浏览器登录态复用（OpenCLI / CDP 真 Chrome）**，这与本项目"不碰登录态、不做风控对抗"的立场不同。要用它，请自行评估风险。

---

## 2. 需要知道的三件事（否则选型会踩坑）

### 2.1 许可证差别很大，商用前必须逐个确认

- `youtube-comment-downloader`、`youtube-comment-suite` 等为 MIT，相对宽松。
- **MediaCrawler 是明确的非商用学习许可**——它功能最强、覆盖最广，但**不能直接用于商业舆情监控或对外数据产品**。
- 没有 LICENSE 文件的仓库在法律上默认"保留所有权利"，不是"随便用"。

### 2.2 采集端的法律风险是真实且正在升级的

Reddit 在 2025 年对 Anthropic 提起投诉、2025 年底又起诉 SerpApi，均涉及未授权抓取/使用内容；其公开内容政策、Responsible Builder Policy 与 robots.txt 都在收紧。同时技术侧也在收紧：Reddit 匿名接口已被封、`.json` 端点自 2026 年起在多数环境返回 403、Pushshift 对普通用户早已不可用。

结论很直接：**能走官方 API 就走官方 API；走不通时优先用"作者自己的登录态看自己有权看的内容"这种边界清晰的路径**，而不是大规模匿名抓取。

### 2.3 平台反爬会让"方案"定期失效——别把采集写进长期资产

B站风控会封死特定工具（2026-06 有工具被 412 拦死）；X、小红书、Instagram 的路径也在反复变。**任何采集方案都应该被当作"可替换的部件"**，这也是本仓库把采集隔离在 `contrib/` 并推荐外部工具的结构性原因。

---

## 3. 把任意工具的输出对齐到 CCF

不管用哪个工具，只要能把它的导出结果映射成下面这几个字段，就能进 `prep.py`：

| CCF 字段 | 必要性 | 说明 |
|---|---|---|
| `id` | **必需** | 稳定唯一 ID，引用溯源依赖它 |
| `text` | **必需** | 正文 |
| `score` | 可选 | 点赞/有用票，用于排序与"高权重陷阱"识别 |
| `reply_count` | 可选 | 用于识别讨论型楼中楼 |
| `author_id` | 可选 | 用于去重与"独立发言人数" |
| `created_at` | 可选 | 用于时间线/爆发曲线 |
| `parent_id` / `is_reply` | 可选 | 用于区分层级 |
| `source` / `title` | 可选 | 跨视频/跨帖聚合时用于区分来源 |

**最小可用**：只要 `id` + `text` 两列，`prep.py` 就能跑（此时不做排序、不做低权重长文精筛，读法要相应调整——见 `docs/domains.md`）。

`prep.py` 内置了常见列名的中英文容错映射（评论ID/id/comment_id、点赞数/like/score 等）。若列名不在映射表里，先跑一次看告警，或直接用一行 pandas/sed 改表头。

---

## 4. 一个决策流程

```
你的语料在哪个平台？
├── B站 ──────── 要 GUI 与内置图表 → BilibiliCrawler
│                要多平台/批量/二级评论 → MediaCrawler（注意非商用）
│                只想零依赖、丢弃链接就跑 → contrib/fetch_bilibili_comments.py
├── YouTube ──── 要轻量导出 → youtube-comment-downloader
│                要 GUI 归档与检索 → youtube-comment-suite
├── Reddit ───── 走官方 API → PRAW / URS（勿依赖 Pushshift 或 .json 端点）
├── 小红书/抖音/快手/微博/贴吧/知乎 → MediaCrawler 是当前覆盖面最广的选择
└── 问卷 / 访谈 / 工单 / 会议纪要 / Issue
                 → 多为自有或可授权数据，导出为 CSV 即可，无需采集工具
```

---

## 5. 与合规文档的关系

采集端的合规边界比综合端更硬。使用任何采集工具前，请读 [docs/compliance.md](compliance.md)，
尤其注意：**不要采集合规红线内的数据、不要外传含个人标识的原始语料、不要提供绕过平台限速的方案**。
本仓库的产出（指南）遵守"观点提炼 + 匿名化引用"，但**采集环节的责任在使用者**。

---

*本文档中第三方项目的 star 数与活跃度标注为 2026-09 调研时点，会随时间变化；选型前请以仓库当前状态为准。*
