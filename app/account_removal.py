"""Remove one member account for good, from the owner-only Site stats page.

Members can only deactivate themselves (rows kept for 90 days). This is the
owner's tool for accounts that should never have existed, like a test sign-up.

The plan is built from the table metadata rather than a hand-kept list, so a
table added later is covered without anyone remembering to update this file:

* A row that points at a removed row through a column marked ``SET NULL``, or
  through an optional column with no rule, keeps living with that column
  emptied (a Ko-fi payment, "added by" on another member's club list).
* Every other pointing row is removed too, and whatever points at it in turn.

Removal is refused when it would reach past the account's own rows into
another member's: a reply someone wrote on this account's discussion, another
member's place in a club this account started. Deactivating is the answer for
those accounts. Rows that point straight at the account (a friendship, a cheer
on its feed, a recommendation sent to it) go with it, as they would for any
deleted account.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import Table, delete, select, update
from sqlalchemy.orm import Session

from . import admin_access, editorial_collections, models
from .database import Base

logger = logging.getLogger("omnitrackr.admin")

CHUNK = 400  # Stays under SQLite's bound-parameter limit on older builds.

USERS = models.User.__table__


def _chunks(values: list) -> list[list]:
    return [values[start:start + CHUNK] for start in range(0, len(values), CHUNK)]


def _pk(table: Table):
    columns = list(table.primary_key.columns)
    if len(columns) != 1:
        raise RuntimeError(f"{table.name} needs a single-column primary key to be removed row by row")
    return columns[0]


def _sets_null(foreign_key) -> bool:
    rule = (foreign_key.ondelete or "").upper()
    if rule == "SET NULL":
        return True
    return not rule and bool(foreign_key.parent.nullable)


def _referencing(table: Table) -> list:
    """Every foreign key in the schema that points at ``table``."""
    found = []
    for other in Base.metadata.sorted_tables:
        for foreign_key in other.foreign_keys:
            if foreign_key.column.table is table:
                found.append(foreign_key)
    return found


def _label(table_name: str) -> str:
    return table_name.replace("_", " ")


@dataclass
class Plan:
    user_id: int
    username: str
    removes: dict[str, set] = field(default_factory=lambda: defaultdict(set))
    empties: dict[tuple[str, str], set] = field(default_factory=lambda: defaultdict(set))
    others: dict[str, int] = field(default_factory=dict)
    refusal: str | None = None

    @property
    def blocked(self) -> bool:
        return bool(self.refusal or self.others)

    def summary(self) -> dict:
        removes = {name: len(ids) for name, ids in self.removes.items() if ids and name != USERS.name}
        empties = defaultdict(int)
        for (name, _column), ids in self.empties.items():
            if ids:
                empties[name] += len(ids)
        reason = self.refusal
        if not reason and self.others:
            parts = ", ".join(f"{count} in {_label(name)}" for name, count in sorted(self.others.items()))
            reason = (f"Removing this account would also delete other members' rows ({parts}). "
                      "Deactivate it instead, or clear those first.")
        return {
            "user_id": self.user_id,
            "username": self.username,
            "rows": [{"table": name, "label": _label(name), "count": count} for name, count in sorted(removes.items())],
            "total_rows": sum(removes.values()),
            "kept_with_link_cleared": [{"table": name, "label": _label(name), "count": count}
                                       for name, count in sorted(empties.items())],
            "other_members_rows": [{"table": name, "label": _label(name), "count": count}
                                   for name, count in sorted(self.others.items())],
            "can_remove": not self.blocked,
            "reason": reason,
        }


def refusal_for(target: models.User, admin: models.User) -> str | None:
    if target.id == admin.id:
        return "You can't remove your own account here."
    if admin_access.is_site_admin(target):
        return "That account is a site admin. Take it out of ADMIN_USERNAMES first."
    if target.username == editorial_collections.EDITOR_USERNAME:
        return "That is the editors account that owns the starter collections."
    return None


def plan_for(db: Session, target: models.User, admin: models.User) -> Plan:
    plan = Plan(user_id=target.id, username=target.username, refusal=refusal_for(target, admin))
    plan.removes[USERS.name].add(target.id)
    tables = Base.metadata.tables
    # Rows reached through a row other than the account itself, by table.
    deeper: dict[str, set] = defaultdict(set)
    queue: list[tuple[Table, set]] = [(USERS, {target.id})]
    while queue:
        table, ids = queue.pop()
        for foreign_key in _referencing(table):
            child = foreign_key.parent.table
            column = foreign_key.parent
            target_column = foreign_key.column
            pk = _pk(table)
            if target_column is pk:
                values = list(ids)
            else:
                values = [value for chunk in _chunks(list(ids))
                          for (value,) in db.execute(select(target_column).where(pk.in_(chunk)))
                          if value is not None]
            if not values:
                continue
            child_pk = _pk(child)
            matched = {row_id for chunk in _chunks(values)
                       for (row_id,) in db.execute(select(child_pk).where(column.in_(chunk)))}
            if not matched:
                continue
            if _sets_null(foreign_key):
                plan.empties[(child.name, column.name)].update(matched)
                continue
            fresh = matched - plan.removes[child.name]
            if not fresh:
                continue
            plan.removes[child.name].update(fresh)
            if table is not USERS:
                deeper[child.name].update(fresh)
            queue.append((child, fresh))

    # A row reached only through another removed row, written by someone else, is theirs.
    for name, ids in deeper.items():
        table = tables[name]
        pk = _pk(table)
        member_columns = [fk.parent for fk in table.foreign_keys if fk.column.table is USERS]
        if not member_columns:
            continue
        count = 0
        for chunk in _chunks(list(ids)):
            rows = db.execute(select(pk, *member_columns).where(pk.in_(chunk))).all()
            count += sum(1 for row in rows
                         if any(value is not None and value != target.id for value in row[1:]))
        if count:
            plan.others[name] = count
    return plan


def remove(db: Session, target: models.User, admin: models.User) -> dict:
    """Delete the account and everything it owns, in one transaction. Raises ValueError when refused."""
    plan = plan_for(db, target, admin)
    summary = plan.summary()
    if plan.blocked:
        raise ValueError(summary["reason"])
    tables = Base.metadata.tables
    user_id, username = target.id, target.username
    joined = target.created_at.date().isoformat() if target.created_at else "unknown"
    try:
        # Clear links first so nothing still points at a row about to go.
        for (name, column_name), ids in plan.empties.items():
            table = tables[name]
            pk = _pk(table)
            for chunk in _chunks(list(ids)):
                db.execute(update(table).where(pk.in_(chunk)).values({column_name: None}))
        # Children before parents: sorted_tables lists parents first.
        for table in reversed(Base.metadata.sorted_tables):
            ids = plan.removes.get(table.name)
            if not ids:
                continue
            pk = _pk(table)
            for chunk in _chunks(list(ids)):
                db.execute(delete(table).where(pk.in_(chunk)))
        db.expunge(target)
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.warning(
        "account removed by admin: admin=%s (id %s) removed username=%s (id %s, joined %s); "
        "%s other rows deleted, %s links cleared",
        admin.username, admin.id, username, user_id, joined, summary["total_rows"],
        sum(item["count"] for item in summary["kept_with_link_cleared"]),
    )
    return summary
