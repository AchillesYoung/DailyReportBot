"""shared.dingtalk 测试：DingTalkClient 类。"""

import time

import pytest
import requests

from dailybot.shared import dingtalk
from dailybot.shared.dingtalk import DingTalkClient, DingTalkError


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body if body is not None else {"errcode": 0, "errmsg": "ok"}
        self.text = text or '{"errcode":0,"errmsg":"ok"}'

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class TestDingTalkClient:
    def test_send_success(self, monkeypatch):
        captured = {}

        def fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

        client = DingTalkClient("https://oapi.dingtalk.com/robot/send?access_token=x", "SECtest")
        client._session.post = fake_post
        client.send_markdown("标题", "正文")
        assert captured["json"]["msgtype"] == "markdown"
        assert captured["json"]["markdown"]["title"] == "标题"

    def test_errcode_nonzero_raises(self, monkeypatch):
        def fake_post(url, json, timeout):
            return FakeResponse(body={"errcode": 310000, "errmsg": "sign error"})

        client = DingTalkClient("https://x")
        client._session.post = fake_post
        with pytest.raises(DingTalkError, match="310000"):
            client.send_markdown("t", "text")

    def test_signed_url_contains_timestamp_and_sign(self):
        url = dingtalk.build_signed_url(
            "https://oapi.dingtalk.com/robot/send?access_token=x",
            "SEC123456",
            1234567890123,
        )
        import urllib.parse
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert query["timestamp"] == ["1234567890123"]
        assert "sign" in query

    def test_injectable_clock(self, monkeypatch):
        captured = {}

        def fake_post(url, json, timeout):
            captured["url"] = url
            return FakeResponse()

        client = DingTalkClient(
            "https://oapi.dingtalk.com/robot/send?access_token=x",
            secret="SECtest",
            clock_ms=lambda: 42,
        )
        client._session.post = fake_post
        client.send_markdown("t", "text")
        assert "timestamp=42" in captured["url"]
