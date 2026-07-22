"""
upload.py

Orchestrates the full upload workflow:
  1. validate the incoming file
  2. work out whether this is a new dataset or a new version of one the
     user has uploaded before (same username + same original filename)
  3. save the raw bytes to disk under a unique stored filename
  4. parse + validate the dataset content
  5. record everything in the database via models.py
  6. run the scheduler and persist the resulting schedule

Nothing here overwrites a previous version -- see utils.versioned_stored_filename.
"""

import os
import time

import config
import models
import parser as dataset_parser
import scheduler
import utils
import validator
import conflict_detector


class UploadResult:
    def __init__(self):
        self.success = False
        self.errors = []
        self.warnings = []
        self.upload_id = None
        self.version = None
        self.is_new_version = False
        self.num_rooms = 0
        self.num_meetings = 0
        self.preview = ""
        self.preview_truncated = False


def save_and_validate(username, original_filename, file_bytes):
    """
    Step 1 of the workflow: validate the file, save it to disk (creating a
    new version if this user has uploaded this filename before), parse and
    validate its contents, and record the upload. Scheduling is *not* run
    here -- see generate_schedule() -- so the dataset can be previewed first.
    """
    result = UploadResult()
    start = time.perf_counter()

    file_errors = validator.validate_file_upload(original_filename, file_bytes)
    if file_errors:
        result.errors = file_errors
        return result

    user, _ = models.get_or_create_user(username)

    dataset_group = utils.dataset_group_key(username, original_filename)
    version = models.next_version_for_group(user["id"], dataset_group)
    result.version = version
    result.is_new_version = version > 1

    stored_filename = utils.versioned_stored_filename(original_filename, version)
    stored_path = os.path.join(config.UPLOAD_DIR, stored_filename)
    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    upload_id = models.create_upload(
        user_id=user["id"],
        dataset_group=dataset_group,
        original_filename=original_filename,
        stored_filename=stored_filename,
        version=version,
        file_size=len(file_bytes),
    )
    result.upload_id = upload_id

    result.preview, result.preview_truncated = preview_text(file_bytes)

    raw_text = file_bytes.decode("utf-8", errors="replace")
    rooms_df, meetings_df, content_errors, content_warnings = (
        validator.validate_dataset_content(raw_text)
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    result.num_rooms = 0 if rooms_df is None else len(rooms_df)
    result.num_meetings = 0 if meetings_df is None else len(meetings_df)
    result.warnings = content_warnings

    if content_errors:
        # Only genuinely fatal, dataset-wide problems land here (empty
        # file, zero usable rooms, zero usable meetings). Row-level mess
        # (bad capacity, missing IDs, NULL fields, etc.) is repaired or
        # skipped automatically by the parser and reported as warnings
        # instead, so a single bad line never blocks a whole upload.
        models.update_upload_processing(
            upload_id, "Failed", num_records=result.num_meetings,
            processing_time_ms=elapsed_ms, num_rooms=result.num_rooms,
            num_meetings=result.num_meetings, warnings=content_warnings,
        )
        result.errors = content_errors
        return result

    models.update_upload_processing(
        upload_id, "Success", num_records=result.num_rooms + result.num_meetings,
        processing_time_ms=elapsed_ms, num_rooms=result.num_rooms,
        num_meetings=result.num_meetings, warnings=content_warnings,
    )
    result.success = True
    return result


class ScheduleResult:
    def __init__(self):
        self.success = False
        self.errors = []
        self.num_scheduled = 0
        self.num_conflicts = 0
        self.schedule = []
        self.conflicts = []
        self.integrity_issues = []


def generate_schedule(upload_id):
    """
    Step 2 of the workflow: re-read the stored file for this upload, run
    the best-fit scheduler, persist schedule_entries, and update the
    upload's schedule_status.
    """
    result = ScheduleResult()
    upload_row = models.get_upload(upload_id)
    if upload_row is None:
        result.errors = ["Upload not found."]
        return result
    if upload_row["processing_status"] != "Success":
        result.errors = ["This dataset failed validation and cannot be scheduled."]
        return result

    stored_path = os.path.join(config.UPLOAD_DIR, upload_row["stored_filename"])
    with open(stored_path, "rb") as f:
        raw_text = f.read().decode("utf-8", errors="replace")

    rooms_df, meetings_df, _, _ = validator.validate_dataset_content(raw_text)

    schedule_df, conflicts_df = scheduler.schedule_meetings(rooms_df, meetings_df)
    result.integrity_issues = conflict_detector.verify_no_double_booking(schedule_df)

    entries = []
    if schedule_df is not None and not schedule_df.empty:
        conflict_reason_by_id = {
            row["meeting_id"]: row["reason"]
            for row in conflicts_df.to_dict("records")
        } if conflicts_df is not None and not conflicts_df.empty else {}

        for row in schedule_df.to_dict("records"):
            entries.append({
                "meeting_id": row["meeting_id"],
                "employee_name": row.get("employee_name", "Unknown"),
                "department": row["department"],
                "assigned_room": None if row["assigned_room"] == "N/A" else row["assigned_room"],
                "room_capacity": row["room_capacity"],
                "attendees": row["attendees"],
                "duration_minutes": row.get("duration_minutes"),
                "time_slot": row["time_slot"],
                "priority": row.get("priority", "Medium"),
                "status": row["status"],
                "conflict_reason": conflict_reason_by_id.get(row["meeting_id"]),
            })
        models.save_schedule_entries(upload_id, entries)

    num_scheduled = sum(1 for e in entries if e["status"] == "Scheduled")
    num_conflicts = sum(1 for e in entries if e["status"] == "Conflict")
    schedule_status = "Generated" if entries else "Not Generated"
    models.update_upload_schedule_status(
        upload_id, schedule_status, num_scheduled=num_scheduled,
        num_conflicts=num_conflicts,
    )

    result.success = True
    result.num_scheduled = num_scheduled
    result.num_conflicts = num_conflicts
    result.schedule = entries
    result.conflicts = conflict_detector.build_conflict_summary(conflicts_df)
    return result


def preview_text(file_bytes, max_lines=40):
    """Return the first N lines of a raw upload for the preview screen."""
    text = file_bytes.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(lines) > max_lines
    return "\n".join(lines[:max_lines]), truncated
