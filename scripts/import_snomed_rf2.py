#!/usr/bin/env python3
"""Import a local SNOMED CT RF2 Snapshot into the embedded terminology index."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.terminology_port import TerminologyPort
from backend.runtime import PATHS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path, help="Directory containing RF2 Snapshot Concept and Description files")
    parser.add_argument("--edition", required=True, help="SNOMED CT edition name, e.g. International or a licensed national extension")
    parser.add_argument("--effective-time", required=True, help="Release effectiveTime in YYYYMMDD format")
    parser.add_argument("--confirm-licensed-use", action="store_true", help="Confirm this organization is entitled to import and use this edition")
    parser.add_argument("--database", type=Path, default=Path(PATHS["database"]), help="HSPTL SQLite database path")
    args = parser.parse_args()
    engine = DeterministicIntelligenceEngine(args.database)
    port = TerminologyPort(db_path=args.database, kernel=EventKernel(engine))
    result = port.import_snomed_rf2(args.snapshot_dir, edition=args.edition,
        effective_time=args.effective_time, licensed_use_confirmed=args.confirm_licensed_use)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
