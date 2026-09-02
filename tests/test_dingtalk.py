"""dingtalk 测试：成功、errcode 非 0、HTTP 错误、网络异常、加签参数。"""

import urllib.parse

import pytest
import requests

from dailybot import dingtalk


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
    assert "sign" not in captured["url"]  # 未配 secret 不加签


def test_errcode_nonzero_raises(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: FakeResponse(body={"errcode": 310000, "errmsg": "sign error"}),
    )
    with pytest.raises(RuntimeError, match="310000"):
        dingtalk.send_markdown("https://x", "t", "text")


def test_http_error_raises(monkeypatch):
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: FakeResponse(status_code=500, text="oops")
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        dingtalk.send_markdown("https://x", "t", "text")


def test_network_error_raises(monkeypatch):
    def fake_post(*a, **k):
        raise requests.ConnectionError("timeout")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(RuntimeError, match="网络请求失败"):
        dingtalk.send_markdown("https://x", "t", "text")


def test_signed_url_contains_timestamp_and_sign(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    dingtalk.send_markdown(
        "https://oapi.dingtalk.com/robot/send?access_token=x",
        "t",
        "text",
        secret="SEC123456",
    )
    query = urllib.parse.parse_qs(urllib.parse.urlparse(captured["url"]).query)
    assert "timestamp" in query and "sign" in query
    assert query["timestamp"][0].isdigit()
    assert query["sign"][0]  # 非空
