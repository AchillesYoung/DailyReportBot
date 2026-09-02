"""briefing 测试：结构、无资讯分支、失败源标注、超长截断、钉钉子集。"""

from datetime import datetime, timedelta, timezone

from dailybot import briefing
from dailybot.collector import CollectResult, Entry, FeedResult, GroupResult

NOW = datetime(2026, 9, 2, 1, 0, 0, tzinfo=timezone.utc)  # 北京 09:00


def _result(groups_entries, failed=None):
    groups = []
    for name, entries in groups_entries:
        feed = FeedResult(source=f"{name}源", entries=entries)
        groups.append(GroupResult(group=name, feeds=[feed]))
    if failed:
        groups[0].feeds.append(FeedResult(source="坏源", error="timeout"))
    return CollectResult(groups=groups)


def _entry(i, hours_ago=1):
    return Entry(
        title=f"标题{i}",
        link=f"https://example.com/{i}",
        published=NOW - timedelta(hours=hours_ago),
    )


def test_standard_morning_structure():
    result = _result([("海外", [_entry(1), _entry(2)]), ("中文", [_entry(3)])])
    text = briefing.render(result, ["站会 10:00"], "morning", NOW)

    assert text.startswith("# 📰 AI 行业早报 · 09月02日")
    assert "## 海外" in text and "## 中文" in text
    assert "[标题1](https://example.com/1)" in text
    assert "## 📌 今日提醒" in text and "- 站会 10:00" in text
    assert "共 2 个源 · 3 条资讯" in text
    assert "09:00 送达" in text


def test_evening_label():
    result = _result([("海外", [_entry(1)])])
    text = briefing.render(result, [], "evening", NOW)
    assert "晚报" in text


def test_no_entries_branch():
    result = CollectResult(groups=[GroupResult("海外", feeds=[])])
    text = briefing.render(result, [], "morning", NOW)
    assert "暂无新资讯" in text
    assert "## 📌" not in text  # 无提醒时不渲染提醒区块


def test_failed_source_is_visible():
    result = _result([("海外", [_entry(1)])], failed=True)
    text = briefing.render(result, [], "morning", NOW)
    assert "⚠️ 坏源 抓取失败" in text


def test_total_entries_cap():
    entries = [_entry(i) for i in range(20)]
    result = _result([("海外", entries)])
    text = briefing.render(result, [], "morning", NOW, max_total_entries=15)
    assert text.count("- [标题") == 15
    assert "还有 5 条未展示" in text


def test_char_budget_truncation_keeps_reminders_and_footer():
    entries = [
        Entry(title="很长的标题" * 30, link=f"https://example.com/{i}", published=NOW)
        for i in range(50)
    ]
    result = _result([("海外", entries)])
    text = briefing.render(
        result, ["站会"], "morning", NOW, max_total_entries=50, max_chars=2000
    )
    assert len(text) <= 2200  # 允许少量结构余量
    assert "## 📌 今日提醒" in text
    assert "送达" in text
    assert "未展示" in text


def test_only_dingtalk_markdown_subset():
    entries = [_entry(1)]
    result = _result([("海外", entries)])
    text = briefing.render(result, ["提醒"], "morning", NOW)
    assert "|" not in text          # 无表格
    assert "```" not in text        # 无代码块
    assert "<" not in text          # 无 HTML
