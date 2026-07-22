"""
download.py

Thin layer that turns report content (from reports.py) or a stored raw
upload into a Flask file response. Kept separate from routes.py so the
routing table stays declarative.
"""

import io
import os

from flask import send_file, send_from_directory

import config
import reports


def send_schedule_csv(entries, download_name):
    csv_text = reports.build_csv(entries)
    buffer = io.BytesIO(csv_text.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer, mimetype="text/csv", as_attachment=True, download_name=download_name
    )


def send_schedule_txt(entries, download_name):
    txt_text = reports.build_txt(entries)
    buffer = io.BytesIO(txt_text.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer, mimetype="text/plain", as_attachment=True, download_name=download_name
    )


def send_original_file(stored_filename, download_name):
    return send_from_directory(
        config.UPLOAD_DIR, stored_filename, as_attachment=True,
        download_name=download_name,
    )
