"""Rules for new usernames and passwords, with messages a person can act on.

Existing accounts are never re-checked: these rules apply only when a username
or password is chosen (sign-up, rename, password change or reset).
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

USERNAME_MIN = 3
USERNAME_MAX = 30
USERNAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
USERNAME_HINT = "3–30 characters: letters, numbers, dots, dashes or underscores"
PASSWORD_MIN = 8
PASSWORD_MAX_BYTES = 72  # bcrypt ignores anything longer
PASSWORD_HINT = "At least 8 characters. A short phrase is easy to remember and hard to guess."

# The most common leaked passwords that meet the length rule (lower-cased).
COMMON_PASSWORDS = frozenset("""
password password1 password12 password123 password1234 passw0rd p@ssw0rd p@ssword 12345678 123456789
1234567890 12345678910 87654321 11111111 00000000 88888888 qwertyui qwerty12 qwerty123 qwerty1234
qwertyuiop 1qaz2wsx 1q2w3e4r 1q2w3e4r5t zaq12wsx asdfghjk asdfasdf iloveyou iloveyou1 sunshine
sunshine1 princess princess1 football football1 baseball baseball1 basketball superman batman123
starwars trustno1 welcome1 welcome123 letmein1 letmein123 abc12345 abcd1234 aa123456 a1234567
admin123 administrator monkey123 dragon123 master123 shadow123 michael1 jennifer computer internet
whatever freedom1 charlie1 jordan23 liverpool chelsea1 arsenal1 pokemon1 minecraft fortnite
omnitrackr omnitrackr1 omnitrackr123 movies123 netflix1 changeme changeme1 secret123 testtest
test1234 test12345 testpass testpassword
""".split())


def username_problem(username: str, *, current_privileged_username: str = "") -> Optional[str]:
    """Why a new username can't be used, or None."""
    if username != username.strip():
        return "Usernames can't start or end with a space."
    if len(username) < USERNAME_MIN or len(username) > USERNAME_MAX:
        return f"Usernames need {USERNAME_HINT}."
    if not USERNAME_RE.fullmatch(username):
        return f"Usernames can use {USERNAME_HINT.split(': ', 1)[1]}, and must start with a letter or number."
    from .admin_access import moderator_usernames
    if username.casefold() in {name.casefold() for name in moderator_usernames()}:
        # Only a current privileged holder may retain a case variant of their
        # own reserved name. An old unprivileged case collision cannot claim it.
        if not current_privileged_username or username.casefold() != current_privileged_username.casefold():
            return "This username is reserved. Choose a different username."
    return None


def username_taken(db: Session, username: str, exclude_user_id: Optional[int] = None) -> bool:
    """Taken if any account already uses it, ignoring capitals ("Dan" blocks "dan")."""
    query = db.query(func.count()).select_from(_users()).filter(func.lower(_users().username) == username.lower())
    if exclude_user_id is not None:
        query = query.filter(_users().id != exclude_user_id)
    return bool(query.scalar())


def _users():
    from .models import User
    return User


def password_problem(password: str, username: str = "", email: str = "") -> Optional[str]:
    """Why a new password is too weak, or None (length and guessability, not symbol rules)."""
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return "Passwords can be at most 72 bytes (about 72 letters)."
    if len(password) < PASSWORD_MIN:
        return f"Use at least {PASSWORD_MIN} characters for your password."
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(lowered)) <= 2:
        return "That password is too easy to guess. Try a short phrase instead."
    name = (username or "").strip().lower()
    mailbox = (email or "").split("@", 1)[0].strip().lower()
    if (name and len(name) >= 3 and name in lowered and len(lowered) - len(name) < 4) or \
            (mailbox and len(mailbox) >= 3 and lowered == mailbox):
        return "Your password shouldn't be your username or email."
    return None
