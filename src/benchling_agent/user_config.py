"""Persistent user configuration stored in ~/.benchling-agent/config.json.

Stores preferences like the default Benchling folder so users don't need
to provide folder IDs on every command.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".benchling-agent"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class UserConfig:
    default_folder_id: str | None = None
    default_folder_name: str | None = None

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> UserConfig:
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            return cls(
                default_folder_id=data.get("default_folder_id"),
                default_folder_name=data.get("default_folder_name"),
            )
        except (json.JSONDecodeError, KeyError):
            return cls()
