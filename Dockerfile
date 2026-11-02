# Hugging Face Spaces（Docker SDK）—— 免费、无需银行卡的 Python 常驻服务。
#
# 为什么用它：Render 的免费 Web Service 现在要绑卡；HF Spaces 的免费 CPU
# Docker 空间邮箱注册即可，不绑卡，且能跑任意 Python HTTP 服务。
#
# 关键约束：
#   - HF Spaces 的 Docker Space 默认把 7860 端口暴露给公网（app_port: 7860）；
#   - --demo = --public 但不校验令牌（平台代理会注入 Authorization 头，空令牌的
#     「开放访问」会被令牌闸门误拦成 401）；--demo 负责绑定 0.0.0.0；
#   - 本项目零第三方依赖，镜像里不需要 pip install。
FROM python:3.12-slim

WORKDIR /app

# 运行所需：app/（WebUI 与核心）、scripts/（预处理与机验）、examples/（示例语料）、
# contrib/（可选采集桥接，selfcheck 会检查它）、SKILL.md（方法论，selfcheck 会检查）。
# .dockerignore 已排除 .git / tests / docs / out 等非运行必需内容。
COPY . /app

ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["python", "-m", "app.webui", "--no-browser", "--demo", "--port", "7860"]
