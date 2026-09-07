"""shared.config 测试：凭证读取、兼容旧变量名。"""

import pytest

from dailybot.shared.config import get_dingtalk_credentials, ConfigError


def test_read_new_variable():
    creds = get_dingtalk_credentials({"DINGTALK_WEBHOOK_URL": "https://x", "DINGTALK_SECRET": "SEC"})
    assert creds.webhook == "https://x"
    assert creds.secret == "SEC"


def test_fallback_to_old_variable():
    creds = get_dingtalk_credentials({"DINGTALK_WEBHOOK": "https://old", "DINGTALK_SECRET": "SEC"})
    assert creds.webhook == "https://old"


def test_new_variable_takes_priority():
    creds = get_dingtalk_credentials({
        "DINGTALK_WEBHOOK_URL": "https://new",
        "DINGTALK_WEBHOOK": "https://old",
    })
    assert creds.webhook == "https://new"


def test_missing_webhook_raises():
    with pytest.raises(ConfigError, match="DINGTALK_WEBHOOK"):
        get_dingtalk_credentials({})


def test_empty_webhook_raises():
    with pytest.raises(ConfigError):
        get_dingtalk_credentials({"DINGTALK_WEBHOOK_URL": ""})


def test_missing_secret_defaults_to_empty():
    creds = get_dingtalk_credentials({"DINGTALK_WEBHOOK_URL": "https://x"})
    assert creds.secret == ""
