@echo off
chcp 65001 >nul
color 0A
title 启动 SayIt 剪贴板保底管家

echo ==================================================
echo   启动 SayIt 剪贴板保底管家 (静默守护版)
echo ==================================================

powershell -ExecutionPolicy Bypass -Command "
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sayit_clipboard_guardian.py*' }
if ($p) {
    Write-Host ('[!] 管家已在后台运行中 (PID: ' + ($p.ProcessId -join ', ') + ')，无需重复启动。') -ForegroundColor Yellow
} else {
    $pyScript = Join-Path $PSScriptRoot 'scripts\sayit_clipboard_guardian.py'
    Start-Process -FilePath 'python.exe' -ArgumentList ('\"' + $pyScript + '\"') -WorkingDirectory (Join-Path $PSScriptRoot 'scripts') -WindowStyle Hidden
    Start-Sleep -Milliseconds 800
    $np = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sayit_clipboard_guardian.py*' }
    if ($np) {
        Write-Host ('[✓ 启动成功] SayIt 剪贴板保底管家已在后台静默就绪 (PID: ' + ($np.ProcessId -join ', ') + ')！') -ForegroundColor Green
        Write-Host '现在无论在什么窗口说话，语音识别结果都会 100% 自动锁定在剪贴板中！随手按 Ctrl+V 即可粘贴。' -ForegroundColor Cyan
    } else {
        Write-Host '[!] 启动失败，请检查 logs\guardian.log' -ForegroundColor Red
    }
}
"

echo.
pause
