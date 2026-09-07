"""钉钉推送：兼容层，内部复用 shared.dingtalk。"""

from __future__ import annotations

import logging

from .shared.dingtalk import send_markdown as _send_markdown

logger = logging.getLogger(__name__)


def send_markdown(
    webhook_url: str,
    title: str,
    text: str,
    secret: str | None = None,
) -> None:
    """发送 markdown 消息到钉钉群机器人。

    任何失败（网络错误 / HTTP 非 2xx / errcode 非 0）都抛出 RuntimeError，
    由调用方决定退出码——推送失败必须显式可见。
    """
    _send_markdown(webhook_url, title, text, secret)

