# HANDOFF —— comment-distillery 项目交接说明

> 生成时间：2026-09-26
> 本文档供**下一个对话/会话**冷启动使用。读完本文即可接手，不必回溯历史。

---

## 一、这是什么

`comment-distillery` 是一个把**任何一群人对同一议题的自发文本**（B站/YouTube 评论区、问卷开放题、访谈逐字稿、产品反馈、Issue 讨论）蒸馏成**带认知框架、带引用溯源、带盲区说明的厚指南**的 Skill + 开源仓库。

**定位（差异化护城河）**：只做最后一跳「评论 → 厚指南」。
- **不写爬虫**（上游交给 MediaCrawler / BilibiliCrawler）
- **不做情感饼图**（那是 L2 红海）
- 做 **L3 建设性综合**

**仓库**：https://github.com/TrueFurina/comment-distillery （public / MIT）
**状态**：七战实战验证完毕，P0/P1/P2 已闭环、P3 适配部分完成，CI 全绿（`bbda7d0` success，3 个 Python 版本）。

**冷启动读这三份**：`HANDOFF.md`（本文，接手）→ [`ROADMAP.md`](ROADMAP.md)（下一步做什么）→ [`docs/retrospective.md`](docs/retrospective.md)（七战方法论沉淀与量化判据）。

---

## 二、目录结构（已全量迁移至 E 盘）

```
E:\Program\comment-distillery\           ← 项目根 = git 仓库根
├── .git/                                （HEAD 见 `git log -1`，remote: SSH）
├── .github/workflows/
│   ├── ci.yml                           （3 个 Python 版本，**13 步**：compileall / 零依赖守卫 / 编码守卫 / 文档一致性机验 / 文档一致性变异验证 / unittest / 无裸铁律 / 判据变异验证 / golden 变异 / golden 基线 / prep 冒烟 / 引用机验冒烟 / 冒烟产出展示）
│   ├── build-exe.yml                    （CI 上真跑 PyInstaller 打包 + 双冒烟，上传 artifact）
│   └── pages.yml                        （官网发布到 GitHub Pages）
├── app_main.py                          （桌面工具入口：源码运行 / PyInstaller 共用；含 --selfcheck / --selftest-gui / --selftest-run）
├── app/
│   ├── core.py                          （★ 逻辑层：只委托 scripts/ 与 contrib/，零 GUI 依赖 → 可单测）
│   └── gui.py                           （界面层：tkinter，唯一接触 GUI 的模块）
├── site/index.html                      （官网单文件静态页；内容全部取自仓库真实数据）
├── assets/icon.ico                      （应用图标，由 scripts/make_icon.py 标准库手写生成，不引 Pillow）
├── scripts/prep.py                      （预处理：编码容错 → 去重 → 去噪 → 按赞降序 → 导出）
├── scripts/verify_citations.py          （引用幻觉机验，强制质量门）
├── scripts/check_rule_tags.py           （机验 SKILL.md 无「裸铁律」，含变异自验）
├── scripts/check_doc_consistency.py     （文档一致性机验：版本口径 / Release tag / 站点数字 / 锚点 / 中英对等 / 已证伪表述，含变异自验；同时取代了原先三处重复的「官网自检」内联实现）
├── scripts/build_exe.py                 （PyInstaller 打包脚本，仅构建期依赖，不进运行期）
├── scripts/make_icon.py                 （标准库手写 ICO）
├── contrib/fetch_bilibili_comments.py   （纯标准库 WBI 签名抓取，含去重与退避）
├── golden/                              （评估集：8 场景 / 4 类，判分器 + 跑分器 + 变异验证）
├── ROADMAP.md                           （长期规划 P0–P5 + P3.5，含验收门槛与停止条件）
├── tests/test_prep.py                   （27 个用例）
├── tests/test_golden.py                 （12 个用例）
├── tests/test_rule_tags.py              （6 个用例）
├── tests/test_app_core.py               （16 个用例，桌面工具逻辑层）
├── docs/collecting.md                   （各社区采集工具 + 许可证 + 风险对照）
├── docs/retrospective.md                （七战沉淀：五次修正 / 7 条判据 / 质量门 G1–G7）
├── docs/rule-provenance.md              （规则溯源：9 铁律 / 5 待复现 / 17 环境事实，附复现判据；计数由机验强制与 SKILL.md 对齐）
├── docs/overturned.md                   （被推翻结论台账 OT-1…OT-5，含"再次推翻的条件"）
├── docs/distribution.md                 （★ 分发作战清单：gh 命令 / awesome PR 文案 / 帖子骨架）
├── SKILL.md / README.md / README.en.md / CHANGELOG.md
│
└── cases/                               ← 实战档案（**产物层已公开进仓库**；原始语料/中间产物按 compliance §2 不公开）
    ├── README.md                        （★ 先读：目录编号 ≠ 战次编号）
    ├── 01-ai-replace-programmer/        （1504 条 · 11 章指南 · 流水线首测）        ✅ 指南已公开
    ├── 02-mountain/                     （3425 条 · 8 章 · 两场核心争议专场）      ✅ 指南已公开
    ├── 03-qingbei-discouraged/          （5052 条 · 13 章 · 楼中楼捞出一级缺失的 7 个议题）✅ 指南已公开
    ├── 04-salary-age43/                 （8941 条 · 23 章 · 双视频合并 · 首次抓到幻觉引用）✅ 指南已公开
    ├── 05-mustwatch-math/               （21100 条 · 正卷 15 章 + 增补卷 10 章）  ✅ 两卷均已公开
    └── notes/
        ├── 评论指南Skill方案论述.md      ✅ 已公开（设计留档）
        ├── comment-distillery开源冲刺路线图.md ✅ 已公开（设计留档）
        ├── memory-snapshot/            ❌ 不公开（会话记忆，非项目资产）
        └── migrate_to_E.py             ❌ 不公开（一次性迁移脚本，含本机路径）
```

