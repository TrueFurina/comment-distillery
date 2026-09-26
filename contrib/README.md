# contrib/ — 可选的采集桥接（非核心）

> **本目录不属于 comment-distillery 的核心范围，也不在官方支持范围内。**
> 核心范围只有一件事：把**已经拿到的**群体文本语料蒸馏成有引用溯源的深度指南。
> 采集（L1）是另一层，已有成熟生态，本项目**不重复造轮子**。

## 为什么单独放这里

三层架构里，本项目的定位是 **L3**：

```
L1 采集   →  L2 统计摘要  →  L3 建设性综合
(红海)       (红海)          ★ 本项目
```

`contrib/` 里的脚本是为了让「只有视频链接、没有 CSV」的用户也能快速上手，属于**便利性桥接**，不改变项目定位。

## 包含什么

| 文件 | 说明 |
|---|---|
| `fetch_bilibili_comments.py` | B站评论拉取（纯标准库、零依赖），输出符合 CCF 的 CSV |

> **也被桌面工具复用**：`app/core.py` 调用本文件的 `crawl(arg, out_csv, roots_only, on_log, on_progress, should_stop)`，不另写一份抓取逻辑。**改本文件时要保证 `crawl()` 的参数语义不变**（GUI 的 ① 采集 页签依赖 `on_progress` 回调与 `should_stop` 协作式停止：中途停止时已抓部分照常写出）。

### 用法

```bash
# 只拉一级评论（推荐：快、稳、观点主体）
python fetch_bilibili_comments.py BV1o74y6XEcM out.csv --roots-only

# 一级 + 讨论型楼中楼（rcount>=3），带指数退避重试
python fetch_bilibili_comments.py BV1o74y6XEcM out.csv

# 也接受完整链接
python fetch_bilibili_comments.py "https://www.bilibili.com/video/BV1o74y6XEcM/" out.csv
```

实现要点（踩坑记录，供参考）：
- 经官方 `view` 接口取 `aid`——**不要自己实现 bv2av**，网上版本错配极多。
- WBI 签名（`w_rid`）+ 强制直连（`ProxyHandler({})`）——绕开 Windows 系统代理污染导致的 `SSL: UNEXPECTED_EOF_WHILE_READING` 假死。
- 子回复接口限流极严，一遇 `-412 / -509` 需长休眠重试；只抓 `reply_count>=3` 的讨论楼，避免无效请求雪崩。

## 更重要的事：用自己的采集器

`contrib/` 只是便利。**更推荐**用成熟的采集工具导出 CSV，再映射成 CCF 喂给本流水线：

- **MediaCrawler** — 多平台（B站/小红书/抖音/快手/微博/贴吧/知乎），Playwright，可复用本机登录态。
- **BilibiliCrawler** — 桌面 GUI，扫码登录，导出 CSV，支持 MCP 调用。
- 平台官方导出 / 自研脚本 / 问卷系统导出 —— 任何能产出 CSV 的方式都行。

映射方式见 [`../docs/canonical-format.md`](../docs/canonical-format.md)：**只需要 `id` + `text` 两列就能跑**，其余字段有则更准。

## 合规（使用者自负）

- **仅限个人学习研究**；禁止商业舆情监控、批量用户画像、二次分发原始数据。
- 遵守目标平台的服务条款与 `robots`；**内置合理限速，不提供任何绕过风控的选项**。
- 登录态（Cookie / SESSDATA）属敏感凭证，**不要硬编码进任何提交**。
- 本目录脚本按「现状」提供，不保证可用性；因使用产生的任何合规责任由使用者承担（见根目录 `LICENSE` 与 `../docs/compliance.md`）。
