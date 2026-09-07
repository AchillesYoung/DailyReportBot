# DailyReportBot 交接文档

## 一句话概括

两个数据源（RSS + Telegram），统一推送钉钉的自动化日报系统。

## 数据流

```
RSS 资源 ──→ collector.py ──→ briefing.py ──→ dingtalk.py ──→ 钉钉
               ↑                  ↓
           5 个源             Markdown 排版
           容错抓取           截断 ≤ 20000 字符

Telegram @aiwizz ──→ telegram_channel.py ──→ telegram_formatter.py ──→ dingtalk.py ──→ 钉钉
                      ↑ HTML 解析              ↑ 拆段 + 链接缩短          ↑ 加签推送
                      ↓                        ↓
                   telegram_models.py       telegram_state.py
                   (ChannelPost)            (原子读写防重)
```

## 两个服务

| 服务 | 入口 | 频率 | 说明 |
|---|---|---|---|
| RSS 日报 | `python -m dailybot` | 每天 09:00 / 20:00 | 抓 RSS → 排版 → 推钉钉 |
| Telegram 转发 | `python -m dailybot.telegram_reporter` | 每小时 | 监听 @aiwizz → 推钉钉 |

## 目录结构

```
dailybot/
├── __main__.py            # RSS 日报入口
├── collector.py           # RSS 抓取（串行、窗口过滤、单源容错）
├── briefing.py            # 日报 Markdown 排版（纯函数）
├── reminders.py           # 提醒规则匹配（daily/weekly × 北京时间）
├── telegram_reporter.py   # Telegram 转发入口
├── telegram_channel.py    # Telegram 公开页 HTML 解析
├── telegram_formatter.py  # Telegram 消息 → 钉钉 Markdown
├── telegram_models.py     # ChannelPost 数据模型
├── telegram_state.py      # 原子状态读写（防重）
├── dingtalk.py            # 统一推送层（加签、发送、错误处理）
├── config.py              # 统一配置读取（兼容新旧变量名）
tests/                     # pytest，43 个用例
deploy/
├── dailybot.env.example   # 环境变量样例
└── systemd/               # 6 个 unit（3 服务 × 2 timer）
```

## 环境变量

```bash
# 必填
DINGTALK_SECRET=SEC...        # 加签密钥
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=...

# 可选（有默认值）
TELEGRAM_CHANNEL=aiwizz       # Telegram 频道名
FORWARDER_STATE_FILE=./state.json
FORWARDER_REPORT_TITLE=Wizz AI 日报
MORNING_REPORT_CRON=0 9 * * *
EVENING_REPORT_CRON=0 20 * * *
```

## 本地开发

```bash
# 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# 复制环境变量
cp deploy/dailybot.env.example .env
# 编辑 .env 填入真实值

# 测试
pytest -q                     # 43 个用例
python -m dailybot --dry-run  # 真实抓取，不推送

# 单条资讯调试
python -m dailybot --since-hours 1 --dry-run
```

## 部署（VPS）

```bash
# 复制项目
scp -r . root@VPS:/opt/dailybot

# 安装依赖
cd /opt/dailybot && python -m venv .venv && pip install -e .

# 配置环境变量
sudo cp deploy/dailybot.env.example /etc/dailybot.env
sudo vim /etc/dailybot.env  # 填入真实密钥

# 启用定时器
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dailybot-morning.timer
sudo systemctl enable --now dailybot-evening.timer
sudo systemctl enable --now dailybot-telegram.timer

# 查看日志
journalctl -u dailybot-morning -f
```

## 关键设计决策

### 为什么串行抓取 RSS？

代码库里有 `asyncio` + `aiohttp` 的异步版本，但最终用串行。原因：

- RSS 源在响应头带 `X-RateLimit-*`，异步并发触发 429
- 5 个源串行 3-5 秒可接受
- 代码简单，单源容错好做

### 为什么不用官方 Telegram Bot API？

`@aiwizz` 是公开频道，网页直接可读。Bot API 需要频道管理员权限，这里是读者视角。

### 截断策略

钉钉有 20000 字符硬限制。`briefing.py` 的截断逻辑是**每砍一条就重新组装判断**，不是只用旧 `text` 长度判断（旧逻辑会导致砍光所有条目）。

### 分页标记

`formatter.py` 分页标记长度用**两遍法**估算：先按最坏情况（每条都是长标题 + 1 链接）算一次，分页后再用实际标记长度校验，超出则重新分页。

### 状态防重

`telegram_state.py` 用 **tmp + rename** 原子写入，防止 cron 并发写坏 JSON。每次只保留最近 1 条 `message_id`。

## 常见问题

### Q: 某个 RSS 源挂了，会影响整体吗？

不会。`collector.py` 逐源 try/except，挂掉的源跳过，其余正常。日志会输出 `⚠ 部分源异常`。

### Q: Telegram 页面改版了怎么办？

改 `telegram_channel.py` 的 `_HTML_PARSER`（正则提取）。当前支持格式：
- `<div class="tgme_widget_message_text">` 内的 `<a>`、`<br>`、`<br/>`
- `<time>` 的 `datetime` 属性

### Q: 要加新的 RSS 源？

编辑 `config.py` 的 `RSS_SOURCES` 字典：
```python
RSS_SOURCES = {
    "新源名": "https://example.com/rss",
    ...
}
```

### Q: 要推送到企业微信/飞书？

实现一个类似 `dingtalk.py` 的推送函数，然后改 `__main__.py` 和 `telegram_reporter.py` 的调用即可。

## 最近重构（2026-09-07）

本次重构修复了 2 个真 bug + 1 个防御性改进：

1. **briefing 截断 bug**：循环里不重新组装，超长时砍光所有条目
2. **collector socket 全局副作用**：`socket.setdefaulttimeout()` 影响全局，改用 requests 显式超时
3. **formatter 分页隐性假设**：9999 宽度假设，改为两遍法校验

同时做了 SOLID 重构：Config 收敛、DingTalkClient 类化、删除兼容层、结构扁平化。