### 交付形态（2026-09-26 新增）

三条入口并存，**共用同一条实现**（GUI 与 CLI 调用的是同一批函数，不存在两套逻辑）：

| 入口 | 面向谁 | 命令 / 方式 |
|---|---|---|
| **桌面 exe**（`dist/comment-distillery.exe`，~11 MB） | 非技术用户 | 双击；四页签：采集 → 预处理 → 导出蒸馏包 → 引用校验 |
| **装进 Agent** | Agent 用户 | `npx skills add TrueFurina/comment-distillery` |
| **命令行脚本** | 开发者 / CI | `python scripts/prep.py …` / `python contrib/fetch_bilibili_comments.py …` |

**关键设计决策：exe 不内置 LLM。** 它只产出「蒸馏包」（语料 + `SKILL.md` + 可直接粘贴的 `PROMPT.md`），蒸馏那一步交还用户自选的 AI。收益：零 API Key、零调用成本，且方法论永远引用仓库当前 `SKILL.md`，**不会随 exe 固化而过期**。

**重构纪律（务必延续）**：`scripts/*.py` 的 `main(argv)` 签名**不可改** —— `tests/` 直接调它。新增能力一律以 `run()` / `crawl()` 形式**追加**。
新增的三个可调用入口：`prep.run()` / `verify_citations.run()` / `fetch_bilibili_comments.crawl()`。

**exe 未被代码签名** → 首次运行 Windows SmartScreen 会拦截，点「更多信息 → 仍要运行」。属正常现象，README 已写明。

**官网数字纪律**：`site/index.html` 里每个数字都必须能在仓库中指到出处（测试数 / 场景数 / 规则分级 / 代码规模），改代码后**同步复核官网**，不要让它变成漂移源。

**`cases/` 的公开口径（2026-09-26 用户拍板）**：只公开**产物层**（9 个 md / 277 KB）。
`.gitignore` 用**扩展名白名单反向**实现（`/cases/**/*.{csv,txt,json,py,svg}` 全部忽略）——
**不要改回 `/cases/` 整目录忽略**，也不要改回「全量公开」：原始语料再分发会推翻 `docs/compliance.md`
§0/§2/§5 的三处声明（其中 §5 的「未复制或再分发原始数据」已被写进各战指南开头，公开语料会让它变成假话）。

