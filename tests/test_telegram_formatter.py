"""forwarder.formatter 测试：Markdown 排版与拆段。"""

from dailybot.telegram_formatter import build_markdown_parts
from dailybot.telegram_models import ChannelPost


def _post(text, post_id=1):
    return ChannelPost(id=post_id, text=text, url=f"https://t.me/aiwizz/{post_id}")


def test_single_part():
    parts = build_markdown_parts(_post("短消息"))
    assert len(parts) == 1
    assert "短消息" in parts[0]
    assert "查看 Telegram 原文" in parts[0]
    assert "https://t.me/aiwizz/1" in parts[0]


def test_multi_part():
    long_text = "这是一段很长的文字。\n" * 2000
    parts = build_markdown_parts(_post(long_text), max_chars=1000)
    assert len(parts) > 1
    assert all("查看 Telegram 原文" in p for p in parts)
    assert all(len(p) <= 1000 for p in parts)
    assert "（1/" in parts[0]


def test_markdown_escaping():
    parts = build_markdown_parts(_post("含 *星号* 和 [链接] 的文本"))
    assert "\\*星号\\*" in parts[0]
    assert "\\[链接\\]" in parts[0]
