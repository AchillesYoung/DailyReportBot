# Tasks: AI 行业资讯钉钉自动化日报系统

## 1. 项目骨架

- [ ] 1.1 创建 `requirements.txt`（feedparser、requests、PyYAML，版本钉死）与 `requirements-dev.txt`（pytest）
- [ ] 1.2 创建包结构 `dailybot/`（`__init__.py`、`__main__.py`、`collector.py`、`reminders.py`、`briefing.py`、`dingtalk.py`）与 `tests/`
- [ ] 1.3 创建 `feeds.yaml`（分组骨架 + 2-3 个海外源示例，待用户补充）与 `reminders.yaml`（示例规则）

## 2. RSS 抓取（spec: rss-feed-collection）

- [ ] 2.1 `collector.py`：加载 feeds.yaml，校验必填字段，非法源跳过并告警
- [ ] 2.2 `collector.py`：串行抓取 + feedparser 解析，时间窗口过滤（UTC 比较；无时间戳条目保留）
- [ ] 2.3 `collector.py`：单源 try/except 容错，错误记录到 FeedResult.error；每源条数上限截断
- [ ] 2.4 测试：窗口过滤、无时间戳保留、单源失败不中断、超限截断

## 3. 提醒（spec: reminder-delivery）

- [ ] 3.1 `reminders.py`：加载 reminders.yaml；`due_today(rules, now, edition)` 实现 daily/weekly 规则（北京时间判定星期）
- [ ] 3.2 `reminders.py`：`editions` 过滤（缺省=早晚都带）；空列表合法返回
- [ ] 3.3 测试：daily/weekly 命中与未命中、edition 过滤、空列表

## 4. 简报排版（spec: briefing-composition）

- [ ] 4.1 `briefing.py`：按模板渲染标题（日期 + 早报/晚报标识）、分组资讯链接列表、提醒区块、尾注（源数/条数/送达时间）
- [ ] 4.2 `briefing.py`：失败源可见标注；"暂无新资讯"分支
- [ ] 4.3 `briefing.py`：总条数上限（默认 15）+ 字节预算截断（默认 12000 字符，标注被省略条数）；提醒与尾注不参与截断
- [ ] 4.4 测试：标准结构、无资讯、失败源标注、超长截断、仅使用钉钉 Markdown 子集（断言无表格/代码块语法）

## 5. 钉钉推送（spec: dingtalk-push）

- [ ] 5.1 `dingtalk.py`：`send_markdown()` 发送 markdown 消息，errcode 非 0 时输出错误并返回失败
- [ ] 5.2 `dingtalk.py`：可选加签（hmac-sha256 + base64 + urlencode，timestamp+sign）
- [ ] 5.3 webhook/secret 仅从环境变量读取；未配置时明确报错
- [ ] 5.4 测试：mock requests，覆盖成功、errcode 非 0、网络异常、加签参数存在性

## 6. CLI 入口

- [ ] 6.1 `__main__.py`：argparse（`--edition morning|evening`、`--since-hours` 覆盖、`--dry-run`、`--feeds`、`--reminders` 路径参数）；默认窗口 morning=13h / evening=11h
- [ ] 6.2 组装全流程；失败语义按 design D8 实现退出码
- [ ] 6.3 本地 `--dry-run` 验证：打印完整 markdown 不推送

## 7. 定时调度（VPS systemd timer）~~原 GitHub Actions~~

- [x] 7.1 `deploy/systemd/`：dailybot-morning.timer（09:00）、dailybot-evening.timer（20:00）、dailybot-telegram.timer（每小时）
- [x] 7.2 systemd service 配置：环境变量文件 `/etc/dailybot.env`、Python venv 路径
- [x] 7.3 README：VPS 部署说明（systemd timer 启用、环境变量配置、日志查看）

## 8. 验证与交付

- [ ] 8.1 全量测试通过（pytest）
- [ ] 8.2 用户补充真实 RSS 源清单到 feeds.yaml
- [ ] 8.3 用户配置 GitHub Secrets；`workflow_dispatch` 手动验证早报、晚报各一次，确认群内排版可读
- [ ] 8.4 `openspec validate ai-news-dingtalk-daily-bot --strict` 通过