**Skill 副本仍在 `C:\Users\Lenovo\.workbuddy\skills\comment-distillery\`**（WorkBuddy 从这里加载，**不要移动**）。仓库是 source of truth，改完用脚本同步过去。

---

## 三、七战档案索引

| # | 规模 | 语料 | 产出 | 关键验证 |
|---|---|---|---|---|
| 1 | 1,504 | B站"AI 替代程序员" | 11 章指南 | 流水线可行性 |
| 2 | 3,425 | 《山》AI 电影 | 8 章 + 7 小节 | 两场核心争议专场 |
| 3 | 5,052 | "清北 discouraged" | 13 章 | **楼中楼捞出一级缺失的 7 个议题，4 条直接对冲前文结论** |
| 4 | 8,941 | 薪资 903 + 43 岁被裁 8038 | 23 章 | **多语料合并产出单语料看不到的洞察**；**引用机验首次抓到幻觉引用** |
| 5 | — | examples/ 合成样例 | 端到端回归 | CI 自动跑 |
| 6 | 21,100（一级去重后 14,526） | 《火柴人 VS 数学》 | **正卷 15 章** | **抓到并修复 22% 重复行缺陷**；首次在近乎全正向情绪语料上验证"反例对冲"仍需主动开采 |
| 7 | **+6,724（楼中楼）** | 同上视频 · 补抓辩论层 | **增补卷 10 章 / 31.0 KB** | **修正正卷 3 条结论**；量化注意力漂移（语法争论楼 2,867 赞 ＝ 实质教育辩论 1,142 赞的 **2.5 倍**）；引用机验 **54 条 / 0 幻觉** |

---

## 四、环境与流程「坑」清单（最重要，务必读）

### A. 抓取链路

| # | 坑 | 症状 | 解法 |
|---|---|---|---|
| A1 | **分页游标重叠** | 抓 20399 行，其中 4501 行是同 ID/同内容/同赞数的完全重复（22%） | 抓取端按 `rpid` 去重，整页重复即终止翻页；`prep.py` 去噪前按 ID 去重，`stats.json` 报 `dup_dropped` |
| A2 | **子回复限流** | 一错就 break，后面全丢 | 指数退避 + 只抓 `rcount>=3` 的讨论型楼 |
| A3 | **bv2av 算法错配** | 网上多版本（6/10 位、基 58/10），算出 aid 偏差几个数量级 | 别算，直接调 `view?bvid=` 接口取 aid |
| A4 | **Windows 系统代理污染 urllib** | 翻页 `SSL: UNEXPECTED_EOF_WHILE_READING`（第 19 页断连只拿 360 条） | `build_opener(ProxyHandler({}))` 强制直连 + 重试，一次拿满 |
| A5 | **楼中楼 = 结构性盲区** | 只抓 `--roots-only` 会丢掉全部反例与专业纠错 | 需要反例时必须全量抓；本战楼中楼 6,724 条 / 占条数 31.9% |

### B. 预处理与交付

| # | 坑 | 症状 | 解法 |
|---|---|---|---|
| B1 | **低赞长文筛选会捞到粘贴板 pasta** | "赞≤8 且长文=高信号"这条规则会捞到鸿蒙 pasta / 歌词 / 小说片段 / 游戏攻略 | 追加人工判据：跳过"无具体指称的叙事性长文"；优先看有具体知识点/论据/来源的长文 |
| B2 | **引用幻觉写作时无法自察** | 写作时会生成"格式正确但语料中不存在"的 ID（第六战抓到把 `c171593986384` 误写为 `c171621986384`） | 交付前**必须**跑 `verify_citations.py`，差集非空不许交付 |
| B3 | **机验脚本正则误报** | markdown 表格转义 `\|` 被当成引用；说明文字里提到错误 ID 也被当成真引用 | 正则需要排除 `\`；文档里引用错误示例时避开引用格式 |

### C. 环境与工具

| # | 坑 | 症状 | 解法 |
|---|---|---|---|
| C1 | **Windows Python 不认 `/c/Users/...`** | 会写成 `C:\c\Users\...` | 一律用 `C:/Users/...` 或 `C:\Users\...` |
| C2 | **Git Bash heredoc 静默改写反斜杠** | 写入的 Python 代码里的 `\\` 被吃掉 | 写文件一律用编辑工具，**不用 heredoc** |
| C3 | **跨盘 `shutil.move` 会被安全钩子拦** | `OSError [WinError 17]` → copy 成功但 rmtree 被 safe-delete 拦截，源侧留下副本 | 跨盘移动用**原生 PowerShell `Move-Item`**，不走 Python shim |
| C4 | **setuptools 损坏**（中断升级导致 `_distutils_hack` 缺失） | `bilibili-api` 装不上 | 弃用第三方库，改纯标准库方案（本项目的零依赖设计正源于此） |
| C5 | **推送认证** | `gho_` token 用 `Bearer` header 必报 invalid | 必须 URL 内嵌：`https://x-access-token:${TOKEN}@github.com/...` |
| C6 | **`github.com:443` 直连被阻断** | `curl` 到 api.github.com 通，但 git 不通，fetch 报 `Connection reset` | origin 已切 SSH：`ssh.github.com:443` 与 `github.com:22` 均可用 |
| C7 | **GITHUB_TOKEN 在 WorkBuddy bash 里读不到** | shell 不继承 HKCU 环境变量 | 用 Python `winreg` 读，或 `~/.workbuddy/bin/gh_run.py` |

