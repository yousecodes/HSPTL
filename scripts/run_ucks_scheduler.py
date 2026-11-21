"""Run one UCKS scheduled-feed cycle against the local HSPTL API.

Intended for Windows Task Scheduler or cron. It does not create a resident
background process; invoke periodically (e.g. every 5-15 minutes).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.hsptl_core.config import DEFAULT_HOST, resolve_port  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run due HSPTL UCKS feed, connector and provider-health checks")
    parser.add_argument("--base-url", default=f"http://{DEFAULT_HOST}:{resolve_port()}",
                        help="Local HSPTL API base URL (default: loopback, honoring HSPTL_PORT)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--loop", action="store_true", help="Keep the scheduler process running and repeat cycles")
    parser.add_argument("--interval-minutes", type=int, default=15, help="Interval between cycles in loop mode (5..1440)")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or not 5 <= args.timeout <= 300:
        parser.error("--limit must be 1..100 and --timeout 5..300")
    if not 5 <= args.interval_minutes <= 1440:
        parser.error("--interval-minutes must be 5..1440")
    if not args.base_url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
        parser.error("Scheduler helper is restricted to a loopback HTTP API address")
    base = args.base_url.rstrip("/")
    def run_cycle() -> int:
        try:
            outputs = {}
            for name, path in (("feeds", "/api/ucks/scheduler/run-due"),
                               ("connectors", "/api/ucks/connectors/run-due")):
                response = requests.post(base + path, params={"limit": args.limit}, timeout=args.timeout)
                response.raise_for_status()
                outputs[name] = response.json()
            health = requests.get(base + "/api/tools/providers/health", params={"probe": "true"}, timeout=min(args.timeout, 30))
            health.raise_for_status()
            outputs["provider_health"] = health.json()
            print(json.dumps(outputs, indent=2, ensure_ascii=False), flush=True)
            return 0
        except requests.RequestException as exc:
            print(f"UCKS scheduler failed: {exc}", file=sys.stderr, flush=True)
            return 1

    if not args.loop:
        return run_cycle()
    print(f"HSPTL UCKS scheduler running; interval={args.interval_minutes} minutes. Press Ctrl+C to stop.", flush=True)
    failures = 0
    try:
        while True:
            failures = 0 if run_cycle() == 0 else failures + 1
            # Back off failed cycles without exceeding the configured interval.
            delay = min(args.interval_minutes * 60, 60 * (2 ** min(failures, 4))) if failures else args.interval_minutes * 60
            time.sleep(delay)
    except KeyboardInterrupt:
        print("HSPTL UCKS scheduler stopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
