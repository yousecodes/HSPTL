"""Import-time startup preflight used by the Windows launcher."""
from __future__ import annotations
import os, sys, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
try:
    from backend.main import app  # noqa: F401 - intentionally exercises runtime initialization
except Exception:
    print('HSPTL startup preflight failed while importing backend.main:', file=sys.stderr)
    traceback.print_exc()
    raise SystemExit(1)
print('HSPTL startup preflight passed. Database migrations and application imports completed.')
