# -*- coding: utf-8 -*-
"""人设素材提取：从解析后的 messages_*.jsonl 提取“她”的消息 + 风格画像 + 抽样。

用法：
    python build_persona.py data/messages_qjh.jsonl --her 名字A,名字B --him 名字C --out persona
"""
import argparse
import json
import os
import random
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="messages_*.jsonl 路径")
    ap.add_argument("--her", help="她的发送者名，逗号分隔", default="")
    ap.add_argument("--him", help="他的发送者名，逗号分隔", default="")
    ap.add_argument("--out", help="输出目录", default="persona")
    args = ap.parse_args()

    her_names = set(x for x in args.her.split(",") if x)
    him_names = set(x for x in args.him.split(",") if x)

    her_msgs, user_msgs = [], []
    for line in open(args.src, encoding="utf-8"):
        m = json.loads(line)
        if m["text"] == "":
            continue
        if m["sender"] in her_names:
            her_msgs.append(m)
        elif m["sender"] in him_names:
            user_msgs.append(m)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "her_messages.jsonl"), "w", encoding="utf-8") as f:
        for m in her_msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    texts = [m["text"] for m in her_msgs if m["text"] != "[图片]"]
    print("她的有效消息:", len(her_msgs), " 文本消息:", len(texts))

    # 句尾字符
    enders = Counter()
    for t in texts:
        if t:
            last = t[-1]
            if last in "。！？～~…、，,啦咯呗嘛呢呀啊哦喔哈吼~！？😊😂🤣🥰😘❤️💗✨🌙👍":
                enders[last] += 1

    # 高频双字词（粗粒度话题词）
    bigram = Counter()
    for t in texts:
        for i in range(len(t) - 1):
            a, b = t[i], t[i + 1]
            if not (a.isalnum() or b.isalnum() or '一' <= a <= '鿿' or '一' <= b <= '鿿'):
                continue
            bigram[t[i:i + 2]] += 1

    hours = Counter()
    for m in her_msgs:
        hours[m["time"][11:13]] += 1

    lens = [len(t) for t in texts]

    report = []
    report.append("=== 风格画像 ===")
    report.append(f"消息总数: {len(her_msgs)} (含图片占位)")
    report.append(f"高频句尾: " + " ".join(f"{c}:{n}" for c, n in enders.most_common(25)))
    report.append(f"高频双字词: " + " ".join(f"{w}:{n}" for w, n in bigram.most_common(80)))
    report.append(f"活跃小时(0-23): " + " ".join(f"{h}:{hours.get(f'{int(h):02d}', 0)}" for h in range(24)))
    report.append(f"消息长度: 均值{sum(lens)/len(lens):.1f} 中位{sorted(lens)[len(lens)//2]} 最长{max(lens)}")
    with open(os.path.join(args.out, "style_profile.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    random.seed(42)
    samples = random.sample(her_msgs, min(150, len(her_msgs))) + her_msgs[-150:]
    samples.sort(key=lambda m: m["time"])
    with open(os.path.join(args.out, "samples.txt"), "w", encoding="utf-8") as f:
        for m in samples:
            f.write(f"[{m['time']}] {m['text']}\n")

    print("done ->", args.out)


if __name__ == "__main__":
    main()
