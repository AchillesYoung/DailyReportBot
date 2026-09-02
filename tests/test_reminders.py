"""reminders 测试：daily/weekly 命中、edition 过滤、空列表。"""

from datetime import datetime, timezone

import pytz

from dailybot import reminders

BJ = pytz.timezone("Asia/Shanghai")

# 2026-09-04 是周五（北京 09:00）
FRIDAY_MORNING = BJ.localize(datetime(2026, 9, 4, 9, 0)).astimezone(timezone.utc)
# 2026-09-02 是周三（北京 09:00）
WEDNESDAY_MORNING = BJ.localize(datetime(2026, 9, 2, 9, 0)).astimezone(timezone.utc)
# 2026-09-04 周五（北京 20:00）
FRIDAY_EVENING = BJ.localize(datetime(2026, 9, 4, 20, 0)).astimezone(timezone.utc)

DAILY = reminders.ReminderRule(text="站会", schedule="daily")
WEEKLY_FRI = reminders.ReminderRule(text="周报", schedule="weekly", days=["fri"])
MORNING_ONLY = reminders.ReminderRule(
    text="早会", schedule="daily", editions=["morning"]
)


def test_daily_rule_fires_every_day():
    assert reminders.due_today([DAILY], WEDNESDAY_MORNING, "morning") == ["站会"]
    assert reminders.due_today([DAILY], FRIDAY_EVENING, "evening") == ["站会"]


def test_weekly_rule_fires_on_matching_day():
    assert reminders.due_today([WEEKLY_FRI], FRIDAY_MORNING, "morning") == ["周报"]


def test_weekly_rule_skipped_on_other_day():
    assert reminders.due_today([WEEKLY_FRI], WEDNESDAY_MORNING, "morning") == []


def test_edition_filter():
    assert reminders.due_today([MORNING_ONLY], FRIDAY_MORNING, "morning") == ["早会"]
    assert reminders.due_today([MORNING_ONLY], FRIDAY_EVENING, "evening") == []


def test_no_edition_filter_means_both():
    assert reminders.due_today([DAILY], FRIDAY_MORNING, "morning") == ["站会"]
    assert reminders.due_today([DAILY], FRIDAY_EVENING, "evening") == ["站会"]


def test_empty_rules_return_empty_list():
    assert reminders.due_today([], FRIDAY_MORNING, "morning") == []


def test_load_reminder_rules(tmp_path):
    cfg = tmp_path / "reminders.yaml"
    cfg.write_text(
        """
reminders:
  - text: "站会 10:00"
    schedule: daily
  - text: "提交周报"
    schedule: weekly
    days: [fri]
    editions: [morning]
  - text: ""          # 非法：无 text，跳过
    schedule: daily
  - text: "非法调度"
    schedule: monthly # 非法 schedule，跳过
""",
        encoding="utf-8",
    )
    rules = reminders.load_reminder_rules(cfg)
    assert len(rules) == 2
    assert rules[0].schedule == "daily"
    assert rules[1].days == ["fri"] and rules[1].editions == ["morning"]


def test_weekday_judged_in_beijing_tz():
    # UTC 2026-09-03 22:00 = 北京 2026-09-04 06:00（周五）——周五规则应命中
    utc_late_thursday = datetime(2026, 9, 3, 22, 0, tzinfo=timezone.utc)
    assert reminders.due_today([WEEKLY_FRI], utc_late_thursday, "evening") == ["周报"]
