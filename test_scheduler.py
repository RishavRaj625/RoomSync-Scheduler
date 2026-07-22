from pathlib import Path

import pandas as pd

from parser import parse_dataset
from scheduler import detect_conflicts, schedule_meetings


SAMPLE_DATASET = Path(__file__).with_name("sample_dataset.txt").read_text(encoding="utf-8")


def test_empty_inputs_return_empty_frames():
    schedule_df, conflicts_df = schedule_meetings(None, None)
    assert schedule_df.empty
    assert conflicts_df.empty


def test_conflict_detection_handles_no_issues():
    raw_text = """ROOMS
R101,20
R102,10

MEETINGS
M001,HR,5,09:00-10:00
M002,Finance,3,10:00-11:00
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)
    assert conflicts_df.empty
    assert detect_conflicts(schedule_df) == []


def test_best_fit_chooses_smallest_sufficient_room():
    raw_text = """ROOMS
R101,30
R102,10
R103,20

MEETINGS
M001,HR,8,09:00-10:00
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)
    assert conflicts_df.empty
    assert schedule_df.iloc[0]["assigned_room"] == "R102"
    assert schedule_df.iloc[0]["room_capacity"] == 10


def test_time_overlap_produces_conflict():
    raw_text = """ROOMS
R101,20

MEETINGS
M001,HR,5,09:00-10:00
M002,Finance,5,09:30-10:30
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)
    assert len(conflicts_df) == 1
    assert conflicts_df.iloc[0]["meeting_id"] == "M002"
    assert "already booked" in conflicts_df.iloc[0]["reason"]
    assert detect_conflicts(schedule_df) == []


def test_capacity_conflict_reason():
    raw_text = """ROOMS
R101,5

MEETINGS
M001,HR,10,09:00-10:00
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)
    assert len(conflicts_df) == 1
    assert "No room has sufficient capacity" in conflicts_df.iloc[0]["reason"]


def test_gap_between_bookings_allows_reuse():
    raw_text = """ROOMS
R101,10

MEETINGS
M001,HR,5,09:00-10:00
M002,Finance,5,10:00-11:00
M003,Sales,5,11:00-12:00
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)
    assert conflicts_df.empty
    assert (schedule_df["assigned_room"] == "R101").all()
    assert detect_conflicts(schedule_df) == []


def test_same_capacity_tie_break_is_deterministic():
    raw_text = """ROOMS
R201,10
R101,10

MEETINGS
M001,HR,5,09:00-10:00
M002,Finance,5,09:00-10:00
"""
    rooms_df, meetings_df, errors = parse_dataset(raw_text)
    assert not errors

    first_schedule, _ = schedule_meetings(rooms_df, meetings_df)
    second_schedule, _ = schedule_meetings(rooms_df, meetings_df)

    assert first_schedule["assigned_room"].tolist() == second_schedule["assigned_room"].tolist()
    assert first_schedule["assigned_room"].tolist() == ["R201", "R101"]


def test_sample_dataset_schedule():
    rooms_df, meetings_df, errors = parse_dataset(SAMPLE_DATASET)
    assert not errors

    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)

    assert len(schedule_df) == len(meetings_df)
    assert detect_conflicts(schedule_df) == []
    # Every conflict row's meeting_id should also show up as "Conflict" in schedule_df.
    conflict_ids = set(conflicts_df["meeting_id"]) if not conflicts_df.empty else set()
    scheduled_conflicts = set(
        schedule_df[schedule_df["status"] == "Conflict"]["meeting_id"]
    )
    assert conflict_ids == scheduled_conflicts


def test_schedule_output_columns():
    rooms_df, meetings_df, _ = parse_dataset(SAMPLE_DATASET)
    schedule_df, conflicts_df = schedule_meetings(rooms_df, meetings_df)

    expected_schedule_columns = {
        "meeting_id",
        "employee_name",
        "department",
        "assigned_room",
        "attendees",
        "room_capacity",
        "duration_minutes",
        "time_slot",
        "start_time",
        "end_time",
        "start_minutes",
        "end_minutes",
        "priority",
        "status",
    }

    assert expected_schedule_columns.issubset(schedule_df.columns)
    if not conflicts_df.empty:
        expected_conflict_columns = {
            "meeting_id",
            "employee_name",
            "department",
            "attendees",
            "requested_time",
            "priority",
            "reason",
        }
        assert expected_conflict_columns.issubset(conflicts_df.columns)


def test_deterministic_output_on_sample_dataset():
    rooms_df, meetings_df, _ = parse_dataset(SAMPLE_DATASET)

    first_schedule, first_conflicts = schedule_meetings(rooms_df, meetings_df)
    second_schedule, second_conflicts = schedule_meetings(rooms_df, meetings_df)

    pd.testing.assert_frame_equal(first_schedule, second_schedule)
    pd.testing.assert_frame_equal(first_conflicts, second_conflicts)
