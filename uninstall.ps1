# SayIt 剪贴板常驻保底管家 - 一键卸载与开机自启移除脚本

$ErrorActionPreference = "Continue"

# 1. 停止运行中的进程
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*sayit_clipboard_guardian.py*" }
if ($p) {
    $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "[✓ 已停止] 守护进程已安全终止。" -ForegroundColor Green
}

# 2. 移除开机启动项
$startupFolder = [System.Environment]::GetFolderPath('Startup')
$startupBat = Join-Path $startupFolder "SayIt-Clipboard-Guardian-AutoStart.bat"
$startupLnk = Join-Path $startupFolder "SayIt剪贴板保底管家.lnk"

if (Test-Path $startupBat) {
    Remove-Item $startupBat -Force -ErrorAction SilentlyContinue
    Write-Host "[✓ 已移除] 开机启动 .bat 文件已清除。" -ForegroundColor Green
}
if (Test-Path $startupLnk) {
    Remove-Item $startupLnk -Force -ErrorAction SilentlyContinue
    Write-Host "[✓ 已移除] 开机启动快捷方式已清除。" -ForegroundColor Green
}

Write-Host "[✓ 卸载完成] 开机自启动已完全关闭。" -ForegroundColor Green
