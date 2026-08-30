# -*- coding: utf-8 -*-
"""
角色聊天机器人 · 微信侧（ilink 对话开放平台，绕开 OpenClaw 框架）
- 收发：微信对话开放平台 ilink API（ilinkai.weixin.qq.com）
- 回复：本地 persona/system_prompt.txt + LLM(Anthropic 兼容接口)
- 说明：把 persona/system_prompt.txt 换成你自己的人设即可复现
"""
import base64
import json
import os
import random
import re
import secrets
import time
from collections import deque
from datetime import datetime

import httpx

from common import BASE, SERVICE, PERSONA, load_dotenv, load_config, load_llm_key

load_dotenv()
config = load_config()
SYSTEM_PROMPT = open(os.path.join(PERSONA, "system_prompt.txt"), encoding="utf-8").read()

# ---------------- 微信账号配置（来自 .env）----------------
TOKEN = os.environ.get("WECHAT_TOKEN", "").strip()
API_BASE = os.environ.get("WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com").rstrip("/")
SYNC_FILE = os.path.join(SERVICE, "wx_sync_buf.json")
if not TOKEN:
    raise RuntimeError("请先在 .env 里设置 WECHAT_TOKEN（微信对话开放平台的 bot token）")

# ilink 协议常量（逆向插件所得，非 OpenClaw 依赖）
APP_ID = "bot"
APP_VERSION = ((2 & 0xFF) << 16) | ((4 & 0xFF) << 8) | (6 & 0xFF)  # 2.4.6
BOT_AGENT = os.environ.get("WECHAT_BOT_AGENT", "openclaw-weixin/2.4.6")

MAX_HISTORY = 6  # 每用户保留最近 N 轮

# LLM 连续失败时的兜底话术（短、自然、每次随机，避免固定一句被看穿）
FALLBACKS = ["刚没看手机", "嗯？", "在的", "刚才没在"]

# 聊天记录落盘（私有文件，用于质量监测和人设修正）
CHATLOG = os.path.join(BASE, "data", "chatlog_wx.jsonl")


def append_chatlog(sender, text):
    try:
        with open(CHATLOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "sender": sender, "text": text},
                ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[log] 落盘失败: {e}")


# ---------------- LLM ----------------
API_KEY, LLM_BASE = load_llm_key()
print(f"[init] LLM: {config['model']}")


# ---------------- ilink API ----------------
def api_headers():
    uin_b64 = base64.b64encode(str(secrets.randbits(32)).encode()).decode()
    return {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {TOKEN}",
        "X-WECHAT-UIN": uin_b64,
        "iLink-App-Id": APP_ID,
        "iLink-App-ClientVersion": str(APP_VERSION),
    }


def base_info():
    return {"channel_version": "2.4.6", "bot_agent": BOT_AGENT}


def load_buf():
    if os.path.exists(SYNC_FILE):
        try:
            return json.load(open(SYNC_FILE, encoding="utf-8")).get("buf", "")
        except Exception:
            pass
    return ""


def save_buf(buf):
    json.dump({"buf": buf, "at": time.time()}, open(SYNC_FILE, "w", encoding="utf-8"))


def get_updates(buf):
    r = httpx.post(
        f"{API_BASE}/ilink/bot/getupdates",
        json={"get_updates_buf": buf or "", "base_info": base_info()},
        headers=api_headers(),
        timeout=40,
    )
    r.raise_for_status()
    return r.json()


def send_text(to_user, text, context_token):
    client_id = secrets.token_hex(16)
    body = {
        "msg": {
            "from_user_id": "",
            "to_user_id": to_user,
            "client_id": client_id,
            "message_type": 2,       # BOT
            "message_state": 2,      # FINISH
            "item_list": [{"type": 1, "text_item": {"text": text}}],  # TEXT
            "context_token": context_token,
        },
        "base_info": base_info(),
    }
    r = httpx.post(
        f"{API_BASE}/ilink/bot/sendmessage",
        json=body,
        headers=api_headers(),
        timeout=20,
    )
    if r.status_code != 200:
        print(f"[wx] send HTTP {r.status_code}: {r.text[:200]}")
        return False
    resp = r.json()
    if resp.get("ret") not in (0, None):
        print(f"[wx] send ret={resp.get('ret')} errmsg={resp.get('errmsg')}")
        return False
    return True


