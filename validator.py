"""
validator.py

Orchestrates dataset validation before it reaches the scheduler:
file-level checks (extension, emptiness, size) plus the parsing /
cross-record checks implemented in parser.py.

Row-level problems (bad capacity, missing department, etc.) no longer
fail the whole upload -- they come back as non-blocking `warnings` and
the offending rows are repaired or skipped by parser.py. Only dataset-
wide problems (empty file, zero usable rooms/meetings) come back as
`errors` and block the upload.
"""

import config
import parser as dataset_parser


def is_allowed_file(filename):
    """Only .txt files are accepted, per the functional requirements."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in config.ALLOWED_EXTENSIONS


def validate_file_upload(filename, file_bytes):
    """
    File-level validation performed before any parsing happens.

    Returns a list of error strings; empty means the file may proceed
    to parsing.
    """
    errors = []

    if not filename:
        errors.append("No file was selected.")
        return errors

    if not is_allowed_file(filename):
        errors.append("Unsupported file format. Only .txt files are allowed.")

    if file_bytes is None or len(file_bytes) == 0:
        errors.append("The uploaded file is empty.")

    if file_bytes is not None and len(file_bytes) > config.MAX_CONTENT_LENGTH:
        errors.append(
            f"File is too large (max {config.MAX_CONTENT_LENGTH // (1024*1024)} MB)."
        )

    return errors


def validate_dataset_content(raw_text):
    """
    Full parse + cross-record validation.

    Returns (rooms_df, meetings_df, errors, warnings):
      * errors   -- fatal, dataset-wide problems that block the upload
                    (empty file, no usable rooms, no usable meetings)
      * warnings -- non-blocking, row-level notices for every row that
                    was auto-repaired or skipped, plus informational
                    flags (e.g. a meeting too big for any room)
    """
    rooms_df, meetings_df, parse_warnings = dataset_parser.parse_dataset(raw_text)

    # A completely empty file comes back from parse_dataset as a single
    # "fatal" entry inside what would otherwise be the warnings list.
    fatal_from_parse = [w["message"] for w in parse_warnings if w["action"] == "fatal"]
    row_warnings = [w for w in parse_warnings if w["action"] != "fatal"]

    if fatal_from_parse:
        return rooms_df, meetings_df, fatal_from_parse, []

    cross_errors, cross_warnings = dataset_parser.validate_dataset(rooms_df, meetings_df)
    warnings = row_warnings + cross_warnings
    return rooms_df, meetings_df, cross_errors, warnings
