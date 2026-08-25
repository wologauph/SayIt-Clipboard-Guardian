@echo off
chcp 65001 >nul
color 0F
title SayIt 剪贴板保底管家 - 运行大盘

echo ==================================================
echo   SayIt 剪贴板保底管家 - 运行状态与最近转录记录
echo ==================================================

powershell -Command "
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sayit_clipboard_guardian.py*' }
if ($p) {
    Write-Host '[状态: 🟢 运行中]' -ForegroundColor Green
    Write-Host ('进程 PID: ' + ($p.ProcessId -join ', ')) -ForegroundColor Cyan
} else {
    Write-Host '[状态: 🔴 未运行]' -ForegroundColor Red
}
Write-Host ''
Write-Host '--- 最近 5 条捕获的语音识别文本 ---' -ForegroundColor Yellow
python -c \"
import sqlite3, json, os
LOCAL_APP_DATA = os.environ.get('LOCALAPPDATA', r'C:\Users\1\AppData\Local')
db_path = os.path.join(LOCAL_APP_DATA, 'com.sayit.app', 'sayit.db')
try:
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute('SELECT rowid, id, timestamp, raw_json FROM history_records ORDER BY rowid DESC LIMIT 5;')
    for i, r in enumerate(cur.fetchall(), 1):
        data = json.loads(r[3])
        txt = data.get('llmText') or data.get('asrText') or ''
        app = data.get('processName', '未知应用')
        print(f'[{i}] ({app}) {txt}')
    conn.close()
except Exception as e:
    print('读取失败:', e)
\"
"

echo.
pause
