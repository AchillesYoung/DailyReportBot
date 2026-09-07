"""统一钉钉推送层：加签、发送、错误处理。

两个业务（dailybot 日报 / forwarder Telegram 转发）共用此模块。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Optional

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


class DingTalkError(RuntimeError):
    """钉钉推送失败。"""


def build_signed_url(webhook_url: str, secret: str, timestamp_ms: int) -> str:
    """按钉钉官方算法为 webhook URL 附加 timestamp 与 sign 参数。"""
    if not secret:
        return webhook_url

    string_to_sign = f"{timestamp_ms}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp_ms}&sign={sign}"


def send_markdown(
    webhook_url: str,
    title: str,
    text: str,
    secret: str | None = None,
) -> None:
    """发送单条 markdown 消息到钉钉群机器人。

    任何失败（网络错误 / HTTP 非 2xx / errcode 非 0）都抛出 DingTalkError。
    """
    timestamp_ms = round(time.time() * 1000)
    url = build_signed_url(webhook_url, secret or "", timestamp_ms)
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise DingTalkError(f"钉钉 webhook 网络请求失败: {exc}") from exc

    if resp.status_code != 200:
        raise DingTalkError(
            f"钉钉 webhook 返回 HTTP {resp.status_code}: {resp.text[:200]}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise DingTalkError(f"钉钉 webhook 返回非 JSON: {resp.text[:200]}") from exc

    errcode = body.get("errcode")
    if errcode != 0:
        raise DingTalkError(
            f"钉钉推送失败: errcode={errcode}, errmsg={body.get('errmsg')}"
        )

    logger.info("钉钉推送成功（title=%s）", title)
