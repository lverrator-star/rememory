# -*- coding: utf-8 -*-
"""
角色聊天机器人 · QQ 侧（OneBot 11 / NapCat）
- 记忆检索(BM25) + LLM(Anthropic 兼容接口) + OneBot 11
- 命令行测试: python bot.py --cli
- 连接 NapCat: python bot.py

复现步骤见 README 与 docs/。把 persona/system_prompt.txt 换成你自己的人设，
data/ 下放你自己导出的 messages_*.jsonl 即可。
"""
import argparse
import asyncio
import glob
import json
import os
import pickle
import random
import re
import time
from collections import deque
from datetime import datetime

import httpx
import jieba
import websockets
from rank_bm25 import BM25Okapi

from common import BASE, SERVICE, PERSONA, DATA, load_dotenv, load_config, load_llm_key

load_dotenv()
config = load_config()
SYSTEM_PROMPT = open(os.path.join(PERSONA, "system_prompt.txt"), encoding="utf-8").read()

# ---------------- 记忆索引 ----------------
# 数据源：data/ 下所有 messages_*.jsonl，每行 {"time","sender","text"}
def _data_sources():
    return sorted(glob.glob(os.path.join(DATA, "messages_*.jsonl")))

# 占位消息（无文字内容，不入索引）
PLACEHOLDER = re.compile(
    r"\[(?:动画表情|通话消息|文件|聊天记录|图文|链接|小程序|红包|转账|视频|"
    r"语音消息|名片消息|不支持的消息类型|位置消息|引用消息|拍一拍消息|卡片式链接)[^\]]*\]"
)


def clean_text(t):
    t = t.replace("[图片]", "(图片)").replace("[表情]", "(表情)")
    t = PLACEHOLDER.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_chunks(chunk_size=12):
    """合并所有数据源，按时间排序切块"""
    msgs = []
    for path in _data_sources():
        for line in open(path, encoding="utf-8"):
            m = json.loads(line)
            if m.get("sender", "").startswith("系统消息"):
                continue
            text = clean_text(m.get("text", ""))
            if not text or text in ("(图片)", "(表情)"):
                continue
            msgs.append((m["time"], m.get("sender", ""), text[:80]))
    msgs.sort(key=lambda x: x[0])
    chunks = []
    for i in range(0, len(msgs), chunk_size):
        group = msgs[i:i + chunk_size]
        chunks.append("\n".join(f"{t} {s}: {x}" for t, s, x in group))
    return chunks


def load_index():
    cache = os.path.join(SERVICE, "memory_index.pkl")
    srcs = _data_sources()
    if os.path.exists(cache) and srcs and all(
        os.path.getmtime(cache) > os.path.getmtime(s) for s in srcs
    ):
        with open(cache, "rb") as f:
            return pickle.load(f)
    chunks = build_chunks()
    tokenized = [list(jieba.cut(c)) for c in chunks]
    pairs = [(c, t) for c, t in zip(chunks, tokenized) if t]
    chunks = [c for c, _ in pairs]
    tokenized = [t for _, t in pairs]
    bm25 = BM25Okapi(tokenized)
    with open(cache, "wb") as f:
        pickle.dump((chunks, bm25), f)
    return chunks, bm25


CHUNKS, BM25_INDEX = load_index()
print(f"[init] 记忆块 {len(CHUNKS)} 个已就绪")

# 聊天记录落盘（私有文件，用于质量监测和人设修正）
CHATLOG = os.path.join(DATA, "chatlog_qq.jsonl")

# LLM 连续失败时的兜底话术（短、自然、每次随机，避免固定一句被看穿）
FALLBACKS = ["刚没看手机", "嗯？", "在的", "刚才没在"]


def append_chatlog(sender, text):
    try:
        with open(CHATLOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "sender": sender, "text": text},
                ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[log] 落盘失败: {e}")


def retrieve(query, topk=None):
    topk = topk or config["memory_topk"]
    tokens = list(jieba.cut(query))
    scores = BM25_INDEX.get_scores(tokens)
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:topk]
    return [CHUNKS[i] for i in order if scores[i] > 0.3]


