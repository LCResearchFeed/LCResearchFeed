# utils/date_normalizer.py

from datetime import datetime, date

def normalize_date(value):
    if not value:
        return None

    # Already datetime
    if isinstance(value, datetime):
        return value

    # Convert date() → datetime()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    # Try multiple string formats
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m", "%Y"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed
            except ValueError:
                continue

    # Unknown format → ignore
    return None
