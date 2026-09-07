"""Telegram 公开频道消息数据模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelPost:
    """一条 Telegram 频道消息。"""

    id: int
    text: str
    url: str
