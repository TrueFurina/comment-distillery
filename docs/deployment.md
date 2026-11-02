# 部署架构

当前采用**双入口**，都不需要银行卡、不需要额外账号：

| 入口 | 用途 | 地址 | 托管 |
|---|---|---|---|
| **交互 demo** | 真点「一键」跑预处理 / 打包 / 引用机验 / 数字机验 | <https://comment-distillery.apps.workbuddy.host/?sharecode=NXMUMDBG2E> | WorkBuddy 托管（`--demo` 公开模式） |
| **静态站** | 落地页 + 预生成样例，永久免费 | <https://truefurina.github.io/comment-distillery/> | GitHub Pages（`site/` + `pages.yml`） |

## 为什么不用 Render / HF Spaces

- **Render**：免费 Web Service 现在要求绑定银行卡。
- **HF Spaces**：免卡，但要额外注册 HF 账号 + 配写权限 token；对当前需求收益不大。

相关文件（`Dockerfile`、`.dockerignore`、`render.yaml`、`scripts/sync_hf_space.py`、`docs/deploy-*.md`）
保留为**备选**，但对应的自动部署工作流已移除，不会在 push 时触发。

## 交互 demo 的运行方式

```bash
python -m app.webui --no-browser --demo
```

- `--demo` = `--public` 但不校验令牌（托管平台代理会注入 `Authorization` 头，
  空令牌的「开放访问」会被令牌闸门误拦成 401）；
- 绑定 `0.0.0.0`，端口读 `PORT` 环境变量；
- 文件收进沙箱，路径白名单仍生效；
- **不接 AI**（BYO-AI），只跑确定性链路：预处理 → 打包 → 引用机验 → 数字机验 → HTML 报告。

## 静态站

`site/` 目录由 `.github/workflows/pages.yml` 在 push 到 `main` 时自动部署到 GitHub Pages。

## 想换宿主

- **有银行卡**：用 `render.yaml`（步骤见 [`deploy-render.md`](deploy-render.md)）。
- **不想绑卡**：用 Hugging Face Spaces（步骤见 [`deploy-hf-space.md`](deploy-hf-space.md)）。
