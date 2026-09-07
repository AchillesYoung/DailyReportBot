"""RSS 抓取：分组配置加载、串行抓取、时间窗口过滤、单源失败容忍。"""

from __future__ import annotations

import html as html_mod
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
import yaml

logger = logging.getLogger(__name__)

#: 单源抓取超时（秒）
FETCH_TIMEOUT_SECONDS = 15
#: 每源保留条目的默认上限
DEFAULT_MAX_ENTRIES_PER_FEED = 10
#: HTTP 请求 User-Agent
_USER_AGENT = "dailybot/0.1 (+https://github.com/AchillesYoung/DailyReportBot)"


@dataclass
class FeedConfig:
    """单个订阅源的配置。"""

    name: str
    url: str
    show_summary: bool = False


@dataclass
class GroupConfig:
    """源分组配置。"""

    name: str
    feeds: list[FeedConfig] = field(default_factory=list)


@dataclass
class Entry:
    """一条资讯条目。"""

    title: str
    link: str
    published: datetime | None  # UTC；无时间戳时为 None
    summary: str = ""
    source_link: str = ""


@dataclass
class FeedResult:
    """单个源的抓取结果：成功时为 entries，失败时为 error。"""

    source: str
    entries: list[Entry] = field(default_factory=list)
    error: str | None = None


@dataclass
class GroupResult:
    """一个分组的抓取结果。"""

    group: str
    feeds: list[FeedResult] = field(default_factory=list)


@dataclass
class CollectResult:
    """全部抓取结果。"""

    groups: list[GroupResult] = field(default_factory=list)

    @property
    def total_entries(self) -> int:
        return sum(len(f.entries) for g in self.groups for f in g.feeds)

    @property
    def total_feeds(self) -> int:
        return sum(len(g.feeds) for g in self.groups)

    @property
    def failed_feeds(self) -> list[FeedResult]:
        return [f for g in self.groups for f in g.feeds if f.error]


def load_feed_configs(path: str | Path) -> list[GroupConfig]:
    """加载 feeds.yaml，跳过缺少 name/url 的非法源并告警。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    groups: list[GroupConfig] = []
    for raw_group in data.get("groups") or []:
        group_name = (raw_group.get("name") or "未分组").strip()
        group = GroupConfig(name=group_name)
        for raw_feed in raw_group.get("feeds") or []:
            name = (raw_feed.get("name") or "").strip()
            url = (raw_feed.get("url") or "").strip()
            if not name or not url:
                logger.warning("跳过非法源（缺少 name 或 url）: %r", raw_feed)
                continue
            group.feeds.append(FeedConfig(name=name, url=url, show_summary=bool(raw_feed.get("show_summary", False))))
        groups.append(group)
    return groups


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    """从 feed 条目解析发布时间，统一为 UTC；失败返回 None。"""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_summary(raw_html: str) -> tuple[str, str]:
    """从 RSS description HTML 中提取摘要文本和原文链接。

    返回 (summary_text, source_link)。
    AIHOT 格式：第 1 段=摘要，第 2 段=阅读原文链接，第 3 段=via AIHOT。
    """
    paragraphs = re.findall(r"<p>(.*?)</p>", raw_html, re.DOTALL)
    summary = ""
    source_link = ""
    if paragraphs:
        summary = re.sub(r"<[^>]+>", "", paragraphs[0]).strip()
    if len(paragraphs) >= 2:
        match = re.search(r'href="([^"]+)"', paragraphs[1])
        if match:
            source_link = html_mod.unescape(match.group(1))
    return summary, source_link


def fetch_feed(
    feed: FeedConfig,
    since: datetime,
    max_entries: int = DEFAULT_MAX_ENTRIES_PER_FEED,
) -> FeedResult:
    """抓取单个源并过滤窗口内条目。失败返回带 error 的 FeedResult。"""
    try:
        resp = requests.get(
            feed.url,
            headers={"User-Agent": _USER_AGENT},
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as exc:  # noqa: BLE001 - 任何异常都不能中断整批
        return FeedResult(source=feed.name, error=f"{type(exc).__name__}: {exc}")

    if parsed.bozo and not parsed.entries:
        exc = parsed.get("bozo_exception")
        return FeedResult(source=feed.name, error=f"feed 解析失败: {exc}")

    entries: list[Entry] = []
    for item in parsed.entries:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        if not title or not link:
            continue
        published = _parse_published(item)
        # 无时间戳的条目保守保留（宁重复勿漏）
        if published is not None and published < since:
            continue
        summary, source_link = "", ""
        if feed.show_summary:
            summary, source_link = _parse_summary(item.get("summary") or "")
        entries.append(Entry(title=title, link=link, published=published, summary=summary, source_link=source_link))

    # 从新到旧排序（无时间戳的排最后），再按上限截断
    entries.sort(
        key=lambda e: e.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return FeedResult(source=feed.name, entries=entries[:max_entries])


def collect(
    configs: list[GroupConfig],
    since_hours: float,
    now: datetime | None = None,
    max_entries_per_feed: int = DEFAULT_MAX_ENTRIES_PER_FEED,
) -> CollectResult:
    """串行抓取所有源，返回窗口内的条目。单源失败不中断。"""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=since_hours)

    result = CollectResult()
    for group in configs:
        group_result = GroupResult(group=group.name)
        for feed in group.feeds:
            feed_result = fetch_feed(feed, since, max_entries_per_feed)
            if feed_result.error:
                logger.warning("源 [%s] 抓取失败: %s", feed.name, feed_result.error)
            group_result.feeds.append(feed_result)
        result.groups.append(group_result)
    return result
