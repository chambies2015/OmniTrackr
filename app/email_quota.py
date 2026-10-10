"""Serialize shared email budget reservations across scheduler processes."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models


# Stable PostgreSQL advisory-lock namespace, shared by both email schedulers.
EMAIL_BUDGET_LOCK = 0x4F4D4E4951554F54


def lock_email_budget(db: Session) -> None:
    if db.get_bind().dialect.name == "sqlite":
        # An UPDATE reserves SQLite's writer lock even when it matches no rows.
        # This mirrors the owner-first locking used for library writes.
        db.query(models.EmailDigestSubscription).filter(models.EmailDigestSubscription.id == -1).update(
            {models.EmailDigestSubscription.id: models.EmailDigestSubscription.id}, synchronize_session=False,
        )
    else:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": EMAIL_BUDGET_LOCK})
