from __future__ import annotations

import sys

from mes_py.settings import load_settings


def main() -> int:
    settings = load_settings()
    try:
        from mes_py.ui.main_window import run_app
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            print(
                "PySide6 is not installed. Run: python -m pip install -e \".[dev]\"",
                file=sys.stderr,
            )
            return 1
        raise
    return run_app(settings)

