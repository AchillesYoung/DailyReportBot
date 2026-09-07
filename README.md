# AI 行业资讯钉钉自动化日报系统

RSS + Telegram 两个数据源，统一推送钉钉群：

| 入口 | 频率 | 数据源 |
|---|---|---|
| `python -m dailybot` | 每天 2 次（北京 09:00 AIHOT 日报 / 10:00 综合早报 / 20:00 晚报） | RSS 资讯聚合 |
| `python -m dailybot.telegram_reporter` | 每小时 1 次 | Telegram `@aiwizz` 频道 |

## 快速开始（VPS 一键部署）

```bash
# 首次部署
git clone https://github.com/AchillesYoung/DailyReportBot.git /opt/dailybot
bash /opt/dailybot/deploy/setup.sh

# 后续更新
cd /opt/dailybot
bash deploy/setup.sh
```

`setup.sh` 自动完成：拉代码 → 建虚拟环境 → 装依赖 → 部署 systemd → 启用全部定时器。

## 钉钉群机器人配置

群设置 → 智能群助手 → 添加机器人 → **自定义机器人**：

- 安全设置选 **加签**，复制 `SEC...` 开头的 secret
- 复制 webhook 地址（`https://oapi.dingtalk.com/robot/send?access_token=...`）
- 填入 `config/dingtalk.env`

## 配置

所有配置文件在 `config/` 目录下：

### `config/dingtalk.env` — 钉钉凭证

```
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=...
DINGTALK_SECRET=SECxxxxxxxxxxxxxxxx
```

| 变量 | 必填 | 说明 |
|---|---|---|
| `DINGTALK_WEBHOOK_URL` | ✅ | 钉钉机器人 webhook 地址 |
| `DINGTALK_SECRET` | 推荐 | 加签的 `SEC...` |
| `TELEGRAM_CHANNEL` | 可选 | 默认 `aiwizz` |

### `config/feeds.yaml` — RSS 源

```yaml
groups:
  - name: 中文社区
    feeds:
      - name: AIHOT 精选
        url: https://aihot.virxact.com/feed.xml?aihot_actor=...
        show_summary: true    # 展示摘要 + 阅读全文链接
      - name: 量子位
        url: https://www.qbitai.com/feed
```

- 按分组组织，分组名会出现在简报标题层级
- `show_summary: true` 启用摘要展示（仅对有结构化 description 的源有效）
- 单个源抓取失败不影响其他源，会在简报中标注 `⚠️ xx 抓取失败`
- 中文媒体很多没有 RSS，可用 [RSSHub](https://docs.rsshub.app/) 桥接

### `config/reminders.yaml` — 提醒事项（暂时禁用）

```yaml
reminders:
  - text: "10:00 产品站会"
    schedule: daily
  - text: "记得提交本周周报"
    schedule: weekly
    days: [fri]
    editions: [morning]
```

## CLI 参数

```bash
python -m dailybot --edition morning [选项]
```

| 参数 | 说明 |
|---|---|
| `--edition {morning,evening}` | 必填，早报或晚报 |
| `--since-hours N` | 覆盖默认时间窗口（早报 13h / 晚报 11h） |
| `--group NAME` | 只推送指定分组（可多次指定），缺省推送全部 |
| `--feeds PATH` | RSS 源配置文件路径，默认 `config/feeds.yaml` |
| `--reminders PATH` | 提醒规则路径，默认 `config/reminders.yaml` |
| `--dry-run` | 只打印 markdown 不推送 |

示例：

```bash
# 只推送 AIHOT 日报分组
python -m dailybot --edition morning --group "AIHOT 日报" --dry-run

# 72 小时窗口，真实推送
python -m dailybot --edition morning --since-hours 72
```

## 定时器

| Timer | 触发时间（北京时间） | 服务 |
|---|---|---|
| `dailybot-aihot.timer` | 每天 09:00 | AIHOT 日报（`--group "AIHOT 日报"`） |
| `dailybot-morning.timer` | 每天 10:00 | 综合早报 |
| `dailybot-evening.timer` | 每天 20:00 | 综合晚报 |
| `dailybot-telegram.timer` | 每小时整点 | Telegram 频道转发 |

## 项目结构

```
DailyReportBot/
├── config/
│   ├── dingtalk.env         # 钉钉凭证
│   ├── feeds.yaml           # RSS 源配置
│   └── reminders.yaml       # 提醒规则
├── dailybot/
│   ├── __main__.py          # RSS 日报 CLI 入口
│   ├── collector.py         # RSS 抓取（串行、窗口过滤、单源容错）
│   ├── briefing.py          # 日报 Markdown 排版
│   ├── reminders.py         # 提醒规则匹配（daily/weekly × 北京时间）
│   ├── dingtalk.py          # 统一钉钉推送层（加签、发送）
│   ├── config.py            # 环境变量读取
│   ├── telegram_reporter.py # Telegram 转发入口
│   ├── telegram_channel.py  # Telegram 公开页 HTML 解析
│   ├── telegram_formatter.py# Telegram → 钉钉 Markdown
│   ├── telegram_models.py   # ChannelPost 数据模型
│   └── telegram_state.py    # 原子状态读写（防重）
├── tests/                   # 46 个测试用例
├── deploy/
│   ├── setup.sh             # 一键部署脚本
│   ├── dailybot.env.example # 环境变量样例
│   └── systemd/             # 服务和定时器定义
└── requirements.txt
```

## 本地开发

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# dry-run 测试
.venv/bin/python -m dailybot --edition morning --dry-run

# 运行测试
.venv/bin/python -m pytest tests/ -q
```

## 行为说明

### RSS 日报

- **时间窗口**：早报 13 小时、晚报 11 小时，合起来覆盖全天
- **无状态**：不记录已推送条目，跨推送去重仅靠时间窗口
- **条数上限**：每源最多 10 条，单次推送最多 15 条
- **长度保护**：消息体超 12000 字符时砍最旧的条目

### Telegram 转发

- **首跑**：只记录最新消息 ID 建基线，不补发历史
- **去重**：`state.json` 原子写入，只发 ID 更大的新消息
- **长消息**：超 15000 字符按行边界拆段

## 卸载

```bash
sudo systemctl stop dailybot-*.timer
sudo systemctl disable dailybot-*.timer
sudo rm /etc/systemd/system/dailybot-*
sudo systemctl daemon-reload
rm -rf /opt/dailybot
```
