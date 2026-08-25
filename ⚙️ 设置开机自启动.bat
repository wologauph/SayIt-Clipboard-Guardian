@echo off
chcp 65001 >nul
color 0B
title 设置 SayIt 剪贴板保底管家 开机自启动

echo ==================================================
echo   设置 SayIt 剪贴板保底管家 开机自启动
echo ==================================================

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

echo.
pause
