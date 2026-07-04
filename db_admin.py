"""Compatibility shim for top-level `db_admin` module used by tests.
Delegates to `twstock.db_admin`.
"""
from importlib import import_module
_mod = import_module('twstock.db_admin')
globals().update({k: getattr(_mod, k) for k in dir(_mod) if not k.startswith('_')})
