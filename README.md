# RoomSync: Smart Meeting Room Allocation & Scheduling System

RoomSync is a full-stack, multi-user Flask web app that takes a plain
`.txt` dataset of rooms and meetings, auto-assigns every meeting to the
best available room with a **best-fit greedy scheduling algorithm**,
and gives each user a dashboard, visual analytics, searchable upload
history, and CSV/TXT exports — all backed by SQLite, no external
services required.

Upload messy, real-world data and it just works: rows with missing or
invalid fields are automatically repaired or safely skipped instead of
rejecting the whole file, and every skip/repair is reported back to you.

---

## Table of Contents

- [What it does](#what-it-does)
- [How it works](#how-it-works)
  - [1. Upload & validation](#1-upload--validation)
  - [2. Scheduling algorithm](#2-scheduling-algorithm)
  - [3. Dashboard, analytics & history](#3-dashboard-analytics--history)
- [Dataset format](#dataset-format)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Routes](#routes)
- [Running tests](#running-tests)
- [Tech stack](#tech-stack)
- [Notes & limitations](#notes--limitations)

---

## What it does

You give RoomSync a text file listing the rooms you have (with
capacities) and the meetings you need to fit (with attendee counts,
departments, and time slots). RoomSync:

1. Parses and validates the file, auto-repairing or skipping any bad
   rows so a few typos never block the whole upload.
2. Runs a best-fit greedy algorithm to assign each meeting to the
   smallest room that fits it and is free during that time slot.
3. Flags anything that couldn't be scheduled (too big for any room,
   or every suitable room already booked) as a **Conflict**.
4. Gives you an interactive schedule table, a personal dashboard, a
   full analytics page with charts, and an audit trail of every
   upload/version/action, all without needing a database server —
   it's just a Flask app + SQLite file.

---

## How it works

### 1. Upload & validation

- `validator.py` first checks the file itself (`.txt`, non-empty,
  under the size limit).
- `parser.py` then parses the `ROOMS` and `MEETINGS` sections line by
  line. Every row is classified into one of three outcomes:
  - **Repaired** — a safe default exists, so the row is kept and
    fixed automatically (e.g. a missing department becomes
    `"Unspecified"`, a missing employee name becomes `"Unknown"`, an
    invalid priority defaults to `"Medium"`).
  - **Skipped** — no safe default exists (missing/invalid capacity,
    a missing ID, a non-numeric or negative attendee count, a broken
    `HH:MM-HH:MM` time range, a duplicate ID). That single row is
    dropped and the rest of the file is still processed normally.
  - **Fatal** — the whole upload is rejected only if the file is
    empty, or if literally zero usable rooms or zero usable meetings
    remain after cleanup.
  - The literal string `NULL` (any casing), blanks, `N/A`, `None`,
    and `-` are all treated as missing values.
- Every repaired/skipped row is recorded with its line number and
  reason and shown to you on the preview page — nothing is silently
  dropped.
- A separate cross-record check flags meetings that request more
  attendees than any room can hold; rather than blocking the upload,
  these are left for the scheduler to naturally mark as conflicts.

### 2. Scheduling algorithm

`scheduler.py` implements an **optimized best-fit greedy** allocator:

1. Rooms are sorted by capacity and grouped into capacity-indexed
   buckets.
2. Meetings are sorted chronologically by start time.
3. For each meeting, binary search finds the smallest capacity bucket
   that can fit the attendee count (best-fit, not first-fit).
4. Within that bucket, a min-heap keyed by each room's next-free time
   surfaces an already-idle room in `O(log R)`; if none is idle, a
   deterministic scan checks for a free gap.
5. If no room fits (too big, or every candidate is already booked),
   the meeting is recorded as a **Conflict** instead of blocking the
   whole run.

This gives roughly `O(M log R)` allocation time after `O(R log R)`
room sorting and `O(M log M)` meeting sorting, using `O(R + M)` space.
Full algorithmic reasoning (why buckets, why a heap, why the
tie-breaking order) is documented at the top of `scheduler.py`.

### 3. Dashboard, analytics & history

- **Dashboard** — quick stats for your account: uploads, scheduled
  vs. conflicted meetings, recent activity.
- **Analytics** — charts built with Chart.js, computed in
  `analytics.py`:
  - Meeting status (Scheduled vs. Conflict) — doughnut chart
  - Meetings assigned per room — bar chart
  - Room utilization (average % of capacity filled) — bar chart
  - Department-wise meeting count — bar chart
  - Room occupancy by time slot — heatmap (room × hour)
  - Peak meeting hours, conflict reasons, and per-user upload
    activity as supporting tables/charts
- **History / Files** — every upload is versioned automatically
  (re-uploading a same-named file creates v2, v3, ... instead of
  overwriting); you can search, filter, rename, delete, and download
  the original file or the generated schedule (CSV/TXT).
- **Activity log** — every upload, schedule generation, and file
  action is logged to both SQLite and `logs/activity.log`.

---

## Dataset format

```
ROOMS
R101,20
R102,10
R103,50

MEETINGS
M001,John Doe,HR,15,09:00-10:00,High
M002,Jane Smith,Finance,8,09:00-10:00,Medium
```

- **Rooms:** `RoomID,Capacity`
- **Meetings:** `MeetingID,Employee,Department,Attendees,Time,Priority`
  - `Priority` is optional (`High` / `Medium` / `Low`, defaults to
    `Medium`).
  - Legacy 4-field lines (`MeetingID,Department,Attendees,Time`, no
    employee/priority) are still accepted for backward compatibility.
  - Blank fields or `NULL` are handled gracefully per the validation
    rules above — you don't need a perfectly clean file.

---

## Project structure

```
RoomSync/
  app.py                # Flask app factory / entry point
  config.py              # paths & constants
  database.py            # SQLite connection + schema
  models.py              # data access layer (users, uploads, schedules, logs)
  routes.py              # all HTTP routes
  upload.py              # upload workflow: validate -> save -> version -> parse
  parser.py              # dataset parsing, auto-repair/skip logic, line-level validation
  scheduler.py           # best-fit greedy allocation algorithm
  conflict_detector.py   # double-booking / capacity conflict checks
  validator.py           # file-level + dataset-level validation orchestration
  history.py             # upload/version history queries
  search.py              # search & filter helpers
  dashboard.py           # dashboard statistics
  analytics.py           # room utilization, dept distribution, heatmap, peak hours, etc.
  reports.py             # CSV/TXT report content builders
  download.py            # Flask file-download helpers
  notifications.py       # flash-message helpers
  logger.py              # activity logging (DB + logs/activity.log)
  utils.py               # small shared helpers

  templates/              # Jinja2 templates (upload, preview, schedule, dashboard, analytics, ...)
  static/                 # CSS (light/dark theme) & JS (theme toggle, quick search)
  uploads/                # stored raw .txt uploads (versioned, never overwritten)
  generated_reports/      # reserved for cached export files
  logs/                   # activity.log
  database/               # roomsync.db (SQLite, created automatically)
```

---

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`.

1. Enter your name (used to track your upload history — no password,
   just identification).
2. Upload a `.txt` dataset (or use the included `sample_dataset.txt`).
3. Preview the parsed dataset — any auto-repaired or skipped rows are
   listed here — then click **Generate Schedule**.
4. Explore the schedule table (sort/filter/search), Dashboard,
   Analytics, Upload History, My Files, and Activity Logs from the
   sidebar.
5. Export the schedule as **CSV** or **TXT**.

Re-uploading a file with the same name creates **Version 2, 3, ...**
automatically — previous versions and their generated schedules are
kept, never overwritten.

---

## Routes

| Route | Description |
|---|---|
| `GET/POST /identify` | Enter a username to start a session |
| `GET /logout` | End the session |
| `GET/POST /upload` | Upload and validate a dataset |
| `GET /preview/<upload_id>` | Preview parsed data + validation warnings |
| `POST /generate/<upload_id>` | Run the scheduler on an uploaded dataset |
| `GET /schedule/<upload_id>` | View the generated schedule |
| `GET /download/<upload_id>/<fmt>` | Download schedule as `csv`/`txt` |
| `GET /download-original/<upload_id>` | Download the original uploaded file |
| `GET /history` | Search/filter upload history (yours or everyone's) |
| `GET/POST /search-users` | Look up another user's activity |
| `GET /files` | Manage your uploaded files (rename/delete) |
| `GET /dashboard` | Personal stats overview |
| `GET /analytics` | Charts: room utilization, department load, occupancy heatmap, etc. |
| `GET /logs` | Activity log |

---

## Running tests

```bash
pytest test_scheduler.py -q
```

---

## Tech stack

- **Backend:** Python, Flask
- **Data processing:** pandas
- **Storage:** SQLite (`database/roomsync.db`, auto-created on first run)
- **Frontend:** Jinja2 templates, vanilla CSS (light/dark theme), vanilla JS
- **Charts:** Chart.js (loaded via CDN)



## Notes & limitations

- Storage is a single SQLite file — no external database server
  required, but this isn't intended for concurrent production
  workloads.
- "Login" is simple username identification, not password-based
  authentication, per the original project spec.
- The best-fit greedy scheduling algorithm is deterministic: given the
  same input, you always get the same room assignments.
- A meeting that requests more attendees than your largest room can
  hold, or that can't find any free room, is marked as a **Conflict**
  rather than silently dropped — it stays visible in the schedule and
  in analytics so you know to address it manually.

Optional Advanced Features:

User Login & Authentication
Admin Dashboard
Role-Based Access (Admin/User)
Email schedule reports
QR Code for downloaded schedules
Calendar view of meetings
Automatic meeting reminders
Room occupancy statistics
Meeting priority handling
AI-based room recommendation
REST API for integration
Backup & Restore
Audit Trail
Multi-language support
Cloud deployment readiness

---
