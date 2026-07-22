"""
parser.py

Parses and performs line-level validation of the raw .txt dataset.

Expected format
---------------
    ROOMS
    R101,20
    R102,10

    MEETINGS
    M001,John Doe,HR,15,09:00-10:00,High
    M002,Jane Smith,Finance,8,09:00-10:00,Medium

Each meeting line is:
    MeetingID,Employee,Department,Attendees,Time,Priority

Priority is optional (defaults to "Medium") and legacy 4-field lines of
the form "MeetingID,Department,Attendees,Time" (no employee/priority)
are still accepted for backward compatibility -- the employee is set to
"Unknown" in that case.

Resilience policy
-----------------
Real-world uploads are messy: blank fields, the literal string "NULL",
negative numbers, non-numeric text, missing keys, etc. Rather than
rejecting the whole file the first time any single line looks wrong,
each row is handled individually:

  * REPAIRABLE issues (a sensible, safe default exists) are fixed
    automatically and the row is kept -- e.g. a missing department
    becomes "Unspecified", an invalid priority becomes "Medium".
  * NON-REPAIRABLE issues (no safe default -- e.g. a missing ID, an
    invalid capacity/attendee count, a broken time range) cause that
    single row to be skipped. The rest of the file is still processed.
  * Only a handful of dataset-wide conditions are FATAL and block the
    whole upload: an empty file, or a file that yields zero usable
    rooms or zero usable meetings once bad rows are removed.

Two entry points are provided:
    parse_dataset(raw_text)            -> (rooms_df, meetings_df, warnings)
    validate_dataset(rooms, meetings)  -> (fatal_errors, extra_warnings)

`warnings` is a list of dicts: {"line", "entity", "id", "action", "message"}
`action` is one of "repaired", "skipped", "flagged", or "fatal".
"""

from datetime import datetime

import pandas as pd

import config


NULL_LITERALS = {"", "null", "n/a", "na", "none", "-"}


def _is_null(value):
    """True for blank strings and common 'null' spellings (case-insensitive)."""
    if value is None:
        return True
    return value.strip().lower() in NULL_LITERALS


def _parse_hhmm(value):
    hour_str, minute_str = value.strip().split(":")
    hour = int(hour_str)
    minute = int(minute_str)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError
    return hour * 60 + minute


