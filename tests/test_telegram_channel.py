"""forwarder.channel 测试：Telegram HTML 解析。"""

from dailybot.telegram_channel import parse_posts


SAMPLE_HTML = """
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="aiwizz/123">
    <div class="tgme_widget_message_text">第一条消息<br>第二行</div>
  </div>
  <div class="tgme_widget_message" data-post="aiwizz/124">
    <div class="tgme_widget_message_text">  </div>
  </div>
  <div class="tgme_widget_message" data-post="aiwizz/125">
    <!-- 无文本元素，媒体消息 -->
  </div>
  <div class="tgme_widget_message" data-post="other/126">
    <div class="tgme_widget_message_text">别的频道</div>
  </div>
</div>
"""


def test_parse_posts():
    posts = parse_posts(SAMPLE_HTML, "aiwizz")
    assert len(posts) == 3
    assert posts[0].id == 123
    assert "第一条消息" in posts[0].text
    assert "第二行" in posts[0].text
    assert posts[1].text == "[媒体消息]"
    assert posts[2].text == "[媒体消息]"
    assert all(p.url.startswith("https://t.me/aiwizz/") for p in posts)


def test_parse_posts_channel_case_insensitive():
    posts = parse_posts(SAMPLE_HTML, "AIWIZZ")
    assert len(posts) == 3