---

## 五、方法论演进（哪些规则被修正过）

流水线的核心方法论在前六战中被**修正了四次**，记下来避免重蹈：

1. **「高赞 = 高信号」❌** → 已废弃。第六战实测：8 条最高价值评论赞数总和仅 12，而最高赞段子单条 236,396。必须先跑脚本筛"赞≤2 且字数≥70"的低赞长文。
2. **「低赞长文 = 真信号区」⚠️** → 需加 pasta 过滤（见 B1）。
3. **「只抓一级评论就够」❌** → 已废弃。反例、专业纠错、事实核查**几乎全在楼中楼**（见 A5）。
4. **「评论真实性靠人工核对」❌** → 已废弃。必须脚本机验（见 B2）。

**已成型的强制规范**：
- 引用格式 `[源:评论ID|赞N|层级]`，交付前必须机验
- 规模 >5000 条走**两段式阅读**（头部高赞 + 低赞长文），并在附录披露未读部分
- 必须有**覆盖率诚实声明**
- 必须有**反例对冲**章节；提出反方观点时同时给出反-反方
- 数字口径单一真值，禁手写漂移

---

## 六、仓库状态

```
HEAD     见 `git log -1`（最后核验 2026-09-26 为 2cae432；**本文件每次提交后 hash 都会前进一格，属正常**——
         先前写法把 hash 写死，导致每次提交都要改一次，是自找的漂移源）
origin   git@github.com:TrueFurina/comment-distillery.git   (SSH)
CI       .github/workflows/ci.yml  **13 个质量门步骤**全绿
         （compileall / 零依赖守卫 / 编码守卫 / 文档一致性机验 / 文档一致性变异验证 / unittest 61 项 /
          无裸铁律 / 判据变异验证 / golden 变异 / golden 基线 / prep 冒烟 / 引用机验冒烟 / 冒烟产出展示）
         另有 build-exe.yml（真打包 + --verify 资源核验 + 三道冒烟 + 文档一致性）与
         pages.yml（官网发布；站点自检已统一走 check_doc_consistency.py，不再内联第三份实现）
安装     npx skills add TrueFurina/comment-distillery   （--list 实测 Found 1 skill）
桌面     双击 dist/comment-distillery.exe（~11 MB 单文件，未签名 → SmartScreen 会提示，属正常）
迁移     E:\Program\comment-distillery，cases/ 已 gitignore，仅本地留存
```

**已确认（2026-09-26 核验）**：迁移后 CI 重跑通过；源侧 `.git` 副本已清理（比对确认独有提交 0）；`git fsck --full` 干净。

---

## 七、下一步（Open Items）

