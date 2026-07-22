"""
dashboard.py

Computes the headline statistics shown on the main dashboard: user
counts, upload/schedule totals, success/failure/conflict counts,
average processing time, and "most active" style leaderboards.
"""

from collections import Counter

import models


def build_dashboard_stats():
    users = models.get_all_users()
    uploads = models.get_all_uploads()
    entries = models.get_all_schedule_entries()

    total_users = len(users)
    new_users = sum(1 for u in users if u["created_at"] == u["last_active"])
    returning_users = total_users - new_users

    total_files = len(uploads)
    schedules_generated = sum(1 for u in uploads if u["schedule_status"] == "Generated")

    successful_allocations = sum(1 for e in entries if e["status"] == "Scheduled")
    failed_allocations = sum(1 for e in entries if e["status"] == "Conflict")
    conflicts_detected = failed_allocations

    processing_times = [u["processing_time_ms"] for u in uploads if u["processing_time_ms"]]
    avg_processing_time = (
        sum(processing_times) / len(processing_times) if processing_times else 0
    )

    upload_counts = Counter(u["username"] for u in uploads)
    most_active_user = upload_counts.most_common(1)[0][0] if upload_counts else "N/A"

    room_counts = Counter(
        e["assigned_room"] for e in entries if e.get("assigned_room")
    )
    most_used_room = room_counts.most_common(1)[0][0] if room_counts else "N/A"

    departments = {e["department"] for e in entries if e.get("department")}
    meeting_ids = {e["meeting_id"] for e in entries}

    return {
        "total_users": total_users,
        "new_users": new_users,
        "returning_users": returning_users,
        "user_names": [u["username"] for u in users],
        "total_uploaded_files": total_files,
        "total_schedules_generated": schedules_generated,
        "successful_allocations": successful_allocations,
        "failed_allocations": failed_allocations,
        "scheduling_conflicts_detected": conflicts_detected,
        "average_processing_time_ms": round(avg_processing_time, 2),
        "most_active_user": most_active_user,
        "most_used_meeting_room": most_used_room,
        "total_departments": len(departments),
        "total_meetings_scheduled": len(meeting_ids),
    }
