# -*- coding: utf-8 -*-
"""说话风格量化分析 — 数据驱动反“伪人感”。

用法：
    python stats_style.py data/messages_xxx.jsonl --her 名字A,名字B --him 名字C

统计输出会给出长度分布、句尾标点/语气词、连发模式、高频词、特征使用率等，
把这些数字填进 persona 的“表达风格”层和 check_quality.py 的 BASELINE 即可。
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime

import jieba


def load(src, her, him):
    her_msgs, him_msgs, msgs = [], [], []
    for line in open(src, encoding="utf-8"):
        m = json.loads(line)
        s = m.get("sender", "")
        t = m.get("text", "").strip()
        if not t or s.startswith("系统"):
            continue
        if any(h in s for h in her):
            her_msgs.append(("her", m["time"], t))
            msgs.append(("her", m["time"], t))
        elif any(h in s for h in him):
            him_msgs.append(("him", m["time"], t))
            msgs.append(("him", m["time"], t))
    return her_msgs, him_msgs, msgs


def stat_len(arr, name):
    lens = sorted(len(t) for t in arr)
    if not lens:
        return
    def q(p):
        return lens[min(len(lens) - 1, int(len(lens) * p))]
    print(f"\n[{name}] 长度(字符): 均值{sum(lens)/len(lens):.1f} 中位{lens[len(lens)//2]} "
          f"P75={q(.75)} P90={q(.9)} 最长{max(lens)}")
    buckets = [(1, 3), (4, 6), (7, 10), (11, 15), (16, 20), (21, 30), (31, 100), (101, 9999)]
    for lo, hi in buckets:
        c = sum(1 for x in lens if lo <= x <= hi)
        print(f"  {lo:>3}-{hi:<4} 字: {c:>5} 条 ({c/len(lens)*100:5.1f}%)")


def tails(arr, name):
    c = Counter()
    for t in arr:
        t = t.rstrip()
        if not t:
            continue
        ch = t[-1]
        if ch in "。！？…~～.!?":
            c[ch] += 1
        elif ch in "啊呀呢嘛呗啦哈哦喔哟咧呐咯嘻吼":
            c[f"语气词'{ch}'"] += 1
        elif ch in "的了着吧呢":
            c[f"虚词'{ch}'"] += 1
        else:
            c["(无标点)"] += 1
    print(f"\n[{name}] 句尾分布:")
    for k, v in c.most_common(15):
        print(f"  {k}: {v} ({v/len(arr)*100:.1f}%)")


def punct_rate(arr, name):
    total = len(arr)
    for pat, label in [
        (r"[?？]", "问号"), (r"[!！]", "感叹号"), (r"…", "省略号"),
        (r"[~～]", "波浪号"), (r"[。.]", "句号"), (r"[,，]", "逗号"),
    ]:
        n = sum(1 for t in arr if re.search(pat, t))
        print(f"[{name}] 含{label}: {n}/{total} ({n/total*100:.1f}%)")


def opener(arr, name, topn=20):
    c = Counter()
    for t in arr:
        t = t.strip()
        if not t:
            continue
        m = re.match(r"^([一-鿿A-Za-z0-9]{1,2})", t)
        if m:
            c[m.group(1)] += 1
    print(f"\n[{name}] 开头两字 top{topn}: {c.most_common(topn)}")


def word_freq(arr, name, topn=40):
    stop = set("的了是在有和就不人都一我你他也这那啊呀呢嘛呗啦哈哦喔哟咧哼唉嗯吧吗咯嘤诶哇么啥")
    c = Counter()
    for t in arr:
        for w in jieba.cut(t):
            w = w.strip()
            if len(w) >= 2 and w not in stop and not re.fullmatch(r"[\W_]+", w):
                c[w] += 1
    print(f"\n[{name}] 高频词 top{topn}: {c.most_common(topn)}")


def interjection_rate(arr, name):
    total = len(arr)
    pats = [
        (r"哈{2,}|hh+|2333|xswl", "笑类(哈哈/hh/233/xswl)"),
        (r"笑死|笑飞|笑晕|笑裂", "笑死/笑飞"),
        (r"em+", "emmm"),
        (r"嗯{1,}", "嗯"),
        (r"草\b|卧槽|我靠|nb|6{2,}", "粗口/网络语"),
        (r"宝宝", "宝宝"),
        (r"呜呜|QAQ|哭了|想哭", "哭类"),
        (r"[😀-🙏🌀-🫶]", "emoji"),
        (r"\[\w+\]", "QQ占位[图片][表情]"),
        (r"[a-zA-Z]{3,}", "英文词"),
    ]
    print(f"\n[{name}] 特征使用率 (n={total}):")
    for pat, label in pats:
        n = sum(1 for t in arr if re.search(pat, t))
        print(f"  {label}: {n} ({n/total*100:.1f}%)")


def bursts(msgs, who, gap=90):
    groups, cur, prev_t = [], [], None
    for w, tstr, txt in msgs:
        t = datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")
        if w == who:
            if cur and (t - prev_t).total_seconds() > gap:
                groups.append(cur)
                cur = []
            cur.append(txt)
        else:
            if cur:
                groups.append(cur)
                cur = []
        prev_t = t
    if cur:
        groups.append(cur)
    c = Counter(len(g) for g in groups)
    print(f"\n[{who}] 连发组: {len(groups)} 组, 组内条数分布: {dict(sorted(c.items()))}")
    if groups:
        print(f"  单条即止 {c[1]} 组 ({c[1]/len(groups)*100:.1f}%), "
              f"2条连发 {c[2]} 组 ({c[2]/len(groups)*100:.1f}%), "
              f"3+条 {sum(v for k, v in c.items() if k >= 3)} 组 "
              f"({sum(v for k, v in c.items() if k >= 3)/len(groups)*100:.1f}%)")
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="messages_*.jsonl 路径")
    ap.add_argument("--her", help="她的发送者名，逗号分隔", default="")
    ap.add_argument("--him", help="他的发送者名，逗号分隔", default="")
    args = ap.parse_args()

    her_names = [x for x in args.her.split(",") if x]
    him_names = [x for x in args.him.split(",") if x]
    her_msgs, him_msgs, msgs = load(args.src, her_names, him_names)
    her = [t for _, _, t in her_msgs]
    him = [t for _, _, t in him_msgs]
    print(f"她的消息: {len(her)} 条, 他的消息: {len(him)} 条")

    stat_len(her, "她")
    if him:
        stat_len(him, "对方")
    tails(her, "她")
    punct_rate(her, "她")
    if him:
        punct_rate(him, "对方")
    opener(her, "她")
    if him:
        opener(him, "对方")
    word_freq(her, "她")
    interjection_rate(her, "她")
    her_groups = bursts(msgs, "her")
    if her_groups:
        sample = [len(t) for g in her_groups if len(g) >= 2 for t in g]
        if sample:
            print(f"  连发组内每条平均长度: {sum(sample)/len(sample):.1f} 字")


if __name__ == "__main__":
    main()
