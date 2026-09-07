"""Telegram 转发应用入口：单次运行，抓取 → 去重 → 推送。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

from . import dingtalk
from .config import DingTalkCredentials, get_dingtalk_credentials
from .telegram_channel import parse_posts
from .telegram_formatter import build_markdown_parts
from .telegram_models import ChannelPost
from .telegram_state import load_last_id, save_last_id

LOGGER = logging.getLogger(__name__)


def preview_url(channel: str) -> str:
    """Telegram 频道公开预览页 URL。"""
    return f"https://t.me/s/{channel.lstrip('@')}"


@dataclass(frozen=True)
class ForwarderConfig:
    """转发配置值对象。"""

    webhook: str
    secret: str = ""
    channel: str = "aiwizz"
    state_file: Path = Path("state.json")
    request_timeout: int = 15
    report_title: str = "Wizz AI 日报"

    @property
    def preview_url(self) -> str:
        return preview_url(self.channel)


def load_forwarder_config(env: dict | None = None) -> ForwarderConfig:
    """从环境变量构建配置（职责与值对象分离）。"""
    env = env or os.environ
    creds = get_dingtalk_credentials(env)
    return ForwarderConfig(
        webhook=creds.webhook,
        secret=creds.secret,
        channel=env.get("TELEGRAM_CHANNEL", "aiwizz").strip().lstrip("@"),
        state_file=Path(env.get("FORWARDER_STATE_FILE", "state.json")),
        report_title=env.get("FORWARDER_REPORT_TITLE", "Wizz AI 日报").strip(),
    )


@dataclass(frozen=True)
class RunResult:
    sent_count: int
    baseline_initialized: bool = False


def fetch_public_posts(config: ForwarderConfig, session=None) -> List[ChannelPost]:
    import requests
    http = session or requests.Session()
    response = http.get(
        config.preview_url,
        headers={"User-Agent": "dailybot-forwarder/1.0"},
        timeout=config.request_timeout,
    )
    response.raise_for_status()
    return parse_posts(response.text, config.channel)


def run_once(
    config: ForwarderConfig,
    fetcher: Callable[[], List[ChannelPost]],
    sender: Callable[[str, str], None],
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
        parts = build_markdown_parts(item, header=f"### {config.report_title}")
        for part in parts:
            sender(f"{config.report_title} #{item.id}", part)
        save_last_id(config.state_file, item.id)
        last_id = item.id
        sent_count += 1

    return RunResult(sent_count=sent_count)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        config = load_forwarder_config()
        client = dingtalk.DingTalkClient(config.webhook, config.secret)
        result = run_once(
            config,
            fetcher=lambda: fetch_public_posts(config),
            sender=client.send_markdown,
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
