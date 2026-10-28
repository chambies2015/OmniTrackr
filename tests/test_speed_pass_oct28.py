"""October 28 speed pass: title lookups through the slug index, cached page sections, shared people lookups."""
from app import models, people_pages, title_pages
from tests.test_optimization_pass_oct17 import GOOD_REVIEW, count_queries
from tests.test_title_pages import add_movie, member


# ---------------------------------------------------------------- slug index

def test_unknown_slug_reads_no_library_rows(db_session):
    a = member(db_session, "ua")
    for n in range(30):
        add_movie(db_session, a, f"Filler {n}", 2000 + n)
    db_session.commit()
    title_pages.find(db_session, "movie", "filler-1-2001")  # builds the index
    with count_queries(db_session) as statements:
        assert title_pages.find(db_session, "movie", "nothing-like-this-1999") is None
    # Only the "anything new?" check: no scan of every title for a mistyped link.
    assert len(statements) == 1 and "max(movies.id)" in statements[0]


def test_new_and_renamed_titles_are_found_at_once(db_session):
    a, b = member(db_session, "na"), member(db_session, "nb")
    add_movie(db_session, a, "Heat", 1995)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "heat-1995") is not None
    add_movie(db_session, b, "Heat", 1995)
    renamed = add_movie(db_session, b, "Ronin", 1998)
    db_session.commit()
    assert len(title_pages.find(db_session, "movie", "heat-1995").items) == 2
    renamed.title, renamed.year = "The Insider", 1999
    db_session.commit()
    assert title_pages.find(db_session, "movie", "ronin-1998") is None
    assert [item.id for item in title_pages.find(db_session, "movie", "the-insider-1999").items] == [renamed.id]


def test_privacy_still_applies_at_once(db_session):
    a = member(db_session, "pa")
    add_movie(db_session, a, "Heat", 1995)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "heat-1995") is not None
    a.movies_private = True
    db_session.commit()
    assert title_pages.find(db_session, "movie", "heat-1995") is None


def test_index_starts_over_when_rows_disappear(db_session):
    a = member(db_session, "da")
    add_movie(db_session, a, "Heat", 1995)
    newest = add_movie(db_session, a, "Ronin", 1998)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "ronin-1998") is not None
    db_session.delete(newest)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "ronin-1998") is None
    assert title_pages.find(db_session, "movie", "heat-1995") is not None


def test_accented_titles_match_their_ascii_slug(db_session):
    a = member(db_session, "aa")
    add_movie(db_session, a, "Pokémon: The First Movie", 1998)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "pokemon-the-first-movie-1998")
    assert group is not None and group.title == "Pokémon: The First Movie"


def test_paths_many_matches_find(db_session):
    a, b = member(db_session, "ma"), member(db_session, "mb")
    add_movie(db_session, a, "Heat", 1995)
    add_movie(db_session, b, " heat ", 1995)
    add_movie(db_session, a, "2001: A Space Odyssey", None)
    db_session.commit()
    slugs = ["heat-1995", "2001-a-space-odyssey", "missing-2000"]
    paths = title_pages.paths_many(db_session, "movie", slugs)
    assert paths == {slug: title_pages.find(db_session, "movie", slug).path for slug in slugs[:2]}


def test_find_many_still_marks_reviewed_rows(db_session):
    a, b = member(db_session, "ra"), member(db_session, "rb")
    reviewed = add_movie(db_session, a, "Arrival", 2016, review=GOOD_REVIEW, review_public=True)
    add_movie(db_session, b, "Arrival", 2016, rating=8)
    db_session.commit()
    groups = title_pages.find_many(db_session, "movie", ["arrival-2016"], reviewed_only=True)
    assert [item.id for item in groups["arrival-2016"].items] == [reviewed.id]
    assert len(title_pages.find_many(db_session, "movie", ["arrival-2016"])["arrival-2016"].items) == 2


# ---------------------------------------------------------------- cached page sections

def test_also_tracked_is_reused_while_fresh(db_session, monkeypatch):
    monkeypatch.setattr(title_pages, "_section_cache_enabled", lambda: True)
    title_pages.clear_section_cache()
    users = [member(db_session, f"s{n}") for n in range(3)]
    for user in users:
        add_movie(db_session, user, "Heat", 1995)
        add_movie(db_session, user, "Ronin", 1998)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "heat-1995")
    first = title_pages.summarize(db_session, group)
    first["related"][0]["title"] = "edited by a caller"
    with count_queries(db_session) as statements:
        second = title_pages.summarize(db_session, group)
    assert [r["title"] for r in second["related"]] == ["Ronin"]
    assert not any("count(DISTINCT" in s or "count(distinct" in s for s in statements)
    title_pages.clear_section_cache()


# ---------------------------------------------------------------- people pages

def test_people_pages_built_with_a_memo_match_fresh_builds(db_session):
    users = [member(db_session, f"p{n}") for n in range(4)]
    for user in users:
        add_movie(db_session, user, "Heat", 1995, director="Michael Mann", rating=8, review=GOOD_REVIEW, review_public=True)
        add_movie(db_session, user, "Collateral", 2004, director="Michael Mann", rating=7)
        add_movie(db_session, user, "Thief", 1981, director="Michael Mann", rating=9)
    db_session.commit()
    fresh = people_pages.build(db_session, people_pages.PERSON, "michael-mann")
    memo: dict = {}
    people_pages.build(db_session, people_pages.PERSON, "nobody-here", memo)
    shared = people_pages.build(db_session, people_pages.PERSON, "michael-mann", memo)
    again = people_pages.build(db_session, people_pages.PERSON, "michael-mann", memo)
    for page in (shared, again):
        assert [(w.url, w.members, w.rated, w.average, w.roles) for w in page.works] == \
               [(w.url, w.members, w.rated, w.average, w.roles) for w in fresh.works]
        assert page.name == fresh.name
