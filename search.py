"""
search.py

Search and filter logic for the "Schedule Results" and "Search & Filter"
screens. Works on plain lists of dicts (already loaded from the database
via models.py) so it stays framework-agnostic and easy to unit test.
"""


def _matches(value, query):
    return query.lower() in str(value).lower() if value is not None else False


def search_schedule_entries(entries, query="", department="", status="",
                             room="", employee="", time_slot=""):
    """Filter schedule_entries rows by any combination of criteria."""
    results = entries

    if department:
        results = [e for e in results if _matches(e.get("department"), department)]
    if status:
        results = [e for e in results if _matches(e.get("status"), status)]
    if room:
        results = [e for e in results if _matches(e.get("assigned_room"), room)]
    if employee:
        results = [e for e in results if _matches(e.get("employee_name"), employee)]
    if time_slot:
        results = [e for e in results if _matches(e.get("time_slot"), time_slot)]

    if query:
        q = query.lower()
        results = [
            e for e in results
            if q in str(e.get("meeting_id", "")).lower()
            or q in str(e.get("employee_name", "")).lower()
            or q in str(e.get("department", "")).lower()
            or q in str(e.get("assigned_room", "")).lower()
            or q in str(e.get("time_slot", "")).lower()
            or q in str(e.get("status", "")).lower()
        ]

    return results


def sort_entries(entries, sort_by="meeting_id", descending=False):
    """Sort a list of dict rows by any key, tolerating missing/None values."""
    def key(entry):
        value = entry.get(sort_by)
        return (value is None, value)

    return sorted(entries, key=key, reverse=descending)


def search_uploads(uploads, query="", username="", filename="", status=""):
    """Filter upload-history rows by any combination of criteria."""
    results = uploads

    if username:
        results = [u for u in results if _matches(u.get("username"), username)]
    if filename:
        results = [u for u in results if _matches(u.get("original_filename"), filename)]
    if status:
        results = [u for u in results if _matches(u.get("processing_status"), status)]

    if query:
        q = query.lower()
        results = [
            u for u in results
            if q in str(u.get("username", "")).lower()
            or q in str(u.get("original_filename", "")).lower()
            or q in str(u.get("processing_status", "")).lower()
            or q in str(u.get("schedule_status", "")).lower()
        ]

    return results


def paginate(items, page=1, page_size=25):
    """Simple in-memory pagination; returns (page_items, total_pages)."""
    page = max(1, page)
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    return items[start:start + page_size], total_pages, page
