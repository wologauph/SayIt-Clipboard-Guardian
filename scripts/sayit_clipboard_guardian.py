"""
SayIt 剪贴板常驻保底管家 (SayIt Clipboard Guardian) v2.0.0
功能：
1. 实时监听 SayIt 语音转文字产物，一旦识别完成，自动将最新文本置入 Windows 剪贴板，并锁定防止被旧剪贴板还原动作覆盖。
2. 智能失败探测 & 自动重试补漏 (Auto Recovery)：
   - 当遇到网络卡顿、心跳超时导致 SayIt 界面显示"无有效声音"/未转录成功时；
   - 只要录音有效时长 > 3.0秒（自动过滤误触极短音频），管家毫秒级自动直连云端极速转录；
   - 转录完成后第一时间自动送入 Windows 剪贴板，并自动回写修复本地数据库历史记录！
"""

import os
import sys
import time
import json
import sqlite3
import ctypes
import threading
import asyncio
import wave
import websockets
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
AUDIO_DIR = os.path.join(LOCAL_APP_DATA, "com.sayit.app", "audio")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) if "scripts" in SCRIPT_DIR else SCRIPT_DIR
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

def double_lock_clipboard(text: str, label="正常转录"):
    """双重锁定剪贴板写入，防止被前端延迟清理覆盖"""
    ok1 = set_clipboard_text(text)
    time.sleep(0.48)
    ok2 = set_clipboard_text(text)
    if ok1 or ok2:
        log(f"  [✓ 成功] ({label}) 最新文本已牢牢锁定至 Windows 剪贴板！随时按 Ctrl+V 即可粘贴。")
    else:
        log(f"  [!] ({label}) 写入剪贴板失败，请检查是否有其他软件占用剪贴板。")

async def async_retranscribe(audio_path, timeout=60):
    """通过 SayIt 原生 WebSocket 协议直接转录本地 WAV"""
    if not os.path.exists(audio_path):
        return None, "音频文件不存在"
    
    uri = "wss://sayitapp.site/ws/transcribe"
    try:
        async with websockets.connect(uri, ping_interval=10, ping_timeout=10) as ws:
            await asyncio.wait_for(ws.recv(), timeout=10.0) # ready
            
            start_cmd = {
                "cmd": "start",
                "device_id": "sayit-91745ee8-1ef1-4cf9-bca1-55dd10ce0dc6",
                "preset": "intent",
                "app_context": {
                    "processName": "Antigravity.exe",
                    "windowTitle": "Auto-Recovery"
                },
                "hotwords": [
                    "ChatGPT", "GPT", "OpenAI", "Claude", "DeepSeek", "豆包", "Gemini",
                    "LLM", "Token", "Prompt", "Agent", "Ollama", "千问", "大模型",
                    "OpenClaw", "ASR", "Codex", "Claude Code", "SayIt", "Hermes",
                    "Vibe Coding", "Typeless", "Vibe"
                ]
            }
            await ws.send(json.dumps(start_cmd))
            
            with wave.open(audio_path, "rb") as wf:
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                duration_sec = n_frames / framerate if framerate else 0
                chunk_size = int(framerate * 0.08)
                frames_sent = 0
                while True:
                    data = wf.readframes(chunk_size)
                    if not data:
                        break
                    await ws.send(data)
                    frames_sent += 1
                    await asyncio.sleep(0.002)
                    
            stop_cmd = {
                "cmd": "stop",
                "audio_stats": {
                    "avg_rms": 0.015,
                    "peak_amplitude": 0.5,
                    "peak_rms": 0.2,
                    "silence_ratio": 0.4,
                    "total_frames": frames_sent
                },
                "usage_meta": {
                    "ptt_hold_ms": int(duration_sec * 1000)
                }
            }
            await ws.send(json.dumps(stop_cmd))
            
            final_text = ""
            asr_text = ""
            start_t = asyncio.get_event_loop().time()
            while True:
                time_left = timeout - (asyncio.get_event_loop().time() - start_t)
                if time_left <= 0:
                    break
                resp_raw = await asyncio.wait_for(ws.recv(), timeout=time_left)
                resp = json.loads(resp_raw)
                if resp.get("type") == "final":
                    asr_text = resp.get("asr_text", "").strip()
                    llm_text = resp.get("llm_text", "").strip()
                    final_text = llm_text or asr_text
                elif resp.get("type") == "done":
                    break
                    
            if final_text:
                return {"text": final_text, "asr_text": asr_text, "duration": duration_sec}, None
            return None, "云端未返回文本"
    except Exception as e:
        return None, str(e)

