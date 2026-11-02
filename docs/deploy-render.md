# 把交互式 demo 部署到 Render（GitHub Actions 自动部署）

> 目标：**交互式 demo 不再依赖任何单一托管平台**。仓库是唯一真源，
> push 到 `main` 后由 GitHub Actions 触发 Render 重新部署，并做健康检查。

## 为什么是 Render

| 平台 | 免费？ | Python 常驻服务 | 备注 |
|---|---|---|---|
| **Render** | ✅ 免费 Web Service（750 h/月） | ✅ | 15 分钟无访问休眠，冷启动 30–60s |
| Fly.io | ❌（已取消免费额度） | ✅ | 按量计费 |
| Railway | ❌（仅试用额度） | ✅ | 之后付费 |
| Koyeb | ✅ 免费一实例 | ✅ | 备选 |
| GitHub Pages | ✅ | ❌ | 只能静态，跑不了 `http.server` |

本项目**零第三方依赖**，Render 原生 Python 运行时直接就能跑，不需要 Docker。

## 一次性配置（约 3 分钟）

### 1. 在 Render 创建服务

1. 注册/登录 <https://render.com>。
2. 控制台 → **New → Blueprint**。
3. 选择本仓库 `TrueFurina/comment-distillery`，Render 会读根目录的 [`render.yaml`](../render.yaml) 自动创建：
   - 类型：Web Service（免费层）
   - 启动命令：`python -m app.webui --no-browser --demo`
   - 健康检查：`/api/hello`
4. 创建完成后，记下服务地址（形如 `https://comment-distillery.onrender.com`）。

### 2. 拿 Deploy Hook

服务页 → **Settings → Deploy Hook** → 复制完整 URL
（形如 `https://api.render.com/deploy/srv-xxxx?key=yyyy`）。

### 3. 在 GitHub 配两个 Secret

仓库 → **Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | 上一步的 Deploy Hook URL |
| `RENDER_APP_URL` | 服务公开地址，如 `https://comment-distillery.onrender.com` |

### 4. 触发

push 到 `main`（改到 `app/**`、`scripts/**`、`examples/**`、`SKILL.md`、`render.yaml` 时），
或手动 **Actions → Deploy demo to Render → Run workflow**。

工作流会：触发 Render 部署 → 轮询 `/api/hello` 直到 200（最多 5 分钟）。
未配置 Secret 时只打印告警并成功退出，不会把 CI 变红。

## 两个入口的分工

| 入口 | 用途 | 地址 |
|---|---|---|
| GitHub Pages（静态） | 落地页 + 预生成样例，永久免费、随时可看 | <https://truefurina.github.io/comment-distillery/> |
| Render（交互） | 真正点「一键」跑预处理/打包/机验 | 由上面的 `RENDER_APP_URL` 决定 |

## 注意

- **免费层会休眠**：15 分钟无访问后实例挂起，下一个访客要等 30–60s 冷启动。演示前可先访问一次「热身」。
- **`--demo` 不校验令牌**：这是公开演示模式；沙箱与路径白名单仍生效，但**不要**在它上面放任何私密数据。
- **AI 仍是 BYO-AI**：公开 demo 不接任何模型；想跑完整指南，请用本地工具或 Skill ZIP 自带 Key。
- 若想换成 Koyeb/Fly，只需替换部署步骤，`render.yaml` 与本工作流可保留作参考。
