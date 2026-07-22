"""
utils.py

Small, dependency-free helper functions shared across modules: file size
formatting, safe filename handling, and dataset-group key derivation used
for version control.
"""

import os
import re
import time
import unicodedata


def secure_filename(filename):
    """Minimal, dependency-free stand-in for werkzeug's secure_filename."""
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    filename = re.sub(r"[^A-Za-z0-9_.\-]", "_", filename)
    return filename.strip("._") or "file.txt"


def dataset_group_key(username, original_filename):
    """
    Key used to group versions of 'the same' upload: same user + same
    original filename (case-insensitive) map to the same version chain.
    """
    return f"{username.strip().lower()}::{original_filename.strip().lower()}"


def versioned_stored_filename(original_filename, version):
    """e.g. 'rooms.txt' + version 3 -> 'rooms__v3__1720600000.txt'"""
    base, ext = os.path.splitext(secure_filename(original_filename))
    return f"{base}__v{version}__{int(time.time() * 1000)}{ext or '.txt'}"


def format_file_size(num_bytes):
    if num_bytes is None:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def minutes_to_hhmm(total_minutes):
    hours, minutes = divmod(int(total_minutes), 60)
    return f"{hours:02d}:{minutes:02d}"
