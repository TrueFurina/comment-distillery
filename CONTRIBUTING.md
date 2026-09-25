# 贡献指南

感谢你有兴趣贡献。这个项目很小，规则也很简单——但下面几条是**硬规则**。

---

## 硬规则（PR 会被直接拒绝的情况）

### 1. 不许引入第三方依赖（核心目录）
`scripts/` 与 `tests/` **只能用 Python 标准库**。这是项目的核心承诺之一（"零依赖，不用 pip install 就能跑"），CI 里有守卫会拦。

需要某个重库才能做的事，请开 issue 讨论，而不是直接加依赖。

### 2. 不许提交真实语料 / 凭证
- 真实评论 CSV、问卷数据、访谈记录、用户反馈 **一律不得提交**（`.gitignore` 已覆盖常见路径，但请自觉）。
- Cookie / token / 登录态 **一律不得提交**。
- `examples/` 下只允许**合成数据**，且必须在文件里注明。

### 3. 不许向核心加入采集 / 反爬 / 绕过限制的代码
采集属于 `contrib/`（可选、无支持），且**不得包含绕过风控的选项**。这是本项目能保持 MIT 可商用、企业可采用的前提。见 `docs/compliance.md`。

### 4. 不许削弱三件套
反例对冲、引用溯源、盲区诚实说明是**不可选**的。任何 PR 若让它们变成 optional，会被拒绝。

---

## 开发流程

```bash
git clone https://github.com/TrueFurina/comment-distillery.git
cd comment-distillery

# 跑测试（无需安装任何东西）
python -m unittest discover -s tests -v

# 端到端冒烟
python scripts/prep.py examples/sample_corpus.csv /tmp/cd-out
python scripts/verify_citations.py examples/sample_guide.md examples/sample_corpus.csv
```

### 提交前自检清单

- [ ] `python -m unittest discover -s tests -v` 全绿
- [ ] 新增行为**都**有对应测试用例（含边界与失败路径）
- [ ] 没有引入第三方依赖
- [ ] 没有提交真实数据 / 凭证
- [ ] 若改了 CLI 参数或产出格式，同步更新 `README.md`、`docs/`、`SKILL.md`
- [ ] 若修了 bug，在 `CHANGELOG.md` 记录（说明**根因**，不只是"修了个 bug"）

---

## 最欢迎的贡献

| 类型 | 说明 |
|---|---|
| **新的语料域适配示例** | 问卷 / 访谈 / 工单 / 会议纪要的真实（脱敏或合成）用例 + 读法经验 |
| **真实踩坑记录** | 环境坑、编码坑、平台坑——这类知识最稀缺 |
| **测试加固** | 尤其是边界条件与失败路径 |
| **文档纠错** | 错别字、过时描述、表述不清 |
| **反例对冲的实例** | 补充被反例推翻的结论案例 |

---

## 关于"修 bug"

修 bug 的 PR 请包含：

1. **根因说明**（不是"这里错了"，而是"为什么会错"）；
2. **能复现该 bug 的测试**（先红后绿）；
3. 若该 bug 有代表性，在 `CHANGELOG.md` 的 Fixed 段落记录。

> 示例：`verify_citations.py` 曾把 markdown 表格内转义的竖线并入 ID，导致真实引用被误报为幻觉。根因是正则字符类未排除反斜杠——修复 + 回归测试 + CHANGELOG 记录，三件一起。

---

## 提交信息

用简洁的祈使句，推荐 `type: subject`：

```
feat: 支持 GitBook 导出的 CCF 映射
fix: prep.py 对 utf-16 编码的容错
docs: 补充访谈语料的角色切分说明
test: 覆盖 csv 字段数不匹配的边界
```

---

## Code of Conduct

参与本项目即表示同意遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。

---

## License

贡献即表示你同意以 [MIT](LICENSE) 许可发布你的贡献。
