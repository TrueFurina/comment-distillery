@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 恢复被归档的 output / out（交付物 + release 启动器）

set "ARC=E:\Program\_cd_scratch_archive_20261102"
set "DST=E:\Program\comment-distillery"

echo ============================================================
echo  恢复被误归档的目录
echo  归档根: %ARC%
echo  目标根: %DST%
echo ============================================================
echo.
echo  将要恢复：
echo    output\  —— 5 份蒸馏报告 + 报告索引.html（交付物，不可再生）
echo    out\     —— release 启动器 make_lnk*.py（从未入库，丢了找不回）
echo.

if not exist "%ARC%" (
  echo [X] 找不到归档根目录：
  echo     %ARC%
  echo.
  echo     若你已把归档挪走，请用记事本改本文件开头的 ARC 一行。
  pause
  exit /b 1
)

set FAIL=0

call :restore_dir "output"
call :restore_dir "out"

echo.
echo ============================================================
echo  恢复完成。当前 output\ 内容：
dir /b "%DST%\output" 2>nul
echo.
if exist "%DST%\output\报告索引.html" (
  echo 正在打开报告索引...
  start "" "%DST%\output\报告索引.html"
) else (
  echo [!] 未找到 报告索引.html —— 归档里可能就没有，请核对。
)
echo.
echo  提示：本脚本只做「补回」，不会覆盖已有同名文件之外的任何东西
echo        ^(robocopy /E 会同步同名文件，因此可重复执行^)。
echo.
timeout /t 6 >nul
endlocal
exit /b %FAIL%

:restore_dir
set "NAME=%~1"
if not exist "%ARC%\%NAME%" (
  echo [跳过] 归档里没有 %NAME%\
  exit /b 0
)
echo ------------------------------------------------------------
echo  恢复 %NAME%\ ...
robocopy "%ARC%\%NAME%" "%DST%\%NAME%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS
set RC=!errorlevel!
if !RC! GEQ 8 (
  echo [X] %NAME%\ 复制失败，robocopy 返回码 !RC!
  set FAIL=1
) else (
  echo [OK] %NAME%\ 已恢复
)
exit /b 0
