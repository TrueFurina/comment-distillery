# 分发作战清单（Distribution Playbook）

> 建立：2026-09-26（P3）｜最后核对：2026-09-26（Release + Pages 已上线后）
> 定位：**本文档是"谁来做"的清单，不是"做了什么"的报告。**
> 分发里**只剩公开发言类动作需要你本人执行**（awesome 列表 PR、社区发帖）——它们以你的身份对外发声，
> 我不代发。其余「仓库权限 / 远端侧」的事（打 tag、建 Release、启用并核验 Pages、元数据）
> 都是**本地 token 直连 API 就能做**的，已完成，见 §0。
> 我能做的是把结构适配好、把文案写好，让你复制粘贴即可。

---

## 0. 已完成（2026-09-26）

| 项 | 状态 | 证据 |
|---|---|---|
| `npx skills add` 适配 | ✅ | `npx skills add TrueFurina/comment-distillery --list` → **Found 1 skill: comment-distillery** |
| SKILL.md frontmatter 规范 | ✅ | description 改为**触发式**（"当用户说…时使用"），新增 `metadata.version` |
| 英文 README 第一屏真实输出片段 | ✅ | 新增「What the output actually looks like」——引用溯源 / 反例对冲 / 行动清单 / 自曝盲区，四段全取真实产出 |
| 中文 README 同步 | ✅ | 同上，加「真实产出长什么样」+ 安装命令 |
| GitHub 仓库元数据 | ✅ | description 已设；topics **16 个**（已补入 `agent-skills` / `claude-skills` / `skills` / `ai-agents`） |
| **落地形态：桌面 exe + 官网**（P3.5） | ✅ | `dist/comment-distillery.exe`（~11 MB，四页签全流程）+ `site/index.html`（单文件静态页，GitHub Pages 发布）；构建可复现（`scripts/build_exe.py` / `scripts/make_icon.py` / `build-exe.yml`）。**理由见 `ROADMAP.md` §P3.5：分发渠道铺得再开，若落地页要求用户先装 Node 再跑 npx，转化会在第一步断掉。** |
| **Release 首发 + Pages 上线**（§1-E） | ✅ | 首发 v1.4.0（exe 11,682,955 字节）→ **当前版 v1.5.0**（exe 11,681,575 字节）；官网 <https://truefurina.github.io/comment-distillery/> HTTP 200。**三处 SHA/体积口径一致**（本地产物 / 站上标注 / Release 资产），且发布件下载回来复算哈希与本地验证件**完全相同**。原判"需要你的仓库权限"是**误判**——本地 token 即可，见 §1-E。 |

**为什么先做 P3.5 再做渠道**：渠道动作（awesome PR / 社区发帖）触达的是**已经会用 skills CLI 的人**，而这条路最窄。桌面 exe 把门槛降到「下载、双击」，它决定的是**分母**；渠道只决定在这个分母里被看见的概率。顺序错了，等于拿最窄的入口去铺最广的渠道。

**适配时确认的关键规范**（来自 vercel-labs/skills 生态文档，非猜测）：

- 仓库根放 `SKILL.md` 即构成**单 skill 仓库**，CLI 自动发现，**无需 manifest**；
- ⚠️ **绝不能在根 SKILL.md 旁边再建 `skills/` 目录**——根 SKILL.md 会短路发现，CLI 不再扫描子目录。我们正好是单 skill 布局，**保持现状即可，不要重构成 `skills/comment-distillery/`**；
- `name` 必须与目录/仓库名一致（`comment-distillery` ✅）；
- `description` 要写成**路由规则**（什么情况下用），不是营销语——它决定 agent 会不会激活这个 skill；
- SKILL.md 建议 < 500 行（当前 ~210 行 ✅）。

---

## 1. 需要你执行的动作（按 ROI 排序）

> **现状：A 与 E 已由我完成**（本地 token 直连 API，无需你的账号）——原先把它们列进"需要你执行"是**误判**。
> **真正需要你的只剩 B / C / D**：它们都以你的身份对外公开发言，我不代发。
> 文案与命令均已成稿，直接复制即可。

### A. GitHub 仓库元数据 — ✅ **已完成，无需你执行**

`npx skills find` 与 GitHub 搜索都读这些字段。

**执行记录（2026-09-26，由本地 token 直连 API 完成）**：

- `description` ✅ 已设（文案比本节原建议更完整，保持不动）；
- `topics` ✅ **16 个**。复核发现原有 `agentskills`（**无连字符**）与生态流通检索词 `agent-skills` **不等价**——等于白加。已补入 4 个：`agent-skills` / `claude-skills` / `skills` / `ai-agents`。

<details>
<summary>原始建议命令 — 已执行完毕，<b>仅存档</b></summary>

