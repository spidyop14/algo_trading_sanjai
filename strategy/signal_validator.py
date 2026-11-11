from datetime import datetime, timedelta, timezone

def valid_frame(frame, minimum: int) -> bool: return frame is not None and len(frame) >= minimum and frame[["open", "high", "low", "close", "volume"]].notna().all().all()
def stale(timestamp, max_age: timedelta, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None: return True
    return now - timestamp.astimezone(timezone.utc) > max_age
