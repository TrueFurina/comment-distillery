@echo off
chcp 65001 >nul
setlocal
title 恢复蒸馏报告到 output

set "SRC=E:\Program\_cd_scratch_archive_20261102\output"
set "DST=E:\Program\comment-distillery\output"
set "IDX=%DST%\报告索引.html"

echo ============================================
echo  恢复被误归档的蒸馏报告
echo  来源: %SRC%
echo  目标: %DST%
echo ============================================
echo.

if not exist "%SRC%" (
  echo [X] 找不到归档目录:
  echo     %SRC%
  echo.
  echo     如果你把归档挪到别处了，请用记事本改本文件里的 SRC 一行。
  pause
  exit /b 1
)

if not exist "%DST%" mkdir "%DST%"

robocopy "%SRC%" "%DST%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo.
  echo [X] 复制失败，robocopy 返回码 %RC%
  pause
  exit /b 1
)

echo.
echo [OK] 已恢复，output 现有内容：
dir /b "%DST%"
echo.
if exist "%IDX%" (
  echo 正在打开报告索引...
  start "" "%IDX%"
) else (
  echo [!] 未找到 报告索引.html，请手动打开 output 目录。
)
echo.
echo 完成。可以关闭本窗口了。
timeout /t 5 >nul
endlocal
