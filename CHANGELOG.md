# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed
- **CI 与 Build exe 双双变红：`actions/checkout` 在 tag 推送时默认只带那一个 tag。**
  v1.4.1 首发时两个工作流都报「引用了不存在的 tag v1.4.0」——而 v1.4.0 明明存在，
  只是**没被 checkout 拉到本地**。这是机验脚本**依赖运行环境**导致的假红。
  - 三个工作流的 checkout 全部加 `fetch-depth: 0`（拉全量 tag）。
  - self-test 改用「本地 tag ∪ 文档中出现的 tag」，使它不依赖运行环境的 tag 完整性——
    否则该项在 CI 里会 SKIP，那个变异就成了漏网、self-test 报假红。
  - 报错信息补上排查指引：再遇到类似情况会明确提示「先怀疑本地只同步了部分 tag，
    修法是加 `fetch-depth: 0`，**而不是删掉文档里的链接**」。
  - 同一行重复出现的同一 tag 只报一次（原先 `[x](url)` 形式会重复两行）。
  - **教训**：判据尽量只读仓库内的事实。一旦依赖本地 tag / 网络 / 外部状态，
    就会在「环境不同」时给出假红或假绿。
- **本修复不需要重发产物**：`check_doc_consistency.py` 与工作流文件都**不在** exe 的随包资源清单里，
  `SKILL.md` 未变，`--verify` 仍 10/10，产物哈希仍是发布件那一份 `dd7ae074…`。
  （这正是「随包资源用显式文件清单、不整目录打包」的收益：构建期/维护期文件不进产物，就不会互相拖累版本。）

## [1.4.1] — 2026-09-26

> **为什么要发 1.4.1 而不是只改文档**：本次改动里有 `SKILL.md` 的新增内容，而 `SKILL.md`
> **是打进 exe 的随包资源**——`build_exe.py --verify` 当场报出「产物内 SKILL.md 与仓库不一致」。
> 于是只剩两个选择：① 让已发布的 exe 带着**落后于仓库的方法论副本**（这正是本项目最忌讳的"产物落后于事实"）；
> ② 重建并如实发一个补丁版。**Release 不可变，内容变了就发新版本，不重写已发布资产。** 选 ②。

### Added
- **文档一致性机验 `scripts/check_doc_consistency.py` + CI 强制**（含变异自验）。
  **动的是一类此前没人管的问题：文档落后于事实。** 起因是 2026-09-26 一次普查漏出 3 处——
  `docs/distribution.md` 的 PR 文案里 Python 版本号比全库其余处**低两个次版本**（且那段是要公开发布的）、
  同文件 §E 把一条**已证伪**的判断当作现状（tag / Release / Pages 本地 token 就能做完）、
  `HANDOFF.md` 把**已经发布上线**的事列为待办。**这类漂移历来靠人眼 grep，而人眼会漏。**
  - 七项检查：① Python 版本口径唯一（对齐 CI matrix 最低版本）② 文档引用的 Release tag 真实存在
    ③ 官网标注的 SHA-256 / 体积 == 真实产物 ④ 官网无外链资源、锚点齐全 ⑤ 中英 README 徽章集合一致
    ⑥ **规则计数三方一致**（SKILL.md 条目数 == `docs/rule-provenance.md` 台账行数 == HANDOFF 声明数）
    ⑦ 已证伪表述不再出现（黑名单每条附「何时 / 被什么证伪」）。
  - **变异验证 7/7**：故意改坏（版本写错 / 引用不存在的 tag / 站点 SHA 不符 / 写回已证伪表述 /
    只删英文 README 一个徽章 / 站点加死锚点 / 台账少记一条）必须各被**对应**的检查拦下。
  - **消除三处重复实现**：`ci.yml` 与 `pages.yml` 原先各自内联了一份「官网自检」，加上脚本里的一份就是三处，
    改一处忘另两处就是漂移。现统一走该脚本的第 4 项检查。
  - CI 的打包工作流用 `--no-artifact`：站点记的是**已发布产物**，与 CI 现打包的字节必然不同
    （PyInstaller 非可复现构建），硬比会逼出「永远不许重建产物」的假红线。
- **中英文 README 首屏加「三条入口」导航**：桌面 exe / `npx skills add` / 官网。
  原先下载入口埋在「快速开始」折叠线以下，等于把 P3.5 的全部意义（把门槛降到「下载、双击」）藏起来。
