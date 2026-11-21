"""Every "how long does it take" guide, in the order the hub lists them.

The writing and the lengths live in one file per format. Each guide is
hand-written: a lead, two sections and three questions, on top of a
part-by-part breakdown (seasons, arcs, books or films) whose numbers were
checked against a named source on the ``reviewed`` date.
"""
from .binge_guides_anime import GUIDES as _ANIME
from .binge_guides_books import GUIDES as _BOOKS
from .binge_guides_films import GUIDES as _FILMS
from .binge_guides_tv import GUIDES as _TV

FIRST_PUBLISHED = "2026-11-10"
GUIDES = {**_TV, **_ANIME, **_BOOKS, **_FILMS}
