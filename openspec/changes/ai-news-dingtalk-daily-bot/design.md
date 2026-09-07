# Design: AI 行业资讯钉钉自动化日报系统

> **注**: 定时调度已从 GitHub Actions 迁移到 VPS systemd timer（见 `deploy/systemd/`）。
> 早报 09:00 / 晚报 20:00 北京时间，Telegram 转发每小时。

## Context

全新仓库，无既有代码。约束来自 proposal 与 specs：

- 忠实聚合器：无 LLM 依赖，每条资讯仅标题 + 链接。
- 无状态：VPS systemd timer 定时触发，跨推送去重仅依赖时间窗口。
- 单源失败容忍，推送失败必须显式可见。
- 每日两推（北京 09:00 / 20:00），窗口分别约 13h / 11h，合计覆盖 24h。
- 钉钉 Markdown 是受限子集（不支持表格；链接/加粗/标题/列表/分割线可用），且有消息长度上限。

## Goals / Non-Goals

**Goals:**

- 四个单一职责模块（抓取 / 提醒 / 排版 / 推送）+ 一个薄 CLI 入口，模块间通过纯数据结构（dataclass/dict）通信，无框架耦合。
- 配置即代码：`feeds.yaml`、`reminders.yaml` 提交仓库；机密仅走环境变量。
- 本地可直接 `python -m dailybot` 跑通，便于调试与手动验证，无需依赖 CI。

**Non-Goals:**

- 不设计插件系统/抽象基类继承树——"提醒来源"只约定一个函数签名（协议），不引入框架式抽象。
- 不处理 RSS 的全文抓取、正文提取、反爬对抗；只读 feed 条目元数据。
- 不做多机器人/多群路由（单 webhook）；后续如需多群再扩展。
- 不做钉钉互动（回调、@人、卡片按钮）。

## Decisions

### D1: 技术栈——Python + feedparser + requests + PyYAML

- **feedparser**：RSS/Atom 解析事实标准，容错性强（对不规范 XML 容忍），自带时间解析（`published_parsed`）。
- **requests**：webhook POST，无需 httpx/异步。
- **标准库 argparse**：CLI 参数（`--edition morning|evening`、`--since-hours`、`--dry-run`），不引入 click/typer，保持零多余依赖。
- 备选：直接 `urllib` + `xml.etree` 手写解析 → 拒绝，feedparser 对脏 feed 的容错不值这个省。

### D2: 模块结构与数据流

```
feeds.yaml ──► collector.fetch() ──► CollectResult
                                        │  ├─ groups: [{group, feeds:[{source, entries|error}]}]
reminders.yaml ──► reminders.load() ──► │  └─ entries: [{title, link, published}]
                                        ▼
                                   briefing.render(edition) ──► markdown text
                                        ▼
                                   dingtalk.send(webhook, secret) ──► exit code
```

- `collector.py`：`fetch_feeds(config, since_hours) -> CollectResult`。串行循环，每源 `try/except`，失败记入 `FeedResult.error`。条目上限截断在此完成（排序后切片）。
- `reminders.py`：`load_reminders(path) -> list[ReminderRule]`；`due_today(rules, now, edition) -> list[str]`。来源抽象就是这一个函数签名：`due_today(rules, now, edition)`——未来 Notion 来源只要提供同签名函数即可，CLI 注入点替换。
- `briefing.py`：`render(result, reminders, edition, now) -> str`。纯函数，无副作用，便于快照测试。
- `dingtalk.py`：`send_markdown(webhook_url, secret|None, title, text)`，加签用 `hmac-sha256` + base64 + urlencode（钉钉官方算法）。
- `__main__.py`：组装以上，处理 `--dry-run`（只打印 markdown 不推送）。

### D3: 时间处理——统一 UTC 内部流转，边界处转换

- 内部一律用带时区的 `datetime`（UTC）比较窗口；`published_parsed`（UTC struct_time）→ UTC datetime。
- 仅在两处涉及北京时间：`reminders` 判定"今天星期几"、标题渲染日期。时区库用 `pytz`（feedparser 的传递依赖，兼容 Python 3.9；未来最低版本升到 3.9+ 稳定后可切换标准库 `zoneinfo`），不引入 `python-dateutil`。
- 备选：第三方 `python-dateutil` → 拒绝，pytz 已够用且零新增依赖成本。

### D4: 窗口语义——"现在往回 N 小时"，与推送时刻解耦