# ---------------- LLM ----------------
API_KEY, API_BASE = load_llm_key()
print(f"[init] LLM: {config['model']}")


def build_messages(history, user_text):
    """构造 Anthropic 风格 messages。history 为 [(user, assistant), ...]"""
    memory = retrieve(user_text)
    mem_block = ""
    if memory:
        mem_block = "【记忆片段】（你们过去的聊天记录，事实以此为准）\n" + "\n---\n".join(memory)
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    system = SYSTEM_PROMPT + f"\n\n现在是：{now}。{mem_block}"
    messages = []
    for u, a in history:
        messages.append({"role": "user", "content": u})
        if a:
            messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": user_text})
    return system, messages


def call_llm(history, user_text, retries=3):
    system, messages = build_messages(history, user_text)
    url = API_BASE.rstrip("/") + "/v1/messages"
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
        time.sleep(2 * (attempt + 1))
    return None


# ---------------- 对话状态 ----------------
class Bot:
    def __init__(self):
        self.sessions = {}  # user_id -> deque[(user_msg, assistant_reply), ...]

    def reply(self, user_id, text):
        hist = self.sessions.setdefault(user_id, deque(maxlen=config["max_turns"]))
        answer = call_llm(list(hist), text)
        if not answer:
            answer = random.choice(FALLBACKS)
            print("[llm] 重试后仍无回复，用兜底话术")
        hist.append((text, answer))
        return answer


bot = Bot()


# ---------------- OneBot 11 ----------------
def split_reply(reply):
    """按真实连发风格拆分：每条尽量<=20字，最多3条。
    （参考统计：连发组内每条平均 9.5 字，2 条连发最常见，3 条及以上约 29%）"""
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


async def onebot_loop():
    url = config["napcat_ws"]
    print(f"[onebot] 连接 NapCat {url} ...")
    while True:
        try:
            async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
                print("[onebot] 已连接，等待消息")
                while True:
                    raw = await ws.recv()
                    try:
                        event = json.loads(raw)
                    except Exception:
                        continue
                    if event.get("post_type") != "message":
                        continue
                    if event.get("message_type") != "private":
                        continue
                    user_id = event.get("user_id")
                    if user_id != config["owner_qq"]:
                        print(f"[onebot] 忽略非主人消息 from {user_id}")
                        continue
                    text = event.get("raw_message", "").strip()
                    if not text:
                        continue
                    print(f"[chat] {user_id}: {text}")
                    reply = bot.reply(user_id, text)
                    print(f"[chat] 角色: {reply}")
                    append_chatlog("他", text)
                    for piece in split_reply(reply):
                        append_chatlog("她", piece)
                    # 不秒回：随机打字延迟 0.8~2.5s
                    await asyncio.sleep(random.uniform(0.8, 2.5))
                    for i, piece in enumerate(split_reply(reply)):
                        action = {
                            "action": "send_private_msg",
                            "params": {"user_id": user_id, "message": piece},
                            "echo": f"{event.get('message_id')}-{i}",
                        }
                        await ws.send(json.dumps(action, ensure_ascii=False))
                        # 连发间隔随机 0.4~1.2s
                        await asyncio.sleep(random.uniform(0.4, 1.2))
        except Exception as e:
            print(f"[onebot] 断线: {e}，5秒后重连")
            await asyncio.sleep(5)


# ---------------- CLI 测试 ----------------
async def cli_loop():
    print("=== 命令行测试模式（输入消息聊天，q 退出）===")
    uid = config["owner_qq"] or 0
    loop = asyncio.get_event_loop()
    while True:
        text = await loop.run_in_executor(None, lambda: input("你: ").strip())
        if text.lower() == "q":
            break
        if not text:
            continue
        reply = bot.reply(uid, text)
        for piece in split_reply(reply):
            print(f"角色: {piece}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="命令行测试模式")
    args = parser.parse_args()
    if args.cli:
        asyncio.run(cli_loop())
    else:
        asyncio.run(onebot_loop())


if __name__ == "__main__":
    main()
