# -*- coding: utf-8 -*-
"""Smoke tests for commands/ package — verify execute() is importable."""
from __future__ import annotations

import importlib
import pkgutil

import twstock.commands as commands_pkg


def test_all_commands_importable():
    """Each submodule of commands/ must expose execute()."""
    for importer, modname, ispkg in pkgutil.iter_modules(commands_pkg.__path__):
        if ispkg:
            continue
        mod = importlib.import_module(f"twstock.commands.{modname}")
        assert hasattr(mod, "execute"), f"commands/{modname}.py missing execute()"
        assert callable(mod.execute), f"commands/{modname}.py execute is not callable"


def test_known_commands_exist():
    """Verify the 6 expected command modules exist."""
    expected = {"update", "indicators", "intraday", "official", "dividend", "strategy"}
    found = {m for _, m, ispkg in pkgutil.iter_modules(commands_pkg.__path__) if not ispkg}
    missing = expected - found
    assert not missing, f"Missing command modules: {missing}"
