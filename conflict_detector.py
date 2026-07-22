"""
conflict_detector.py

Independent conflict-checking layer that sits on top of scheduler.py.
scheduler.py already avoids double-booking while allocating, but this
module re-verifies the final schedule and produces the human-readable
conflict/rejection reasons shown in the UI and stored in the database.
"""

import scheduler


def verify_no_double_booking(schedule_df):
    """
    Re-check the generated schedule for overlapping bookings in the same
    room. Returns a list of description strings (empty if clean).
    """
    return scheduler.detect_conflicts(schedule_df)


def build_conflict_summary(conflicts_df):
    """
    Turn the conflicts DataFrame produced by scheduler.schedule_meetings()
    into a list of dicts ready for display / storage.
    """
    if conflicts_df is None or conflicts_df.empty:
        return []
    return conflicts_df.to_dict("records")


def capacity_violations(rooms_df, meetings_df):
    """Meetings that could never fit in any room, regardless of time."""
    if rooms_df is None or rooms_df.empty or meetings_df is None or meetings_df.empty:
        return []

    max_capacity = rooms_df["capacity"].max()
    oversized = meetings_df[meetings_df["attendees"] > max_capacity]
    return [
        {
            "meeting_id": row["meeting_id"],
            "employee_name": row.get("employee_name", "Unknown"),
            "attendees": row["attendees"],
            "reason": (
                f"Requested {row['attendees']} attendees exceeds the largest "
                f"room capacity of {max_capacity}."
            ),
        }
        for _, row in oversized.iterrows()
    ]