```bash
gh repo edit TrueFurina/comment-distillery \
  --description "Turn a pile of crowd text into an evidence-cited action guide — install: npx skills add TrueFurina/comment-distillery" \
  --add-topic agent-skills \
  --add-topic claude-skills \
  --add-topic claude-code \
  --add-topic skills \
  --add-topic ai-agents \
  --add-topic comment-analysis \
  --add-topic text-mining \
  --add-topic zero-dependency
```

</details>

**验收**：`gh repo view TrueFurina/comment-distillery --json description,repositoryTopics` 里能**同时**看到 `agent-skills` 与 `claude-skills`。

### B. awesome 列表 PR（每个 5 分钟，中等 ROI）

已核实的真实列表仓库（**都还活着，且接受社区条目**）：

| 仓库 | 特点 | 优先级 |
|---|---|---|
| <https://github.com/ComposioHQ/awesome-claude-skills> | 规模最大（~68k★），收录 1000+ skills，有明确社区贡献路径 | **P0** |
| <https://github.com/VoltAgent/awesome-claude-skills> | "the most contributed Agent Skills repository"，有 CONTRIBUTING.md | P1 |
| <https://github.com/m-fyi/awesome-claude-skills> | 按**真实安装数**排名，有 live directory（aaaa.fyi） | P2 |

> `skills.sh`（vercel 官方 leaderboard）**不需要 PR**——安装量上去会自动出现。所以 A 和 B 之外，真正能推它上榜的只有"让更多人装"。

**PR 文案（英文，直接复制）**

Title:
```
add comment-distillery — distill crowd text into an evidence-cited guide
```

Body:
```
## What it does

Distills a pile of unstructured crowd text (comment exports, open-ended survey
answers, interview transcripts, product feedback, issue threads, danmaku) into a
thick Markdown guide: cognitive frameworks + consensus vs. disagreement +
counter-example hedging + citation provenance + action checklist + honest
blind-spot disclosure.

## Why it's not "another summarizer"

- **Citation provenance is machine-gated.** Every cited item ID is diffed against
  the source corpus; a non-empty diff blocks delivery. This gate caught 2
  hallucinated citations in our own output — IDs that looked perfectly valid.
- **Mandatory counter-examples.** Every consensus must be paired with the
  strongest opposing argument. In one run, reply threads overturned 3 conclusions
  that the top-level-only pass had produced.
- **Zero dependencies, stdlib only.** No pip install, Python 3.10+.
- **Platform-neutral.** Any agent that reads SKILL.md can use it.

## Install

npx skills add TrueFurina/comment-distillery

## Links

- Repo: https://github.com/TrueFurina/comment-distillery
- Real output sample: examples/sample_guide.md
- Provenance log (which run validated which rule): docs/rule-provenance.md
- Overturned-claims log: docs/overturned.md

## Notes for reviewers

Not a scraper and not a sentiment dashboard by design — collection (L1) and
statistics (L2) are left to the existing ecosystem. This is L3 only.
```

### C. Reddit / 社区 Show & Tell（各 15 分钟，长尾流量）

| 渠道 | 建议标题 | 备注 |
|---|---|---|
| r/ClaudeAI | "Built a skill that turns comment sections into evidence-cited guides — and it caught its own hallucinated citations" | 强调**引用机验抓到自己的幻觉**，这是最有传播力的点 |
| r/LocalLLaMA | 同上，但强调**零依赖纯标准库**，本地可跑 | 该社区对"不联网、不装包"敏感 |
| 掘金 / 知乎 | 「把 2 万条评论炼成一份有据可查的指南：我们踩过的 5 个坑」 | 中文社区偏好**复盘/踩坑**叙事，不是功能介绍 |

**Reddit 正文骨架**（照这个写，别写成功能列表）：

```
Hook:  我们让 agent 写长篇引文分析，它编出的引用 ID 格式完全正确、
       肉眼无法分辨——直到我们用脚本做差集才发现它们根本不存在。（真事，抓到 2 次）

What:  comment-distillery — 把一群人的自发文本炼成带引用、带反例、带盲区说明的指南。
       零依赖，npx skills add TrueFurina/comment-distillery

3 things that make it different:
       1. 引用机验是硬门（差集非空不许交付）
       2. 反例对冲是强制的——每条共识必须配反方论据
       3. 它主动交代自己哪里可能错（四类偏差）

Honest part: 我们还做不到的——判分器只判形式与引用真实性，不判"结论对不对"。
       docs/retrospective.md 里写了 5 条已知局限。

Ask:   想要的是"有没有人也在做 L3 综合"的讨论，不是 star。
```

> ⚠️ 发帖时**不要**用营销语气，不要只丢链接。Reddit 对 self-promo 敏感——以"我们踩了这个坑、这是解法"的复盘口吻发，附完整 honest limitations，效果好得多。

### D. 方法论长文（P2 优先级，长尾搜索）

标题方向：**"Why comment sections are the most underrated dataset"** 或
「为什么"高赞"是最差的信号：我们在 4.5 万条评论上被数据打穿了五次」

