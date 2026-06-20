import re
from datetime import datetime, timedelta, timezone


def parse_time_reference(query: str) -> str:
    """
    Detects temporal references in a user query.
    Returns one of: 'today', 'yesterday', 'this_week', 'last_week', 'none'.
    """
    q = query.lower().strip()

    if re.search(r'\btoday\b', q) or re.search(r'\bthis morning\b', q) or re.search(r'\btonight\b', q):
        return "today"
    if re.search(r'\byesterday\b', q):
        return "yesterday"
    if re.search(r'\blast week\b', q):
        return "last_week"
    if re.search(r'\bthis week\b', q):
        return "this_week"

    return "none"


def get_time_range(reference: str) -> tuple[datetime, datetime] | None:
    """
    Returns (start, end) datetime range for a given temporal reference.
    All times are in UTC.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if reference == "today":
        return (today_start, now)
    elif reference == "yesterday":
        yesterday_start = today_start - timedelta(days=1)
        return (yesterday_start, today_start)
    elif reference == "this_week":
        # Monday of this week
        week_start = today_start - timedelta(days=now.weekday())
        return (week_start, now)
    elif reference == "last_week":
        this_week_start = today_start - timedelta(days=now.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        return (last_week_start, this_week_start)

    return None
