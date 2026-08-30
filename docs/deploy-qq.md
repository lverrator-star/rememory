# QQ 部署（OneBot 11 / NapCat）

QQ 侧走 OneBot 11 协议，需要一个本地运行的 NapCat 实例登录你的 QQ 号，`bot.py` 通过 WebSocket 连接它收发消息。

> 注意：NapCat 需要**在你自己电脑上登录 QQ 号**。QQ 号异地登录有封号风险，所以这条链路**绑死本机**，不适合搬到云服务器。

## 1. 安装 NapCat

1. 下载 [NapCat](https://github.com/NapNeko/NapCatQQ)（Windows 版）。
2. 解压后运行 `launcher.bat`（或 `launcher-user.bat`），按提示**扫码登录**你的 QQ 号。

## 2. 配置 OneBot 11 WebSocket

编辑 NapCat 的配置文件（`napcat/config/` 下），确保开启正向 WebSocket 服务，监听地址与 `bot.py` 一致：

- 默认地址：`ws://127.0.0.1:3001`
- 如果你改了端口，同步改 `.env` 里的 `NAPCAT_WS` 或 `service/config.json` 里的 `napcat_ws`。

## 3. 配置并运行

在项目根目录 `.env` 里填：

```
OWNER_QQ=你的QQ号
NAPCAT_WS=ws://127.0.0.1:3001
LLM_API_KEY=...
LLM_BASE_URL=...
```

先本地试聊（NapCat 需已登录在线）：

```bash
cd service
python bot.py --cli     # 命令行直接聊，不经过 QQ
python bot.py           # 连接 NapCat，正式收发 QQ 私聊
```

`bot.py` 只响应 `OWNER_QQ` 的私聊消息，其他消息一律忽略。

## 4. 后台常驻 + 开机自启（Windows）

把 `service/bot.py` 也做成独立进程，参照 `start_wechat_bot.bat` / `start_wechat_bot.vbs` 的写法即可：

1. 建 `start_qq_bot.bat`（`chcp 65001` + `cd /d "%~dp0"` + `python -u -X utf8 bot.py >> logs\qq_bot.log 2>&1`）。
2. 建 `start_qq_bot.vbs` 隐藏窗口启动上面的 bat。
3. 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 加一项指向 vbs。
4. 同时把 NapCat 也加进开机自启（NapCat 后启动没关系，`bot.py` 自带 5 秒重连）。

## 5. 验证

- 用另一个 QQ 号给你的机器人发私聊，确认能收到回复。
- 看 `logs/qq_bot.log` 是否有 `[chat]` 流转。
- 聊几句后跑 `python check_quality.py` 体检。
