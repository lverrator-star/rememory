# -*- coding: utf-8 -*-
"""重建记忆索引并做检索自测。

用法：python rebuild_index.py [关键词1 关键词2 ...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bot  # import 即触发 load_index

queries = sys.argv[1:] or ["一起做过什么", "生日", "旅游", "吵架", "晚安"]
print(f"\n=== 检索自测（块数 {len(bot.CHUNKS)}）===")
for q in queries:
    hits = bot.retrieve(q)
    print(f"\nQ: {q} → {len(hits)} 块")
    for h in hits[:1]:
        print(h[:180].replace("\n", " | "))
