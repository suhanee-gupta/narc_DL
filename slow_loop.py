import threading
from user_context import UserContextStore
from config import SLOW_LOOP_INTERVAL_SEC


class SlowLoop:
    def __init__(self, context_store: UserContextStore,
                 interval_sec: int = SLOW_LOOP_INTERVAL_SEC):
        self.context_store = context_store
        self.interval_sec  = interval_sec
        self._timer: threading.Timer | None = None
        self._running = False

    def run_once(self) -> int:
        """Flush buffer → update user_vec + click_history → save profiles."""
        updated = self.context_store.flush_updates()
        print(f"[SlowLoop] Updated {updated} user profiles.")
        return updated

    def start_background(self) -> None:
        self._running = True
        self._schedule()
        print(f"[SlowLoop] Started — fires every {self.interval_sec}s.")

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()
        print("[SlowLoop] Stopped.")

    def _tick(self) -> None:
        if not self._running:
            return
        self.run_once()
        self._schedule()

    def _schedule(self) -> None:
        self._timer = threading.Timer(self.interval_sec, self._tick)
        self._timer.daemon = True
        self._timer.start()