- `SKILL.md` 环境坑新增 3 条（文档口径漂移靠人眼必漏 / 同一判据多处内联实现即漂移源 /
  在 CI 里比站点产物哈希会制造假红线），规则条目 28 → 31。

### Fixed
- **`docs/distribution.md` 的 PR 文案版本号漂移**：全库其余处已统一为 3.10+（CI matrix 最低 3.10），
  且这段文案是要**公开提交到 awesome 列表**的。已改正并加机验锁死。
  - 同族排查：`4 条`与`3 条`（楼中楼推翻结论）**不是漂移**——分属战3 与战7，`docs/retrospective.md`
    战表与 `docs/overturned.md` OT-3 各自对得上；「2 次幻觉引用」三处一致。**族穷举后再下结论，而不是只修已知的那一处。**
- **`docs/distribution.md` §E 与实际不符**：原文写「Release 首发与 Pages 核验（需要你的仓库权限，5 分钟）」，
  但三步**均已完成**（tag `v1.4.0` → `0ba07ce`、Release 已挂 exe、Pages 已启用并线上 HTTP 200）。
  已改写为完成态并附可复算证据（含 run id）；同时更正一处**根因误判**——Pages 首次部署失败的真因是
  **Pages 根本没启用**（`GET /repos/.../pages` → 404），不是「Source 没切到 GitHub Actions」。
- **`HANDOFF.md` 的「当前状态」与第 14 项**：删除"Release 首发后核验 Pages"这条已完成的待办；
  剩余「需要你本人账号」的动作从两类收敛为**一类**（awesome PR / 社区发帖——以用户身份公开发言）。
- **`docs/rule-provenance.md` §3 台账静默缺 10 条**：SKILL.md 的 `[环境]` 条目已有 17 条，台账只记了 7 行
  ——**"加了条目不进台账"这个缺口长期没人发现，因为没人对过数**。已补全 17 行，并把三方计数纳入机验（上述第 6 项）。
- **`ROADMAP.md` §P3 表**补入「Release 首发 + 官网上线」一行；§P3.5 验收补上 `--verify` 10/10 与发布上线事实。

### 备注
- 机验脚本首次跑通时**拦下了我刚刚写下的、解释这三处漂移的那段文字**——因为我在文档里原样引用了被禁的字符串。
  检查是对的，措辞是错的：**描述一个漂移时不该复现它的字面量**。该设计经验已写进脚本注释（与
  `verify_citations.py` 的已知误报同源：**"提及"与"断言"在纯文本里无法区分**）。
- 打包产物 `comment-distillery.exe` 已重建（内含 1.4.1 的 `SKILL.md`），随本版发布。**不重写 v1.4.0 的资产。**

## [1.4.0] — 2026-09-26（含 1.2 / 1.3 全部变更）

### Added
- **交付形态：Windows 桌面工具**（`app/` + `app_main.py`，约 11 MB 单文件 exe，免安装）—— 四页签一站式：① 采集 B站评论（含楼中楼，可中途停止）② 预处理（去重/去噪/统计）③ 导出蒸馏包 ④ 引用机验。
  - **不内置 LLM 是刻意选择**：exe 只产出「蒸馏包」（语料 + 方法论 + 可直接粘贴的 `PROMPT.md`），蒸馏交还给用户自选的 AI。因此**零 API Key、零调用成本**，且方法论永远引用仓库当前 `SKILL.md`，不会随 exe 固化而过期。
  - **GUI 只用标准库 `tkinter`**，零第三方运行期依赖；PyInstaller 仅构建期依赖。核心层 `app/core.py` **不重写任何方法论**，全部委托调用 `scripts/` 与 `contrib/`，保证 exe 与仓库永不分叉。
  - 自检三项全 PASS：`--selfcheck`（资源齐全）/ `--selftest-gui`（真建窗口）/ `--selftest-run`（端到端真跑 预处理→打包→引用机验）。
  - **`build_exe.py --verify`**：逐项比对产物内随包资源与仓库当前版本的 SHA-256，并反向检查"产物里混入了构建期脚本"。**防的是一类最隐蔽的漂移**——改了 `SKILL.md`/脚本后忘重建，exe 外表无异常、`--selfcheck` 照样 PASS（它只看"文件在不在"），但用户导出的蒸馏包里带的是过期方法论。
  - 随包资源改为**显式文件清单**（不再整目录打包）：`build_exe.py` / `make_icon.py` 属构建期，**故意不进产物**——否则"改构建脚本 → 产物过期 → 重建 → 又变"形成循环。
  - 构建可复现：`scripts/make_icon.py`（标准库手写 ICO，不引入 Pillow）+ `scripts/build_exe.py`（PyInstaller）+ `.github/workflows/build-exe.yml`（CI 真打包 + 双冒烟 + `--verify`）。
