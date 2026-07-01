# -*- coding: utf-8 -*-
"""Shared helpers for official subpackage."""


def safe_float(val, default=0.0):
    try:
        val = str(val).replace(",", "") if val not in ('-', '', None) else val
        return float(val) if val not in ('-', '', None) else default
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        val = str(val).replace(",", "") if val not in ('-', '', None) else val
        return int(val) if val not in ('-', '', None) else default
    except (ValueError, TypeError):
        return default
