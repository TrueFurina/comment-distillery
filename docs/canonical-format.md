# Canonical Corpus Format（统一语料格式，CCF）

**核心思想**：采集层的差异（平台、字段名、层级模型、时间格式）**全部关在输入层**。任何来源归一成同一张表之后，下游 6 步流水线完全一致。

这是本项目实现"平台中立"的工程手段——不是写一堆平台适配器，而是定义一个足够小的公共内核。

---

## 1. 字段定义

| 字段 | 类型 | 必需 | 语义与约定 |
|---|---|---|---|
| `id` | string | ✅ | 唯一标识，**溯源锚点**。省略时脚本按行号生成 `r{i}`（但这样无法跨轮次对齐，不推荐） |
| `text` | string | ✅ | 正文。空值 / 纯符号 / 纯 emoji / 纯链接 / 含广告关键词者会被去噪丢弃 |
| `score` | int | 推荐 | **群体认可度**：点赞 / 赞同 / upvotes / stars。用于排序与权重，**不是真值**（见 SKILL.md「高权重 ≠ 高信号」） |
| `reply_count` | int | 推荐 | 被回复数。用于筛选「讨论型深水区」（如 `>=3` 的楼中楼） |
| `parent_id` | string | 可选 | 父条目 ID，用于还原层级 |
| `is_reply` | bool | 可选 | 是否回复。决定输出里的 `一级` / `回复` 标记。真值集合：`1/true/yes/是/回复/子` |
| `created_at` | string | 可选 | 时间。用于时间切片偏差分析（格式不限，原样保留） |
| `author_id` | string | 可选 | 作者标识。**仅用于内部的多样性与去重统计，产出中不得外泄** |
| `source` | string | 可选 | 来源标记。合并多份语料时用于区分（如 `bilibili` / `reddit` / `survey-2026Q3`） |

### 最小可用集

```csv
id,text
c001,这条评论只提供正文也能跑
c002,只是精度会降低——没有权重就没法排序
```

**`id` + `text` 两列即可运行**，其余字段有则更准。

---

## 2. 字段别名表（自动映射）

`prep.py` 与 `verify_citations.py` 的字段识别规则：**先精确匹配，再子串匹配（子串候选须 ≥3 字符，避免 `id` 误命中 `用户id`）**。

| 逻辑字段 | 认得的列名（不区分大小写） |
|---|---|
| `id` | `评论id` `comment_id` `commentid` `cid` `id` `评论编号` `条目id` `item_id` |
| `text` | `评论内容` `content` `text` `内容` `comment` `正文` `message` `body` `回复内容` |
| `score` | `点赞数` `likes` `like` `点赞` `赞` `score` `upvotes` `upvote` `赞同数` `赞同` `热度` `stars` `star` |
| `reply_count` | `回复数` `replies` `reply` `reply_count` `子评论数` `回复` |
| `created_at` | `发布时间` `时间` `created_at` `datetime` `timestamp` `date` `time` `创建时间` |
| `is_reply` | `是否为回复` `is_reply` `isreply` `是否回复` `类型` |
| `author_id` | `用户id` `userid` `uid` `author_id` `作者id` `author` `用户` `用户标识` |
| `parent_id` | `父评论id` `parent_id` `parentid` `父id` `根评论id` `root_id` `root_comment_id` |
| `source` | `source` `来源` `平台` `platform` |

> 你的列名不在表里？两个办法：① 改成表里的任一名字（推荐，零成本）；② 提 PR 加一行别名。

---

## 3. 常见来源的映射示例

### 3.1 BilibiliCrawler / contrib fetch 脚本导出

原始列（中文）：

```csv
评论ID,根评论ID,是否为回复,评论内容,点赞数,回复数,时间,父评论ID,用户ID
c312425418241,c312425418241,否,这条评论的正文…,393,12,2026-08-01 10:22:31,,12345678
```

映射：**零改动直接可用**（列名已在别名表内）。

### 3.2 MediaCrawler 导出

MediaCrawler 的 JSON/CSV 字段名通常为 `comment_id` / `content` / `like_count` / `sub_comment_count` / `create_time` / `user_id`。
注意 `like_count` 的子串匹配会命中 `like`（✅），`sub_comment_count` 不在别名表内 → **建议在导出时改名或用一行 Python 映射**：

```python
import csv
ren = {"comment_id": "id", "content": "text", "like_count": "score",
       "sub_comment_count": "reply_count", "create_time": "created_at",
       "user_id": "author_id"}
with open("raw.csv", encoding="utf-8-sig", newline="") as f, \
     open("ccf.csv", "w", encoding="utf-8", newline="") as g:
    r = csv.DictReader(f)
    w = csv.DictWriter(g, fieldnames=["id", "text", "score", "reply_count", "created_at", "author_id"])
    w.writeheader()
    for row in r:
        w.writerow({v: row.get(k, "") for k, v in ren.items()})
```

### 3.3 问卷开放题（一个受访者一条，或一题一列）

问卷通常没有"点赞"。此时 `score` **留空或填 0**——流水线不依赖它排序，但需要你改用「主题饱和度」判断何时停止阅读（读完全部即可，问卷量通常不大）。

```csv
id,text,created_at
resp001,我觉得最大的问题是流程太复杂…,2026-09-01
resp002,希望能支持批量导出…,2026-09-01
```

> ⚠️ 问卷语料**不要**把 `author_id` 设成姓名/学号——用匿名编号。

### 3.4 访谈逐字稿

逐字稿通常是"说话人 + 段落"结构，先切成「发言片段」再归一：

```csv
id,text,author_id,created_at,source
i01-p03,（受访者A）我一开始以为这个功能很简单…,speakerA,2026-08-15,interview-A
i01-p04,（主持人）那你后来怎么处理的？,interviewer,2026-08-15,interview-A
```

> 提示：访谈里主持人的提问通常属于**噪音**（不是受访者的观点），可在 CCF 里用 `source` 或先人工剔除；若保留，需在指南中明确区分"研究者的提问"与"受访者的表达"。

### 3.5 GitHub Issue / PR 讨论

GitHub API 的数据天然贴合 CCF：`id` ← comment `id`，`text` ← `body`，`score` ← reactions `+1` 数，
`created_at` ← `created_at`，`author_id` ← `user.login`，`parent_id` ← 被回复的 comment id。

> ⚠️ GitHub 用户名是**公开身份**，比匿名 UID 更敏感。产出中引用内容时**不要带上 `@username`**。

---

## 4. 多份语料合并

同议题的多来源合并常能浮现单份看不到的结构性洞察（实测：两份关于"程序员薪资 / 中年被裁"的独立语料合并后，才看出"初级岗位消失 → 成长通道断裂"这条闭环）。

合并时**务必**：

1. 用 `source` 字段标记来源，避免无法区分；
2. 确认 `id` 无冲突（不同平台可能都用纯数字 ID）——**加前缀**：`bl_c123` / `rd_456`；
3. 在指南的「方法与边界」里披露合并口径（哪几份、各自规模、时间跨度）。

**⚠️ 合并的 `score` 不可直接比较**——B站的赞和 Reddit 的 upvote 不是同一量纲。若要跨源排序，需先归一化（如各自转百分位），否则只用它做**同源内**排序。

---

## 5. 编码

脚本按 `utf-8-sig → gb18030 → gbk → utf-8` 顺序尝试，中文 Windows 常见的 GBK 导出可自动处理。

若仍失败，用一行命令转码：

```bash
python -c "open('ccf.csv','w',encoding='utf-8-sig').write(open('raw.csv',encoding='gb18030').read())"
```
