from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DATABASE_URL = f"sqlite:///{(DEFAULT_DATA_DIR / 'mes.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    database_url: str
    bootstrap_email: str
    bootstrap_password: str


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("MES_DATABASE_URL", DEFAULT_DATABASE_URL),
        bootstrap_email=os.getenv("MES_BOOTSTRAP_EMAIL", "admin@local"),
        bootstrap_password=os.getenv("MES_BOOTSTRAP_PASSWORD", "admin123"),
    )

