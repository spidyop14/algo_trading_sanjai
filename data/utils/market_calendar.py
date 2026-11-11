from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

class NSEMarketCalendar:
    def __init__(self, holidays: set[str] | None = None): self.holidays = holidays or set()
    def status(self, at: datetime | None = None) -> str:
        at = (at or datetime.now(IST)).astimezone(IST)
        if at.weekday() >= 5 or at.date().isoformat() in self.holidays: return "CLOSED"
        now = at.time()
        if time(9, 0) <= now < time(9, 15): return "PRE_MARKET"
        if time(9, 15) <= now <= time(15, 30): return "OPEN"
        return "CLOSED"
    def is_open(self, at: datetime | None = None) -> bool: return self.status(at) == "OPEN"
