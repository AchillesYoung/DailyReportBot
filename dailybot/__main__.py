"""CLI 入口：组装 抓取 → 提醒 → 排版 → 推送 全流程。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import briefing, collector, dingtalk, reminders

#: 各推送类型的默认时间窗口（小时）。早报覆盖昨晚以来，晚报覆盖今早以来。
DEFAULT_WINDOWS = {"morning": 13.0, "evening": 11.0}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dailybot",
        description="AI 行业资讯钉钉自动化日报：抓取 RSS → 排版 → 推送钉钉群",
    )
    parser.add_argument(
        "--edition",
        choices=["morning", "evening"],
        required=True,
        help="推送类型：morning=早报 / evening=晚报",
    )
    parser.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="覆盖默认时间窗口（小时）；默认早报 13h / 晚报 11h",
    )
    parser.add_argument("--feeds", default="feeds.yaml", help="RSS 源配置文件路径")
    parser.add_argument(
        "--reminders", default="reminders.yaml", help="提醒规则配置文件路径"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 markdown 不推送（本地调试用）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    since_hours = (
        args.since_hours
        if args.since_hours is not None
        else DEFAULT_WINDOWS[args.edition]
    )

    # 1. 加载配置（缺失/非法 → 明确报错，退出码 2）
    try:
        feed_configs = collector.load_feed_configs(Path(args.feeds))
        reminder_rules = reminders.load_reminder_rules(Path(args.reminders))
    except (OSError, ValueError) as exc:
        print(f"配置加载失败: {exc}", file=sys.stderr)
        return 2

    # 2. 抓取（单源失败容忍；全部失败也继续推送"暂无新资讯"）
    result = collector.collect(feed_configs, since_hours, now=now)

    # 3. 提醒
    due = reminders.due_today(reminder_rules, now, args.edition)

    # 4. 排版
    text = briefing.render(result, due, args.edition, now)

    if args.dry_run:
        print(text)
        return 0

    # 5. 推送（webhook 未配置或推送失败 → 退出码 1）
    # 兼容旧变量名 DINGTALK_WEBHOOK，优先用新名 DINGTALK_WEBHOOK_URL
    webhook_url = os.environ.get("DINGTALK_WEBHOOK_URL") or os.environ.get(
        "DINGTALK_WEBHOOK"
    )
    secret = os.environ.get("DINGTALK_SECRET") or None
    if not webhook_url:
        print(
            "未配置 DINGTALK_WEBHOOK_URL 或 DINGTALK_WEBHOOK 环境变量，无法推送",
            file=sys.stderr,
        )
        return 1

    edition_label = "早报" if args.edition == "morning" else "晚报"
    beijing_now = now.astimezone(reminders.BEIJING_TZ)
    title = f"AI 行业{edition_label} · {beijing_now.strftime('%m月%d日')}"

    try:
        dingtalk.send_markdown(webhook_url, title, text, secret=secret)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
