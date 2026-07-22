"""
notifications.py

Thin wrapper around Flask's flash() that standardizes the notification
categories called for in the spec (upload success/failure, invalid
dataset, conflicts detected, schedule generated, downloads, duplicates,
etc.) so templates can render consistent alert styling.
"""

from flask import flash

CATEGORY_STYLES = {
    "success": "success",
    "error": "danger",
    "warning": "warning",
    "info": "info",
}


def notify(message, category="info"):
    flash(message, CATEGORY_STYLES.get(category, "info"))


def upload_successful(filename):
    notify(f"Upload successful: '{filename}'.", "success")


def upload_failed(reason=""):
    notify(f"Upload failed. {reason}".strip(), "error")


def invalid_dataset(count):
    notify(f"Invalid dataset: {count} validation error(s) found.", "error")


def dataset_warnings(count):
    notify(
        f"Dataset uploaded with {count} row-level issue(s) — problem rows were "
        "automatically repaired or skipped so the rest of the file could still "
        "be processed. See details below.",
        "warning",
    )


def scheduling_conflict_detected(count):
    notify(f"Scheduling conflict detected for {count} meeting(s).", "warning")


def schedule_generated_successfully(num_scheduled):
    notify(f"Schedule generated successfully: {num_scheduled} meeting(s) placed.",
           "success")


def file_downloaded(filename):
    notify(f"File downloaded: '{filename}'.", "info")


def duplicate_file_uploaded(filename, version):
    notify(
        f"'{filename}' already exists for this user — saved as Version {version} "
        "instead of overwriting.",
        "warning",
    )


def file_deleted(filename):
    notify(f"File deleted: '{filename}'.", "info")


def file_renamed(old_name, new_name):
    notify(f"Renamed '{old_name}' to '{new_name}'.", "info")
