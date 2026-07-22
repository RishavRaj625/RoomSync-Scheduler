"""
scheduler.py

Algorithm Used:
- Optimized Best-Fit Greedy Scheduling
- Capacity-indexed room groups
- Min-Heap based room availability

Time Complexity:
- Parsing: O(N)
- Sorting Rooms: O(R log R)
- Sorting Meetings: O(M log M)
- Allocation: Target approximately O(M log R)

Space Complexity:
- O(R + M)

Implements the Best-Fit Greedy Scheduling Algorithm for the Meeting Room
Allocation System.

Scheduling workflow
-------------------
1. Sort rooms by capacity and group them into capacity-indexed buckets.
2. Sort meetings chronologically by precomputed start minute.
3. For each meeting, binary-search the smallest capacity bucket that can fit
   the attendee count (best-fit starts at the minimum sufficient capacity).
4. Within each bucket, use a min-heap keyed by (max_end, order_index) to
   quickly find rooms that are already idle before the meeting start; fall
   back to a deterministic order_index scan with O(log B) overlap checks when
   every room still has a booking ending after the meeting start.
5. If no suitable room is found, record the meeting as a conflict.

Why these data structures
-------------------------
- Capacity buckets + bisect_left: skip undersized rooms in O(log C) time,
  where C is the number of distinct capacities (C <= R).
- Per-room sorted booking lists: meetings are processed in nondecreasing start
  order, so appending keeps intervals sorted and enables O(log B) overlap checks
  via bisect on neighboring bookings only.
- Min-heap per capacity bucket: rooms with max_end <= meeting_start are provably
  free (all prior bookings ended), so the heap surfaces idle rooms in O(log R)
  time instead of scanning every peer in the bucket.
- order_index tie-breaking: preserves deterministic best-fit output when several
  rooms share the same capacity.
"""

from __future__ import annotations

import heapq
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


@dataclass(frozen=True)
class RoomOption:
    """Compact room record avoids repeated pandas row access in hot loops."""

    room_id: Any
    capacity: int
    order_index: int


PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


@dataclass(frozen=True)
class MeetingRequest:
    """Compact meeting record caches fields used repeatedly by allocation."""

    meeting_id: Any
    employee_name: Any
    department: Any
    attendees: int
    time_slot: str
    start_time: Any
    end_time: Any
    start_minutes: int
    end_minutes: int
    duration_minutes: int
    priority: str = "Medium"


@dataclass
class RoomState:
    """
    Mutable per-room scheduling state.

    max_end tracks the latest booking end across the room. When a new meeting
    starts at or after max_end, every existing booking has already finished, so
    the room is available without an overlap scan.
    """

    room_id: Any
    capacity: int
    order_index: int
    bookings: List[Tuple[int, int]] = field(default_factory=list)
    starts: List[int] = field(default_factory=list)
    max_end: int = 0


class CapacityBucket:
    """
    Rooms that share one capacity value.

    The availability heap orders rooms by (max_end, order_index, room_id).
    max_end acts as each room's next-available boundary: if a meeting starts
    at or after max_end, the room is idle. order_index preserves deterministic
    best-fit tie-breaking among rooms of equal capacity.

    Complexity
    ----------
    find_available: O(B log H + H log H) worst case, where B is rooms in the
    bucket and H is heap size; often O(log H) when a heap fast-path hit occurs.
    assign: O(log B) for heap push plus O(1) append to sorted booking lists.
    """

    __slots__ = ("capacity", "_rooms", "_room_order", "_availability_heap")

    def __init__(self, capacity: int, rooms: Sequence[RoomState]) -> None:
        self.capacity = capacity
        self._rooms: Dict[Any, RoomState] = {room.room_id: room for room in rooms}
        self._room_order = sorted(rooms, key=lambda room: room.order_index)
        self._availability_heap: List[Tuple[int, int, Any]] = []
        for room in self._room_order:
            self._push_heap_entry(room)

    def _push_heap_entry(self, room: RoomState) -> None:
        heapq.heappush(
            self._availability_heap,
            (room.max_end, room.order_index, room.room_id),
        )

    def find_available(self, start: int, end: int) -> Optional[RoomState]:
        """
        Return the first available room in best-fit tie order for [start, end).

        Phase 1 (heap): collect idle rooms with max_end <= start and pick the
        smallest order_index among them.
        Phase 2 (scan): walk remaining rooms in order_index order and use binary
        search overlap detection for rooms that may still have a gap.
        """
        deferred: List[Tuple[int, int, Any]] = []
        chosen: Optional[RoomState] = None

        while self._availability_heap and self._availability_heap[0][0] <= start:
            max_end, order_index, room_id = heapq.heappop(self._availability_heap)
            room = self._rooms[room_id]

            if room.max_end != max_end:
                self._push_heap_entry(room)
                continue

            deferred.append((order_index, max_end, room_id))

        if deferred:
            deferred.sort(key=lambda item: (item[0], item[2]))
            _, _, chosen_id = deferred[0]
            chosen = self._rooms[chosen_id]

            for order_index, max_end, room_id in deferred[1:]:
                heapq.heappush(
                    self._availability_heap,
                    (max_end, order_index, room_id),
                )
            return chosen

        for room in self._room_order:
            if room.max_end <= start:
                return room
            if not _has_overlap(room.starts, room.bookings, start, end):
                return room

        return None

    def assign(self, room: RoomState, start: int, end: int) -> None:
        """Record a booking and refresh the room's heap entry."""
        room.bookings.append((start, end))
        room.starts.append(start)
        room.max_end = max(room.max_end, end)
        self._push_heap_entry(room)


