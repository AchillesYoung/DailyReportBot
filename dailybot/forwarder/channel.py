"""Telegram 公开预览页解析：提取消息 ID、正文、原文链接。"""

from typing import List

from bs4 import BeautifulSoup

from .models import ChannelPost


def _readable_text(element) -> str:
    for line_break in element.find_all("br"):
        line_break.replace_with("\n")
    lines = [" ".join(line.split()) for line in element.get_text().splitlines()]
    return "\n".join(line for line in lines if line)


def parse_posts(html: str, channel: str) -> List[ChannelPost]:
    channel = channel.lstrip("@")
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for element in soup.select(".tgme_widget_message[data-post]"):
        data_post = element.get("data-post", "")
        try:
            post_channel, raw_id = data_post.rsplit("/", 1)
            message_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if post_channel.casefold() != channel.casefold():
            continue

        text_element = element.select_one(".tgme_widget_message_text")
        text = _readable_text(text_element) if text_element is not None else "[媒体消息]"
        posts.append(
            ChannelPost(
                id=message_id,
                text=text or "[媒体消息]",
                url=f"https://t.me/{channel}/{message_id}",
            )
        )

    return sorted(posts, key=lambda post: post.id)
