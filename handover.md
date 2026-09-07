# DailyReportBot 交接文档

## 项目概况

AI 行业资讯钉钉自动化日报系统，两个入口：

- **RSS 日报**：抓取 RSS 源 → 排版 → 推送钉钉群（每天 3 次）
- **Telegram 转发**：抓取 @aiwizz 频道 → 推送钉钉群（每小时）

## 仓库

```
https://github.com/AchillesYoung/DailyReportBot.git
```

## VPS 部署

```bash
git clone https://github.com/AchillesYoung/DailyReportBot.git /opt/dailybot
bash /opt/dailybot/deploy/setup.sh
```

后续更新：`cd /opt/dailybot && bash deploy/setup.sh`

脚本自动：git pull → 装依赖 → 部署 systemd → 重启定时器。

## 定时器

| Timer | 北京时间 | UTC 时间 | 服务 |
|---|---|---|---|
| dailybot-aihot | 09:00 | 01:00 | AIHOT 日报 |
| dailybot-morning | 10:00 | 02:00 | 综合早报 |
| dailybot-evening | 20:00 | 12:00 | 综合晚报 |
| dailybot-telegram | 每小时 | 每小时 | Telegram 转发 |

VPS 是 UTC 时区，timer 文件里写的是 UTC 时间。

## 配置文件（都在 config/ 目录）

- `dingtalk.env` — 钉钉 webhook + secret
- `feeds.yaml` — RSS 源，按分组组织
- `reminders.yaml` — 提醒规则（当前已禁用）

## CLI 用法

```bash
# dry-run
python -m dailybot --edition morning --dry-run

# 只跑某个分组
python -m dailybot --edition morning --group "AIHOT 日报" --dry-run

# 真实推送（需要 config/dingtalk.env 配好）
python -m dailybot --edition evening
```

## feeds.yaml 结构

```yaml
groups:
  - name: 分组名
    feeds:
      - name: 源名
        url: https://...
        show_summary: true  # 可选，启用摘要提取
```

`show_summary` 目前只用于 AIHOT 源，提取 RSS description 的第一段摘要 + 原文链接。

## 关键设计决策

- **单源容错**：某个 RSS 源抓取失败不中断整体，只在简报中标注
- **无状态推送**：不记录已推送条目，靠时间窗口去重
- **截断保护**：消息超 12000 字符从最旧条目开始砍
- **`--group` 过滤**：timer 用 `--group "AIHOT 日报"` 让 AIHOT 单独 9 点推，综合 10 点推
- **`python-dotenv`**：代码自动从 `config/dingtalk.env` 加载凭证，VPS 上不用手动 export

## 代码结构

```
dailybot/
├── __main__.py          # CLI 入口
├── collector.py         # RSS 抓取 + 配置加载
├── briefing.py          # 日报 Markdown 排版
├── reminders.py         # 提醒规则（当前禁用）
├── dingtalk.py          # 钉钉推送（加签 + 发送）
├── config.py            # 环境变量读取
├── telegram_reporter.py # Telegram 转发入口
├── telegram_channel.py  # Telegram HTML 解析
├── telegram_formatter.py# Telegram → 钉钉 Markdown
├── telegram_models.py   # 数据模型
└── telegram_state.py    # 状态读写
```

## 测试

```bash
.venv/bin/python -m pytest tests/ -q   # 46 个用例
```

## 未完成事项

- `reminders.yaml` 提醒功能代码在但 `__main__.py` 中已禁用（传空列表）
- `_parse_summary()` 用正则解析 HTML，对非 AIHOT 格式的 RSS 可能不准
- `telegram_reporter.py` 和 `__main__.py` 两个入口缺测试
- `telegram_formatter._highlight_entities()` 有子串误匹配和加粗损坏两个已知 bug