# ---------------- LLM 调用（带重试：强思考模型偶尔空回复时补一次） ----------------
def call_llm(history, user_text, retries=3):
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    system = SYSTEM_PROMPT + f"\n\n现在是：{now}。"
    messages = []
    for u, a in history:
        messages.append({"role": "user", "content": u})
        if a:
            messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": user_text})
    url = LLM_BASE + "/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    for attempt in range(retries):
        body = {
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "system": system,
            "messages": messages,
        }
        if attempt > 0:
            body["messages"] = messages[:-1] + [
                {"role": "user", "content": messages[-1]["content"] + "\n（必须直接用文字回复，不要说别的）"}
            ]
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=120)
            if r.status_code == 200:
                data = r.json()
                text = "".join(
                    b.get("text", "")
                    for b in data.get("content", [])
                    if b.get("type") == "text"
                ).strip()
                if text:
                    return text
                print("[llm] 空回复，重试")
            else:
                print(f"[llm] HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[llm] 第{attempt+1}次失败: {e}")
        time.sleep(1.5 * (attempt + 1))
    return None


def split_reply(reply):
    """按真实连发风格拆分：每条尽量<=20字，最多3条。"""
    parts = [p.strip() for p in reply.splitlines() if p.strip()]
    out = []
    for p in parts:
        for seg in re.split(r"(?<=[。！？…!?])\s*", p):
            seg = seg.strip()
            if seg:
                out.append(seg)
    final = []
    for seg in out:
        while len(seg) > 20 and len(final) < 3:
            final.append(seg[:20])
            seg = seg[20:]
        if len(final) >= 3:
            break
        final.append(seg)
    return final[:3] if final else [reply]


# ---------------- 主循环 ----------------
def main():
    buf = load_buf()
    sessions = {}  # from_user_id -> deque[(user, assistant)]
    print(f"[wx] 开始轮询 ilink（buf 长度 {len(buf)}）")
    while True:
        try:
            resp = get_updates(buf)
            if resp.get("ret") not in (0, None):
                print(f"[wx] getupdates ret={resp.get('ret')} errmsg={resp.get('errmsg')}，10秒后重试")
                time.sleep(10)
                continue
            new_buf = resp.get("get_updates_buf")
            if new_buf:
                buf = new_buf
                save_buf(buf)
            msgs = resp.get("msgs") or []
            for m in msgs:
                from_user = m.get("from_user_id") or ""
                ctx_token = m.get("context_token") or ""
                text = ""
                for item in m.get("item_list") or []:
                    if item.get("type") == 1:
                        text += item.get("text_item", {}).get("text", "")
                text = text.strip()
                if not text:
                    continue
                print(f"[chat] {from_user}: {text}")
                append_chatlog("他", text)
                hist = sessions.setdefault(from_user, deque(maxlen=MAX_HISTORY))
                reply = call_llm(list(hist), text)
                if not reply:
                    reply = random.choice(FALLBACKS)
                    print("[llm] 重试后仍无回复，用兜底话术")
                hist.append((text, reply))
                # 不秒回：随机打字延迟
                time.sleep(random.uniform(0.8, 2.2))
                for piece in split_reply(reply):
                    print(f"[chat] 角色: {piece}")
                    append_chatlog("她", piece)
                    ok = send_text(from_user, piece, ctx_token)
                    if not ok:
                        print("[wx] 发送失败")
                    time.sleep(random.uniform(0.4, 1.2))
        except httpx.HTTPError as e:
            print(f"[wx] 网络错误: {e}，5秒后重试")
            time.sleep(5)
        except Exception as e:
            print(f"[wx] 错误: {e}，5秒后重试")
            time.sleep(5)


if __name__ == "__main__":
    main()
