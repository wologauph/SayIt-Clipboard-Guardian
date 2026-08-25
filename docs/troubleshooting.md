# 故障排查与常见问题 (Troubleshooting)

### Q1: 语音识别完成了，但剪贴板没有更新？
1. 双击运行 `📊 查看运行状态与最新转录.bat` 查看守护进程是否处于 `🟢 运行中` 状态。
2. 查看 `logs/guardian.log` 确认是否有数据库连接或剪贴板写入报错。
3. 检查是否有第三方剪贴板工具（如 Ditto 等）锁定了剪贴板操作。

### Q2: 电脑重启后没有自动运行？
1. 双击运行 `⚙️ 设置开机自启动.bat` 或以 PowerShell 运行 `setup.ps1`。
2. 检查 `shell:startup`（Windows 启动文件夹）中是否存在 `SayIt-Clipboard-Guardian-AutoStart.bat`。

### Q3: 占用系统资源多吗？
极度轻量。守护脚本在空闲时进入 Sleep 周期，占用内存约 10~15MB，CPU 占用率为 0.00%。
