@echo off
chcp 65001 >nul
color 0E
title 取消 SayIt 剪贴板保底管家 开机自启动

echo ==================================================
echo   取消 SayIt 剪贴板保底管家 开机自启动
echo ==================================================

powershell -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"

echo.
pause
