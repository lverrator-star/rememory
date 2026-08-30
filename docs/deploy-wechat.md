# 微信部署（ilink 对话开放平台）

微信侧直接调用微信对话开放平台的 ilink API（长轮询收发），**不经过 OpenClaw 等 agent 框架**，保证回复质量不被框架注入污染。

## 1. 获取 bot token

在[微信对话开放平台](https://chatbot.weixin.qq.com)（或企业微信的相应入口）创建一个机器人，拿到 **bot token** 和 **baseUrl**。

> 如果你之前用过 OpenClaw 的微信插件，token 在 `~/.openclaw/openclaw-weixin/accounts/*.json` 里能找到；但更推荐自己在平台重新申请一个，避免泄露 OpenClaw 相关账号。

## 2. 配置 `.env`

在项目根目录 `.env` 里填：

```
WECHAT_TOKEN=你的ilink_bot_token
WECHAT_BASE_URL=https://ilinkai.weixin.qq.com
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=GLM-5.3-Flash
```

## 3. 运行

```bash
cd service
python wechat_bot.py
```

看到 `[wx] 开始轮询 ilink` 即为正常。用微信给机器人发消息，它会随机延迟后回复（多条短句连发）。

## 4. 后台常驻 + 开机自启（Windows）

已提供三件套，双击即可：

- `start_wechat_bot.bat`：前台/后台运行，日志写入 `logs\wechat_bot.log`
- `start_wechat_bot.vbs`：**隐藏窗口**启动上面的 bat
- `restart_wechat_bot.bat`：杀掉旧进程 + 重启

开机自启：

1. `Win + R` → `shell:startup`，把 `start_wechat_bot.vbs` 的快捷方式放进去；或
2. 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 新建字符串值，数据填 `wscript.exe "完整路径\start_wechat_bot.vbs"`。

## 5. 协议字段说明

`wechat_bot.py` 里的 ilink 协议是从微信插件逆向得到的，几个关键字段：

- 请求头 `AuthorizationType: ilink_bot_token` + `Authorization: Bearer <token>`
- `getupdates`（长轮询，timeout 40s）、`sendmessage` 两个端点
- `bot_agent` 默认 `openclaw-weixin/2.4.6`，是**客户端标识字符串**（接口期望的版本号），不是对 OpenClaw 的依赖；可用环境变量 `WECHAT_BOT_AGENT` 覆盖

微信接口若将来变动，需要按实际抓包结果重新适配这两个端点的字段。

## 6. 验证

- 给机器人发消息，看 `logs\wechat_bot.log` 的 `[chat]` 流转。
- 聊几句后 `python check_quality.py` 体检，对比基准指标。
