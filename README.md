# AI 行业资讯钉钉自动化日报系统

每天北京时间 **09:00（早报）** 与 **20:00（晚报）**，自动抓取配置的 RSS 源，把行业资讯按分组排版成 Markdown 简报，推送到钉钉群机器人。忠实聚合：每条资讯只有标题 + 原文链接，感兴趣就点进去看。

## 快速开始（部署）

### 1. 创建钉钉群机器人

群设置 → 智能群助手 → 添加机器人 → **自定义机器人**：

- 安全设置选 **加签**，复制 `SEC...` 开头的 secret
- 复制 webhook 地址（`https://oapi.dingtalk.com/robot/send?access_token=...`）

### 2. 推送代码到 GitHub

```bash
git init && git add -A && git commit -m "init: ai daily report bot"
git remote add origin git@github.com:<you>/DailyReportBot.git
git push -u origin main
```

### 3. 配置 Secrets

仓库页面 → Settings → Secrets and variables → Actions → New repository secret：

| Name | 必填 | 说明 |
|---|---|---|
| `DINGTALK_WEBHOOK_URL` | ✅ | 钉钉机器人的 webhook 地址 |
| `DINGTALK_SECRET` | 推荐 | 加签的 `SEC...`（机器人开启加签时必填） |

### 4. 验证

- **手动试跑**：Actions → AI Daily Report → Run workflow → 选 morning/evening
- **自动触发**：每天 UTC 01:00 / 12:00（北京 09:00 / 20:00），GitHub cron 可能延迟数分钟到数十分钟，属正常现象

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

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 只打印 markdown，不推送（调试排版用）
.venv/bin/python -m dailybot --edition morning --dry-run

# 真实推送（需要环境变量）
export DINGTALK_WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=..."
export DINGTALK_SECRET="SEC..."   # 可选
.venv/bin/python -m dailybot --edition evening

# 测试
.venv/bin/python -m pytest tests/ -q
```

### CLI 参数

| 参数 | 说明 |
|---|---|
| `--edition morning\|evening` | 推送类型，决定标题与默认窗口 |
| `--since-hours N` | 覆盖默认窗口（早报 13h / 晚报 11h） |
| `--feeds PATH` | RSS 配置路径（默认 `./feeds.yaml`） |
| `--reminders PATH` | 提醒配置路径（默认 `./reminders.yaml`） |
| `--dry-run` | 只打印不推送 |

## 行为说明

- **时间窗口**：早报取最近 13 小时、晚报取最近 11 小时内发布的条目，合起来覆盖全天，重叠约 1 小时（宁可偶尔重复，不漏资讯）。
- **无状态**：不记录已推送条目，跨推送去重仅靠时间窗口。
- **条数上限**：每源最多 10 条，单次推送最多 15 条，超出在尾注标注。
- **长度保护**：消息体超 12000 字符时砍最旧的条目，提醒与尾注永不截断。
- **失败语义**：某源挂了 → 简标注 `⚠️`，其余照常；推送失败 → Action 标红可见。

## 项目结构

```
dailybot/
├── collector.py    # RSS 抓取（串行、窗口过滤、单源容错）
├── reminders.py    # 提醒规则匹配（daily/weekly × 北京时间）
├── briefing.py     # 钉钉 Markdown 排版（纯函数）
├── dingtalk.py     # webhook 推送（可选加签）
└── __main__.py     # CLI 组装
tests/              # pytest，27 个用例
.github/workflows/daily-report.yml
feeds.yaml / reminders.yaml
```

设计与决策记录见 `openspec/changes/ai-news-dingtalk-daily-bot/`。
