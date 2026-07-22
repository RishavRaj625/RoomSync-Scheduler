"""
config.py

Central configuration for the RoomSync application: filesystem paths,
upload constraints, and small tunables used across modules. Keeping this
in one place means routes.py, upload.py, database.py, etc. never hardcode
paths themselves.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = os.path.join(BASE_DIR, "generated_reports")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "roomsync.db")
ACTIVITY_LOG_FILE = os.path.join(LOGS_DIR, "activity.log")

for _directory in (UPLOAD_DIR, REPORTS_DIR, LOGS_DIR, DATABASE_DIR):
    os.makedirs(_directory, exist_ok=True)

ALLOWED_EXTENSIONS = {"txt"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

SECRET_KEY = "roomsync-dev-secret-key-change-in-production"

# Priority values accepted in the dataset (used for tie-breaking / display).
VALID_PRIORITIES = {"High", "Medium", "Low"}
DEFAULT_PRIORITY = "Medium"

PAGE_SIZE_DEFAULT = 25
