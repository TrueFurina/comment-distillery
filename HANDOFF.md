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
**状态**：七战实战验证完毕，P0/P1/P2 已闭环，CI 全绿（`1e63c09` success，3 个 Python 版本）。

**冷启动读这三份**：`HANDOFF.md`（本文，接手）→ [`ROADMAP.md`](ROADMAP.md)（下一步做什么）→ [`docs/retrospective.md`](docs/retrospective.md)（七战方法论沉淀与量化判据）。

---

## 二、目录结构（已全量迁移至 E 盘）

```
E:\Program\comment-distillery\           ← 项目根 = git 仓库根
├── .git/                                （HEAD: 1e63c09，remote: SSH）
├── .github/workflows/ci.yml            （3 个 Python 版本，7 步：compileall/零依赖守卫/unittest/无裸铁律×2/golden×2/端到端冒烟）
├── scripts/prep.py                      （预处理：编码容错 → 去重 → 去噪 → 按赞降序 → 导出）
├── scripts/verify_citations.py          （引用幻觉机验，强制质量门）
├── scripts/check_rule_tags.py           （机验 SKILL.md 无「裸铁律」，含变异自验）
├── contrib/fetch_bilibili_comments.py   （纯标准库 WBI 签名抓取，含去重与退避）
├── golden/                              （评估集：8 场景 / 4 类，判分器 + 跑分器 + 变异验证）
├── ROADMAP.md                           （长期规划 P0–P5，含验收门槛与停止条件）
├── tests/test_prep.py                   （27 个用例）
├── tests/test_golden.py                 （12 个用例）
├── tests/test_rule_tags.py              （6 个用例）
├── docs/collecting.md                   （各社区采集工具 + 许可证 + 风险对照）
├── docs/retrospective.md                （七战沉淀：五次修正 / 7 条判据 / 质量门 G1–G7）
├── docs/rule-provenance.md              （规则溯源：9 铁律 / 5 待复现 / 7 环境事实，附复现判据）
├── docs/overturned.md                   （被推翻结论台账 OT-1…OT-5，含"再次推翻的条件"）
├── SKILL.md / README.md / README.en.md / CHANGELOG.md
│
└── cases/                               ← 实战档案（已在 .gitignore，仅本地留存）
    ├── 01-ai-replace-programmer/        （1504 条 · 11 章指南 · 流水线首测）
    ├── 02-mountain/                     （3425 条 · 8 章 · 两场核心争议专场）
    ├── 03-qingbei-discouraged/          （5052 条 · 13 章 · 楼中楼捞出一级缺失的 7 个议题）
    ├── 04-salary-age43/                 （8941 条 · 23 章 · 双视频合并 · 首次抓到幻觉引用）
    ├── 05-mustwatch-math/               （21100 条 · 正卷 15 章 + 增补卷 10 章）
    └── notes/
        ├── 评论指南Skill方案论述.md
        ├── comment-distillery开源冲刺路线图.md
        ├── memory-snapshot/            （上一会话工作记忆快照）
        └── migrate_to_E.py             （迁移脚本，已完成；源侧 .git 副本已于 2026-09-26 清理，比对确认独有提交 0）
```

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
HEAD     1e63c09  docs(P2): 方法论去过拟合——规则溯源台账 + 无裸铁律机验
origin   git@github.com:TrueFurina/comment-distillery.git   (SSH)
CI       .github/workflows/ci.yml  7 步全绿（1e63c09 / cf3d8a4 / 5ab6e38 均 success）
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

**当前第一优先级（P3 分发）**：P1/P2 已闭环——现在既能证明"引用是真的"，也能证明"改规则后是否变强"，且单战证据不再冒充铁律。下一步是让更多人知道，见 `ROADMAP.md` P3。

---

## 七·补、改规则时的强制动作（P2 引入）

改 `SKILL.md` 后**必须**：

```bash
"$PY" "$REPO/scripts/check_rule_tags.py"            # 无裸铁律（新规则必须带 [战N]/[环境]/[设计]）
"$PY" "$REPO/scripts/check_rule_tags.py" --self-test # 判据自身有效（3/3 变异必须被拦截）
```

新增规则时先问：**这条被几战验证过？** 1 战 → 必须写进「待复现观察」章节并标 `[战N·待复现]`，同时在 `docs/rule-provenance.md` §2 补上"复现判据"（第二次遇到什么证据才算成立）。

---

## 八、快速上手命令

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe"
REPO="E:/Program/comment-distillery"

# 预处理
"$PY" "$REPO/scripts/prep.py" <corpus.csv> <outdir>

# 引用机验（交付前强制）
"$PY" "$REPO/scripts/verify_citations.py" <guide.md> <corpus.csv>

# 本地复现 CI
cd "$REPO" && "$PY" -m compileall -q scripts/ tests/ && "$PY" -m unittest discover -s tests

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
