# -*- coding: utf-8 -*-
"""Ensure intentionally removed legacy modules stay removed."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DELETED_MODULES = [
    "strategy/vision_engine.py",
    "polars_compat.py",
    "official/price_adjuster.py",
]

PRODUCTION_FILES = [
    "strategy_runner.py",
    "main.py",
    "strategy/patterns_strategy.py",
    "strategy/chips_strategy.py",
    "strategy/ma_strategy.py",
    "strategy/sr_analyzer.py",
    "strategy/prediction_strategy.py",
]

DELETED_NAME_FRAGMENTS = ["vision_engine", "polars_compat", "price_adjuster"]


def test_deleted_modules_do_not_exist() -> None:
    for module_path in DELETED_MODULES:
        assert not (PROJECT_ROOT / module_path).exists(), f"Unexpected legacy module: {module_path}"


def test_production_code_does_not_reference_deleted_modules() -> None:
    for file_path in PRODUCTION_FILES:
        source = (PROJECT_ROOT / file_path).read_text(encoding="utf-8")
        for fragment in DELETED_NAME_FRAGMENTS:
            offending = [
                (line_number, line.strip())
                for line_number, line in enumerate(source.splitlines(), 1)
                if fragment in line and not line.strip().startswith("#")
            ]
            assert not offending, f"{file_path} references removed {fragment}: {offending[:3]}"
