# Golden Test Set

让「换模型 / 改 SKILL.md / 调参数后是否变强」从**感觉**变成**数据**。

设计照搬 AGI-Distiller 的三分离原则，格式改为 JSON 以适应本项目的**零依赖**约束（PyYAML 会破承诺）。

```
golden/
├── cases/*.json        场景集（纯数据，可增删，不含逻辑）
│   ├── citation.json          引用真实
│   ├── coverage.json          覆盖率诚实
│   ├── counterevidence.json   反例开采
│   ├── layering.json          辩论层意识
│   └── inference_quality.json 推断质量（边界意识 / 盲区披露 / 数字锚定）
├── graders.py          判分器（只判分，不关心回复是谁产生的）
├── run_golden.py       跑分器（编排 + 报告落盘 + 变异验证）
├── replies/baseline/   理想回复（应拿满分；也是变异验证的原料）
├── replies/example/    弱推断对照样本（演示 --replies 如何抓住过度泛化 / 无来源数字）
└── results/            跑分报告（gitignore，随时可重生成）
```

## 用法

```bash
# 1) 离线判分（推荐）——不绑定任何 CLI 或模型
#    把每个场景的 agent 回复存为 <dir>/<case_id>.txt
python golden/run_golden.py --replies <dir>

# 2) 基线自测：场景集与 baseline 是否自洽（应 100 分）
python golden/run_golden.py --baseline

# 3) 变异验证：判分器是否真的能扣分（CI 强制）
python golden/run_golden.py --self-test

# 4) 跨版本对比
python golden/run_golden.py --compare results/a.json results/b.json
```

## 给真实回复做体检（`--replies` 实战）

`--replies` 是这套评估集的**主用途**：把你蒸馏出的真实回复拿去跑分，不绑定任何 CLI 或模型。
它直接复用 `grade()`，包括 `inference_quality` 三个推断质量维度——所以"引用真实但推断薄弱"的回复会被扣分。

### 步骤

```bash
# 0) 先看有哪些场景、各自属于哪类（case_id 就是你要创建的 txt 文件名）
python -c "import sys; sys.path.insert(0,'golden'); import graders; \
           [print(c['id'], '->', c['category']) for c in graders.load_cases()]"

# 1) 建一个目录，把每个场景的回复存成 <case_id>.txt
mkdir -p /tmp/my-replies
#    例如针对 inference-scope-hedging 场景：
#    echo "你的结论文本…" > /tmp/my-replies/inference-scope-hedging.txt
#    （只跑你关心的场景即可——没提供的场景会被列为 no_reply，不计入总分，
#      不会悄悄被当成 0 分拉低成绩）

# 2) 跑分
python golden/run_golden.py --replies /tmp/my-replies
#    默认会把报告落盘到 golden/results/；加 --no-save 只打印不落盘
```

### 对照：理想 vs 弱推断

仓库自带 `golden/replies/example/` 两个"故意写弱"的样本，可直接复跑看效果：

```bash
python golden/run_golden.py --replies golden/replies/example --no-save
```

| 样本 | 类别 | 评分 | 被抓的原因 |
|---|---|---|---|
| `inference-scope-hedging`（example） | `inference_quality` | **0/5** | 把"六成评论吐槽"直接推成"口碑全面崩坏"——无边界锚定、无盲区披露 |
| `inference-numeric-anchoring`（example） | `inference_quality` | **2/5** | 给了 31.9% 却没锚定样本量（软扣分，非归零） |
| 同两个场景（baseline） | `inference_quality` | **5/5** | 锚定到本批样本、主动披露局限、百分比绑定语料 |

> 注意：这两个 example 只覆盖了 2 个场景，所以 `总分` 只反映这 2 个场景的加权结果（16/100），
> 不是全集分数。全集对照请用 `--baseline`（应 100 分）。

## 场景结构（JSON）

```json
{
  "id": "citation-provenance",
  "category": "citation",
  "weight": 3,
  "prompt": "给 agent 的输入指令",
  "expect": {
    "must_contain": ["[源:"],
    "citation_real": {"corpus": "examples/sample_corpus.csv"}
  },
  "rationale": "为什么这个场景重要（出处）",
  "source": "战4 / 战6"
}
```

规则类型：

| 规则 | 含义 | 红线？ |
|---|---|---|
| `must_contain` | 全部关键词必须出现 | |
| `must_contain_any` | 至少一个候选词出现 | |
| `must_not_contain` | 禁词出现即整场景 0 分 | ✅ |
| `regex_must_hit` / `regex_must_not_hit` | 正则命中判定（后者为红线） | 后者 ✅ |
| `citation_real` | 引用机验（复用 `scripts/verify_citations.py`），差集非空即 0 分 | ✅ |
| `files_must_exist` / `files_must_not_exist` | 产物路径判定（后者为红线） | 后者 ✅ |
| `inference_quality` | 推断质量判分（边界意识 / 盲区披露 / 数字锚定），软扣分、无红线 | |

**计分**：每场景 0–5 分 = `5 × 通过规则数 / 总规则数`；**命中任一红线直接 0 分**。
**加权**：`总分 = Σ(score×weight) / Σ(5×weight) × 100`。

## 为什么必须有 `--self-test`

测试全绿 ≠ 判分器有效。一个永远给满分的判分器能让所有测试通过，却什么都没测出来。

`--self-test` 从每份 baseline 派生"故意违反"的变异体（删关键词 / 插禁词 / 把引用 ID 换成不存在的 `c9999999`），
验证分数**必须下降**、红线类**必须归 0**。**变异体还能拿满分 = 判分器无效，退出码 1。**

当前：10 个场景 / 35 个变异体，全部被正确扣分。

## 已知局限（诚实）

1. **禁词是朴素字符串匹配，否定语境会误伤**。实测踩过：baseline 写"绝不能**凭印象**补一个 ID"，
   被 `must_not_contain: ["凭印象"]` 判为红线——语义完全正确却被判错。
   规避：写 baseline/回复时绕开禁词的否定用法；选用带上下文的短语（如"凭印象补"而非"凭印象"）能降低误伤率。
2. **`regex_*` 规则的变异无法通用构造**（不知道该删哪段文本才能让它不命中），`--self-test` 记为 skipped。
    当前 10 个场景均未使用 regex 规则，故不影响有效性。
3. **判的是形式与可溯源 + 推断质量结构信号**。2026-11-02 新增 `inference_quality` 类别（边界意识 / 盲区披露 / 数字锚定），
   能抓住"引用真实但过度泛化 / 无盲区意识 / 数字无来源"的回复（见 `cases/inference_quality.json`）。
   但仍是**结构信号而非语义级判分**——不调用模型，无法判断推理链本身是否严密，别把它当成质量证明。
4. **场景覆盖 5 类**。语料域适配、跨语料聚合等能力尚无场景。