- **官网**（`site/index.html`）—— 单文件静态页，仿 SecAutoMind 设计系统；**其中每个数字都可在仓库中指到出处**，并保留 honest limitations 段落。`.github/workflows/pages.yml` 发布到 GitHub Pages。
- **CLI 脚本抽出可调用入口**（纯增量，未改任何 CLI 签名）：`prep.run()` / `verify_citations.run()` / `fetch_bilibili_comments.crawl()`，供桌面工具与 CLI 共用同一条实现，避免两套逻辑漂移。
- **`corpus_ccf.csv`** —— `prep.py` 新增产出规范语料（Canonical Corpus Format），作为引用机验与跨语料合并的单一真值源。
- `tests/test_app_core.py`（16 个用例，全量 45 → **61**）。

### Fixed
- **CI 的 Windows 打包工作流整步失败：`print` 中文在 cp1252 控制台上抛 `UnicodeEncodeError`**（tag 首跑实测暴露）。报错看着像逻辑错，实际是编码错——**本地中文区域是 cp936 所以一切正常，问题只在 CI 才现形**。两头修：① 五个脚本入口加 `utf8_stdout()`（`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，被重定向成 StringIO 时静默跳过）；② `build-exe.yml` 统一设 `PYTHONUTF8=1`；③ `ci.yml` 加一道**编码守卫**步骤：在 `PYTHONIOENCODING=cp1252` 下真跑一遍「话最多」的四个脚本，锁死这类回归（顺带断言图标重生成字节不变 = 构建可复现）。
- **CI 哈希步骤的 `Select-String` 按 ANSI 读无 BOM 的 UTF-8 文件**：从 `site/index.html` 抓体积标注必然乱码 → 匹配不到 → 下一步 `$Matches[0]` 索引越界。改用 `Get-Content -Raw -Encoding UTF8` + `[regex]::Match`，并在正则未命中时给出明确错误而不是让 PowerShell 抛异常。
- **`verify_citations.py` 的 `--field` 参数形同虚设**：一直被 argparse 解析，却从未传进 `load_ids()`，显式指定列名等于无效。现已接通，并补了「显式指定 → 命中；指定不存在的列 → 回退」的双向验证。
- **重复评论未被去重**（第六战实测发现）：一份 20,399 行的抓取结果里，**4,501 行是同 ID、同内容、同赞数的完全重复行**（占 22%），根因是热度排序（`mode=3`）下点赞数实时变化、分页游标在相邻页之间重叠。后果不只是规模虚高——**它会让同一条观点被重复计入共识度**，直接污染"高赞即共识"的判断。修复：
  - `scripts/prep.py` 在去噪前按 ID 去重，并在 `stats.json` 新增 `dup_dropped` 字段；
  - `contrib/fetch_bilibili_comments.py` 的 `fetch_main` 按 `rpid` 去重，整页重复时提前终止翻页；
  - 新增 2 个回归测试（`test_duplicate_ids_are_dropped` / `test_dup_dropped_zero_on_clean_corpus`），并做**变异验证**：人为取消去重后测试必须 FAIL。

### Added（P3 分发 / P2 方法论去过拟合 / 语料）
- **P3 分发（进行中）** — `docs/distribution.md` 作战清单：可直接复制的 GitHub metadata 命令、awesome 列表英文 PR 文案、Reddit/中文社区帖子骨架、方法论长文大纲。
  - 已完成：`npx skills add TrueFurina/comment-distillery` 适配（`--list` 实测 **Found 1 skill**）；SKILL.md frontmatter 改为**触发式 description** + `metadata.version`；中英文 README 第一屏新增**真实产出片段**（引用溯源 / 反例对冲 / 行动清单 / 自曝盲区四段）。
  - ⚠️ 适配规范要点：仓库根 `SKILL.md` 即构成单 skill 仓库、无需 manifest；**绝不能在其旁边再建 `skills/` 目录**（根 SKILL.md 会短路 CLI 发现）。
  - 已完成（2026-09-26）：GitHub 元数据 —— description 已设、topics **12 → 16**（补入 `agent-skills` / `claude-skills` / `skills` / `ai-agents`）。**复核发现原 `agentskills` 无连字符，与生态流通检索词 `agent-skills` 不等价，等于白加。**
  - 仅剩需仓库所有者执行的：awesome 列表 PR（3 个已核实仓库）/ 社区发帖。文案已就位。
- **`cases/` 实战档案公开（产物层）** — 七战的最终产物首次进仓库：**9 个 md / 277 KB**，含 6 份各战深度指南 + 设计留档（方案论述 / 开源冲刺路线图）+ 导读 README。
  - **只公开产物层**：原始评论 CSV 与流水线中间产物（`all_comments.txt` / `id_map.json` / `stats.json`）**不公开**，依据 `docs/compliance.md` §2「不得二次分发原始语料」。实现方式为 `.gitignore` 按扩展名反向白名单（`/cases/**/*.{csv,txt,json,py,svg}` 全忽略）。
  - `cases/README.md` 导读明确两件易错事：**目录编号 ≠ 战次编号**（`05-mustwatch-math` 实为第 6+7 战；第 5 战是回归测试、在 `examples/`）；第 6 战增补卷与正卷的**结论冲突是有意保留**的真实痕迹，非文档错误。
- **P2 方法论去过拟合** — SKILL.md 里多数规则只被 1 战验证过，个案被写成铁律会误导后续使用者。现在每条规则带溯源标记，且**机验强制**：
  - `docs/rule-provenance.md` — 规则溯源台账：**9 条铁律**（≥2 战独立验证）/ **5 条待复现**（仅 1 战）/ 7 条环境事实。每条待复现项附**复现判据**（第二次遇到什么证据才算成立）。
  - `docs/overturned.md` — 被推翻结论台账 OT-1…OT-5，每条写明「曾经相信 / 被什么打穿 / 现在怎么做 / **再次推翻的条件**」。附元观察：五次失效的共同点是**用代理指标代替真值**（点赞数↔认可度、文本长度↔思考深度、楼层深度↔观点完整性、ID 格式↔引用真实、行数↔语料规模）。
  - `scripts/check_rule_tags.py` — 机验 SKILL.md 无裸铁律，含 `--self-test` 变异验证。实测：**24/24 条目带标记、裸铁律 0；变异 3/3 拦截**。已接入 CI（新增两步）。
  - SKILL.md 新增「待复现观察」章节，单战证据（meta 噪音 / 多语料合并 / 楼中楼两用途 / 粘贴板污染 / 注意力漂移 2.5×）**降级为假设**，不再混在铁律里。
  - `tests/test_rule_tags.py`（6 个用例，全量 39 → **45**）。
- **golden 评估集** — 让「换模型 / 改 SKILL.md / 调参数后是否变强」从感觉变成数据。8 个场景分 4 类（`citation` / `coverage` / `counterevidence` / `layering`），每类都有真实出处：
  - `golden/cases/*.json` — 场景集（纯数据）。**用 JSON 不用 YAML**：本项目零依赖是硬约束，PyYAML 会破承诺。
  - `golden/graders.py` — 判分器，8 种规则类型；`citation_real` **复用** `scripts/verify_citations.py`，不重写。
  - `golden/run_golden.py` — 跑分器：`--replies <dir>` **离线判分**（不绑定任何 CLI 或模型）/ `--baseline` / `--self-test` / `--compare`。
  - **`--self-test` 变异验证**：从 baseline 派生"故意违反"的回复，验证分数必须下降、红线类必须归 0。实测 **31 个变异体全部被正确扣分**。一个永远给满分的判分器能让所有测试通过，却什么都没测出来——这一步就是防它。
  - 实测：baseline 跑分 **100.0 / 100**；已接入 CI（新增 `--self-test` + `--baseline` 两步）与 `tests/test_golden.py`（12 个用例，全量 39）。
- `docs/collecting.md` — **语料从哪来**：按平台汇总当下可用的现成采集工具（B站 / YouTube / Reddit / 小红书·抖音·快手·微博·贴吧·知乎 / agent-native 多平台），标注许可证差异与法律风险，并给出"任意工具输出 → CCF"的字段映射方法与选型决策流程。
- `docs/retrospective.md` — **七战沉淀**：五次被打穿的方法论、7 条可复用量化判据、交付质量门 G1–G7、与 AGI-Distiller 的对照学习、已知局限。
- `ROADMAP.md` — 长期规划 P0–P5，每阶段含**验收门槛与停止条件**。

### Validated
- **第六战**：B站「入站必刷」级视频（3,640 万播放 / 31,145 条评论），一级评论 14,526 条（去重去噪后口径），产出 15 章深度指南。本次为迄今最大规模，并首次在**近乎全正向情绪的语料**上验证"反例对冲"仍需主动开采（详见指南第十四章）。回归用例增至 **27 个**。
- **第七战（辩论层补抓）**：同视频全量补抓楼中楼 **6,724 条**（一级 14,376 + 楼中楼 6,724 = **21,100** 条），产出增补卷 10 章 / 31.7KB，引用机验 **54 条 / 0 幻觉**。三项实证：
  - **楼中楼是结构性刚需**：占条数 31.9% 却只占点赞量 14.6%（均赞 22.0 vs 一级 60.1）——声音小但信息密度高；**正卷 3 处结论/引用被修正**（教育应用反例、欧拉公式解析被判循环论证、aleph 表述被推翻），已在正卷卷首回填交叉引用。
  - **注意力漂移首次量化**：一条与视频数学内容**零相关**的英语语法争论楼（81 条 / 2,867 赞）是"视频有无教育价值"实质辩论（69 条 / 1,142 赞）的 **2.5 倍**。
  - **"低赞长文＝真信号"规则被修正**：低赞区混入大量**粘贴板 pasta**（鸿蒙长文 / 歌词 / 游戏攻略），需追加"有具体指称"的人工判据。

### Planned
- 更多语料域的适配示例（问卷 / 访谈 / 工单）
- 跨语料聚合（同一议题的多来源合并）
- 真·人工校验 loop

---

## [1.1.0] — 2026-09-26

### Added
- **场景升维**：从"B站评论"泛化为**任何群体文本语料**（评论区 / 问卷开放题 / 访谈逐字稿 / 产品反馈 / Issue 讨论 / 会议纪要 / 弹幕）。
- **Canonical Corpus Format（CCF）**：统一语料格式，把平台差异关在输入层；完整字段别名表见 `docs/canonical-format.md`。
- `docs/domains.md` — 各语料域的偏差结构与读法调整。
- `docs/pipeline.md` — 6 步流水线详解与实操参数。
- `docs/compliance.md` — 合规与伦理边界细化。
- `contrib/` — 可选采集桥接（`fetch_bilibili_comments.py`），明确标注非核心、无支持。
- `examples/` — 合成示例语料与示例指南（零真实用户数据）。
- `tests/` — 25 个回归用例（纯标准库 unittest）。
- `.github/workflows/ci.yml` — 多版本测试 + **零依赖守卫** + 端到端冒烟。

### Changed
- `prep.py` 通用化：扩展字段别名、输出 `low_score_long.txt`（低权重长文，真信号区）、新增作者多样性统计、更保守的子串匹配（避免 `id` 误命中 `用户id`）。
- 新增独立工具 `verify_citations.py`：把此前写在 SKILL.md 里的引用机验代码片段，升级为一等公民脚本。
- `SKILL.md` 重写为平台中立 + 语料域无关。

### Fixed
- `verify_citations.py`：markdown 表格内转义的竖线（`[源:c123\|权重7\|一级]`）会被并入 ID，导致把真实引用误报为幻觉引用。已修正字符类并加回归测试。

---

## [1.0.0] — 2026-09-03

### Added
- 6 步流水线：接入 → 预处理 → 通读聚类 → 框架抽取 → 结构化输出 → 验证。
- 三件套护城河：**反例对冲 / 引用溯源 / 盲区诚实说明**。
- 三档输出（深度版默认 / 标准版 / 极简版）。
- `scripts/prep.py` — 零依赖预处理（编码容错、去噪、按权重排序、保留 ID 映射）。
- 合规前置声明。

### Validated
跨话题、跨规模、跨语料形态的实战验证（详见 `SKILL.md` 「首测数据集」）：

| # | 规模 | 语料 | 关键验证 |
|---|---|---|---|
| 1 | 1,504 | AI 替代程序员 | 流水线可行性 |
| 2 | 3,425 | AI 生成科幻电影 | 争议专场结构 |
| 3 | 5,052 | 精英教育心态 | **楼中楼推翻顶层结论**（4 条直接对冲） |
| 4 | 8,941 | 双视频合并（薪资 / 中年被裁） | **多语料合并产出新洞察**；**引用机验抓到 1 条幻觉引用** |