**长期规划已单独成文 → [`ROADMAP.md`](ROADMAP.md)**（P0 收尾 ✅ / P1 golden ✅ / P2 去过拟合 ✅ / P3 分发 / P4 场景升维 / P5 研究问题）。以下为状态更新：

1. ✅ **正卷交叉引用**已回填（2026-09-26）：正卷卷首新增"本卷 3 处结论/引用在增补卷中被修正"提示块，指向第五章 / 7.2 节 / 第十四章。
2. ⏸ **跨平台对照**：本视频在 YouTube 有大量评论，楼中楼里已见观众搬运英文解析。**已列入 P5 长线，且当前停止新增抓取**（语料已足够）。
3. ⏸ **`docs/collecting.md` 扩充**：可补"输出 → CCF 字段映射"的完整示例。优先级低于 P3。
4. ⏸ **真·人工校验 loop**：列入 P5。现状澄清——现有 7 道门（见 `docs/retrospective.md` §4）**只卡形式与引用真实性，不检验推断质量**。
5. ✅ **反例开采 vs 深度解析开采**：已拆开，且**已标为 `[战7·待复现]`**——单战证据，移入 SKILL.md「待复现观察」章节，不再是铁律。
6. ✅ **七战沉淀件**：`docs/retrospective.md` —— 五次方法论修正 + 7 条量化判据 + 交付质量门 G1–G7 + 与 AGI-Distiller 对照 + 已知局限。
7. ✅ **P1 golden 评估集**（2026-09-26）：8 场景 / 4 类，baseline 100.0，变异 31/31 拦截。
8. 🆕 **P2 方法论去过拟合**（2026-09-26）：`docs/rule-provenance.md` + `docs/overturned.md` + `scripts/check_rule_tags.py`（CI 强制）。**读规则时注意：带 `[战N·待复现]` 的是假设，不是规律。**
9. 🟡 **P3 分发**（2026-09-26）：`npx skills add` 适配 ✅（实测 Found 1 skill）+ README 真实产出片段 ✅ + GitHub 元数据 ✅ + **topics 已补齐 ✅**（16 个，补入 `agent-skills` / `claude-skills` / `skills` / `ai-agents`——**由本地 token 直接调 API 执行，不需用户操作**）。**仅剩两项需要你的账号**——awesome 列表 PR（§1-B 有现成英文文案）/ 社区发帖（§1-C 有骨架）。我无账号、不代发公开内容。
10. ✅ **`cases/` 产物层公开**（2026-09-26 用户拍板）：9 个 md / **277 KB** 进仓库（各战指南 + 设计留档）；原始语料与中间产物按 `docs/compliance.md` §2 **保持不公开**。实现与红线见 §二 的「公开口径」。
11. ✅ **LICENSE 保留 MIT**（2026-09-26 用户确认）：依据是 `docs/compliance.md` §0——"本项目可以 MIT 开源、可被企业采用"。**不适用**"原创项目一律不加 LICENSE"这条个人规则（它针对私有项目；公开仓库无 LICENSE = 保留所有权利，反而与分发目标矛盾）。
12. ✅ **P3.5 交付形态**（2026-09-26）：Windows 桌面 exe（`app/` + `app_main.py`）+ 官网（`site/`）+ 可复现构建（`scripts/make_icon.py` / `scripts/build_exe.py` / `build-exe.yml` / `pages.yml`）。**exe 三项自检全 PASS**（资源齐全 / 真建窗口 / 端到端跑通预处理→打包→引用机验）。设计决策与回滚方式见 `ROADMAP.md` §P3.5。
13. ✅ **顺带修掉两个真 bug**（2026-09-26）：① `verify_citations.py` 的 `--field` 参数一直被解析却从未传下去（形同虚设），已接通；② `crawl()` 的协作式停止钩子与 `_CallbackWriter` —— GUI 中途停止时已抓部分照常写出。
14. ✅ **GitHub Release + Pages 首发**（2026-09-26）：tag `v1.4.0` → `0ba07ce`（**已移到修复 CI 红之后的提交**——当时它**从未成功构建过**，属"尚未成立"而非"已发布后又变"；与后来 v1.4.1 的处理**不同**：已发布的内容变了就**发新版、不重写资产**）；Release 已挂 exe（**11,682,955 字节**）；官网 <https://truefurina.github.io/comment-distillery/> 线上 HTTP 200。**原判"需要你的仓库权限"是误判**——本地 token 直连 API 全做完。**Pages 首次部署失败的真因不是 Source 选错，是 Pages 根本没启用**（`GET /repos/.../pages` → 404）；一行 `POST /pages {"build_type":"workflow"}` 修好。发布件已下载回来复算 SHA-256，与本地冒烟验证件**完全一致**。三条工作流全绿：CI `36225711223` / Deploy site `36225711371` / Build exe `36225715001`。

