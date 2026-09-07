"""shared.dingtalk 测试：统一推送层。"""

import urllib.parse

import pytest
import requests

from dailybot.shared import dingtalk


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body if body is not None else {"errcode": 0, "errmsg": "ok"}
        self.text = text or '{"errcode":0,"errmsg":"ok"}'

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def test_send_success(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    dingtalk.send_markdown("https://oapi.dingtalk.com/robot/send?access_token=x", "标题", "正文")
    assert captured["json"]["msgtype"] == "markdown"
    assert captured["json"]["markdown"]["title"] == "标题"


def test_errcode_nonzero_raises(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: FakeResponse(body={"errcode": 310000, "errmsg": "sign error"}),
    )
    with pytest.raises(dingtalk.DingTalkError, match="310000"):
        dingtalk.send_markdown("https://x", "t", "text")


def test_signed_url_contains_timestamp_and_sign():
    url = dingtalk.build_signed_url(
        "https://oapi.dingtalk.com/robot/send?access_token=x",
        "SEC123456",
        1234567890123,
    )
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert query["timestamp"] == ["1234567890123"]
    assert "sign" in query
    assert query["sign"][0]
