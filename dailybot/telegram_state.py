"""转发状态持久化：原子写入，防半写文件。"""

import json
import os
from pathlib import Path
import tempfile
from typing import Optional


def load_last_id(path: Path) -> Optional[int]:
    if not path.exists():
        return None

    try:
        value = json.loads(path.read_text(encoding="utf-8"))["last_id"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("state must contain an integer last_id") from error

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("state last_id must be a non-negative integer")
    return value


def save_last_id(path: Path, message_id: int) -> None:
    if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 0:
        raise ValueError("message_id must be a non-negative integer")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump({"last_id": message_id}, temporary, ensure_ascii=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
