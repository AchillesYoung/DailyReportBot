# Proposal: AI 行业资讯钉钉自动化日报系统

## Why

团队需要每天低成本地对齐 AI 行业动态：人工刷资讯源费时费力，且容易遗漏。通过 RSS 聚合 + 钉钉群机器人定时推送，可以让团队每天早晚各收到一份排版清晰的资讯简报，零人工干预。同时把团队的高频固定事项（站会、周报等）随日报一起推送，减少遗忘。

## What Changes

- 新增 RSS 资讯抓取能力：按分组配置多个 RSS 订阅源，串行抓取，按时间窗口过滤新条目，单源失败容忍（降级不中断）。
- 新增提醒事项能力：从本地配置读取固定文案提醒，按日程规则（每天 / 每周几）随推送附带；架构上预留"提醒来源"抽象，后续可扩展 Notion 等外部来源（本期仅实现配置来源）。
- 新增 Markdown 简报排版能力：把资讯（按源分组）+ 提醒 + 尾注元信息渲染为钉钉机器人支持的 Markdown 消息。
- 新增钉钉推送能力：通过群机器人 webhook 发送 Markdown 消息，失败时让任务显式失败可见。
- 新增定时编排：GitHub Actions 每日两推（北京时间 09:00 与 20:00），接受 GitHub cron 的延迟漂移。

明确不做（Non-goals）：
- 不引入 LLM 摘要/点评——系统定位为"忠实的信息聚合器"，每条资讯只带标题 + 原文链接。
- 不做跨推送的持久化去重状态——纯时间窗口过滤，接受偶尔重复。
- 不做并发抓取（源数量少，串行足够）。
- 本期不接 Notion API（仅预留抽象）。
- 不做 Web UI / 管理后台，配置即代码（YAML 提交仓库）。

## Capabilities

### New Capabilities

- `rss-feed-collection`: 按分组配置 RSS 源，串行抓取并按时间窗口过滤条目；单源失败时降级处理并在简报中标注。
- `reminder-delivery`: 从配置读取固定文案提醒，按日程规则（每日 / 指定星期几）决定是否随推送展示；来源可扩展。
- `briefing-composition`: 将资讯分组列表、提醒列表、元信息（源数量、条目数、送达时间）渲染为钉钉 Markdown 格式的简报文本。
- `dingtalk-push`: 通过钉钉群机器人 webhook 推送 Markdown 消息，处理签名鉴权与失败上报。
- `scheduled-orchestration`: GitHub Actions 定时工作流，每日两次（北京 09:00 / 20:00）触发抓取-排版-推送全流程，两次推送使用不同的时间窗口参数。

### Modified Capabilities

（无——本仓库此前无任何 spec。）

## Impact

- **新增代码**: Python 包（抓取 / 提醒 / 排版 / 推送四个模块）+ CLI 入口；`feeds.yaml` / `reminders.yaml` 配置文件；GitHub Actions workflow。
- **依赖**: `feedparser`（RSS 解析）、`requests`（webhook）、`PyYAML`（配置）。无 LLM 依赖。
- **Secrets**: `DINGTALK_WEBHOOK_URL`（及可选的加签 secret）存 GitHub Secrets。
- **外部系统**: 钉钉群机器人（自定义机器人，Markdown 消息类型）；GitHub Actions（cron 调度）。
- **无破坏性变更**：仓库当前无既有代码。
