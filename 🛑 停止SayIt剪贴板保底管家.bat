@echo off
chcp 65001 >nul
color 0C
title 停止 SayIt 剪贴板保底管家

echo ==================================================
echo   停止 SayIt 剪贴板保底管家
echo ==================================================

powershell -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sayit_clipboard_guardian.py*' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('[✓ 已停止] 结束管家进程 PID: ' + $_.ProcessId) -ForegroundColor Green } } else { Write-Host '[!] 后台未发现运行中的 SayIt 剪贴板保底管家。' -ForegroundColor Yellow }"

echo.
pause
