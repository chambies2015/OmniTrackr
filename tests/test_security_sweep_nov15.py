"""Sweep of the Nov 15 merges: the Nov 14b sweep (#211), 24 more In order guides (#212) and the
site search rebuild (#213). The search box answers as people type, so most fixes are about
how much work one search does on a big title index; results must stay exactly the same."""
import difflib
import random

import pytest

from app import site_search, title_pages, title_search
from app.routers import site_search as search_router
from tests.test_site_search import fresh_caches, library  # noqa: F401  (fixtures)

KINDS = list(title_pages.KINDS)


def _index(size=title_search.PREFIX_MIN_ENTRIES + 500, seed=3):
    rng = random.Random(seed)
    words = ["".join(rng.choice("aeioustrnlmkdh") for _ in range(rng.randint(1, 8))) for _ in range(800)]
    known = ["Interstellar", "The Witcher 3 Wild Hunt", "Frieren Beyond Journey's End", "Star Wars", "Dune Part Two"]
    entries = []
    for number in range(size):
        title = known[number % len(known)] if number % 40 == 0 else " ".join(
            rng.choice(words) for _ in range(rng.randint(1, 4)))
        base = title_pages.slugify(title)
        entries.append({"kind": rng.choice(KINDS), "label": "x", "title": title.title(), "year": None, "slug": base,
                        "image": None, "members": rng.randint(1, 9), "words": base.split("-"), "base": base})
    return entries, words


def _full_scan(entries, text, kind=None):
    """title_search.ranked as it was before the two-letter lookup."""
    query = title_pages.slugify(text[:title_search.QUERY_MAX])
    if (query == "title" and "title" not in text.lower()) or len(query.replace("-", "")) < 2:
        return []
    tokens = [token for token in query.split("-") if token]
    scored = []
    for entry in entries:
        if kind is not None and entry["kind"] != kind:
            continue
        rank = title_search._rank(entry, query, tokens)
        if rank is not None:
            scored.append((rank, -entry["members"], len(entry["title"]), entry["title"].casefold(), entry))
    scored.sort(key=lambda row: row[:4])
    return [row[-1] for row in scored]


def _plain_suggest(text, entries, guides):
    """site_search.suggest as it was before the length and letter checks."""
    query, _ = site_search._query(text)
    if len(query) < 4:
        return None
    names = {}
    for entry in entries:
        names.setdefault(entry["base"], entry["title"])
    for entry in guides:
        if entry["section"] != "Page":
            names.setdefault(entry["base"], entry["title"])
    close = difflib.get_close_matches(query, list(names), n=1, cutoff=site_search.SUGGEST_CUTOFF)
    if close:
        return names[close[0]]
    prefixes = {}
    for base, title in names.items():
        prefixes.setdefault(base[:len(query)], title)
    close = difflib.get_close_matches(query, list(prefixes), n=1, cutoff=site_search.SUGGEST_CUTOFF + 0.06)
    return prefixes[close[0]] if close else None


def _typo(rng, text):
    letters = list(text)
    for _ in range(rng.randint(0, 3)):
        spot = rng.randrange(len(letters)) if letters else 0
        roll = rng.random()
        if roll < 0.33 and letters:
            del letters[spot]
        elif roll < 0.66:
            letters.insert(spot, rng.choice("aeiostrx "))
        elif letters:
            letters[spot] = rng.choice("aeiostrx")
    return "".join(letters)


# ---------------------------------------------------------------- ranking

def test_two_letter_lookup_ranks_exactly_like_a_full_scan():
    entries, words = _index()
    rng = random.Random(11)
    queries = ["a", "a b", "st wa", "the witcher 3", "3", "1 2 3", "!!", "title", "interstellar", "zzzz",
               " ".join("ab" for _ in range(30))]
    queries += [rng.choice(words)[:rng.randint(1, 6)] for _ in range(150)]
    queries += [" ".join(rng.choice(words)[:3] for _ in range(rng.randint(2, 3))) for _ in range(100)]
    for query in queries:
        for kind in (None, rng.choice(KINDS)):
            assert title_search.ranked(entries, query, kind=kind) == _full_scan(entries, query, kind), (query, kind)


def test_the_lookup_is_built_once_per_index_and_again_for_a_new_one():
    entries, _ = _index()
    title_search.ranked(entries, "star")
    first = title_search._prefix_cache["positions"]
    title_search.ranked(entries, "dune")
    assert title_search._prefix_cache["positions"] is first

    rebuilt = [dict(entry) for entry in entries]
    title_search.ranked(rebuilt, "star")
    assert title_search._prefix_cache["entries"] is rebuilt and title_search._prefix_cache["positions"] is not first
    # A list that grew since is looked at again rather than trusted.
    rebuilt.append({**rebuilt[0], "title": "Zebra Quest", "base": "zebra-quest", "slug": "zebra-quest",
                    "words": ["zebra", "quest"]})
    assert [e["title"] for e in title_search.ranked(rebuilt, "zebra")] == ["Zebra Quest"]


