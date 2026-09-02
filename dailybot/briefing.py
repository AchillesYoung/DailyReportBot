"""简报排版：把抓取结果与提醒渲染为钉钉 Markdown 消息。"""

from __future__ import annotations

import html
from datetime import datetime

from .collector import CollectResult, Entry
from .reminders import BEIJING_TZ

#: 单次推送展示的条目总数上限
DEFAULT_MAX_TOTAL_ENTRIES = 15
#: 消息体字符数安全阈值（钉钉 markdown 上限约 20000 字节，留足余量）
DEFAULT_MAX_TEXT_CHARS = 12000

_EDITION_LABELS = {"morning": "早报", "evening": "晚报"}


def _entry_line(entry: Entry) -> str:
    title = html.unescape(entry.title)
    return f"- [{title}]({entry.link})"


def _render_body(result: CollectResult, entries_budget: int) -> tuple[list[str], int]:
    """渲染资讯区块，返回 (行列表, 因总量上限被省略的条数)。

    entries_budget 为全局条数上限：超限时分组内按时间从新到旧截断。
    """
    lines: list[str] = []
    omitted = 0
    remaining = entries_budget

    has_any = any(f.entries for g in result.groups for f in g.feeds)
    if not has_any:
        lines.append("暂无新资讯")
        lines.append("")
        return lines, 0

    for group in result.groups:
        group_entries = [f for f in group.feeds if f.entries]
        group_failures = [f for f in group.feeds if f.error]
        if not group_entries and not group_failures:
            continue

        lines.append(f"## {group.group}")
        lines.append("")
        for feed in group_entries:
            if remaining <= 0:
                omitted += len(feed.entries)
                continue
            kept = feed.entries[:remaining]
            omitted += len(feed.entries) - len(kept)
            remaining -= len(kept)
            if len(group_entries) > 1:
                lines.append(f"**{feed.source}**")
                lines.append("")
            for entry in kept:
                lines.append(_entry_line(entry))
            lines.append("")
        for feed in group_failures:
            lines.append(f"⚠️ {feed.source} 抓取失败")
            lines.append("")
    return lines, omitted


def render(
    result: CollectResult,
    reminders: list[str],
    edition: str,
    now: datetime,
    max_total_entries: int = DEFAULT_MAX_TOTAL_ENTRIES,
    max_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> str:
    """渲染完整简报 markdown。

    结构：标题 → 分组资讯 → 提醒（如有）→ 尾注。
    超过 max_chars 时从新到旧的反方向截断资讯，提醒与尾注不截断。
    """
    beijing_now = now.astimezone(BEIJING_TZ)
    label = _EDITION_LABELS.get(edition, edition)
    date_str = beijing_now.strftime("%m月%d日")

    title = f"📰 AI 行业{label} · {date_str}"

    body_lines, omitted = _render_body(result, max_total_entries)

    reminder_lines: list[str] = []
    if reminders:
        reminder_lines.append("## 📌 今日提醒")
        reminder_lines.append("")
        reminder_lines.extend(f"- {text}" for text in reminders)
        reminder_lines.append("")

    def build_footer(omitted_count: int) -> list[str]:
        lines = ["---"]
        footer = (
            f"共 {result.total_feeds} 个源 · {result.total_entries} 条资讯"
            f" · {beijing_now.strftime('%H:%M')} 送达"
        )
        if omitted_count > 0:
            footer += f" · 还有 {omitted_count} 条未展示"
        lines.append(footer)
        return lines

    def assemble(body: list[str]) -> str:
        parts = [f"# {title}", ""]
        parts.extend(body)
        parts.extend(reminder_lines)
        parts.extend(build_footer(omitted))
        return "\n".join(parts)

    text = assemble(body_lines)

    # 字节预算：超限时从最旧的条目开始砍（保持从新到旧的展示顺序不变，
    # 逐条移除资讯行直到长度达标；提醒与尾注始终保留）
    if len(text) > max_chars:
        entry_indices = [
            i for i, line in enumerate(body_lines) if line.startswith("- [")
        ]
        extra_omitted = 0
        for i in reversed(entry_indices):
            if len(text) <= max_chars:
                break
            body_lines[i] = ""
            extra_omitted += 1
            omitted += 1
        body_lines = [line for line in body_lines if line != ""]
        if extra_omitted:
            text = assemble(body_lines)

    return text
