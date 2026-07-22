"""
analytics.py

Derived analytics computed from all schedule_entries across every
upload: room utilization, department-wise distribution, peak meeting
hours, meeting success rate, conflict statistics, per-user activity,
and the datasets that back the Analytics page's visualizations
(meeting status, meetings-per-room, room utilization %, department
distribution, and the room/time-slot occupancy heatmap).
"""

from collections import Counter, defaultdict

import models
import parser as dataset_parser
import utils


def _hour_bucket(time_slot):
    """'09:30-10:30' -> '09:00'-style hour bucket for peak-hour analysis."""
    try:
        start = time_slot.split("-")[0]
        hour = start.split(":")[0]
        return f"{int(hour):02d}:00"
    except (ValueError, IndexError, AttributeError):
        return "Unknown"


def _hours_spanned(time_slot):
    """Every whole hour a time slot touches, e.g. '09:30-11:00' -> [9, 10]."""
    try:
        start, end, start_minutes, end_minutes = dataset_parser.parse_time_range(time_slot)
        if start_minutes is None:
            return []
        first_hour = start_minutes // 60
        # exclusive end hour: if it ends exactly on the hour, don't count that hour
        last_hour = (end_minutes - 1) // 60
        return list(range(first_hour, last_hour + 1))
    except (ValueError, TypeError):
        return []


def build_analytics():
    entries = models.get_all_schedule_entries()
    uploads = models.get_all_uploads()

    scheduled = [e for e in entries if e["status"] == "Scheduled"]
    conflicted = [e for e in entries if e["status"] == "Conflict"]

    # ---- Meeting status graph (Scheduled vs Conflict) ----------------
    meeting_status_counts = [
        {"status": "Scheduled", "count": len(scheduled)},
        {"status": "Conflict", "count": len(conflicted)},
    ]

    # ---- Meetings assigned per room (bar graph) -----------------------
    room_counts = Counter(e["assigned_room"] for e in scheduled if e.get("assigned_room"))
    room_utilization = sorted(
        [{"room": room, "meetings_hosted": count} for room, count in room_counts.items()],
        key=lambda r: r["meetings_hosted"], reverse=True,
    )

    # ---- Room utilization % (how full each room typically runs) -------
    room_attendee_sum = defaultdict(int)
    room_capacity_sum = defaultdict(int)
    for e in scheduled:
        room = e.get("assigned_room")
        if not room or not e.get("room_capacity") or not e.get("attendees"):
            continue
        room_attendee_sum[room] += e["attendees"]
        room_capacity_sum[room] += e["room_capacity"]

    room_capacity_utilization = sorted(
        [
            {
                "room": room,
                "utilization_pct": round((room_attendee_sum[room] / room_capacity_sum[room]) * 100, 1)
                if room_capacity_sum[room] else 0.0,
                "meetings_hosted": room_counts.get(room, 0),
            }
            for room in room_capacity_sum
        ],
        key=lambda r: r["utilization_pct"], reverse=True,
    )

    # ---- Department-wise meeting count graph ---------------------------
    dept_counts = Counter(e["department"] for e in entries if e.get("department"))
    department_distribution = sorted(
        [{"department": dept, "meetings": count} for dept, count in dept_counts.items()],
        key=lambda d: d["meetings"], reverse=True,
    )

    # ---- Room occupancy by time slot (heatmap) -------------------------
    heatmap_counts = defaultdict(int)
    rooms_seen = set()
    hours_seen = set()
    for e in scheduled:
        room = e.get("assigned_room")
        if not room:
            continue
        hours = _hours_spanned(e.get("time_slot", ""))
        if not hours:
            continue
        rooms_seen.add(room)
        for hour in hours:
            hours_seen.add(hour)
            heatmap_counts[(room, hour)] += 1

    heatmap_rooms = sorted(rooms_seen)
    heatmap_hours = sorted(hours_seen)
    occupancy_heatmap = {
        "rooms": heatmap_rooms,
        "hours": [f"{h:02d}:00" for h in heatmap_hours],
        "matrix": [
            [heatmap_counts.get((room, hour), 0) for hour in heatmap_hours]
            for room in heatmap_rooms
        ],
    }

    # ---- Peak meeting hours --------------------------------------------
    hour_counts = Counter(_hour_bucket(e.get("time_slot", "")) for e in entries)
    peak_hours = sorted(
        [{"hour": hour, "meetings": count} for hour, count in hour_counts.items()
         if hour != "Unknown"],
        key=lambda h: h["hour"],
    )

    # ---- Success / conflict rate ----------------------------------------
    total = len(entries)
    success_rate = round((len(scheduled) / total) * 100, 2) if total else 0.0
    conflict_rate = round((len(conflicted) / total) * 100, 2) if total else 0.0

    # ---- Conflict statistics by reason -----------------------------------
    reason_counts = Counter(e.get("conflict_reason") or "Unspecified" for e in conflicted)
    conflict_reasons = [
        {"reason": reason, "count": count} for reason, count in reason_counts.most_common()
    ]

    # ---- User activity statistics ------------------------------------------
    user_upload_counts = Counter(u["username"] for u in uploads)
    user_activity = sorted(
        [{"username": user, "uploads": count} for user, count in user_upload_counts.items()],
        key=lambda u: u["uploads"], reverse=True,
    )

    return {
        "meeting_status_counts": meeting_status_counts,
        "room_utilization": room_utilization,
        "room_capacity_utilization": room_capacity_utilization,
        "department_distribution": department_distribution,
        "occupancy_heatmap": occupancy_heatmap,
        "peak_hours": peak_hours,
        "meeting_success_rate": success_rate,
        "meeting_conflict_rate": conflict_rate,
        "conflict_reasons": conflict_reasons,
        "user_activity": user_activity,
        "total_meetings_analyzed": total,
    }
