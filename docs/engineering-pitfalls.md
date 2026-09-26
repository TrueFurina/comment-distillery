# 工程坑台账（Engineering Pitfalls）

> 建立：2026-09-26（拆分读者边界）
> **本文记录的是「维护 / 构建这个仓库」才会踩到的坑**，不是「用这个 skill 做蒸馏」会踩到的坑。
> 蒸馏侧的坑在 [`SKILL.md`](../SKILL.md) 的「环境坑」章节。
> 计数由 `scripts/check_doc_consistency.py` 强制与 `docs/rule-provenance.md` §3.2 对齐。

## 为什么要有这份文件（拆分动机）

`SKILL.md` 是 **exe 的随包资源**（见 `scripts/build_exe.py` 的 `ADD_DATA`）——**改它就必须重发一版产物**。
而 "怎么让 CI 在 Windows 上不因编码炸掉""PyInstaller 的相对路径怎么算" 这类坑，
对**只做蒸馏、不维护仓库**的人**零价值**；把它们留在 `SKILL.md` 里，直接后果是：

> 为改一条构建笔记，被迫发一版新 exe。实测发生过：v1.4.1 就是因为往 `SKILL.md` 塞了 3 条
> *仓库维护类*环境事实而被迫发的版——那次发版对 exe 用户没有任何价值。

**判据（新增条目时先问这一句）**：

> 这个坑会让「只用不维护」的人改变做法吗？ —— **会 → 进 `SKILL.md`**；**不会 → 进本文**。

**本文刻意不进打包产物**：`ADD_DATA` 不含本文件。收益是改本文、改 CI、改检查脚本都不必重发 exe
（实测：v1.4.1 → v1.5.0 之间的工作流与检查脚本修复，产物字节一个没动，因此无需发补丁版）。

---

## 坑清单（13 条）

