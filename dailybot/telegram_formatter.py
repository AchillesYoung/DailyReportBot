"""Telegram 消息转钉钉 Markdown 排版与拆段。

长消息按 15000 字符上限拆分为多条，每段带序号和原文链接。
"""

from __future__ import annotations

import re
from typing import List

from .telegram_models import ChannelPost


def _escape_markdown(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    for character in ("*", "_", "[", "]", "`"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _is_section_break(line: str) -> bool:
    return (
        line.startswith("● ")
        or line.startswith("—")
        or (line.startswith("【") and line.endswith("】"))
        or re.match(r"^\d+\.\s", line) is not None
    )


def _format_report_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    formatted = []

    for line in lines:
        if not line:
            if formatted and formatted[-1] != "":
                formatted.append("")
            continue

        if formatted and formatted[-1] != "" and _is_section_break(line):
            formatted.append("")
        formatted.append(line)

    while formatted and formatted[-1] == "":
        formatted.pop()
    return "\n".join(formatted)


def _split_text(text: str, limit: int) -> List[str]:
    if limit < 1:
        raise ValueError("max_chars is too small for the required original link")
    if not text:
        return [""]

    chunks = []
    remaining = text
    while len(remaining) > limit:
        boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
            chunks.append(remaining[:boundary])
            remaining = remaining[boundary:]
        else:
            chunks.append(remaining[:boundary])
            remaining = remaining[boundary + 1 :]
    chunks.append(remaining)
    return chunks


def build_markdown_parts(
    post: ChannelPost,
    max_chars: int = 15000,
    header: str = "### Wizz AI 日报",
) -> List[str]:
    """把一条 Telegram 消息渲染为钉钉 markdown 分段列表。

    两遍法：先用最坏估计的 header 宽度分页，再用实际页数校验，
    如果实际 header 更宽（页数位数增加），用真实宽度重分一次。
    """
    suffix = f"\n\n[查看 Telegram 原文]({post.url})"
    escaped = _escape_markdown(_format_report_text(post.text))

    # 第一遍：用最坏估计的 header 宽度分页（假设页数 ≤ 4 位）
    worst_header = f"{header}（9999/9999）\n\n"
    content_limit = max_chars - len(worst_header) - len(suffix)
    if content_limit < 1:
        raise ValueError("max_chars is too small for the required original link")
    chunks = _split_text(escaped, content_limit)

    # 第二遍：用实际页数校验 header 宽度
    total = len(chunks)
    real_header = f"{header}（{total}/{total}）\n\n" if total > 1 else f"{header}\n\n"
    real_limit = max_chars - len(real_header) - len(suffix)
    if real_limit < 1:
        raise ValueError("max_chars is too small for the required original link")
    if len(real_header) > len(worst_header):
        # 实际 header 比最坏估计更宽，用真实宽度重分一次
        chunks = _split_text(escaped, real_limit)
        total = len(chunks)
    real_header = f"{header}（{total}/{total}）\n\n" if total > 1 else f"{header}\n\n"

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        marker = f"（{index}/{total}）" if total > 1 else ""
        part = f"{header}{marker}\n\n{chunk}{suffix}"
        if len(part) > max_chars:
            raise ValueError("formatted DingTalk message exceeds max_chars")
        parts.append(part)
    return parts
