"""
models.py

Data-access layer. Every function here executes SQL against the database
defined in database.py and returns plain dicts/lists so the rest of the
app (routes, dashboard, analytics, history, search) never writes raw SQL.
"""

from datetime import datetime

from database import db_cursor


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- users --

def get_or_create_user(username):
    """Look up a user by name, creating one if this is their first visit."""
    now = datetime.now().isoformat(timespec="seconds")
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row is not None:
            cur.execute(
                "UPDATE users SET last_active = ? WHERE id = ?", (now, row["id"])
            )
            user = dict(row)
            user["last_active"] = now
            return user, False

        cur.execute(
            "INSERT INTO users (username, created_at, last_active) VALUES (?, ?, ?)",
            (username, now, now),
        )
        user = {
            "id": cur.lastrowid,
            "username": username,
            "created_at": now,
            "last_active": now,
        }
        return user, True


def get_user_by_name(username):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        return _row_to_dict(cur.fetchone())


def get_all_users():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users ORDER BY last_active DESC")
        return _rows_to_dicts(cur.fetchall())


def count_users():
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM users")
        return cur.fetchone()["c"]


# -------------------------------------------------------------- uploads --

def next_version_for_group(user_id, dataset_group):
    with db_cursor() as cur:
        cur.execute(
            "SELECT MAX(version) AS max_v FROM uploads "
            "WHERE user_id = ? AND dataset_group = ?",
            (user_id, dataset_group),
        )
        max_v = cur.fetchone()["max_v"]
        return (max_v or 0) + 1


def create_upload(user_id, dataset_group, original_filename, stored_filename,
                   version, file_size):
    now = datetime.now()
    with db_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO uploads
               (user_id, dataset_group, original_filename, stored_filename,
                version, upload_date, upload_time, file_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, dataset_group, original_filename, stored_filename,
                version, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                file_size,
            ),
        )
        return cur.lastrowid


def update_upload_processing(upload_id, processing_status, num_records,
                              processing_time_ms, num_rooms=0, num_meetings=0,
                              warnings=None):
    import json

    warnings = warnings or []
    with db_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE uploads SET processing_status = ?, num_records = ?,
               processing_time_ms = ?, num_rooms = ?, num_meetings = ?,
               num_warnings = ?, warnings_json = ?
               WHERE id = ?""",
            (processing_status, num_records, processing_time_ms, num_rooms,
             num_meetings, len(warnings), json.dumps(warnings), upload_id),
        )


def update_upload_schedule_status(upload_id, schedule_status, num_scheduled=0,
                                   num_conflicts=0):
    with db_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE uploads SET schedule_status = ?, num_scheduled = ?,
               num_conflicts = ? WHERE id = ?""",
            (schedule_status, num_scheduled, num_conflicts, upload_id),
        )


def get_upload(upload_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,))
        return _row_to_dict(cur.fetchone())


def get_upload_warnings(upload_id):
    """Decode the stored warnings_json for an upload back into a list of dicts."""
    import json

    upload_row = get_upload(upload_id)
    if not upload_row or not upload_row.get("warnings_json"):
        return []
    try:
        return json.loads(upload_row["warnings_json"])
    except (ValueError, TypeError):
        return []


def get_uploads_for_user(user_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM uploads WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        return _rows_to_dicts(cur.fetchall())


def get_versions_for_group(user_id, dataset_group):
    with db_cursor() as cur:
        cur.execute(
            """SELECT * FROM uploads WHERE user_id = ? AND dataset_group = ?
               ORDER BY version DESC""",
            (user_id, dataset_group),
        )
        return _rows_to_dicts(cur.fetchall())


def get_all_uploads():
    with db_cursor() as cur:
        cur.execute(
            """SELECT uploads.*, users.username AS username FROM uploads
               JOIN users ON users.id = uploads.user_id
               ORDER BY uploads.id DESC"""
        )
        return _rows_to_dicts(cur.fetchall())


def delete_upload(upload_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM schedule_entries WHERE upload_id = ?", (upload_id,))
        cur.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))


def rename_upload(upload_id, new_original_name):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE uploads SET original_filename = ? WHERE id = ?",
            (new_original_name, upload_id),
        )


# ------------------------------------------------------------- schedule --

def save_schedule_entries(upload_id, entries):
    """entries: list of dicts matching schedule_entries columns."""
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM schedule_entries WHERE upload_id = ?", (upload_id,))
        cur.executemany(
            """INSERT INTO schedule_entries
               (upload_id, meeting_id, employee_name, department, assigned_room,
                room_capacity, attendees, duration_minutes, time_slot, priority,
                status, conflict_reason)
               VALUES (:upload_id, :meeting_id, :employee_name, :department,
                       :assigned_room, :room_capacity, :attendees,
                       :duration_minutes, :time_slot, :priority, :status,
                       :conflict_reason)""",
            [{**e, "upload_id": upload_id} for e in entries],
        )


def get_schedule_for_upload(upload_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM schedule_entries WHERE upload_id = ? ORDER BY id",
            (upload_id,),
        )
        return _rows_to_dicts(cur.fetchall())


def get_all_schedule_entries():
    with db_cursor() as cur:
        cur.execute(
            """SELECT schedule_entries.*, uploads.original_filename,
                      uploads.user_id, users.username
               FROM schedule_entries
               JOIN uploads ON uploads.id = schedule_entries.upload_id
               JOIN users ON users.id = uploads.user_id"""
        )
        return _rows_to_dicts(cur.fetchall())


# ---------------------------------------------------------------- logs --

def log_activity(username, action, details="", user_id=None):
    now = datetime.now().isoformat(timespec="seconds")
    with db_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO activity_logs (user_id, username, action, details,
               timestamp) VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, action, details, now),
        )


def get_recent_logs(limit=200):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        return _rows_to_dicts(cur.fetchall())


def get_logs_for_user(username, limit=200):
    with db_cursor() as cur:
        cur.execute(
            """SELECT * FROM activity_logs WHERE username = ?
               ORDER BY id DESC LIMIT ?""",
            (username, limit),
        )
        return _rows_to_dicts(cur.fetchall())
