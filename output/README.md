# ⚠️ 本目录不是 scratch —— 请勿整体清空

`output/` 存放的是**用户交付物**，不是可以随手清掉的临时垃圾。

## 里面有什么

| 条目 | 说明 | 可否删除 |
|---|---|---|
| `distill-YYYYMMDD-HHMMSS/` | 蒸馏包。内含 `report.html`、`guide.md`、`corpus_ccf.csv`、`stats.json` 以及**按标题命名的报告副本** | ❌ 不可删 |
| `报告索引.html` | 全部报告的总入口（链接指向各包的标题命名副本） | ❌ 不可删 |
| `prep-*/` | 预处理中间产物，可重跑 | ⚠️ 先确认 |
| `comments-*.csv` | 采集到的原始评论。**受平台/合规约束，重新采集不等于拿到同一批数据** | ❌ 不可删 |
| `e2e*` `dbg*` `tmp*` `ctl` `p13*` `ui-final` 等 | 调试/冒烟遗留 | ✅ 可删（用 `scripts/clean_scratch.py`） |

## 为什么不能像清理 scratch 那样清掉

1. **产物不可复现**。蒸馏依赖 LLM，同一个视频、同一个模型跑两轮，引用数与标题都会不同
   （实测：`BV1U4nZ6aE9W` 第一轮 62 条引用、第二轮 51 条引用，标题也不一样）。
   「应用下次运行会重建」只对**目录结构**成立，**不会重建历史报告内容**。
2. **没有版本库兜底**。`.gitignore` 忽略了 `output/*`（合规要求：不得二次分发原始语料），
   所以报告**从来没有进过 git**，一旦被清空就无法从版本库恢复。

## 清理前请走这两步

```bash
# 1) 先备份交付物（快照到 output/_backup/<时间戳>/）
python scripts/backup_reports.py

# 2) 再清调试残留（默认 dry-run，只打印不删；确认后加 --yes）
python scripts/clean_scratch.py
python scripts/clean_scratch.py --yes
```

`clean_scratch.py` 内置保护名单，`distill-*` / `报告索引*` / `comments-*.csv` / `prep-*`
即使传 `--yes` 也不会被删。

## 如果已经误删了

历史归档：`E:\Program\_cd_scratch_archive_20261102\output\`
双击项目根的 `恢复报告.bat` 可一键拷回。
