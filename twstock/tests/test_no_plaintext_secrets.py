# -*- coding: utf-8 -*-
"""Guard local credential handling without requiring a Git checkout."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_example_env_exists() -> None:
    assert (PROJECT_ROOT / "api.env.example").exists()


def test_gitignore_blocks_local_credentials_and_databases() -> None:
    content = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    for expected in ("api.env", ".env", "*.db", "*.db-wal"):
        assert expected in content


def test_checked_in_local_env_contains_only_empty_placeholders() -> None:
    """A local sample file may exist, but it must not contain a live token."""
    env_path = PROJECT_ROOT / "api.env"
    if not env_path.exists():
        return
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    for key in ("FINMIND_TOKEN", "LONGCAT_API_KEY"):
        assert values.get(key, "") in {"", f"your_{key.lower()}_here"}
