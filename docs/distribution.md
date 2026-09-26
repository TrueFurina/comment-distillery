# 分发作战清单（Distribution Playbook）

> 建立：2026-09-26（P3）
> 定位：**本文档是"谁来做"的清单，不是"做了什么"的报告。**
> 分发里有一半动作**必须你本人执行**（需要 GitHub / Reddit 账号、涉及公开发言）。
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

**为什么先做 P3.5 再做渠道**：渠道动作（awesome PR / 社区发帖）触达的是**已经会用 skills CLI 的人**，而这条路最窄。桌面 exe 把门槛降到「下载、双击」，它决定的是**分母**；渠道只决定在这个分母里被看见的概率。顺序错了，等于拿最窄的入口去铺最广的渠道。

**适配时确认的关键规范**（来自 vercel-labs/skills 生态文档，非猜测）：

- 仓库根放 `SKILL.md` 即构成**单 skill 仓库**，CLI 自动发现，**无需 manifest**；
- ⚠️ **绝不能在根 SKILL.md 旁边再建 `skills/` 目录**——根 SKILL.md 会短路发现，CLI 不再扫描子目录。我们正好是单 skill 布局，**保持现状即可，不要重构成 `skills/comment-distillery/`**；
- `name` 必须与目录/仓库名一致（`comment-distillery` ✅）；
- `description` 要写成**路由规则**（什么情况下用），不是营销语——它决定 agent 会不会激活这个 skill；
- SKILL.md 建议 < 500 行（当前 ~210 行 ✅）。

---

## 1. 需要你执行的动作（按 ROI 排序）

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
- **Zero dependencies, stdlib only.** No pip install, Python 3.8+.
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

### E. Release 首发与 Pages 核验（需要你的仓库权限，5 分钟）

代码侧已全部就位，剩下两步**必须在推送到远端之后**做，本地验证不了：

1. **打 tag 并发 Release**（把 `dist/comment-distillery.exe` 挂上去，Release 正文附 SHA-256）：
   ```bash
   git tag -a v1.4.0 -m "v1.4.0 — 桌面工具 + 官网"
   git push origin v1.4.0
   gh release create v1.4.0 dist/comment-distillery.exe \
     --title "v1.4.0 — Windows 桌面工具 + 官网" \
     --notes-file <(sed -n '/## \[1.4.0\]/,/^---$/p' CHANGELOG.md)
   ```
   或用网页端 Releases → Draft a new release → 选 `v1.4.0` → 上传 exe。
2. **核验 Pages 生效**：推送后到 Actions 看 `pages` 工作流。若失败，**最常见原因是仓库 Settings → Pages 的 Source 没切到 `GitHub Actions`**（默认是 `Deploy from a branch`，本仓库没有 `gh-pages` 分支，会 404）。
3. **核验下载链路**：打开 <https://truefurina.github.io/comment-distillery/>，点「下载 exe」应落到 Release 页；确认 SmartScreen 提示属正常（未签名）。

---

## 2. 验收与停止条件

| 项 | 验收 | 停止条件 |
|---|---|---|
| npx 适配 | ✅ `--list` 能发现 1 个 skill | 无 |
| 元数据 | `gh repo view` 能看到 description + topics | 无 |
| awesome PR | **至少 1 个合入** | **3 个月内 PR 全被拒且社区零反馈 → 回到定位重新评估**，不继续堆渠道动作 |
| 社区发帖 | 各渠道发一轮 | 同上 |
| 长文 | 发布并进入长尾搜索 | 无 deadline |

**不把 star 当目标**，只当"分发是否奏效"的观测指标。

---

## 3. 维护提醒

- 改 `SKILL.md` 的 `description` 后要**同步 `metadata.version`**（semver）；
- skill 副本仍需同步到 `~/.workbuddy/skills/comment-distillery/`（WorkBuddy 加载点）；
- 每次改完跑 `npx skills add TrueFurina/comment-distillery --list` 复核发现仍正常（它会 clone 远端，**必须推送后才看得到新 description**）。
