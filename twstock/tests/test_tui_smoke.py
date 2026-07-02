# -*- coding: utf-8 -*-
"""Smoke tests for tui/ package — verify TUIApp is instantiable."""
from __future__ import annotations

from twstock.tui.app import TUIApp


def test_tuiapp_instantiable():
    """TUIApp can be created without errors."""
    app = TUIApp()
    assert app is not None
    assert hasattr(app, "run")
    assert hasattr(app, "_cache")
