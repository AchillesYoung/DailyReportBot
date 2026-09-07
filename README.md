# AI 行业资讯钉钉自动化日报系统

两个数据源（RSS + Telegram），统一推送钉钉：

| 入口 | 频率 | 数据源 |
|---|---|---|
| `dailybot.rss` | 每天 2 次（北京 09:00 / 20:00） | RSS 资讯聚合 |
| `dailybot.telegram` | 每小时 1 次 | Telegram `@aiwizz` 频道 |

## 快速开始（VPS 部署）

### 1. 创建钉钉群机器人

群设置 → 智能群助手 → 添加机器人 → **自定义机器人**：

- 安全设置选 **加签**，复制 `SEC...` 开头的 secret
- 复制 webhook 地址（`https://oapi.dingtalk.com/robot/send?access_token=...`）

### 2. VPS 上安装

```bash
# 以 Ubuntu 24.04 为例，Python 3.12 已自带
sudo mkdir -p /opt/dailybot
sudo chown $USER:$USER /opt/dailybot
cd /opt/dailybot

# 拉代码
git clone https://github.com/<you>/DailyReportBot.git .

# 建虚拟环境
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 配环境变量
cp deploy/dailybot.env.example .env
# 编辑 .env，填入 DINGTALK_WEBHOOK_URL 和 DINGTALK_SECRET
```

### 3. 启用 systemd timer

```bash
# 复制服务文件
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo cp deploy/systemd/*.timer /etc/systemd/system/

# 启动并启用
sudo systemctl daemon-reload
sudo systemctl enable --now dailybot-morning.timer
sudo systemctl enable --now dailybot-evening.timer
sudo systemctl enable --now dailybot-telegram.timer

# 查看状态
systemctl list-timers dailybot-*
```

### 4. 手动验证

```bash
# 手动跑一次早报
systemctl start dailybot-morning.service

# 手动跑一次转发
systemctl start dailybot-telegram.service

# 看日志
journalctl -u dailybot-morning.service -f
```

## 配置

### `feeds.yaml` — RSS 源

```yaml
groups:
  - name: 海外官方
    feeds:
      - name: OpenAI Blog
        url: https://openai.com/blog/rss.xml
```

- 按分组组织，分组名会出现在简报标题层级
- 单个源抓取失败不影响其他源，会在简报中标注 `⚠️ xx 抓取失败`
- 中文媒体很多没有 RSS，可用 [RSSHub](https://docs.rsshub.app/) 桥接后填入

### `reminders.yaml` — 提醒事项

```yaml
reminders:
  - text: "10:00 产品站会"
    schedule: daily            # 每次都带
  - text: "记得提交本周周报"
    schedule: weekly
    days: [fri]                # mon..sun，按北京时间判定
    editions: [morning]        # 可选；缺省 = 早晚都带
```

### `.env` — 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DINGTALK_WEBHOOK_URL` | ✅ | 钉钉机器人 webhook 地址 |
| `DINGTALK_SECRET` | 推荐 | 加签的 `SEC...` |
| `TELEGRAM_CHANNEL` | 可选 | 默认 `aiwizz` |
| `FORWARDER_STATE_FILE` | 可选 | 默认 `./state.json` |

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# dailybot 日报：只打印 markdown，不推送
.venv/bin/python -m dailybot --edition morning --dry-run

# dailybot 日报：真实推送
export DINGTALK_WEBHOOK_URL="..."
export DINGTALK_SECRET="..."
.venv/bin/python -m dailybot --edition evening

# forwarder 转发：真实推送
.venv/bin/python -m dailybot.telegram_reporter

# 测试
.venv/bin/python -m pytest tests/ -q
```

## 项目结构

```
dailybot/
├── rss_collector.py       # RSS 抓取（串行、窗口过滤、单源容错）
├── rss_briefing.py        # 日报 Markdown 排版（纯函数）
├── rss_reminders.py       # 提醒规则匹配（daily/weekly × 北京时间）
├── telegram_channel.py    # Telegram 公开页 HTML 解析
├── telegram_formatter.py  # Telegram 消息 → 钉钉 Markdown（长文拆段）
├── telegram_models.py     # ChannelPost 数据模型
├── telegram_state.py      # 原子状态读写（防重）
├── telegram_reporter.py   # Telegram 转发入口
├── dingtalk.py            # 统一推送层（加签、发送、错误处理）
├── config.py              # 统一配置读取（兼容新旧变量名）
├── __main__.py            # 日报入口
└── __init__.py

tests/                     # pytest，43 个用例
deploy/systemd/            # VPS 定时器
```

## 行为说明

### dailybot 日报

- **时间窗口**：早报取最近 13 小时、晚报取最近 11 小时，合起来覆盖全天，重叠约 1 小时
- **无状态**：不记录已推送条目，跨推送去重仅靠时间窗口
- **条数上限**：每源最多 10 条，单次推送最多 15 条，超出在尾注标注
- **长度保护**：消息体超 12000 字符时砍最旧的条目，提醒与尾注永不截断

### forwarder 转发

- **首跑行为**：只记录最新消息 ID 建基线，**不补发历史**
- **去重**：`state.json` 原子写入，只发 ID 更大的新消息
- **长消息**：超 15000 字符按行边界拆段，每段带序号和原文链接
- **媒体消息**：不下载图片/视频，显示 `[媒体消息]` + 原文链接
- **失败语义**：任一分段失败不推进游标，下次重试

## 卸载

```bash
sudo systemctl stop dailybot-*.timer
sudo systemctl disable dailybot-*.timer
sudo rm /etc/systemd/system/dailybot-*
sudo systemctl daemon-reload
rm -rf /opt/dailybot
```

设计与决策记录见 `openspec/changes/ai-news-dingtalk-daily-bot/`。
