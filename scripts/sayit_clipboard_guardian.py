"""
SayIt 剪贴板常驻保底管家 (SayIt Clipboard Guardian) v1.0.0
功能：实时监听 SayIt 语音转文字产物，一旦识别完成，自动将最新文本置入 Windows 剪贴板，并锁定防止被旧剪贴板还原动作覆盖。
"""

import os
import sys
import time
import json
import sqlite3
import ctypes
from ctypes import wintypes
from datetime import datetime

# Windows 剪贴板底层 API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL

GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13

# 动态定位 SayIt 数据库路径
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
DB_PATH = os.path.join(LOCAL_APP_DATA, "com.sayit.app", "sayit.db")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "guardian.log")
PID_FILE = os.path.join(LOG_DIR, "guardian.pid")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    if sys.stdout is not None:
        try:
            print(line, flush=True)
        except:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def set_clipboard_text(text: str) -> bool:
    """带自旋重试的 Windows 原生 Unicode 剪贴板写入"""
    if not text:
        return False
    for _ in range(12):
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                raw_bytes = text.encode('utf-16le') + b'\x00\x00'
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw_bytes))
                if h_mem:
                    p_mem = kernel32.GlobalLock(h_mem)
                    if p_mem:
                        ctypes.memmove(p_mem, raw_bytes, len(raw_bytes))
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                        return True
                    kernel32.GlobalFree(h_mem)
            finally:
                user32.CloseClipboard()
        time.sleep(0.04)
    return False

def get_latest_record():
    """以只读无锁 URI 方式安全读取 SQLite WAL 数据库最新转录"""
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=0.5)
        cur = conn.cursor()
        cur.execute("SELECT rowid, id, timestamp, raw_json FROM history_records ORDER BY rowid DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        if row:
            rowid, id_, ts, raw = row
            try:
                data = json.loads(raw)
                text = data.get("llmText") or data.get("asrText") or ""
                return {
                    "rowid": rowid,
                    "id": id_,
                    "timestamp": ts,
                    "text": text.strip(),
                    "app": data.get("processName", ""),
                    "raw": data
                }
            except:
                pass
    except Exception as e:
        pass
    return None

def write_pid():
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except:
        pass

def main():
    write_pid()
    log(f"=== SayIt 剪贴板常驻保底管家已启动 (PID: {os.getpid()}) ===")
    
    init_rec = get_latest_record()
    last_rowid = init_rec["rowid"] if init_rec else 0
    last_ts = init_rec["timestamp"] if init_rec else 0
    
    log(f"基线定位完成: 当前最新记录 rowid={last_rowid}, timestamp={last_ts}")
    log("正在持续静默监听 SayIt 语音转文字事件...")

    while True:
        try:
            rec = get_latest_record()
            if rec:
                is_new = (rec["rowid"] > last_rowid) or (rec["timestamp"] > last_ts)
                if is_new and rec["text"]:
                    last_rowid = max(last_rowid, rec["rowid"])
                    last_ts = max(last_ts, rec["timestamp"])
                    
                    target_text = rec["text"]
                    log(f"⚡ [捕获到新语音] 长度={len(target_text)} 字符 | 应用={rec['app']} | 内容: {target_text[:30]}...")
                    
                    # 第一次写入剪贴板 (毫秒级即时响应)
                    ok1 = set_clipboard_text(target_text)
                    
                    # 等待 480ms (精准穿透 SayIt 自身的 400ms 剪贴板还原动作)
                    time.sleep(0.48)
                    
                    # 第二次强制覆盖加固写入，确保 100% 留存剪贴板！
                    ok2 = set_clipboard_text(target_text)
                    
                    if ok1 or ok2:
                        log("  [✓ 成功] 最新语音转录文本已牢牢锁定至 Windows 剪贴板！随时按 Ctrl+V 即可粘贴。")
                    else:
                        log("  [!] 写入剪贴板失败，请检查是否有其他软件长期独占剪贴板。")
                        
            time.sleep(0.12)
        except Exception as e:
            log(f"[异常恢复] {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
