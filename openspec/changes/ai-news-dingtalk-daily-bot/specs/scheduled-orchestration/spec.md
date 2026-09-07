## Purpose

通过 VPS systemd timer 每日两次定时触发完整流程（抓取 → 组装 → 推送），以不同时段参数区分早报与晚报，并提供手动触发手段。

> **注**: 原设计为 GitHub Actions，已迁移到 VPS systemd timer（见 `deploy/systemd/`）。

## ADDED Requirements

### Requirement: 定时触发

系统 SHALL 通过 VPS systemd timer 每日触发两次：北京时间 09:00（早报）与北京时间 20:00（晚报）。VPS 系统时钟 MUST 设置为 Asia/Shanghai。

#### Scenario: 定时触发

- **WHEN** systemd timer 到达配置的时间
- **THEN** 对应的 service 被触发，并携带正确的推送类型参数（早报或晚报）

### Requirement: 时段参数化

两次推送 SHALL 使用不同的时间窗口参数：早报窗口 MUST 覆盖自前一日晚报以来的时段（约 13 小时），晚报窗口 MUST 覆盖自当日早报以来的时段（约 11 小时）；具体小时数 MUST 为可配置值。推送类型（早/晚）MUST 传入排版以区分标题。

#### Scenario: 早报窗口

- **WHEN** 早报运行
- **THEN** 抓取过滤使用早报窗口（默认 13 小时）并将推送类型标记为早报

#### Scenario: 晚报窗口

- **WHEN** 晚报运行
- **THEN** 抓取过滤使用晚报窗口（默认 11 小时）并将推送类型标记为晚报

### Requirement: 手动触发

系统 SHALL 支持 CLI 手动触发，且 MUST 允许手动选择推送类型（早报/晚报）以便调试与补发。

#### Scenario: 手动补发早报

- **WHEN** 用户在 VPS 上运行 `python -m dailybot --edition morning --dry-run`
- **THEN** 系统按早报参数执行完整流程并打印结果（dry-run 模式不推送）

### Requirement: 依赖与机密管理

系统 SHALL 从环境变量读取钉钉 webhook 配置。依赖 MUST 通过锁定的依赖清单安装（如 `requirements.txt`），保证可复现。

#### Scenario: 环境变量注入

- **WHEN** systemd service 运行
- **THEN** webhook URL 等机密从 `/etc/dailybot.env` 读取，代码不打印其值
