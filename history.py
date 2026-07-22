"""
history.py

Read-side helpers for upload history and file version history, built on
top of models.py. Kept separate from models.py so routes.py has a
purpose-built API for the "history" and "previous user search" screens.
"""

import utils
import models


def history_for_user(username):
    """All uploads by one user, most recent first."""
    user = models.get_user_by_name(username)
    if user is None:
        return []
    return models.get_uploads_for_user(user["id"])


def all_history():
    """Full upload history across every user (admin / global view)."""
    return models.get_all_uploads()


def version_history(username, original_filename):
    """All versions of one dataset name for one user, newest version first."""
    user = models.get_user_by_name(username)
    if user is None:
        return []
    group = utils.dataset_group_key(username, original_filename)
    return models.get_versions_for_group(user["id"], group)


def group_uploads_by_dataset(uploads):
    """Group a flat upload list by dataset_group, for a version-aware view."""
    groups = {}
    for upload in uploads:
        groups.setdefault(upload["dataset_group"], []).append(upload)
    for group in groups.values():
        group.sort(key=lambda u: u["version"], reverse=True)
    return groups