- 早报 13h、晚报 11h，互补覆盖 24h 且允许约 1h 重叠（容忍重复，符合既定决策）。窗口 = `now - Nh <= published <= now`。
- 无 published 的条目：**视为窗口内（保留）**——宁可偶发重复，不漏掉无时间戳源的内容；spec 中对应场景按此实现。
- 备选：解析失败即丢弃 → 拒绝，漏资讯比重复更损害日报价值。

### D5: 消息长度控制——条目级预算截断

- 钉钉 markdown 消息 text 上限约 20000 字节，但实际可读性阈值远低。双保险：
  1. **总量上限**：`max_total_entries`（默认 15），全局按时间倒序保留。
  2. **字节预算**：渲染后超阈值（默认 12000 字符）时从新到旧的反方向（即砍掉最旧的）逐条移除并在末尾标注"还有 N 条未展示"。提醒与尾注不参与截断。
- 备选：拆多条消息发送 → 拒绝（本期）。多条消息在群里刷屏，违背"美观可读"目标；上限+截断足够。

### D6: 配置格式

`feeds.yaml`：

```yaml
groups:
  - name: 海外媒体
    feeds:
      - name: OpenAI Blog
        url: https://openai.com/blog/rss.xml
  - name: 中文社区
    feeds:
      - name: 机器之心
        url: https://www.jiqizhixin.com/rss
```

`reminders.yaml`：

```yaml
reminders:
  - text: "10:00 产品站会"
    schedule: daily            # daily | weekly
  - text: "提交周报"
    schedule: weekly
    days: [fri]                # mon..sun，北京时间
    editions: [morning]        # 可选；缺省=早晚都带
```

### D7: GitHub Actions——两个 cron 一个 workflow

- 单 workflow 两 cron：`0 1 * * *`（UTC 01:00 = 北京 09:00）、`0 12 * * *`（UTC 12:00 = 北京 20:00）。运行时用事件/cron 表达式匹配决定 `--edition`，或简单起见：`workflow_dispatch` 输入 + schedule 各自调用 `python -m dailybot --edition morning|evening`（用 `github.event.schedule` 区分）。
- `pip install -r requirements.txt`，版本全部钉死（`==`）。
- Secrets：`DINGTALK_WEBHOOK_URL`、`DINGTALK_SECRET`（可选）。

### D8: 失败语义

| 失败点 | 行为 |
|---|---|
| 单源抓取失败 | 记录 error，简报标注，继续 |
| 全部源失败 | 仍推送（含"暂无新资讯"+失败清单），exit 0 |
| 配置文件缺失/非法 | 明确报错，exit 非 0 |
| webhook 未配置 | 明确报错，exit 非 0 |
| 推送失败 | 输出钉钉错误码，exit 非 0（Action 标红） |

## Risks / Trade-offs

- [GitHub cron 延迟可能达数十分钟，极端时被跳过] → 接受（已确认的决策）；`workflow_dispatch` 兜底补发。
- [部分中文 AI 源无 RSS 或需 RSSHub 桥接，feed 质量参差] → feeds.yaml 可随时增删；feedparser 容错；失败源可见标注便于发现坏源。
- [无状态时间窗口在 Action 延迟较大时可能漏掉窗口边缘条目] → 窗口留 1h 重叠冗余，宁重复勿漏。
- [feed 时间戳时区/格式脏乱] → feedparser 统一解析为 UTC struct_time；无时间戳条目按 D4 保守保留。
- [钉钉消息长度上限触发截断，重要资讯被砍] → 全局上限 15 条 + 按时间倒序保留最新；尾注披露截断数量。
- [webhook URL 泄露可被任意推送] → 仅存 Secrets；不在日志打印；建议机器人开启"加签"。

## Migration Plan

全新项目，无迁移。上线步骤：

1. 合并代码与 workflow → 2. 配置 Secrets → 3. 手动 `workflow_dispatch` 验证早报/晚报各一次 → 4. 等次日 cron 自动运行确认。

回滚：禁用 workflow 或在钉钉群移除机器人即可，无副作用。

## Open Questions

- 具体的 RSS 源清单（哪些海外源、是否引入 RSSHub）——配置层面问题，不影响架构，实现任务中建好 feeds.yaml 骨架后由用户补充。
- 单源/总量上限的默认值（10/15）是否顺手——运行几天后可调，纯配置改动。
