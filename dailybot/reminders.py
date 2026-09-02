"""提醒事项：本地配置来源，按日程规则（daily/weekly）与推送类型匹配。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytz
import yaml

#: 星期判定与日期展示均使用北京时间（pytz 兼容 Python 3.9）
BEIJING_TZ = pytz.timezone("Asia/Shanghai")

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class ReminderRule:
    """一条提醒规则。"""

    text: str
    schedule: str = "daily"  # daily | weekly
    days: list[str] = field(default_factory=list)  # weekly 时生效，mon..sun
    editions: list[str] = field(default_factory=list)  # 空 = 早晚都带


def load_reminder_rules(path: str | Path) -> list[ReminderRule]:
    """加载 reminders.yaml，跳过缺少 text 或 schedule 非法的规则。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules: list[ReminderRule] = []
    for raw in data.get("reminders") or []:
        text = (raw.get("text") or "").strip()
        schedule = (raw.get("schedule") or "daily").strip().lower()
        if not text or schedule not in ("daily", "weekly"):
            continue
        days = [str(d).strip().lower() for d in (raw.get("days") or [])]
        editions = [str(e).strip().lower() for e in (raw.get("editions") or [])]
        rules.append(
            ReminderRule(text=text, schedule=schedule, days=days, editions=editions)
        )
    return rules


def due_today(
    rules: list[ReminderRule], now: datetime, edition: str
) -> list[str]:
    """返回本次推送应携带的提醒文案列表。

    星期几按北京时间判定。edition 为 "morning" 或 "evening"。
    """
    beijing_now = now.astimezone(BEIJING_TZ)
    weekday_key = _WEEKDAY_KEYS[beijing_now.weekday()]
    edition = edition.lower()

    due: list[str] = []
    for rule in rules:
        if rule.editions and edition not in rule.editions:
            continue
        if rule.schedule == "daily":
            due.append(rule.text)
        elif rule.schedule == "weekly" and weekday_key in rule.days:
            due.append(rule.text)
    return due