def auto_recover_record(rec_id, audio_path, duration):
    """后台独立线程执行失败自愈与剪贴板注入"""
    def worker():
        log(f"🔄 [启动自动自愈] 正在为失败录音 (ID: {rec_id}, 时长: {duration:.1f}s) 重新识别...")
        try:
            res, err = asyncio.run(async_retranscribe(audio_path))
            if res and res.get("text"):
                target_text = res["text"]
                log(f"✨ [自愈成功] 成功转录出 {len(target_text)} 字符: {target_text[:35]}...")
                
                # 写入剪贴板
                double_lock_clipboard(target_text, label="自愈重试")
                
                # 回写数据库
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=3.0)
                    cur = conn.cursor()
                    cur.execute("SELECT raw_json FROM history_records WHERE id=?", (rec_id,))
                    row = cur.fetchone()
                    if row:
                        data = json.loads(row[0])
                        data["asrText"] = res.get("asr_text", "")
                        data["llmText"] = target_text
                        data["isEmpty"] = False
                        data["charCount"] = len(target_text)
                        data["asrDurationSec"] = duration
                        data["asrProvider"] = "Qwen3-ASR-1.7B"
                        if "failReason" in data:
                            del data["failReason"]
                        if "failReasonCode" in data:
                            del data["failReasonCode"]
                        new_raw = json.dumps(data, ensure_ascii=False)
                        cur.execute("UPDATE history_records SET is_empty=0, char_count=?, raw_json=? WHERE id=?", (len(target_text), new_raw, rec_id))
                        conn.commit()
                    conn.close()
                    log("  [✓ 同步] 已将修复结果回写至 SayIt 本地数据库！")
                except Exception as dbe:
                    log(f"  [!] 回写数据库失败: {dbe}")
            else:
                log(f"❌ [自愈重试未获取到文本] 详情: {err}")
        except Exception as e:
            log(f"❌ [自愈线程异常] {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

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
                duration = data.get("durationSec") or data.get("audioDurationSec") or 0.0
                audio_path = data.get("audioFilePath") or os.path.join(AUDIO_DIR, f"{id_}.wav")
                is_empty = data.get("isEmpty", False) or not text.strip()
                return {
                    "rowid": rowid,
                    "id": id_,
                    "timestamp": ts,
                    "text": text.strip(),
                    "app": data.get("processName", ""),
                    "duration": duration,
                    "audio_path": audio_path,
                    "is_empty": is_empty,
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
    log(f"=== SayIt 剪贴板保底 & 智能自愈管家 v2.0 已启动 (PID: {os.getpid()}) ===")
    
    init_rec = get_latest_record()
    last_rowid = init_rec["rowid"] if init_rec else 0
    last_ts = init_rec["timestamp"] if init_rec else 0
    
    log(f"基线定位完成: 当前最新记录 rowid={last_rowid}, timestamp={last_ts}")
    log("正在持续静默监听 SayIt 语音转文字事件 (支持成功转录秒级保底 & 失败录音自动补漏)...")

    recovering_ids = set()

    while True:
        try:
            rec = get_latest_record()
            if rec:
                is_new = (rec["rowid"] > last_rowid) or (rec["timestamp"] > last_ts)
                if is_new:
                    last_rowid = max(last_rowid, rec["rowid"])
                    last_ts = max(last_ts, rec["timestamp"])
                    
                    if not rec["is_empty"] and rec["text"]:
                        # 正常识别成功流程
                        target_text = rec["text"]
                        log(f"⚡ [捕获到新语音] 长度={len(target_text)} 字符 | 应用={rec['app']} | 内容: {target_text[:30]}...")
                        double_lock_clipboard(target_text, label="正常识别")
                    else:
                        # 识别失败 / 无有效声音 / 超时
                        duration = rec.get("duration", 0.0)
                        if duration <= 3.0:
                            log(f"⏸️ [过滤] 忽略极短误触录音 (时长: {duration:.1f}s, ID: {rec['id']})")
                        else:
                            if rec["id"] not in recovering_ids:
                                recovering_ids.add(rec["id"])
                                log(f"⚠️ [发现转录失败录音] 时长: {duration:.1f}s | 应用: {rec['app']} | ID: {rec['id']} -> 自动触发后台重试...")
                                auto_recover_record(rec["id"], rec["audio_path"], duration)
                                
            time.sleep(0.12)
        except Exception as e:
            log(f"[异常恢复] {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
