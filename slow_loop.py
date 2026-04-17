"""
Slow loop — runs every SLOW_LOOP_INTERVAL_SEC (default 1 hour).

Drains the interaction buffer in UserContextStore, updates all user
context vectors, persists them to disk, and optionally resets the bandit.

Can be triggered manually (run_once) or started as a background daemon thread.
"""

import threading
from user_context import UserContextStore
from bandits import LinUCBBandit
from config import SLOW_LOOP_INTERVAL_SEC


class SlowLoop:
    def __init__(
        self,
        context_store: UserContextStore,
        bandit: LinUCBBandit,
        interval_sec: int = SLOW_LOOP_INTERVAL_SEC,
        persist_path: str = "user_contexts.npz",
        reset_bandit: bool = False,
    ):
        self.context_store = context_store
        self.bandit = bandit
        self.interval_sec = interval_sec
        self.persist_path = persist_path
        self.reset_bandit = reset_bandit
        self._timer: threading.Timer | None = None
        self._running = False

    def run_once(self) -> int:
        """
        Flush the interaction buffer, update all user context vectors,
        persist to disk, and optionally reset the bandit.
        Returns the number of user vectors that changed.
        """
        updated = self.context_store.flush_updates()
        self.context_store.save(self.persist_path)
        if self.reset_bandit:
            self.bandit.reset()
        return updated

    def start_background(self) -> None:
        """Start the periodic slow loop as a background daemon thread."""
        self._running = True
        self._schedule()
        print(f"[SlowLoop] Started — fires every {self.interval_sec}s.")

    def stop(self) -> None:
        """Cancel the background timer."""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
        print("[SlowLoop] Stopped.")

    def _tick(self) -> None:
        if not self._running:
            return
        n = self.run_once()
        print(f"[SlowLoop] Updated {n} user context vectors → {self.persist_path}")
        self._schedule()

    def _schedule(self) -> None:
        self._timer = threading.Timer(self.interval_sec, self._tick)
        self._timer.daemon = True
        self._timer.start()
