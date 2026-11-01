# 收尾说明（2026-11-01 更新）

## 状态：提交已完成，只差推送

```
HEAD = 1d2349c  feat(web+gui): 一键完成 + BYO-AI 蒸馏 + 第 11 项机验
         36 files changed, 14046 insertions(+), 115 deletions(-)
工作区 = 干净（git status 无输出）
origin/main = 1b82a95 (release v1.7.0)
```

⚠️ 远端落后 **2 个**提交：`06e392c`（修 launch-webui.bat）和 `1d2349c`（本次）。
两个都从未推送过，不是只有本次。

## 你只需要推一次

```bat
cd E:\Program\comment-distillery
git push origin main
```

已核验：`origin/main` 是 `main` 的祖先（`merge-base --is-ancestor` 返回 0），
没有分叉，是干净的快进推送，不会被拒绝。

推送后 CI 会跑，我在本地已把 CI 全部步骤跑通（见下）。

## CI 各步本地实测结果（在当前已提交的代码树上）

| CI 步骤 | 结果 |
|---|---|
| 语法检查 compileall | 通过（rc=0）|
| 守卫「零依赖」 | 通过：scripts/ tests/ app/ contrib/ 无第三方依赖 |
| 守卫「编码」cp1252 | 通过：check_rule_tags 22 条 / 裸铁律 0 |
| 机验 11 项 | 全 OK（1 项因无 tag 跳过）|
| 机验 --self-test | 变异全被拦截 |
| 全量测试 | `Ran 190 tests ... OK (skipped=1)` |
| golden 基线 | 100.0；31 个变异全部被正确扣分 |

其中「界面页签 == 文档」= GUI 6 个 / Web 7 个，一键入口已写入文档。

## 我在你仓库里实际做过的事

### 清理（已生效）
- 删 `dist/llm.json`（含明文 DeepSeek api_key，原本躺在待分发目录里）
- 删根目录 `_dbg3.py` / `_probe_llm.py` / `e2e-01-auto.png`
- 备份在 `removed_backup/`（若你还想要）

### 提交（已生效）
- 36 个文件入库，作者 `TrueFurina <206423360+TrueFurina@users.noreply.github.com>`
- `git fsck` 无报错，历史完整

### 修复过一次我自己造成的破坏（必须告知）
- 我为规避提交失败执行了 `git config --unset gc.auto / maintenance.auto`
- 你的目录挂载在重写 `.git/config` 时丢内容，config 一度变 0 字节甚至消失，remote/分支配置丢失
- 已用 printf 重建标准 config 并核验：`remote.origin.url` 正常、`branch=main`、`HEAD` 正常
- 换行策略未受影响：`.gitattributes` 里 `* text=auto eol=lf` 由版本化文件决定，
  实测 `git status` 干净、`check-attr` 显示 `eol: lf`，没有 CRLF 回归

## 仍未做的事 + 原因

### 1) exe 未重打（这是当前**唯一**真实的产品缺陷）
`dist/comment-distillery.exe` 时间戳 `10-29 22:35`，
而 `app/webui_page.py` 是 `22:43` —— exe 比源码旧 8 分钟，最后一次前端修复没进 exe。

本沙盒是 Linux 且无 PyInstaller，你要的是 Windows `.exe`，无法在此构建。

### 2) 版本号未切（有意不做，不是遗漏）
- `CHANGELOG` 停在 `[Unreleased]`，站点仍是 `v1.7.0` + SHA `8de11dc3…`（11.5 MB）
- 我核实过：站点数字与 `dist/` 里的 exe **完全一致**，所以站点并不陈旧，
  它标的就是已发布的 v1.7.0 产物。我上一轮说"站点数字陈旧"是判断错误，已纠正。
- 现在若把 CHANGELOG 改成 v1.8.0，但 exe 还是旧的、站点还写 v1.7.0，
  等于对外宣称了一个不存在的版本。仓库自身的判据也写了正确顺序：
  **commit（含文档）→ git tag → 复核 → push**，且"发布件不可变，内容变了就发新版"。
- 所以正确做法是：等你打完新 exe，拿到新体积与 SHA，再一次性改 CHANGELOG 版本号 +
  站点版本 + 站点数字 + 打 tag。不要分两次改，否则中间态一定是数字漂移。

## 推荐顺序
1. `git push origin main`（推 2 个提交，CI 会验证）
2. 本机重打 exe：`python scripts\build_exe.py`，再 `--verify`
3. 双冒烟：自检 + 端到端
4. 拿到新 exe 的体积/SHA → 一次性切 CHANGELOG 版本号 + 站点数字 → `git tag vX.Y.Z` → 跑机验 → push
