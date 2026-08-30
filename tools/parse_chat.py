# -*- coding: utf-8 -*-
"""解析 QQ 消息管理器导出的 txt 聊天记录 → JSONL（每行 {"time","sender","text"}）。

用法：
    python parse_chat.py 某人(QQ号).txt --label qjh --out data/messages_qjh.jsonl
"""
import argparse
import json
import os
import re
from collections import Counter

MSG_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+)$")


def parse_file(path):
    """返回 [(time, sender, text), ...]"""
    messages = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    cur_time = cur_sender = None
    cur_text = []
    for line in lines:
        m = MSG_RE.match(line)
        if m:
            if cur_time is not None:
                messages.append((cur_time, cur_sender, "\n".join(cur_text).strip()))
            cur_time, cur_sender = m.group(1), m.group(2)
            cur_text = []
        elif cur_time is not None:
            cur_text.append(line)
    if cur_time is not None:
        messages.append((cur_time, cur_sender, "\n".join(cur_text).strip()))
    return messages


def stats(messages, label):
    n = len(messages)
    senders = Counter(s for _, s, _ in messages)
    lens = [len(t) for _, _, t in messages]
    non_empty = [t for _, _, t in messages if t and t != "[图片]"]
    out = [f"=== {label} ==="]
    out.append(f"总消息数: {n}")
    out.append(f"发送人分布: {dict(senders)}")
    out.append(f"时间跨度: {messages[0][0]} ~ {messages[-1][0]}")
    out.append(f"平均长度: {sum(lens)/max(n,1):.1f} 字符, 中位: {sorted(lens)[n//2] if n else 0}")
    short = sum(1 for l in lens if l <= 4)
    out.append(f"超短消息(≤4字): {short} ({short/max(n,1)*100:.1f}%)")
    all_text = "".join(non_empty)
    char_cnt = Counter(all_text)
    out.append("高频字符: " + " ".join(f"{c}:{cnt}" for c, cnt in char_cnt.most_common(40)))
    return "\n".join(out), messages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="QQ 导出的 txt 文件")
    ap.add_argument("--label", help="输出/统计标签", default="chat")
    ap.add_argument("--out", help="输出 jsonl 路径", default="")
    args = ap.parse_args()

    msgs = parse_file(args.src)
    s, msgs = stats(msgs, args.label)
    print(s)

    out = args.out or os.path.join("data", f"messages_{args.label}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for t, sender, text in msgs:
            f.write(json.dumps({"time": t, "sender": sender, "text": text},
                               ensure_ascii=False) + "\n")
    print(f"{args.label}: {len(msgs)} 条 -> {out}")


if __name__ == "__main__":
    main()
