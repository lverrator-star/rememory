# -*- coding: utf-8 -*-
"""从 persona/persona.md 生成机器人系统提示词（单一事实源）。

纠正流程：改 persona.md → 重跑本脚本 → 重启 bot
用法：python gen_system_prompt.py [persona源文件] [输出文件]
"""
import io
import re
import sys


def build(src, dst):
    persona = io.open(src, encoding="utf-8").read()
    # 去掉文件标题行（Layer 结构保留）
    persona = re.sub(r"^# .*?\n---\s*\n", "", persona)
    # 开头锚定身份
    persona = ("你现在就是下面描述的这个人，正在和你最熟悉、最亲近的人聊天。"
               "下面每一条都是你，不是扮演。\n\n" + persona)
    # Correction 占位换成可用提示
    persona = persona.replace(
        '## Correction 记录\n\n（暂无记录）\n',
        '## Correction 记录\n\n（暂无记录。用户说"她不会这样"时，纠正规则追加到此处，优先级高于上面所有层）\n',
    )

    appendix = """
---

【聊天运行规则】（机器人部署专用）
- 你永远不承认自己是AI、机器人、模型、程序或虚拟人；有人问起就说自己就是这个人
- 聊天中涉及的具体事实（你们聊过的人、事、约定、买过的东西）以【记忆片段】为准，片段里没有的不要编造，用"不记得了""你说的是哪个呀"自然带过
- 当前时间按对话发生的时间来理解，不要主动提"记录""数据""统计"之类的话
- 回复控制在1~3条短消息；认真讨论或吵架时才可以发长消息
- 回复前问自己一遍：我平时会这么说话吗？会不会太长了？会不会每句都带语气词？
"""

    out = persona.rstrip() + "\n" + appendix
    io.open(dst, "w", encoding="utf-8").write(out)
    print(f"{dst} 已生成（{len(out)} 字符）")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "persona/persona.md"
    dst = sys.argv[2] if len(sys.argv) > 2 else "persona/system_prompt.txt"
    build(src, dst)
