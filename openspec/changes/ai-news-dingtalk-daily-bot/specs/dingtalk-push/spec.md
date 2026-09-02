## Purpose

通过钉钉群自定义机器人 webhook 把 Markdown 简报安全地推送到指定群聊，并对鉴权与失败做显式处理。

## ADDED Requirements

### Requirement: webhook 推送

系统 SHALL 通过钉钉自定义机器人的 webhook URL 发送 `markdown` 类型消息。webhook URL（含 access_token）MUST 从环境变量 / CI Secrets 读取，MUST NOT 硬编码或提交到仓库。

#### Scenario: 成功推送

- **WHEN** webhook URL 有效且消息体合法
- **THEN** 系统发送 markdown 消息且钉钉返回 errcode 为 0，流程报告成功

#### Scenario: 缺少 webhook 配置

- **WHEN** 环境变量中未配置 webhook URL
- **THEN** 系统以明确的错误信息失败退出，且 CI 任务显示失败

### Requirement: 加签鉴权支持

系统 SHALL 支持钉钉机器人的"加签"安全设置：当配置了加签 secret 时，请求 MUST 附带正确的 `timestamp` 与 `sign` 参数。加签 secret MUST 从环境变量 / CI Secrets 读取。

#### Scenario: 配置加签时请求带签名

- **WHEN** 配置了加签 secret
- **THEN** 发送请求的 URL 中包含基于该 secret 计算的合法 timestamp 与 sign 参数

### Requirement: 推送失败显式可见

系统 SHALL 把推送失败（网络错误、HTTP 非 2xx、钉钉返回 errcode 非 0）视为任务失败，MUST 以非零退出码或 CI 失败状态显式暴露，MUST NOT 静默吞掉。

#### Scenario: 钉钉返回业务错误

- **WHEN** 钉钉返回 errcode 非 0（如签名错误、关键字拦截）
- **THEN** 系统输出钉钉返回的错误码与错误信息，并以失败状态结束

#### Scenario: 网络层失败

- **WHEN** webhook 请求发生网络超时或连接错误
- **THEN** 系统输出失败原因并以失败状态结束
