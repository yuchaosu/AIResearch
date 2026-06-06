"""Load configuration from config.yaml with sensible defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "data_dir": "data",
    "pdf_dir": "data/pdfs",
    "summary_dir": "data/summaries",
    "db_path": "data/papers.db",
    "openalex_mailto": "",
    "download": {
        "enabled": True,
        "delay_seconds": 20,
        "jitter_seconds": 10,
        "max_per_run": 25,
        "timeout": 60,
        "user_agent": "autoPaper/0.1 (academic research)",
    },
    "summarizer": {
        "command": "claude",
        "model": "sonnet",
        "max_chars": 60000,
        "timeout": 300,
    },
    "venue_keys": {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict[str, Any], root: Path):
        self._d = data
        self.root = root

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Config":
        root = Path(__file__).resolve().parent.parent
        cfg_path = Path(path) if path else root / "config.yaml"
        loaded = {}
        if cfg_path.exists():
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return cls(_deep_merge(DEFAULTS, loaded), root)

    def __getitem__(self, key: str) -> Any:
        return self._d[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def path(self, key: str) -> Path:
        """Resolve a configured path relative to the project root."""
        p = Path(self._d[key])
        return p if p.is_absolute() else (self.root / p)

    def ensure_dirs(self) -> None:
        for key in ("data_dir", "pdf_dir", "summary_dir"):
            self.path(key).mkdir(parents=True, exist_ok=True)
        self.path("db_path").parent.mkdir(parents=True, exist_ok=True)
