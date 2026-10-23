@echo off
chcp 65001 >nul
REM ============================================================
REM  comment-distillery · 本地平台一键启动
REM  双击即：启动本地 Web 界面 + 自动打开浏览器
REM  只监听 127.0.0.1，不联网、不上传任何数据
REM  关闭：在弹出的黑窗口按 Ctrl+C，或直接关掉它
REM  （脚本目录即仓库根，换机器/换盘符也能用）
REM ============================================================
setlocal
title comment-distillery 平台
cd /d "%~dp0"

REM 1) 优先用 WorkBuddy 管理的 Python（与项目 CI 同版本，最稳）
if exist "%LOCALAPPDATA%\WorkBuddy\binaries\python\versions\3.13.12\python.exe" (
    "%LOCALAPPDATA%\WorkBuddy\binaries\python\versions\3.13.12\python.exe" -m app --web
    goto :done
)

REM 2) 系统 Python Launcher（py.exe，通常随官方 Python 安装）
where py >nul 2>nul && (
    py -3 -m app --web
    goto :done
)

REM 3) 兜底：PATH 里能找到的 python
python -m app --web

:done
if errorlevel 1 (
    echo.
    echo 启动失败：本机没找到可用的 Python。请先安装 Python 3.10+ 或 WorkBuddy 运行时。
    pause
)
endlocal
