from datetime import datetime, timezone


def format_local(iso_string):
    if not iso_string:
        return iso_string

    dt = datetime.fromisoformat(iso_string)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
