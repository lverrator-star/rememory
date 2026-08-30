# -*- coding: utf-8 -*-
"""共享：环境变量 / 配置 / LLM 密钥加载（不含任何个人数据）。

约定：
- 项目根目录放一个 .env（从 .env.example 复制），存密钥与个人账号信息
- config.json 放运行参数；不存在时回退到 config.example.json
"""
import json
import os
import shutil
import sqlite3
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE = os.path.join(BASE, "service")
DATA = os.path.join(BASE, "data")
PERSONA = os.path.join(BASE, "persona")


def load_dotenv(path=None):
    """极简 .env 加载器，避免额外依赖。已存在的环境变量优先，不被覆盖。"""
    path = path or os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def load_config():
    path = os.path.join(SERVICE, "config.json")
    if not os.path.exists(path):
        path = os.path.join(SERVICE, "config.example.json")
    cfg = json.load(open(path, encoding="utf-8"))

    # 允许环境变量覆盖（主要是个人的 QQ 号等）
    if os.environ.get("LLM_MODEL"):
        cfg["model"] = os.environ["LLM_MODEL"]
    if os.environ.get("OWNER_QQ"):
        cfg["owner_qq"] = int(os.environ["OWNER_QQ"])
    if os.environ.get("NAPCAT_WS"):
        cfg["napcat_ws"] = os.environ["NAPCAT_WS"]
    if os.environ.get("LLM_MAX_TOKENS"):
        cfg["max_tokens"] = int(os.environ["LLM_MAX_TOKENS"])
    return cfg


def load_llm_key():
    """返回 (api_key, base_url)。

    优先环境变量 LLM_API_KEY / LLM_BASE_URL；若未设置且配置了 CC_SWITCH_DB，
    则从 CC Switch 的数据库中读取（Anthropic 兼容供应商）。
    """
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", "").strip()
    if key and base:
        return key, base.rstrip("/")

    db = os.environ.get("CC_SWITCH_DB", "").strip()
    if db and os.path.exists(db):
        tmp = os.path.join(tempfile.gettempdir(), "ccsw_read.db")
        shutil.copy(db, tmp)
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        cur.execute("SELECT settings_config FROM providers")
        for (cfg,) in cur.fetchall():
            c = json.loads(cfg)
            env = c.get("env", {})
            if env.get("ANTHROPIC_AUTH_TOKEN"):
                con.close()
                return (env["ANTHROPIC_AUTH_TOKEN"],
                        env.get("ANTHROPIC_BASE_URL", "").rstrip("/"))
        con.close()

    raise RuntimeError(
        "未找到 LLM 密钥：请在 .env 里设置 LLM_API_KEY + LLM_BASE_URL，"
        "或设置 CC_SWITCH_DB 指向 CC Switch 数据库。"
    )
