# 把交互式 demo 部署到 Hugging Face Spaces（免银行卡）

> 为什么不用 Render：Render 的免费 Web Service 现在**要绑银行卡**。
> Hugging Face Spaces 的免费 CPU Docker 空间**邮箱注册即可、不绑卡**，
> 且能跑任意 Python HTTP 服务——正好适合本项目（零第三方依赖 + 单端口）。

## 两个入口的分工

| 入口 | 用途 | 地址 |
|---|---|---|
| GitHub Pages（静态） | 落地页 + 预生成样例，永久免费 | <https://truefurina.github.io/comment-distillery/> |
| **HF Space（交互）** | 真点「一键」跑预处理/打包/机验 | `https://<owner>-<space>.hf.space` |

## 一次性配置（约 5 分钟）

### 1. 注册 Hugging Face

<https://huggingface.co> → Sign Up（**邮箱即可，不绑卡**）。

### 2. 创建写权限 token

头像 → **Settings → Access Tokens → New token** → 类型选 **Write** → 复制。

### 3. 在 GitHub 配两个 Secret

仓库 → **Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 |
|---|---|
| `HF_TOKEN` | 上一步的 token |
| `HF_SPACE` | 目标 Space，如 `TrueFurina/comment-distillery` |

> Space 不需要你手动创建：首次同步时 `scripts/sync_hf_space.py` 会自动建
> （Docker SDK），已存在则复用。

### 4. 触发

push 到 `main`（改到 `app/**`、`scripts/**`、`examples/**`、`Dockerfile` 等时），
或手动 **Actions → Deploy demo to Hugging Face Spaces → Run workflow**。

工作流会：同步仓库到 Space → 写 Space 元数据 README → 轮询 `/api/hello` 直到 200
（最多 10 分钟；超时只告警，因为首次 Docker 构建可能更久）。

## 地址怎么算

Space 的公开地址是 `https://<owner>-<space>.hf.space`，其中 `/` 换成 `-`、全小写。
例如 `TrueFurina/comment-distillery` → <https://truefurina-comment-distillery.hf.space>。

## 关键文件

| 文件 | 作用 |
|---|---|
| `Dockerfile` | `python:3.12-slim` + `CMD python -m app.webui --no-browser --demo --port 7860` |
| `.dockerignore` | 排除 `.git`/`tests`/`docs`/`out` 等非运行必需内容 |
| `scripts/sync_hf_space.py` | 建 Space + 上传仓库 + 写 front matter README |
| `.github/workflows/deploy-hf-space.yml` | push 触发 + 健康检查 |

## 注意

- **免费 CPU 会休眠**：一段时间无访问后实例挂起，下一个访客要等冷启动。演示前先访问一次「热身」。
- **`--demo` 不校验令牌**：公开演示模式，别放私密数据（沙箱与路径白名单仍生效）。
- **AI 仍是 BYO-AI**：公开 demo 不接任何模型；完整指南生成请用本地工具或 Skill ZIP。
- **构建失败**：到 Space 页面 → **Logs / Build** 看 Docker 构建日志；最常见是端口不是 7860
  或 `app_port` 元数据没写对。
- **想换回 Render**：`render.yaml` 与 `.github/workflows/deploy-render.yml` 仍保留，
  但那条路需要绑卡。
