# -*- coding: utf-8 -*-
"""质量体检：对比机器人回复 vs 参考数据基准（数据驱动反“伪人感”）。

用法：先聊几句让 chatlog 落盘，然后 `python check_quality.py`。

BASELINE 里的数字是“某份真实数据集”统计出来的示例基准，
请用 tools/ 下的 stats_style.py 对自己的聊天记录重新统计后替换。
"""
import json
import os
import re
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

# 示例基准（来自某份真实聊天记录统计，替换成你自己的）
BASELINE = {
    "median_len": 5,          # 长度中位数 5-6 字
    "le6_pct": 60.0,          # ≤6 字占比 ~60%
    "le10_pct": 82.0,         # ≤10 字占比 ~82%
    "no_punct_pct": 71.0,     # 句尾无标点 ~71%
    "tone_pct": 5.0,          # 语气词结尾 ~5%
    "qmark_pct": 2.6,         # 含问号 ~2.6%
}

# AI 腔 / 破绽词（出现即扣分）
AI_TELLS = [
    "随时待命", "请问有什么可以帮", "很高兴为", "我明白了", "我理解了",
    "我记好", "我记下", "收到", "好的呢", "正在为您", "为您服务",
    "作为AI", "作为人工智能", "我是一个AI", "帮您", "亲爱的用户",
    "当然可以", "没问题，", "让我来", "让我帮",
]


def load_her():
    msgs = []
    for f in ("chatlog_wx.jsonl", "chatlog_qq.jsonl"):
        p = os.path.join(DATA, f)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            m = json.loads(line)
            if m.get("sender") == "她" and m.get("text", "").strip():
                msgs.append(m["text"].strip())
    return msgs


def report():
    msgs = load_her()
    if not msgs:
        print("还没有“她”的回复记录（chatlog 为空）。聊几句之后再来体检。")
        return

    lens = sorted(len(t) for t in msgs)
    le6 = sum(1 for x in lens if x <= 6) / len(lens) * 100
    le10 = sum(1 for x in lens if x <= 10) / len(lens) * 100
    tails = Counter()
    for t in msgs:
        ch = t[-1]
        if ch in "。！？…~～.!?":
            tails[ch] += 1
        elif ch in "啊呀呢嘛呗啦哈哦喔哟咧呐咯嘻":
            tails[f"语气词'{ch}'"] += 1
        else:
            tails["(无标点)"] += 1
    no_punct = tails["(无标点)"] / len(msgs) * 100
    tone = sum(v for k, v in tails.items() if k.startswith("语气词")) / len(msgs) * 100
    qmark = sum(1 for t in msgs if re.search(r"[?？]", t)) / len(msgs) * 100
    tells = Counter()
    for t in msgs:
        for w in AI_TELLS:
            if w in t:
                tells[w] += 1

    print(f"=== 质量体检（{len(msgs)} 条回复）===")
    print(f"长度: 中位 {lens[len(lens)//2]} (基准 {BASELINE['median_len']}) | ≤6字 {le6:.0f}% (基准 {BASELINE['le6_pct']:.0f}%) | ≤10字 {le10:.0f}% (基准 {BASELINE['le10_pct']:.0f}%)")
    print(f"句尾无标点: {no_punct:.0f}% (基准 {BASELINE['no_punct_pct']:.0f}%) | 语气词结尾: {tone:.1f}% (基准 {BASELINE['tone_pct']}%) | 含问号: {qmark:.1f}% (基准 {BASELINE['qmark_pct']}%)")
    print(f"平均长度: {sum(lens)/len(lens):.1f} 字")

    print("\n--- 偏差提示 ---")
    warns = 0
    if abs(lens[len(lens)//2] - BASELINE['median_len']) > 3:
        print(f"⚠ 长度中位偏离基准 {abs(lens[len(lens)//2]-BASELINE['median_len'])} 字，回复偏{'长' if lens[len(lens)//2] > BASELINE['median_len'] else '短'}")
        warns += 1
    if le6 < BASELINE['le6_pct'] - 15:
        print(f"⚠ 短句占比过低（{le6:.0f}%），有写长文的倾向")
        warns += 1
    if no_punct < BASELINE['no_punct_pct'] - 15:
        print(f"⚠ 无标点占比过低（{no_punct:.0f}%），句尾标点用多了")
        warns += 1
    if tone > BASELINE['tone_pct'] + 8:
        print(f"⚠ 语气词使用超标（{tone:.1f}%），每句加'呀/呢'会显得假")
        warns += 1
    if tells:
        print(f"⚠ AI 腔词出现 {sum(tells.values())} 次: {dict(tells)}")
        warns += 1
    if warns == 0:
        print("✓ 各项指标都在基准范围内，表现健康")

    print("\n--- 最近 8 条“她”的回复 ---")
    for t in msgs[-8:]:
        print(f"  ({len(t)}字) {t}")


if __name__ == "__main__":
    report()
