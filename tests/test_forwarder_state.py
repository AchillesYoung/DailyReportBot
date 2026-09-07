"""forwarder.state 测试：原子状态读写。"""

from pathlib import Path

import pytest

from dailybot.forwarder.state import load_last_id, save_last_id


def test_load_missing():
    assert load_last_id(Path("/nonexistent/state.json")) is None


def test_save_and_load(tmp_path):
    path = tmp_path / "state.json"
    save_last_id(path, 42)
    assert load_last_id(path) == 42


def test_save_overwrites(tmp_path):
    path = tmp_path / "state.json"
    save_last_id(path, 1)
    save_last_id(path, 2)
    assert load_last_id(path) == 2


def test_invalid_state_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"last_id": "not-a-number"}')
    with pytest.raises(ValueError):
        load_last_id(path)


def test_negative_id_raises(tmp_path):
    path = tmp_path / "state.json"
    with pytest.raises(ValueError):
        save_last_id(path, -1)
