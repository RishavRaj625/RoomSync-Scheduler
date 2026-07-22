"""
database.py

Owns the SQLite connection and schema for RoomSync. Every other module
that needs persistence goes through get_connection() / init_db() here
rather than opening its own connection, so the schema lives in one place.
"""

import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_active TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    dataset_group TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    version INTEGER NOT NULL,
    upload_date TEXT NOT NULL,
    upload_time TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    num_records INTEGER NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'Pending',
    schedule_status TEXT NOT NULL DEFAULT 'Not Generated',
    processing_time_ms REAL NOT NULL DEFAULT 0,
    num_rooms INTEGER NOT NULL DEFAULT 0,
    num_meetings INTEGER NOT NULL DEFAULT 0,
    num_scheduled INTEGER NOT NULL DEFAULT 0,
    num_conflicts INTEGER NOT NULL DEFAULT 0,
    num_warnings INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS schedule_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id INTEGER NOT NULL,
    meeting_id TEXT NOT NULL,
    employee_name TEXT NOT NULL,
    department TEXT NOT NULL,
    assigned_room TEXT,
    room_capacity INTEGER,
    attendees INTEGER,
    duration_minutes INTEGER,
    time_slot TEXT,
    priority TEXT,
    status TEXT NOT NULL,
    conflict_reason TEXT,
    FOREIGN KEY (upload_id) REFERENCES uploads (id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_uploads_user ON uploads (user_id);
CREATE INDEX IF NOT EXISTS idx_uploads_group ON uploads (dataset_group);
CREATE INDEX IF NOT EXISTS idx_schedule_upload ON schedule_entries (upload_id);
CREATE INDEX IF NOT EXISTS idx_logs_username ON activity_logs (username);
"""


def get_connection():
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor(commit=False):
    """Context manager yielding a cursor, closing the connection afterwards."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables/indexes if they do not already exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
