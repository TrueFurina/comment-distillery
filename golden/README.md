# Golden Test Set

让「换模型 / 改 SKILL.md / 调参数后是否变强」从**感觉**变成**数据**。

设计照搬 AGI-Distiller 的三分离原则，格式改为 JSON 以适应本项目的**零依赖**约束（PyYAML 会破承诺）。

```
golden/
├── cases/*.json        场景集（纯数据，可增删，不含逻辑）
│   ├── citation.json          引用真实
│   ├── coverage.json          覆盖率诚实
│   ├── counterevidence.json   反例开采
│   └── layering.json          辩论层意识
├── graders.py          判分器（只判分，不关心回复是谁产生的）
├── run_golden.py       跑分器（编排 + 报告落盘 + 变异验证）
├── replies/baseline/   理想回复（应拿满分；也是变异验证的原料）
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

**计分**：每场景 0–5 分 = `5 × 通过规则数 / 总规则数`；**命中任一红线直接 0 分**。
**加权**：`总分 = Σ(score×weight) / Σ(5×weight) × 100`。

## 为什么必须有 `--self-test`

测试全绿 ≠ 判分器有效。一个永远给满分的判分器能让所有测试通过，却什么都没测出来。

`--self-test` 从每份 baseline 派生"故意违反"的变异体（删关键词 / 插禁词 / 把引用 ID 换成不存在的 `c9999999`），
验证分数**必须下降**、红线类**必须归 0**。**变异体还能拿满分 = 判分器无效，退出码 1。**

当前：8 个场景 / 31 个变异体，全部被正确扣分。

## 已知局限（诚实）

1. **禁词是朴素字符串匹配，否定语境会误伤**。实测踩过：baseline 写"绝不能**凭印象**补一个 ID"，
   被 `must_not_contain: ["凭印象"]` 判为红线——语义完全正确却被判错。
   规避：写 baseline/回复时绕开禁词的否定用法；选用带上下文的短语（如"凭印象补"而非"凭印象"）能降低误伤率。
2. **`regex_*` 规则的变异无法通用构造**（不知道该删哪段文本才能让它不命中），`--self-test` 记为 skipped。
   当前 8 个场景均未使用 regex 规则，故不影响有效性。
3. **判的是形式与可溯源，不判推断质量**。一条"引用真实但推理错误"的结论能通过全部 8 个场景——
   这是本评估集的边界，不是它的缺陷，但也别把它当成质量证明。
4. **场景只覆盖 4 类**。语料域适配、跨语料聚合等能力尚无场景。
