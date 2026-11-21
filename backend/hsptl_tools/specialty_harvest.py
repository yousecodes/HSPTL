#!/usr/bin/env python3
"""Backward-compatible Specialty Harvest command and import facade."""
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.hsptl_tools.specialty_harvest import *  # noqa: F401,F403,E402
from backend.hsptl_tools.specialty_harvest import main  # noqa: E402

if __name__ == "__main__":
    main()