def _minutes_to_datetime(minutes):
    return datetime(1900, 1, 1, minutes // 60, minutes % 60)


def parse_time_range(time_str):
    """Parse 'HH:MM-HH:MM' -> (start, end, start_minutes, end_minutes)."""
    try:
        if _is_null(time_str):
            raise ValueError
        start_str, end_str = time_str.split("-")
        start_minutes = _parse_hhmm(start_str)
        end_minutes = _parse_hhmm(end_str)
        start = _minutes_to_datetime(start_minutes)
        end = _minutes_to_datetime(end_minutes)
        return start, end, start_minutes, end_minutes
    except (ValueError, AttributeError):
        return None, None, None, None


def _warn(warnings, line_no, entity, entity_id, action, message):
    warnings.append({
        "line": line_no,
        "entity": entity,
        "id": entity_id,
        "action": action,
        "message": message,
    })


def parse_dataset(raw_text):
    """
    Parse the raw dataset text into rooms and meetings DataFrames.

    Bad rows are repaired when a safe default exists, otherwise skipped
    (never crash the whole upload over a single messy line). See the
    module docstring's "Resilience policy" for the exact rules.

    Returns
    -------
    tuple(pd.DataFrame, pd.DataFrame, list[dict])
        rooms_df    -> room_id, capacity
        meetings_df -> meeting_id, employee_name, department, attendees,
                       time_slot, start_time, end_time, start_minutes,
                       end_minutes, duration_minutes, priority
        warnings    -> structured, human-readable notices for every row
                       that was repaired or skipped (see module docstring)
    """
    warnings = []
    rooms = []
    meetings = []

    if raw_text is None or not raw_text.strip():
        return pd.DataFrame(), pd.DataFrame(), [{
            "line": 0, "entity": "file", "id": None, "action": "fatal",
            "message": "The uploaded file is empty.",
        }]

    lines = [line.strip() for line in raw_text.splitlines()]
    section = None

    seen_room_ids = set()
    seen_meeting_ids = set()

    for line_no, line in enumerate(lines, start=1):
        if not line:
            continue

        upper = line.upper()
        if upper == "ROOMS":
            section = "ROOMS"
            continue
        if upper == "MEETINGS":
            section = "MEETINGS"
            continue

        if section == "ROOMS":
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2:
                _warn(warnings, line_no, "room", None, "skipped",
                      f"Line {line_no}: Invalid room entry '{line}' "
                      "(expected format: RoomID,Capacity) \u2014 row skipped.")
                continue

            room_id, capacity_str = parts

            if _is_null(room_id):
                _warn(warnings, line_no, "room", None, "skipped",
                      f"Line {line_no}: Missing room ID \u2014 row skipped.")
                continue

            if room_id in seen_room_ids:
                _warn(warnings, line_no, "room", room_id, "skipped",
                      f"Line {line_no}: Duplicate room ID '{room_id}' \u2014 row skipped.")
                continue

            if _is_null(capacity_str):
                _warn(warnings, line_no, "room", room_id, "skipped",
                      f"Line {line_no}: Missing capacity for room '{room_id}' "
                      "\u2014 row skipped (no safe default for capacity).")
                continue

            try:
                capacity = int(capacity_str)
                if capacity <= 0:
                    raise ValueError
            except ValueError:
                _warn(warnings, line_no, "room", room_id, "skipped",
                      f"Line {line_no}: Invalid capacity '{capacity_str}' for room "
                      f"'{room_id}' (must be a positive integer) \u2014 row skipped.")
                continue

            seen_room_ids.add(room_id)
            rooms.append({"room_id": room_id, "capacity": capacity})

        elif section == "MEETINGS":
            parts = [p.strip() for p in line.split(",")]

            if len(parts) == 4:
                meeting_id, department, attendees_str, time_str = parts
                employee_name = "Unknown"
                priority = config.DEFAULT_PRIORITY
            elif len(parts) == 5:
                meeting_id, employee_name, department, attendees_str, time_str = parts
                priority = config.DEFAULT_PRIORITY
            elif len(parts) == 6:
                (meeting_id, employee_name, department, attendees_str,
                 time_str, priority) = parts
                if priority not in config.VALID_PRIORITIES:
                    _warn(warnings, line_no, "meeting", meeting_id, "repaired",
                          f"Line {line_no}: Invalid priority '{priority}' for "
                          f"meeting '{meeting_id}' \u2014 defaulted to "
                          f"'{config.DEFAULT_PRIORITY}'.")
                    priority = config.DEFAULT_PRIORITY
            else:
                _warn(warnings, line_no, "meeting", None, "skipped",
                      f"Line {line_no}: Invalid meeting entry '{line}' (expected "
                      "format: MeetingID,Employee,Department,Attendees,Time,Priority) "
                      "\u2014 row skipped.")
                continue

            if _is_null(meeting_id):
                _warn(warnings, line_no, "meeting", None, "skipped",
                      f"Line {line_no}: Missing meeting ID \u2014 row skipped.")
                continue

            if meeting_id in seen_meeting_ids:
                _warn(warnings, line_no, "meeting", meeting_id, "skipped",
                      f"Line {line_no}: Duplicate meeting ID '{meeting_id}' "
                      "\u2014 row skipped.")
                continue

            if _is_null(employee_name):
                _warn(warnings, line_no, "meeting", meeting_id, "repaired",
                      f"Line {line_no}: Missing employee name for meeting "
                      f"'{meeting_id}' \u2014 defaulted to 'Unknown'.")
                employee_name = "Unknown"

            if _is_null(department):
                _warn(warnings, line_no, "meeting", meeting_id, "repaired",
                      f"Line {line_no}: Missing department for meeting "
                      f"'{meeting_id}' \u2014 defaulted to 'Unspecified'.")
                department = "Unspecified"

            if _is_null(attendees_str):
                _warn(warnings, line_no, "meeting", meeting_id, "skipped",
                      f"Line {line_no}: Missing attendee count for meeting "
                      f"'{meeting_id}' \u2014 row skipped (no safe default for "
                      "attendee count).")
                continue

            try:
                attendees = int(attendees_str)
                if attendees <= 0:
                    raise ValueError
            except ValueError:
                _warn(warnings, line_no, "meeting", meeting_id, "skipped",
                      f"Line {line_no}: Invalid attendee count '{attendees_str}' "
                      f"for meeting '{meeting_id}' (must be a positive integer) "
                      "\u2014 row skipped.")
                continue

            start, end, start_minutes, end_minutes = parse_time_range(time_str)
            if start is None or end is None:
                _warn(warnings, line_no, "meeting", meeting_id, "skipped",
                      f"Line {line_no}: Invalid time format '{time_str}' for "
                      f"meeting '{meeting_id}' (expected format: HH:MM-HH:MM) "
                      "\u2014 row skipped.")
                continue

            if end_minutes <= start_minutes:
                _warn(warnings, line_no, "meeting", meeting_id, "skipped",
                      f"Line {line_no}: End time must be after start time for "
                      f"meeting '{meeting_id}' \u2014 row skipped.")
                continue

            seen_meeting_ids.add(meeting_id)
            meetings.append(
                {
                    "meeting_id": meeting_id,
                    "employee_name": employee_name,
                    "department": department,
                    "attendees": attendees,
                    "time_slot": time_str,
                    "start_time": start,
                    "end_time": end,
                    "start_minutes": start_minutes,
                    "end_minutes": end_minutes,
                    "duration_minutes": end_minutes - start_minutes,
                    "priority": priority,
                }
            )

        else:
            _warn(warnings, line_no, "file", None, "skipped",
                  f"Line {line_no}: Data found outside of ROOMS/MEETINGS sections: "
                  f"'{line}' \u2014 line skipped.")

    rooms_df = pd.DataFrame(rooms, columns=["room_id", "capacity"])
    meetings_df = pd.DataFrame(
        meetings,
        columns=[
            "meeting_id", "employee_name", "department", "attendees",
            "time_slot", "start_time", "end_time", "start_minutes",
            "end_minutes", "duration_minutes", "priority",
        ],
    )

    return rooms_df, meetings_df, warnings


def validate_dataset(rooms_df, meetings_df):
    """
    Cross-record validation performed after line-level parsing.

    Returns (fatal_errors, extra_warnings):
      * fatal_errors  -- dataset genuinely unusable (block the upload)
      * extra_warnings -- informational, non-blocking (e.g. a meeting
        that will never fit any room -- the scheduler will surface it
        as a conflict rather than the upload failing outright)
    """
    fatal_errors = []
    extra_warnings = []

    if rooms_df is None or rooms_df.empty:
        fatal_errors.append(
            "No valid rooms were found in the dataset. At least one room "
            "with a valid ID and a positive integer capacity is required."
        )

    if meetings_df is None or meetings_df.empty:
        fatal_errors.append(
            "No valid meetings were found in the dataset. At least one "
            "meeting with a valid ID, attendee count, and time slot is "
            "required."
        )

    if (
        rooms_df is not None and not rooms_df.empty
        and meetings_df is not None and not meetings_df.empty
    ):
        max_capacity = rooms_df["capacity"].max()
        oversized = meetings_df[meetings_df["attendees"] > max_capacity]
        for _, row in oversized.iterrows():
            extra_warnings.append({
                "line": None, "entity": "meeting", "id": row["meeting_id"],
                "action": "flagged",
                "message": (
                    f"Meeting '{row['meeting_id']}' requests {row['attendees']} "
                    f"attendees, which exceeds the largest available room "
                    f"capacity of {max_capacity}. It will be marked as a "
                    "conflict during scheduling."
                ),
            })

    return fatal_errors, extra_warnings