class BestFitScheduler:
    """
    Capacity-indexed best-fit greedy scheduler.

    Complexity
    ----------
    Construction: O(R log R) for sorting and bucket creation.
    schedule_all: O(M log M + M * (log R + average bucket work)).
    """

    __slots__ = ("_capacities", "_buckets", "_max_capacity")

    def __init__(self, rooms: Sequence[RoomOption]) -> None:
        bucket_map: Dict[int, List[RoomState]] = {}
        for room in rooms:
            bucket_map.setdefault(room.capacity, []).append(
                RoomState(
                    room_id=room.room_id,
                    capacity=room.capacity,
                    order_index=room.order_index,
                )
            )

        self._capacities = sorted(bucket_map)
        self._buckets = {
            capacity: CapacityBucket(capacity, bucket_map[capacity])
            for capacity in self._capacities
        }
        self._max_capacity = self._capacities[-1] if self._capacities else 0

    @property
    def max_capacity(self) -> int:
        return self._max_capacity

    def has_capacity_for(self, attendees: int) -> bool:
        """True when at least one room meets the attendee requirement."""
        return bisect_left(self._capacities, attendees) < len(self._capacities)

    def assign(self, meeting: MeetingRequest) -> Optional[Tuple[Any, int]]:
        """
        Assign one meeting to the smallest sufficient available room.

        Returns (room_id, capacity) on success, otherwise None.
        Complexity: O(log R + B) where B is rooms checked in visited buckets.
        """
        first_feasible = bisect_left(self._capacities, meeting.attendees)

        for capacity in self._capacities[first_feasible:]:
            bucket = self._buckets[capacity]
            room = bucket.find_available(meeting.start_minutes, meeting.end_minutes)
            if room is not None:
                bucket.assign(room, meeting.start_minutes, meeting.end_minutes)
                return room.room_id, room.capacity

        return None


def _time_to_minutes(value):
    """Fallback for older DataFrames that do not yet include minute columns."""
    return value.hour * 60 + value.minute


def _meeting_records(meetings_df):
    """
    Convert meeting rows once before scheduling.

    Complexity: O(M log M) for chronological sorting plus O(M) conversion.
    """
    if meetings_df is None or meetings_df.empty:
        return []

    records = meetings_df.to_dict("records")
    meetings = []
    for record in records:
        start_minutes = record.get("start_minutes")
        end_minutes = record.get("end_minutes")
        if start_minutes is None or pd.isna(start_minutes):
            start_minutes = _time_to_minutes(record["start_time"])
        if end_minutes is None or pd.isna(end_minutes):
            end_minutes = _time_to_minutes(record["end_time"])

        priority = record.get("priority") or "Medium"
        duration = record.get("duration_minutes")
        if duration is None or (isinstance(duration, float) and pd.isna(duration)):
            duration = int(end_minutes) - int(start_minutes)

        meetings.append(
            MeetingRequest(
                meeting_id=record["meeting_id"],
                employee_name=record.get("employee_name", "Unknown"),
                department=record["department"],
                attendees=int(record["attendees"]),
                time_slot=record["time_slot"],
                start_time=record["start_time"],
                end_time=record["end_time"],
                start_minutes=int(start_minutes),
                end_minutes=int(end_minutes),
                duration_minutes=int(duration),
                priority=priority,
            )
        )

    # Higher-priority meetings are offered rooms first; ties keep
    # chronological order so the best-fit heap logic stays deterministic.
    meetings.sort(
        key=lambda m: (PRIORITY_RANK.get(m.priority, 1), m.start_minutes)
    )
    return meetings


def _room_options(rooms_df):
    """
    Sort rooms once and assign stable order_index values for tie-breaking.

    Complexity: O(R log R).
    """
    rooms_sorted = rooms_df.sort_values(by="capacity", ascending=True, kind="mergesort")
    rooms = [
        RoomOption(
            room_id=record["room_id"],
            capacity=int(record["capacity"]),
            order_index=index,
        )
        for index, record in enumerate(rooms_sorted.to_dict("records"))
    ]
    return rooms


def _has_overlap(starts: Sequence[int], bookings: Sequence[Tuple[int, int]], start: int, end: int) -> bool:
    """
    Check overlap in O(log B) by inspecting only adjacent sorted bookings.

    In a start-sorted interval list, only the booking immediately before the
    insertion point and the booking at the insertion point can overlap a new
    interval.
    """
    insert_at = bisect_left(starts, start)

    if insert_at > 0 and bookings[insert_at - 1][1] > start:
        return True

    if insert_at < len(bookings) and bookings[insert_at][0] < end:
        return True

    return False


