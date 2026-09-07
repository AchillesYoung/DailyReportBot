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


def test_char_budget_removes_only_enough_entries():
    """回归：截断应该砍到达标为止，而不是砍光所有条目。"""
    entries = [
        Entry(title=f"标题{i}" + "字" * 200, link=f"https://example.com/{i}", published=NOW)
        for i in range(10)
    ]
    result = _result([("海外", entries)])
    text = briefing.render(
        result, ["站会"], "morning", NOW, max_total_entries=10, max_chars=800
    )
    # 应保留部分条目，而不是全部砍光
    kept_count = text.count("- [标题")
    assert 0 < kept_count < 10
    assert f"还有 {10 - kept_count} 条未展示" in text


def test_only_dingtalk_markdown_subset():
    entries = [_entry(1)]
    result = _result([("海外", entries)])
    text = briefing.render(result, ["提醒"], "morning", NOW)
    assert "|" not in text          # 无表格
    assert "```" not in text        # 无代码块
    assert "<" not in text          # 无 HTML


def test_summary_with_source_link_rendered():
    entry = Entry(
        title="AIHOT条目",
        link="https://aihot.virxact.com/items/abc",
        published=NOW - timedelta(hours=1),
        summary="这是一段摘要内容，描述了某个AI新闻的关键信息",
        source_link="https://mp.weixin.qq.com/s/xyz",
    )
    result = _result([("AIHOT", [entry])])
    text = briefing.render(result, [], "morning", NOW)
    assert "这是一段摘要内容" in text
    assert "[阅读全文](https://mp.weixin.qq.com/s/xyz)" in text


def test_summary_without_source_link():
    entry = Entry(
        title="条目",
        link="https://example.com/1",
        published=NOW - timedelta(hours=1),
        summary="摘要文字",
        source_link="",
    )
    result = _result([("源", [entry])])
    text = briefing.render(result, [], "morning", NOW)
    assert "摘要文字" in text
    assert "阅读全文" not in text


def test_empty_summary_no_extra_output():
    entry = _entry(1)
    result = _result([("源", [entry])])
    text = briefing.render(result, [], "morning", NOW)
    assert text.count("\n") < 10  # 紧凑输出，无多余行
