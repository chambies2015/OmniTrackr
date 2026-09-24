# Library paging and search

The tracker uses `/library/page/{category}` to load 50 titles at a time. Search
and sorting operate on the full owned category before the page is selected.
Tied sort values use the item ID as a stable secondary order. Counts describe
the full filtered library. An offset beyond the last page is clamped, including
after deletion. Direct navigation from universal search or Today's pick can
prioritize the exact owned ID among duplicate titles.

Universal search uses `/library/search?q=...`. It returns at most eight compact
results across all six categories, prioritizing exact title matches, title
prefixes, title substrings, then metadata/review matches. Private reviews are
searched in the database but not included in these responses. Requests require
authentication, restrict all queries to the current user, and use private,
no-store caching. The browser debounces and cancels obsolete search requests.

Existing category endpoints and exports retain their full-list contracts.
The activity journal's item selector still uses its existing library index;
this change removes that index from universal search, not from the journal.
Database substring search still scans matching users' records; this is not a
full-text index. No database migration is required.

## Reproducing the local comparison

Run `python -m pytest tests/test_library_performance.py -q -s` in the project's
test environment. This seeds only the isolated test database with 3,000 movies,
each containing a synthetic private review, and compares response sizes. It
does not connect to production or assert timing thresholds.

One local SQLite/TestClient run produced:

| Request | Response bytes | Local elapsed | Returned rows |
| --- | ---: | ---: | ---: |
| Existing `/movies/` | 5,908,894 | 107 ms | 3,000 |
| First `/library/page/movies` | 98,437 | 9 ms | 50 |
| `/library/search?q=Synthetic` | 761 | 11 ms | 8 |

These are illustrative measurements, not production latency or browser render
benchmarks. Page loading also bounds immediate table rendering and poster
lookups. Poster retrieval concurrency is capped at four (lower on constrained
connections). Merely paging/filtering/sorting skips the dashboard refresh
normally performed after edits; explicit refreshes and mutations retain it.

Frontend behavior tests: `node --test tests/test_library_ui.cjs tests/test_todays_pick_ui.cjs`.
Backend contract tests: `python -m pytest tests/test_library.py -q`.
