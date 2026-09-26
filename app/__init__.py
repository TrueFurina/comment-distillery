#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-distillery 桌面工具。

分层（GUI 只占一层，其余可被测试直接导入）：

    core.py     逻辑层：包装仓库已有的 scripts/*.py 与 contrib/*.py，无 GUI 依赖
    gui.py      界面层：tkinter（唯一接触 GUI 的模块）
    __main__.py 入口：python -m app

设计红线：**不重写任何方法论逻辑**。采集 / 预处理 / 引用机验 / 规则机验
全部调用仓库里已有的脚本 —— 它们是单一实现，CLI、GUI、CI 共用一套，
避免出现"exe 里的规则和仓库悄悄漂移"。
"""

__version__ = "1.0.0"
__all__ = ["core", "gui", "__version__"]
