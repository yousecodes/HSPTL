"""In-process scheduling for the synthetic data factory.

No external cron, no cloud scheduler, no separate daemon. One daemon thread
wakes on a fixed interval, queues any due schedule, and lets the existing job
runner execute it. It starts automatically with the local application; set
``HSPTL_DISABLE_BACKGROUND_WORKERS=1`` only for tests or maintenance.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger("hsptl.synthetic.scheduler")

TICK_SECONDS = float(os.environ.get("HSPTL_SYNTHETIC_SCHEDULER_TICK", "60"))


class SyntheticScheduler:
    def __init__(self, factory, *, tick_seconds: float = TICK_SECONDS):
        self.factory = factory
        self.tick_seconds = max(5.0, tick_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> threading.Thread | None:
        if os.environ.get("HSPTL_DISABLE_BACKGROUND_WORKERS", "") == "1":
            return None
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="hsptl-synthetic-scheduler")
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.wait(self.tick_seconds):
            try:
                queued = self.factory.run_due_schedules()
                if queued:
                    logger.info("Queued %d synthetic schedule(s)", len(queued))
            except Exception:  # noqa: BLE001 - the scheduler must never die
                logger.exception("Synthetic scheduler tick failed")

    def run_once(self) -> list[dict]:
        """Synchronous tick, used by tests and by the manual run-due endpoint."""
        return self.factory.run_due_schedules()


def start_scheduler(factory) -> threading.Thread | None:
    return SyntheticScheduler(factory).start()
