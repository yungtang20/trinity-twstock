# -*- coding: utf-8 -*-
"""Smoke tests for tui/ package — verify TUIApp is instantiable."""

from __future__ import annotations

from twstock.tui.app import TUIApp


def test_tuiapp_instantiable():
    """TUIApp can be created without errors.

    A + ① 組合：TUIApp 不再持有 _cache（render_dashboard 自行取用共享快取）。
    """
    app = TUIApp()
    assert app is not None
    assert hasattr(app, "run")
    assert not hasattr(app, "_cache"), "A + ① 組合：_cache 應由 render_dashboard 自行管理"
