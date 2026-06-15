from calendar import monthrange
from datetime import datetime, timezone


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    last_day = monthrange(year, month)[1]
    return (
        datetime(year, month, 1, tzinfo=timezone.utc),
        datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc),
    )


def month_key_bounds(month_key: str) -> tuple[datetime, datetime]:
    year, month = (int(part) for part in month_key.split("-", 1))
    return month_bounds(year, month)


def months_ago_start(months: int, now: datetime | None = None) -> datetime:
    if months < 1:
        raise ValueError("months must be at least 1")
    now = now or datetime.now(timezone.utc)
    month_index = now.year * 12 + now.month - months
    year, zero_based_month = divmod(month_index, 12)
    return datetime(year, zero_based_month + 1, 1, tzinfo=timezone.utc)


def average_cycle_days(items) -> float:
    durations = []
    for item in items:
        if not item.created_at or not item.completed_at:
            continue
        created = _as_utc(item.created_at)
        completed = _as_utc(item.completed_at)
        if completed >= created:
            durations.append((completed - created).total_seconds() / 86400)
    return sum(durations) / len(durations) if durations else 0.0


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
