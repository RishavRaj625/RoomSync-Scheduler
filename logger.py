"""
logger.py

Records user/system activity in two places:
  1. the activity_logs table (queryable from the UI), via models.py
  2. a plain-text log file on disk, for ops-style tailing/debugging

Every route that changes state (upload, delete, rename, generate
schedule, download, etc.) should call log_event() once.
"""

from datetime import datetime

import config
import models


def log_event(username, action, details="", user_id=None):
    """Log one activity event to the database and to logs/activity.log."""
    models.log_activity(username=username, action=action, details=details,
                         user_id=user_id)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {username} :: {action} :: {details}\n"
    try:
        with open(config.ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        # Logging must never break the request; the DB row is authoritative.
        pass


def read_log_file(max_lines=500):
    """Return the most recent lines from the activity log file."""
    try:
        with open(config.ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except OSError:
        return []
