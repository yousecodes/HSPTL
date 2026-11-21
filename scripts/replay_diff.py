#!/usr/bin/env python3
"""Verify the event chain and run two canonical replay passes for a stable diff."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.golden import run_replay_diff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    result = run_replay_diff(EventKernel(DeterministicIntelligenceEngine(args.database)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] and result["diff"]["equal"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
