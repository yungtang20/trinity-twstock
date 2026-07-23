"""Pytest bootstrap for stable package imports."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_PARENT = PROJECT_ROOT.parent

# Do not mutate os.getcwd(): tests and application code should resolve paths
# independently of how pytest was launched.
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))