**当前状态（2026-09-26）**：P0 / P1 / P2 已闭环，P3 适配侧全部完成（含 topics 补齐），**P3.5 交付形态完成并已发布上线**（当前版 Release **v1.4.1** + 官网），`cases/` 产物层已公开。**代码侧无待办，远端侧也无待办**——tag / Release / Pages 全部由本地 token 完成并逐项核验。剩余**只有一类**「需要你本人账号」的动作：**awesome PR ×3 与社区发帖**（以你的身份公开发言，我不代发；文案命令已就位，见 `docs/distribution.md` §1-B/C/D）。**P4 经拍板不做**（保留合成样例；原始语料明确无需备份）。**P5 为长线研究问题，不设 deadline**。

---

## 七·补、改规则时的强制动作（P2 引入）

改 `SKILL.md` 后**必须**：

```bash
"$PY" "$REPO/scripts/check_rule_tags.py"            # 无裸铁律（新规则必须带 [战N]/[环境]/[设计]）
"$PY" "$REPO/scripts/check_rule_tags.py" --self-test # 判据自身有效（3/3 变异必须被拦截）
```

新增规则时先问：**这条被几战验证过？** 1 战 → 必须写进「待复现观察」章节并标 `[战N·待复现]`，同时在 `docs/rule-provenance.md` §2 补上"复现判据"（第二次遇到什么证据才算成立）。

---

## 七·补二、改文档 / 站点 / 版本号时的强制动作（2026-09-26 引入）

**为什么会有这一节**：本仓库最忌讳「数字漂移」，但这类问题历来靠人眼 grep 把关，而人眼会漏——
2026-09-26 一次普查就漏出 3 处：① PR 文案里的 Python 版本号比全库其余处**低两个次版本**（CI matrix 最低为 3.10）；
② `docs/distribution.md` §E 把一条**已证伪**的判断当作现状（Release / Pages 其实本地 token 就能做完）；
③ `HANDOFF.md` 里 Release 仍被列为待办（实际早已发布上线）。**靠自觉不如靠机验。**

```bash
"$PY" "$REPO/scripts/check_doc_consistency.py"             # 6 项检查（存在 dist/*.exe 时会核对站点 SHA/体积）
"$PY" "$REPO/scripts/check_doc_consistency.py" --self-test # 判据自身有效（6/6 变异必须被拦截）
# CI 的打包工作流用 --no-artifact：站点记的是**已发布产物**，与 CI 现打包的字节必然不同
# （PyInstaller 非可复现），硬比会逼出「永远不许重建」的假红线。
```

被拦下的两类事：① **版本口径**（徽章 / 正文 / 各文档必须与 CI matrix 的最低版本一致）；
② **已证伪表述**（黑名单在脚本 `REFUTED` 里，每条附「何时 / 被什么证伪」；
说明「曾经这么以为」的句子含 `原以为 / 原判 / 误判` 等标记则放行）。

**顺带消除的第三份实现**：`ci.yml` / `pages.yml` 原先各自内联了一份「官网自检」，
加上脚本里的一份就是三处——改一处忘另两处就是漂移。现统一走 `check_doc_consistency.py` 的第 4 项检查。

### 踩到的一个 CI 陷阱（2026-09-26，实锤）

**`actions/checkout` 在 tag 推送时默认只带那一个 tag。** 于是 v1.4.1 首发时，
`Build exe` 与 `CI` 双双变红，报的都是「引用了不存在的 tag v1.4.0」——
而 v1.4.0 明明存在，只是**没被 checkout 拉到本地**。

