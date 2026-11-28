"""Guide text that changes on a date (Nov 27 2026).

Seasonal and release guides are written before the dates they describe: "Violent Night 2 opens on
December 4", "most of them aren't out yet". Read a week later, those lines are wrong. A field that will
go stale can be written as a ``Dated`` value instead of a plain string:

    Dated("Violent Night 2 opens on December 4.",
          ("2026-12-04", "Violent Night 2 opened on December 4."))

``Dated`` is a ``str`` whose value is the text as first written, so code that only reads the guide
(word counts, search, tests) keeps working. A renderer calls ``resolve(value, today)`` on whatever it is
about to draw, and each ``Dated`` inside it becomes the version for that day: the last one whose start
date is on or before ``today``.
"""
from datetime import date
from typing import Any


class Dated(str):
    """A string with later versions, each a ``("YYYY-MM-DD", text)`` pair in date order."""

    later: tuple

    def __new__(cls, first: str, *later: tuple):
        value = super().__new__(cls, first)
        starts = [start for start, _ in later]
        if starts != sorted(starts):
            raise ValueError("Dated versions must be in date order")
        for start in starts:
            date.fromisoformat(start)
        value.later = tuple(later)
        return value

    def __reduce__(self):
        return (Dated, (str(self), *self.later))

    def on(self, day: date) -> str:
        text = str.__str__(self)
        iso = day.isoformat()
        for start, version in self.later:
            if iso >= start:
                text = version
        return text

    def versions(self) -> list[str]:
        """Every version, the first one included (for tests that check all of a page's words)."""
        return [str.__str__(self)] + [version for _, version in self.later]


def resolve(value: Any, day: date) -> Any:
    """``value`` with every ``Dated`` inside it (in dicts, lists and tuples) replaced by its text for ``day``."""
    if isinstance(value, Dated):
        return value.on(day)
    if isinstance(value, dict):
        return {key: resolve(item, day) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, day) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve(item, day) for item in value)
    return value
