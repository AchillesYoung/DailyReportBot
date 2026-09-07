"""Telegram 转发应用入口：单次运行，抓取 → 去重 → 推送。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

import requests

from ..shared import dingtalk
from .channel import parse_posts
from .formatter import build_markdown_parts
from .models import ChannelPost
from .state import load_last_id, save_last_id

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    webhook: str
    secret: str = ""
    channel: str = "aiwizz"
    state_file: Path = Path("state.json")
    request_timeout: int = 15

    @property
    def preview_url(self) -> str:
        return f"https://t.me/s/{self.channel.lstrip('@')}"

    @classmethod
    def from_env(cls):
        # 兼容旧变量名 DINGTALK_WEBHOOK，优先用新名 DINGTALK_WEBHOOK_URL
        webhook = (
            os.environ.get("DINGTALK_WEBHOOK_URL")
            or os.environ.get("DINGTALK_WEBHOOK", "")
        ).strip()
        if not webhook:
            raise ValueError(
                "DINGTALK_WEBHOOK_URL or DINGTALK_WEBHOOK is required"
            )
        return cls(
            webhook=webhook,
            secret=os.environ.get("DINGTALK_SECRET", "").strip(),
            channel=os.environ.get("TELEGRAM_CHANNEL", "aiwizz").strip().lstrip("@"),
            state_file=Path(os.environ.get("FORWARDER_STATE_FILE", "state.json")),
        )


@dataclass(frozen=True)
class RunResult:
    sent_count: int
    baseline_initialized: bool = False


def fetch_public_posts(config: Config, session=None) -> List[ChannelPost]:
    http = session or requests.Session()
    response = http.get(
        config.preview_url,
        headers={"User-Agent": "dailybot-forwarder/1.0"},
        timeout=config.request_timeout,
    )
    response.raise_for_status()
    return parse_posts(response.text, config.channel)


def run_once(
    config: Config,
    fetcher: Callable[[], List[ChannelPost]],
    sender: Callable[[str, str, str], None],
) -> RunResult:
    posts = sorted(fetcher(), key=lambda item: item.id)
    last_id = load_last_id(config.state_file)

    if last_id is None:
        if not posts:
            return RunResult(sent_count=0)
        save_last_id(config.state_file, posts[-1].id)
        return RunResult(sent_count=0, baseline_initialized=True)

    sent_count = 0
    for item in posts:
        if item.id <= last_id:
            continue
        parts = build_markdown_parts(item)
        for part in parts:
            sender(config.webhook, f"Wizz AI 日报 #{item.id}", part, config.secret)
        save_last_id(config.state_file, item.id)
        last_id = item.id
        sent_count += 1

    return RunResult(sent_count=sent_count)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        config = Config.from_env()
        result = run_once(
            config,
            fetcher=lambda: fetch_public_posts(config),
            sender=dingtalk.send_markdown,
        )
    except Exception as error:
        LOGGER.error("Forwarding run failed: %s", error)
        return 1

    if result.baseline_initialized:
        LOGGER.info("Baseline initialized; historical posts were not sent")
    else:
        LOGGER.info("Forwarding run completed; sent %d new post(s)", result.sent_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