- 两头修：① 三个工作流的 checkout 全部加 **`fetch-depth: 0`**（拉全量 tag）；
  ② self-test 改用「本地 tag ∪ 文档中出现的 tag」，使它**不依赖运行环境的 tag 完整性**
  （否则 CI 里那个变异会 SKIP 掉，self-test 报假红）。
- 报错信息也改了：再遇到类似情况，会明确提示「先怀疑本地只同步了部分 tag，
  修法是给 checkout 加 fetch-depth: 0，**而不是删掉文档里的链接**」。
- **教训**：机验脚本一旦依赖运行环境（本地 tag、网络、外部状态），
  它就会在「环境不同」时给出假红/假绿。**判据要尽量只读仓库内的事实。**

---

## 八、快速上手命令

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe"   # 托管 3.13，零依赖脚本用
PY313="C:/Users/Lenovo/AppData/Local/Programs/Python/Python313/python.exe"    # 官方 3.13，**带 tkinter**（GUI / 打包用）
BUILD_PY="E:/Program/_cd_build/venv313/Scripts/python.exe"                    # 独立构建 venv（tkinter + PyInstaller 6.22.3）
REPO="E:/Program/comment-distillery"

# 预处理
"$PY" "$REPO/scripts/prep.py" <corpus.csv> <outdir>

# 引用机验（交付前强制）
"$PY" "$REPO/scripts/verify_citations.py" <guide.md> <corpus.csv>

# 本地复现 CI
cd "$REPO" && "$PY" -m compileall -q scripts/ tests/ golden/ app/ contrib/ && "$PY" -m unittest discover -s tests

# 桌面工具（源码运行；GUI 需带 tkinter 的解释器，托管 Python 3.13 无 tkinter）
"$PY313" "$REPO/app_main.py" --selfcheck                    # 资源齐全性（结果落盘 --report <path>）
"$PY313" "$REPO/app_main.py" --selftest-gui                 # 真建窗口后自动关闭
"$PY313" "$REPO/app_main.py" --selftest-run <outdir>        # 端到端：预处理→打包→引用机验

# 打 exe（构建期需 PyInstaller；用带 tkinter 的 Python 建独立 venv）
"$PY" "$REPO/scripts/make_icon.py"                          # 生成 assets/icon.ico（标准库手写）
"$BUILD_PY" "$REPO/scripts/build_exe.py"                    # 产出 dist/comment-distillery.exe
"$BUILD_PY" "$REPO/scripts/build_exe.py" --verify           # ★ 产物内资源是否与仓库逐项一致（防陈旧副本）
"$REPO/dist/comment-distillery.exe" --selfcheck --report <path>
"$REPO/dist/comment-distillery.exe" --selftest-run <dir>    # 端到端
# 注：本地若有"批量删除守卫"，`--clean` 可能被拦；不加 --clean 直接重建即可（--noconfirm 会覆盖）。

# golden 评估集（改 SKILL.md / 换模型后是否变强，用它测）
"$PY" "$REPO/golden/run_golden.py" --self-test          # 变异验证：判分器是否真能扣分（CI 强制）
"$PY" "$REPO/golden/run_golden.py" --baseline           # 基线跑分：应 100.0
"$PY" "$REPO/golden/run_golden.py" --replies <dir>      # 离线判分（<case_id>.txt，不绑任何 CLI）
"$PY" "$REPO/golden/run_golden.py" --compare a.json b.json

# 抓取（纯标准库，无需安装依赖）
"$PY" "$REPO/contrib/fetch_bilibili_comments.py" BV1xxxxxxxxx out.csv            # 含楼中楼
"$PY" "$REPO/contrib/fetch_bilibili_comments.py" BV1xxxxxxxxx out.csv --roots-only  # 仅一级
```

**同步 Skill 副本**（改完仓库后必须执行）：
```python
import shutil
shutil.copyfile(r'E:\Program\comment-distillery\SKILL.md',
                r'C:\Users\Lenovo\.workbuddy\skills\comment-distillery\SKILL.md')
```