- **隔离 venv 里 `pip install` 卡在 `pyyaml`/setuptools 编译** `[环境]`（`cython_sources` / `_distutils_hack` 缺失）：是 setuptools 在中断升级里**损坏**了。修复 `pip install --force-reinstall --no-deps setuptools wheel`，并优先用镜像的二进制 wheel（`--only-binary :all:`）。**这也是本仓库坚持零依赖纯标准库的原因之一。**
- **跨盘移动文件不要用 Python `shutil.move`** `[环境]`：Windows 跨盘时它退化为 copy+rmtree，而 rmtree 可能被安全删除钩子拦截 → 报 `[WinError 17] 系统无法将文件移到不同的磁盘驱动器`，**copy 已成功但源侧留下副本**（静默产生重复）。**跨盘移动请用原生 PowerShell `Move-Item`**。
- **GitHub 推送两条通道，哪条通走哪条** `[环境]`：`github.com:443` 直连可能被阻断（`curl` 到 `api.github.com` 通但 `git` 不通，表现为 fetch `Connection reset`）；改用 **SSH**（`ssh.github.com:443` 与 `github.com:22` 实测均可用）。若走 HTTPS，`gho_` 类 token **必须 URL 内嵌**（`https://x-access-token:${TOKEN}@github.com/...`），用 `Authorization: Bearer` header 会报 invalid。
- **⚠️ `.gitignore` 里写 `cases/` 会吞掉任意层级的同名目录** `[环境]`：gitignore 中不带前导斜杠的目录名匹配**任意层级**，实测导致 `golden/cases/` 被一并忽略——`git add golden` 静默跳过场景文件，**既不报错也不进暂存区**，只会在核对清单时才发现少了一整个目录。**必须写成 `/cases/` 锚定仓库根**；同理检查 `data/` / `out/` / `tmp/` 等条目。
- **Windows 控制台默认 cp1252 → `print` 中文直接抛 `UnicodeEncodeError`** `[环境]`：报错看着像逻辑错，实际是编码错（**本地中文区域是 cp936，一切正常，所以极易漏到 CI 才炸**）。实测 GitHub 的 windows runner 因此让整个构建步骤失败。两头修：① 脚本入口 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`；② CI 设 `PYTHONUTF8=1`，并加一道「在 `PYTHONIOENCODING=cp1252` 下跑一遍」的守卫步骤。
- **PowerShell 5.1 的 `Select-String` 默认按 ANSI 读文件** `[环境]`：拿它去匹配**无 BOM 的 UTF-8** 中文（如从 `site/index.html` 里抓体积标注）会乱码、静默匹配不到，下一步 `$Matches[0]` 直接索引越界失败。必须显式 `Get-Content -Raw -Encoding UTF8` + `[regex]::Match`。
- **PyInstaller 的 `--add-data` 一旦配合 `--specpath`，相对路径会相对 spec 目录解析** `[环境]`：实测报 `Unable to find build/SKILL.md`。**一律传绝对路径**。
- **打包产物里的资源是"快照"，自检只看"在不在"** `[环境]`：改了 `SKILL.md`/脚本忘重建，exe 外表无异常、启动自检照样 PASS，但用户导出的包里是过期方法论。**必须做内容级核验**（读产物归档、与仓库逐项比对 SHA-256）；且**别用"扫 exe 明文找关键字"**——归档是压缩的，必然搜不到，会得到假结论。
- **⚠️ 文档口径漂移靠人眼 grep 必定会漏** `[环境]`：一次"已全面核对"的普查仍漏出 3 处——① PR 文案里的 Python 版本号比全库其余处**低两个次版本**（且那段是要公开发布的）；② 某文档把一条**已证伪**的判断当作现状（Release / Pages 其实本地 token 就能做完）；③ 另一文档把**已经发布上线**的事列为待办。**结论：凡是"文档里的数字/判断必须等于某处事实"的约束，都要写成机验脚本**（`scripts/check_doc_consistency.py`，CI 强制 + 变异自验），不要指望自查。
- **同一件事在多个工作流里各内联一份实现，本身就是漂移源** `[环境]`：`ci.yml` 与 `pages.yml` 曾各写一份"官网自检"，加上脚本里的一份共三处——只要判据变一次就会有一处忘记改。**同一个判据只留一处实现，其余全部调它。**
- **在 CI 里比对"站点标注的产物哈希"会制造假红线** `[环境]`：站点写的是**已发布的那一份**产物的 SHA-256，而 CI 重新打包得到的字节必然不同（PyInstaller 非可复现构建）。若在 CI 硬比，等于逼出"永远不许重建产物"。正确做法：CI 跳过该项（`--no-artifact`），**本地出包后**跑完整版核对，并在**发布后把资产下载回来复算哈希**。
- **`actions/checkout` 在 tag 推送时默认只带那一个 tag** `[环境]`：实测 v1.4.1 首发时 CI 与打包工作流**双双假红**，报"引用了不存在的 tag v1.4.0"——而它明明存在，只是没被拉到本地。修法：三个工作流全部加 `fetch-depth: 0`。**元教训：判据尽量只读仓库内的事实**；依赖本地 tag / 网络 / 外部状态 → 环境一变就假红或假绿，而**假红比不检查更坏，它会训练人"看到红就绕过去"**。
- **Actions 的 job 日志端点 302 后会转发 `Authorization` → `401`** `[环境]`：`GET /repos/{o}/{r}/actions/jobs/{id}/logs` 会跳转到 blob 存储，urllib 会把 `Authorization` 一起带过去，于是被拒（`InvalidAuthenticationInfo`）。修法：自定义 redirect handler，跳转后**剥掉** `Authorization` 头（已封装为 `~/.workbuddy/bin/gh_logs.py`，见本文末）。

---

## 维护本文的规矩

1. **新增条目必须同步 `docs/rule-provenance.md` §3.2 一行**（机验会卡：两边行数不等即 CI 红）。
2. 新增前先自问那句判据：**会让"只用不维护"的人改变做法吗？** 会的话它属于 `SKILL.md`，不属于本文。
3. 条目必须带 `[环境]` 标记（与 `SKILL.md` 同一套标记口径）。
4. **本文不进打包产物**——所以改本文**不需要**重发 exe。若你不确定某次改动是否需要重发，
   跑 `python scripts/build_exe.py --verify`：它逐项比对产物内资源与仓库是否一致。

---

## 附：相关的本地工具

本仓库维护期用到的、不属于仓库内容的辅助工具（放在 `~/.workbuddy/bin/`，不进仓库）：

| 工具 | 用途 | 记下的理由 |
|---|---|---|
| `gh_run.py` | 读 GitHub token（WorkBuddy shell 不继承 HKCU 环境变量，改走 `winreg`） | 无 `gh` CLI 时的替代路径 |
| `gh_logs.py` | 拉 Actions job 日志 | 见上表最后一条：302 后必须剥 `Authorization` |

> 两个工具都用 `urllib.request.build_opener(urllib.request.ProxyHandler({}))` **强制直连**——
> 系统代理（Clash 等）失效后仍会被 `getproxies()` 沿用，表现为"网络假死"。
