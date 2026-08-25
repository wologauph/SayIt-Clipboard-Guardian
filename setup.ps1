# SayIt 剪贴板常驻保底管家 - 一键部署与开机自启脚本

$ErrorActionPreference = "Continue"

$projectRoot = $PSScriptRoot
$scriptPath = Join-Path $projectRoot "scripts\sayit_clipboard_guardian.py"
$startupFolder = [System.Environment]::GetFolderPath('Startup')
$startupBat = Join-Path $startupFolder "SayIt-Clipboard-Guardian-AutoStart.bat"
$oldStartupLnk = Join-Path $startupFolder "SayIt剪贴板保底管家.lnk"

# 1. 解锁所有脚本文件
Get-ChildItem -Path $projectRoot -Recurse | ForEach-Object {
    Unblock-File $_.FullName -ErrorAction SilentlyContinue
}

# 2. 清理旧版 .lnk 快捷方式（避免 Windows 静默拦截坑）
if (Test-Path $oldStartupLnk) {
    Remove-Item $oldStartupLnk -Force -ErrorAction SilentlyContinue
}

# 3. 创建开机自启 .bat 文件直接放入启动文件夹
$batContent = @"
@echo off
start "" /B powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Process python.exe -ArgumentList '\"$scriptPath\"' -WorkingDirectory '$projectRoot\scripts' -WindowStyle Hidden"
"@
Set-Content -Path $startupBat -Value $batContent -Encoding utf8

# 4. 更新/创建桌面【我的软件】快捷方式
$mySoftFolder = "C:\Users\1\Desktop\我的软件"
if (Test-Path $mySoftFolder) {
    $mySoftLnk = Join-Path $mySoftFolder "SayIt剪贴板保底管家.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($mySoftLnk)
    $sc.TargetPath = Join-Path $projectRoot "🚀 启动SayIt剪贴板保底管家.bat"
    $sc.WorkingDirectory = $projectRoot
    $sc.Description = "SayIt 剪贴板常驻保底管家"
    $sc.Save()
}

# 5. 检查并启动当前实例
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*sayit_clipboard_guardian.py*" }
if (-not $p) {
    Start-Process -FilePath "python.exe" -ArgumentList ('"' + $scriptPath + '"') -WorkingDirectory (Join-Path $projectRoot "scripts") -WindowStyle Hidden
}

Write-Host "[✓ 部署完成] 开机自启动与桌面入口已成功配置！" -ForegroundColor Green
Write-Host "  启动项文件: $startupBat" -ForegroundColor Cyan
Write-Host "  主脚本位置: $scriptPath" -ForegroundColor Cyan
