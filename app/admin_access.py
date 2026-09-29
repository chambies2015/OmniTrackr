"""Who may open the owner-only Site stats page.

Access comes from environment variables so it never lives in the database:

    ADMIN_USERNAMES=dan,other            (preferred)
    COLLECTION_MODERATOR_USERNAMES=dan    (existing moderator list, also admins)

Variable names are matched case-insensitively because hosting dashboards make
it easy to type `collection_moderator_usernames`, and Linux environment
variables are case-sensitive.
"""
from __future__ import annotations

import os

ADMIN_ENV_NAMES = ("ADMIN_USERNAMES", "COLLECTION_MODERATOR_USERNAMES")


def _env_values(name: str) -> list[str]:
    wanted = name.upper()
    return [value for key, value in os.environ.items() if key.upper() == wanted]


def _usernames(*names: str) -> set[str]:
    found: set[str] = set()
    for name in names:
        for raw in _env_values(name):
            found.update(part.strip().lower() for part in raw.split(",") if part.strip())
    return found


def moderator_usernames() -> set[str]:
    """Collection/review moderators (the original moderator list plus admins)."""
    return _usernames(*ADMIN_ENV_NAMES)


def admin_usernames() -> set[str]:
    return _usernames(*ADMIN_ENV_NAMES)


def is_site_admin(user) -> bool:
    username = getattr(user, "username", None)
    return bool(username) and username.lower() in admin_usernames()