def _build_schedule_row(meeting, assigned_room, assigned_capacity, status):
    """Create a consistent schedule row for both successful and conflicted meetings."""
    return {
        "meeting_id": meeting.meeting_id,
        "employee_name": meeting.employee_name,
        "department": meeting.department,
        "assigned_room": assigned_room,
        "attendees": meeting.attendees,
        "room_capacity": assigned_capacity,
        "duration_minutes": meeting.duration_minutes,
        "time_slot": meeting.time_slot,
        "start_time": meeting.start_time,
        "end_time": meeting.end_time,
        "start_minutes": meeting.start_minutes,
        "end_minutes": meeting.end_minutes,
        "priority": meeting.priority,
        "status": status,
    }


def _build_conflict_row(meeting, reason):
    """Create a consistent conflict row for unscheduled meetings."""
    return {
        "meeting_id": meeting.meeting_id,
        "employee_name": meeting.employee_name,
        "department": meeting.department,
        "attendees": meeting.attendees,
        "requested_time": meeting.time_slot,
        "priority": meeting.priority,
        "reason": reason,
    }


def schedule_meetings(rooms_df, meetings_df):
    """
    Run the optimized best-fit greedy scheduling algorithm.

    Parameters
    ----------
    rooms_df : pd.DataFrame
        Columns: room_id, capacity
    meetings_df : pd.DataFrame
        Columns: meeting_id, department, attendees, time_slot,
                 start_time, end_time, start_minutes, end_minutes

    Returns
    -------
    tuple(pd.DataFrame, pd.DataFrame)
        schedule_df  -> one row per meeting, with assigned room and status
        conflicts_df -> one row per unscheduled meeting, with a reason

    Complexity: O(R log R + M log M + M log R) target for the full pipeline.
    """
    schedule_rows = []
    conflict_rows = []

    if rooms_df is None or rooms_df.empty or meetings_df is None or meetings_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    rooms = _room_options(rooms_df)
    meetings = _meeting_records(meetings_df)
    scheduler = BestFitScheduler(rooms)

    for meeting in meetings:
        assignment = scheduler.assign(meeting)

        if assignment is not None:
            assigned_room, assigned_capacity = assignment
            schedule_rows.append(
                _build_schedule_row(
                    meeting,
                    assigned_room,
                    assigned_capacity,
                    "Scheduled",
                )
            )
        else:
            reason = _determine_conflict_reason(
                meeting,
                scheduler.has_capacity_for(meeting.attendees),
                scheduler.max_capacity,
            )
            conflict_rows.append(_build_conflict_row(meeting, reason))
            schedule_rows.append(
                _build_schedule_row(
                    meeting,
                    "N/A",
                    None,
                    "Conflict",
                )
            )

    schedule_df = pd.DataFrame(schedule_rows)
    conflicts_df = pd.DataFrame(conflict_rows)

    return schedule_df, conflicts_df


def _determine_conflict_reason(meeting, has_fitting_room, max_capacity):
    """Build a human-readable explanation without rescanning room data."""
    if not has_fitting_room:
        return (
            f"No room has sufficient capacity ({meeting.attendees} attendees "
            f"requested, largest room holds {max_capacity})."
        )

    return (
        f"All rooms large enough for {meeting.attendees} attendees were "
        f"already booked during {meeting.time_slot}."
    )


def detect_conflicts(schedule_df):
    """
    Independent verification pass over a generated schedule.

    Confirms that no two 'Scheduled' meetings assigned to the same room
    have overlapping time slots. This acts as a safety net / sanity check
    on top of the allocation performed in schedule_meetings().

    Complexity: O(S log S) for S scheduled meetings due to sorting, then O(S)
    for adjacent interval checks. Memory is O(S) for record conversion.

    Parameters
    ----------
    schedule_df : pd.DataFrame
        Output of schedule_meetings() (the schedule_df return value).

    Returns
    -------
    list[str]
        Descriptions of any double-booking issues found. Empty if the
        schedule is internally consistent.
    """
    issues = []

    if schedule_df is None or schedule_df.empty:
        return issues

    scheduled = schedule_df[schedule_df["status"] == "Scheduled"].copy()
    if scheduled.empty:
        return issues

    if "start_minutes" not in scheduled.columns:
        scheduled["start_minutes"] = scheduled["start_time"].map(_time_to_minutes)
    if "end_minutes" not in scheduled.columns:
        scheduled["end_minutes"] = scheduled["end_time"].map(_time_to_minutes)

    scheduled = scheduled.sort_values(["assigned_room", "start_minutes"])

    for room_id, group in scheduled.groupby("assigned_room", sort=False):
        rows = group.to_dict("records")
        for current_row, next_row in zip(rows, rows[1:]):
            if int(current_row["end_minutes"]) > int(next_row["start_minutes"]):
                issues.append(
                    f"Room {room_id}: '{current_row['meeting_id']}' overlaps "
                    f"with '{next_row['meeting_id']}'."
                )

    return issues
