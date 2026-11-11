import threading
from time import sleep
from backend.core.logger import get_logger
from data.utils.market_calendar import NSEMarketCalendar

class PaperTradingScheduler:
    _lock = threading.Lock(); _thread = None; _stop = threading.Event()
    def __init__(self, process_once, interval_seconds=300, calendar=None): self.process_once, self.interval_seconds, self.calendar = process_once, interval_seconds, calendar or NSEMarketCalendar(); self.log = get_logger("orbit.paper_scheduler")
    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive(): return False
            self._stop.clear(); self._thread = threading.Thread(target=self._loop, daemon=True, name="orbit-paper-scheduler"); self._thread.start(); return True
    def stop(self): self._stop.set()
    def _loop(self):
        while not self._stop.is_set():
            try:
                if self.calendar.is_open(): self.process_once()
            except Exception as error: self.log.error("paper_scheduler_error=%s", error)
            self._stop.wait(self.interval_seconds)
