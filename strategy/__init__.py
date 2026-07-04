"""Compatibility shim: expose `strategy` package by delegating to `twstock.strategy`.

This file allows tests and older import styles that do `from strategy.xxx import Y`
to continue working without changing test code. It imports submodules lazily.
"""
from importlib import import_module
import sys

# Ensure that 'strategy.<name>' resolves to 'twstock.strategy.<name>' modules
_SUBMODULES = [
    'base', 'chips_strategy', 'composites', 'kronos_engine', 'indicators',
    'ma_strategy', 'patterns_strategy', 'prediction_strategy', '_utils',
    'strategies', 'sr_analyzer'
]

for name in _SUBMODULES:
    mod_name = f"twstock.strategy.{name}"
    try:
        mod = import_module(mod_name)
        sys.modules[f"strategy.{name}"] = mod
    except Exception:
        # defer import errors to real import time
        pass

# Also expose top-level attributes from twstock.strategy if needed
try:
    pkg = import_module('twstock.strategy')
    for k, v in vars(pkg).items():
        if not k.startswith('_') and k not in globals():
            globals()[k] = v
except Exception:
    pass