素材全部现成（`docs/retrospective.md` + `docs/overturned.md`）：

1. 高赞 ≠ 高信号（8 条最高价值评论赞数总和 12，最高赞段子单条 236,396）
2. 低赞长文 ≠ 真信号（会捞出粘贴板 pasta）
3. 只抓一级评论 = 丢掉全部反例（补抓楼中楼后 3 条结论被推翻）
4. 引用真实性不能靠人工核对（幻觉 ID 格式完美）
5. 重复行不只是规模虚高（22% 重复会污染"高赞即共识"）

**元论点（这篇文章真正值钱的地方）**：五次失效的共同点是**用代理指标代替真值**——
点赞数↔认可度、文本长度↔思考深度、楼层深度↔观点完整性、ID 格式↔引用真实、行数↔语料规模。

### E. Release 首发与 Pages 核验 — ✅ **已完成（2026-09-26，无需你执行）**

**原以为这一步"需要你的仓库权限"——判断错了。** 本地有 token，`git push` + REST API 足以完成全部三步，
且比网页端更可核验（每步都留了可复算的证据）：

| 步 | 结果 | 证据 |
|---|---|---|
| 打 tag | ✅ `v1.4.0` → `0ba07ce`（修复后的提交，非首次失败的那个） | `git ls-remote --tags origin` |
| 建 Release + 挂 exe | ✅ [releases/tag/v1.4.0](https://github.com/TrueFurina/comment-distillery/releases/tag/v1.4.0) | 资产 `comment-distillery.exe` **11,682,955 字节**（11.1 MB），正文含 SHA-256 |
| 启用 Pages | ✅ `POST /repos/.../pages {"build_type":"workflow"}` | **首次部署失败的真因是 Pages 根本没启用**（`GET /pages` → 404），不是 Source 选错 |
| 核验 Pages | ✅ <https://truefurina.github.io/comment-distillery/> HTTP 200 | 站上标注 SHA `9435e748…` / 11.1 MB，与本地产物、Release 资产**三处一致** |
| 核验下载链路 | ✅ 下载回本地**复算 SHA-256 完全一致** | 证明「发布件 == 本地冒烟验证过的那一份」 |

**三条工作流在 HEAD / tag 上全绿**（可复查 run id）：
CI `36225711223`（main）· Deploy site `36225711371`（main）· Build Windows exe `36225715001`（v1.4.0）。

**后续版本（v1.4.1 起）改用「发新版」而非移动 tag**：v1.4.0 发完后发现 `SKILL.md`（**随包资源**）
新增了内容，`build_exe.py --verify` 当场报出「产物内 SKILL.md 与仓库不一致」。此时两条路——
改写已发布的 v1.4.0 资产，或如实发一个补丁版。**选后者：Release 不可变，内容变了就发新版本。**
（v1.4.0 当时移动 tag 是因为它**从未成功构建过**，CI 首跑即红，属"尚未成立"而非"已发布后又变"。）

**顺手记下的两个坑**（已同步进 `SKILL.md` 环境事实）：
- PyInstaller **不是可复现构建** → tag 触发的 CI 改为**只产出 Artifact、不自动覆盖 Release 资产**，
  否则已写进官网与 Release 的 SHA-256 会被重新打包的字节当场打成假话。
- exe 未签名 → SmartScreen 拦截属正常，README 与官网均已写明。

---

## 2. 验收与停止条件

| 项 | 验收 | 停止条件 |
|---|---|---|
| npx 适配 | ✅ `--list` 能发现 1 个 skill | 无 |
| 元数据 | ✅ `gh repo view` 能看到 description + topics | 无 |
| 落地形态（exe + 官网） | ✅ exe 三项自检全 PASS；官网 HTML 自检 + 无头渲染核验通过 | 无 |
| Release + Pages | ✅ Release 资产可下载且**复算哈希与本地件一致**；官网线上 HTTP 200 | 无 |
| awesome PR | **至少 1 个合入** | **3 个月内 PR 全被拒且社区零反馈 → 回到定位重新评估**，不继续堆渠道动作 |
| 社区发帖 | 各渠道发一轮 | 同上 |
| 长文 | 发布并进入长尾搜索 | 无 deadline |

> 上表**只剩两行未完成**（awesome PR / 社区发帖），且都属"以你身份公开发言"。
> 其余全部已闭环并有可复算证据——不要因为文档没更新而重复劳动。

**不把 star 当目标**，只当"分发是否奏效"的观测指标。

---

## 3. 维护提醒

- 改 `SKILL.md` 的 `description` 后要**同步 `metadata.version`**（semver）；
- skill 副本仍需同步到 `~/.workbuddy/skills/comment-distillery/`（WorkBuddy 加载点）；
- 每次改完跑 `npx skills add TrueFurina/comment-distillery --list` 复核发现仍正常（它会 clone 远端，**必须推送后才看得到新 description**）。
