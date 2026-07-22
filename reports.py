"""
reports.py

Builds the exportable report content for a generated schedule. Kept
separate from download.py: this module builds the *content* (strings),
download.py is the thin Flask layer that streams it back as a file.
"""

import csv
import io

REPORT_COLUMNS = [
    ("meeting_id", "Meeting ID"),
    ("employee_name", "Employee Name"),
    ("department", "Department"),
    ("assigned_room", "Meeting Room"),
    ("room_capacity", "Room Capacity"),
    ("duration_minutes", "Duration (min)"),
    ("time_slot", "Time Slot"),
    ("status", "Allocation Status"),
    ("conflict_reason", "Conflict Reason"),
]


def build_csv(entries):
    """Return CSV text for a list of schedule_entries dicts."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in REPORT_COLUMNS])
    for entry in entries:
        writer.writerow([entry.get(key, "") for key, _ in REPORT_COLUMNS])
    return buffer.getvalue()


def build_txt(entries):
    """Return a human-readable fixed-width text report."""
    lines = []
    header = " | ".join(label for _, label in REPORT_COLUMNS)
    lines.append(header)
    lines.append("-" * len(header))
    for entry in entries:
        row = " | ".join(str(entry.get(key, "") or "") for key, _ in REPORT_COLUMNS)
        lines.append(row)
    return "\n".join(lines) + "\n"
