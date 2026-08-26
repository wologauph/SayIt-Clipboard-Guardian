@echo off
chcp 65001 >nul
color 0B
title SayIt 剪贴板保底管家 - 一键设置开机自启

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_PATH=%STARTUP_DIR%\run_sayit_guardian.vbs"

echo ==================================================
echo   SayIt 剪贴板保底管家 - 一键挂载开机自启
echo ==================================================
echo.

echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_PATH%"
echo WshShell.Run "pythonw.exe ""C:\Users\1\Desktop\我的软件\SayIt-Clipboard-Guardian\scripts\sayit_clipboard_guardian.py""", 0, False >> "%VBS_PATH%"

echo [成功] 已成功将静默守护管家挂载至 Windows 开机启动项!
echo 路径: %VBS_PATH%
echo 以后每次开机，管家都会全自动在后台运行，无需手动启动。
echo.

start "" powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Process pythonw.exe -ArgumentList '"C:\Users\1\Desktop\我的软件\SayIt-Clipboard-Guardian\scripts\sayit_clipboard_guardian.py"' -WorkingDirectory 'C:\Users\1\Desktop\我的软件\SayIt-Clipboard-Guardian\scripts'"

echo [成功] 当前后台管家服务已为您即刻启动!
echo.
pause