def test_small_lists_skip_the_lookup():
    entries, _ = _index(size=50)
    title_search.ranked(entries, "star")
    assert title_search._prefix_cache["entries"] is None


def test_a_rebuilt_index_has_its_lookup_ready_before_anyone_searches(db_session, monkeypatch):
    entries, _ = _index()
    monkeypatch.setattr(title_search, "build_index", lambda db: entries)
    assert title_search.index(db_session) is entries
    assert title_search._prefix_cache["entries"] is entries


# ---------------------------------------------------------------- "Did you mean"

def test_suggestions_match_plain_difflib():
    entries, words = _index()
    guides = site_search.guide_entries()
    rng = random.Random(5)
    seeds = ["interstellar", "the witcher 3", "frieren", "star wars", "dune part two", "breaking bad", "naruto"]
    queries = [_typo(rng, rng.choice(seeds + words)) for _ in range(250)] + ["qqqqqqzz", "ab", "x" * 80]
    for query in queries:
        assert site_search.suggest(query, entries, guides) == _plain_suggest(query, entries, guides), query
        kind = rng.choice(KINDS)
        own = [entry for entry in entries if entry["kind"] == kind]
        assert site_search.suggest(query, entries, site_search._NO_GUIDES, kind=kind) == _plain_suggest(query, own, []), (query, kind)


def test_suggestion_spellings_are_kept_per_index_and_format():
    entries, _ = _index()
    guides = site_search.guide_entries()
    site_search.suggest("interstelar", entries, guides)
    first = site_search._suggest_cache["names"][None][1]
    # Searching one format doesn't throw away the spellings for all of them.
    site_search.suggest("frirein", entries, site_search._NO_GUIDES, kind="anime")
    site_search.suggest("frirein", entries, guides)
    assert site_search._suggest_cache["names"][None][1] is first
    assert set(site_search._suggest_cache["names"]) == {None, "anime"}
    # A new day's guide list or a rebuilt index starts over.
    site_search.suggest("frirein", entries, list(guides))
    assert site_search._suggest_cache["names"][None][1] is not first
    site_search.suggest("frirein", [dict(entry) for entry in entries], guides)
    assert set(site_search._suggest_cache["names"]) == {None}


# ---------------------------------------------------------------- popular titles

def test_popular_titles_are_worked_out_once_per_index(monkeypatch):
    entries, _ = _index()
    calls = []
    real = site_search._popular
    monkeypatch.setattr(site_search, "_popular", lambda *args: calls.append(args[1:]) or real(*args))
    first = site_search.popular(entries)
    assert site_search.popular(entries) == first and site_search.popular(entries, "movie", 12)
    assert calls == [(None, site_search.POPULAR_LIMIT), ("movie", 12)]
    first[0]["title"] = "changed by a caller"
    assert site_search.popular(entries)[0]["title"] != "changed by a caller"
    site_search.popular([dict(entry) for entry in entries])
    assert len(calls) == 3
    # Still never a title only one member tracks.
    assert all(item["members"] >= 2 for item in site_search.popular(entries, limit=40))


def test_empty_search_page_and_api_share_the_popular_lists(client, library, monkeypatch):
    calls = []
    real = site_search._popular
    monkeypatch.setattr(site_search, "_popular", lambda *args: calls.append(args[1:]) or real(*args))
    for _ in range(3):
        assert client.get("/search").status_code == 200
        assert client.get("/api/search").status_code == 200
    assert sorted(calls, key=str) == sorted([(None, site_search.POPULAR_LIMIT), (None, search_router.POPULAR_ON_PAGE)], key=str)


# ---------------------------------------------------------------- the /search page

def test_results_page_ranks_the_index_once(client, library, monkeypatch):
    calls = []
    real = title_search.ranked
    monkeypatch.setattr(title_search, "ranked", lambda *args, **kwargs: calls.append(args[1]) or real(*args, **kwargs))
    page = client.get("/search", params={"q": "inter", "kind": "movie"})
    assert page.status_code == 200 and "Interstellar" in page.text
    assert calls == ["inter"]
    # The chips still count every format, and "All" counts both.
    assert 'href="/search?q=inter&amp;kind=tv"' in page.text and "TV <span>1</span>" in page.text


@pytest.mark.parametrize("kind", [None, "movie"])
def test_page_counts_match_the_api(client, library, kind):
    # Interstellar (a film) and Interview with the Vampire (a series) match "inter".
    params = {"q": "inter", **({"kind": kind} if kind else {})}
    data = client.get("/api/search", params=params).json()
    result = site_search.search(library, "inter", kind, limit=36, counts=True)
    assert [t["title"] for t in result["titles"]] == [t["title"] for t in data["titles"]]
    assert result["counts"] == {None: 2, "movie": 1, "tv": 1} and result["total"] == data["total"]
