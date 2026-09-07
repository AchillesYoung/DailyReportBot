"""collector 测试：窗口过滤、无时间戳保留、单源失败容忍、超限截断、配置校验。"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from dailybot import collector


def _struct_time(dt: datetime) -> time.struct_time:
    return dt.utctimetuple()


def _entry(title, link, published=None):
    e = {"title": title, "link": link}
    if published is not None:
        e["published_parsed"] = _struct_time(published)
    return e


def _fake_entries_response(entries):
    """构造一个 mock requests.Response，让 feedparser.parse 能解析出给定条目。"""
    # feedparser.parse 接受 bytes / str，这里用空 HTML 让它走内部 dict 逻辑不行。
    # 更好的方式：mock feedparser.parse 直接返回 FakeParsed。
    resp = MagicMock()
    resp.content = b"<html></html>"
    resp.raise_for_status = lambda: None
    return resp


class FakeParsed:
    """模拟 feedparser.parse 的返回值。"""

    def __init__(self, entries, bozo=False, bozo_exception=None):
        self.entries = entries
        self.bozo = bozo
        self._bozo_exception = bozo_exception

    def get(self, key, default=None):
        if key == "bozo_exception":
            return self._bozo_exception
        return default


NOW = datetime(2026, 9, 1, 4, 0, 0, tzinfo=timezone.utc)  # 北京 12:00
SINCE = NOW - timedelta(hours=12)


def test_load_feed_configs_skips_invalid(tmp_path):
    cfg = tmp_path / "feeds.yaml"
    cfg.write_text(
        """
groups:
  - name: 海外
    feeds:
      - name: Good
        url: https://example.com/rss
      - name: ""
        url: https://example.com/no-name
      - name: NoUrl
        url: ""
""",
        encoding="utf-8",
    )
    groups = collector.load_feed_configs(cfg)
    assert len(groups) == 1
    assert groups[0].name == "海外"
    assert [f.name for f in groups[0].feeds] == ["Good"]


def _patch_fetch(monkeypatch, entries):
    """Mock requests.get + feedparser.parse 以返回给定条目列表。"""
    fake_parsed = FakeParsed(entries)
    monkeypatch.setattr(
        collector.requests, "get",
        lambda *a, **k: _fake_entries_response(entries),
    )
    monkeypatch.setattr(
        collector.feedparser, "parse",
        lambda *a, **k: fake_parsed,
    )


def test_window_filtering(monkeypatch):
    entries = [
        _entry("新1", "https://a/1", NOW - timedelta(hours=1)),
        _entry("新2", "https://a/2", NOW - timedelta(hours=11)),
        _entry("旧", "https://a/3", NOW - timedelta(hours=25)),
    ]
    _patch_fetch(monkeypatch, entries)
    feed = collector.FeedConfig(name="S", url="https://x")
    result = collector.fetch_feed(feed, SINCE)
    assert result.error is None
    assert [e.title for e in result.entries] == ["新1", "新2"]


def test_entries_without_timestamp_are_kept(monkeypatch):
    entries = [_entry("无时间", "https://a/1", None)]
    _patch_fetch(monkeypatch, entries)
    result = collector.fetch_feed(collector.FeedConfig("S", "https://x"), SINCE)
    assert [e.title for e in result.entries] == ["无时间"]
    assert result.entries[0].published is None


def test_feed_failure_tolerated(monkeypatch):
    def fake_get(url, **kwargs):
        if "bad" in url:
            raise ConnectionError("boom")
        return _fake_entries_response([])

    monkeypatch.setattr(collector.requests, "get", fake_get)
    good_parsed = FakeParsed([_entry("好", "https://a/1", NOW - timedelta(hours=1))])
    monkeypatch.setattr(collector.feedparser, "parse", lambda *a, **k: good_parsed)

    configs = [
        collector.GroupConfig(
            name="G",
            feeds=[
                collector.FeedConfig("Bad", "https://bad/rss"),
                collector.FeedConfig("Good", "https://good/rss"),
            ],
        )
    ]
    result = collector.collect(configs, since_hours=12, now=NOW)
    assert result.failed_feeds[0].source == "Bad"
    assert "boom" in result.failed_feeds[0].error
    good = result.groups[0].feeds[1]
    assert good.error is None and len(good.entries) == 1


def test_bozo_without_entries_is_failure(monkeypatch):
    monkeypatch.setattr(
        collector.requests, "get",
        lambda *a, **k: _fake_entries_response([]),
    )
    monkeypatch.setattr(
        collector.feedparser, "parse",
        lambda *a, **k: FakeParsed([], bozo=True, bozo_exception="xml broken"),
    )
    result = collector.fetch_feed(collector.FeedConfig("S", "https://x"), SINCE)
    assert result.error is not None


def test_per_feed_max_entries(monkeypatch):
    entries = [
        _entry(f"E{i}", f"https://a/{i}", NOW - timedelta(hours=1))
        for i in range(15)
    ]
    _patch_fetch(monkeypatch, entries)
    result = collector.fetch_feed(
        collector.FeedConfig("S", "https://x"), SINCE, max_entries=10
    )
    assert len(result.entries) == 10


def test_collect_totals(monkeypatch):
    _patch_fetch(
        monkeypatch,
        [_entry("X", "https://a/1", NOW - timedelta(hours=1))],
    )
    configs = [
        collector.GroupConfig(
            "G1", [collector.FeedConfig("A", "u1"), collector.FeedConfig("B", "u2")]
        )
    ]
    result = collector.collect(configs, since_hours=12, now=NOW)
    assert result.total_feeds == 2
    assert result.total_entries == 2
