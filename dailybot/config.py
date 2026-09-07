"""共享配置：环境变量读取、凭证解析。"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """配置缺失或非法。"""


@dataclass(frozen=True)
class DingTalkCredentials:
    """钉钉推送凭证。"""

    webhook: str
    secret: str


def get_dingtalk_credentials(env: dict | None = None) -> DingTalkCredentials:
    """从环境变量读取钉钉凭证，兼容新旧变量名。

    - DINGTALK_WEBHOOK_URL（新）优先
    - 回退到 DINGTALK_WEBHOOK（旧）
    - DINGTALK_SECRET 始终从同一变量读取
    """
    env = env or os.environ
    webhook = (
        env.get("DINGTALK_WEBHOOK_URL") or env.get("DINGTALK_WEBHOOK", "")
    ).strip()
    if not webhook:
        raise ConfigError(
            "未配置 DINGTALK_WEBHOOK_URL 或 DINGTALK_WEBHOOK 环境变量"
        )
    secret = env.get("DINGTALK_SECRET", "").strip()
    return DingTalkCredentials(webhook=webhook, secret=secret)
