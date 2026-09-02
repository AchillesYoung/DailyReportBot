"""钉钉推送：自定义机器人 webhook，markdown 消息，可选加签。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse

import requests

logger = logging.getLogger(__name__)

#: webhook 请求超时（秒）
REQUEST_TIMEOUT_SECONDS = 15


def _signed_url(webhook_url: str, secret: str) -> str:
    """按钉钉官方算法为 webhook URL 附加 timestamp 与 sign 参数。"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


def send_markdown(
    webhook_url: str,
    title: str,
    text: str,
    secret: str | None = None,
) -> None:
    """发送 markdown 消息到钉钉群机器人。

    任何失败（网络错误 / HTTP 非 2xx / errcode 非 0）都抛出异常，
    由调用方决定退出码——推送失败必须显式可见。
    """
    url = _signed_url(webhook_url, secret) if secret else webhook_url
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RuntimeError(f"钉钉 webhook 网络请求失败: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"钉钉 webhook 返回 HTTP {resp.status_code}: {resp.text[:200]}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"钉钉 webhook 返回非 JSON: {resp.text[:200]}") from exc

    errcode = body.get("errcode")
    if errcode != 0:
        raise RuntimeError(
            f"钉钉推送失败: errcode={errcode}, errmsg={body.get('errmsg')}"
        )

    logger.info("钉钉推送成功（title=%s）", title)
