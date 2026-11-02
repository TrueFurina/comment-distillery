#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本仓库同步到 Hugging Face Space（Docker SDK，免卡免费）。

由 `.github/workflows/deploy-hf-space.yml` 在 push 到 main 后调用。

环境变量：
    HF_TOKEN   有写权限的 Hugging Face token（Settings → Access Tokens → write）
    HF_SPACE   目标 Space，形如 ``<owner>/<space-name>``

设计要点：
- **Space 是部署产物，不是源码真源**：源码永远在 GitHub，本脚本只做单向同步。
- **README 单独生成**：HF Space 需要 YAML front matter（sdk/app_port）才能识别
  Docker；仓库自己的 README 没有这段，所以上传后用它覆盖 Space 的 README。
- 未配置环境变量时**成功退出**（打印提示），不让「还没开通」把 CI 变红。
"""
from __future__ import annotations

import os
import sys

# 不上传的东西：源码真源与构建无关的目录，以及会被 Space README 覆盖的 README。
IGNORE = [
    ".git/**",
    ".github/**",
    "tests/**",
    "out/**",
    "output/**",
    "**/__pycache__/**",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/**",
    "docs/**",
    "site/**",
    "deliverables/**",
    "assets/**",
    "golden/**",
    "cases/**",
    "README.md",
    "README.zh.md",
    "README.en.md",
    "render.yaml",
]

SPACE_README = """---
title: Comment Distillery
emoji: 🧪
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Comment Distillery · 评论蒸馏器

把一群人对同一议题的自发文本，蒸馏成**带引用溯源的行动指南**。

这是公开演示实例：**确定性模式（不接 AI）**，可体验「预处理 → 打包 → 引用机验 →
数字机验 → HTML 报告」全链路。想跑完整的 AI 指南生成，请用本地工具或 Skill ZIP
自带 Key（模型与额度全在用户侧）。

- 源码：<https://github.com/TrueFurina/comment-distillery>
- 静态站：<https://truefurina.github.io/comment-distillery/>
"""


def main() -> int:
    token = (os.environ.get("HF_TOKEN") or "").strip()
    space = (os.environ.get("HF_SPACE") or "").strip()
    if not token or not space:
        print("[skip] 未配置 HF_TOKEN / HF_SPACE，跳过同步（见 docs/deploy-hf-space.md）")
        return 0

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("[error] 缺少 huggingface_hub：pip install 'huggingface_hub>=0.24'", file=sys.stderr)
        return 2

    api = HfApi(token=token)

    # 1) 建 Space（已存在则复用，不会改 SDK）
    api.create_repo(repo_id=space, repo_type="space", space_sdk="docker", exist_ok=True)
    print(f"[ok] Space 就绪：{space}")

    # 2) 同步仓库（排除 .git/tests/docs 等）
    api.upload_folder(
        folder_path=".",
        repo_id=space,
        repo_type="space",
        ignore_patterns=IGNORE,
        commit_message="deploy: sync from GitHub",
    )
    print("[ok] 仓库已同步")

    # 3) 写 Space 元数据 README（front matter 决定 sdk/app_port）
    api.upload_file(
        path_or_fileobj=SPACE_README.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=space,
        repo_type="space",
        commit_message="deploy: space metadata",
    )
    print("[ok] Space README 已写入")

    slug = space.lower().replace("/", "-").replace("_", "-").replace(".", "-")
    print(f"[done] 地址（首次构建需几分钟）：https://{slug}.hf.space")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
