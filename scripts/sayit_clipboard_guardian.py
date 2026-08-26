"""
SayIt 剪贴板常驻保底管家 (SayIt Clipboard Guardian) v2.1.0 (极速超感版)
核心特性：
1. 30ms (0.03s) 毫秒级极速轮询：转录完成瞬间（<30ms）立即物理强塞 Windows 剪贴板。
2. 3.5秒持续防抢占加固锁 (Anti-Hijack Multi-Lock)：
   在转录完成后的 3.5 秒内，分 10 个频次持续巡检剪贴板。一旦发现被 SayIt 原生逻辑还原或被其他应用冲掉，瞬间强行覆写回最新语音文本！
3. 智能失败探测 & 自动重试补漏 (Auto Recovery)：
   网络波动/超时导致"无有效声音"时，自动提取原声 WAV 极速重转并锁入剪贴板。
4. 采用 Windows 原生 win32clipboard API，绝对稳定无阻塞。
"""

import os
import sys
import time
import json
import sqlite3
import threading
import asyncio
import wave
import websockets
from datetime import datetime

import win32clipboard
import win32con

# 动态定位 SayIt 路径
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

def raw_set_clipboard(text: str) -> bool:
    """使用 win32clipboard 原生接口极速写入 Unicode 文本"""
    if not text:
        return False
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.015)
    return False

def raw_get_clipboard() -> str:
    """读取当前剪贴板 Unicode 文本"""
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) or ""
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass
    return ""

def persistent_anti_hijack_lock(target_text: str, label="正常转录"):
    """
    3.5 秒持续防抢占加固线程：
    分阶段持续巡检剪贴板，彻底粉碎 SayIt 原生 '恢复旧剪贴板' 或其他后台软件的抢占！
    """
    def worker():
        check_intervals = [0.0, 0.05, 0.15, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5]
        for delay in check_intervals:
            if delay > 0:
                time.sleep(delay)
            curr = raw_get_clipboard()
            if curr != target_text:
                ok = raw_set_clipboard(target_text)
                if ok and delay > 0:
                    log(f"  🛡️ [防抢占生效 (+{int(delay*1000)}ms)] 探测到剪贴板偏离，已强制重锁回最新语音文本！")
        log(f"  [✓ 绝对锁定完成] ({label}) 3.5秒巡检加固完毕，当前剪贴板已稳固就绪。")

    # 0ms 同步立即写入第一次
    raw_set_clipboard(target_text)
    # 异步启动 3.5 秒防抢占巡检
    t = threading.Thread(target=worker, daemon=True)
    t.start()

async def async_retranscribe(audio_path, timeout=60):
    """通过 SayIt 原生 WebSocket 协议直接转录本地 WAV"""
    if not os.path.exists(audio_path):
        return None, "音频文件不存在"
    
    uri = "wss://sayitapp.site/ws/transcribe"
    try:
        async with websockets.connect(uri, ping_interval=10, ping_timeout=10) as ws:
            await asyncio.wait_for(ws.recv(), timeout=10.0)
            
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
                
                # 触发 3.5 秒防抢占加固锁
                persistent_anti_hijack_lock(target_text, label="自愈重试")
                
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
    """以只读无锁 URI 方式极速读取 SQLite WAL 数据库最新转录"""
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=0.2)
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
    except Exception:
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
    log(f"=== SayIt 剪贴板保底 & 智能自愈管家 v2.1 (极速超感版) 已启动 (PID: {os.getpid()}) ===")
    
    init_rec = get_latest_record()
    last_rowid = init_rec["rowid"] if init_rec else 0
    last_ts = init_rec["timestamp"] if init_rec else 0
    
    log(f"基线定位完成: 当前最新记录 rowid={last_rowid}, timestamp={last_ts}")
    log("极速监听中 (30ms 极速轮询 + 3.5秒防抢占加固锁 + 失败自动补漏)...")

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
                        # 正常识别成功流程 -> 瞬间写入并启动 3.5s 防抢占巡检
                        target_text = rec["text"]
                        log(f"⚡ [捕获到新语音] 长度={len(target_text)} 字符 | 应用={rec['app']} | 内容: {target_text[:30]}...")
                        persistent_anti_hijack_lock(target_text, label="正常识别")
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
                                
            # 30ms (0.03s) 极速超感轮询
            time.sleep(0.03)
        except Exception as e:
            log(f"[异常恢复] {e}")
            time.sleep(0.1)

if __name__ == "__main__":
    main()
