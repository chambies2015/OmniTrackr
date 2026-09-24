# Growth and trust operations

This is the canonical engineering note for OmniTrackr activation, retention,
analytics boundaries, and advertising readiness. Product claims and policy text
remain authoritative on the public Privacy, Advertising, Roadmap, and Changelog
pages.

## Activation path

Configured trusted operators can view aggregate activation stages in the
existing site-health panel. No separate event stream is created, and public
collection discovery does not depend on an operator queue.

| Stage | Definition |
| --- | --- |
| Accounts created | All account records. |
| Email verified | Accounts with a verified email. |
| Library started | Verified accounts with at least one built-in media item. |
| Five titles saved | Verified accounts with at least five built-in media items across all six categories. |
| Returned after activation | Activated accounts with at least two successful logins recorded after this release. |

The return stage is intentionally conservative. Login counting starts when the
schema addition is deployed; historical visits are not inferred or backfilled.
The moderator response excludes email addresses, media titles, searches, review
text, private notes, and page histories.

## Public collection to private library

Public collection pages link to `/collections/public/{id}/save`. The standalone,
ad-free, analytics-free page is `noindex` and `private, no-store`, including
authentication and validation failures. Reading the page or its authenticated
preview never creates a collection. The preview distinguishes exact edition
matches from new titles; readers select titles and explicitly confirm the save.
New records begin unfinished, unrated, and without a public review. Reused
records retain every personal field.

The existing strictly validated, 24-hour same-tab authentication return retains
this save page through signup, email verification and login. Returning loads a
fresh preview; it never performs a save. Verification completed in another tab
may lose this optional return context. The original public collection remains
available to revisit.

A save checks current source visibility, moderation and the complete copied
content version. Changes require a fresh preview. A transaction saves the
selection and a `collection_save_receipts` row together. Its unique key uses the
account, source collection, content version and selected item IDs, so repeated
clicks or a retry after a lost response reuse the original saved collection,
including after a private rename or edit. A different selection or revised
source can create a separate copy after explicit confirmation. Result links use
the existing owner-checked `/?collection={id}` navigation.

The receipt table is an additive `Base.metadata.create_all` schema change; it
does not rewrite existing tables or data. Deleting a saved collection removes
its receipt, allowing a future explicit save. Source edits, withdrawal or deletion
never update or remove private copies. Copies from before this release and
imported backups remain intact and are not retrospectively linked to a source.
The older `/copy` endpoint keeps its response contract and uses the same
duplicate protection for the full selection.

## Interactive demo to first title

The homepage links to an interactive `/demo` before signup. Six fictional sample
entries are rendered on the server so the page remains useful without JavaScript.
Its small standalone script supports category filters, adding sample titles,
completion, ratings and notes, with statistics calculated from the sample library.
Practice state lives only in the page's memory and resets on reload or Reset.
The demo sends no library requests, uses no browser storage, and never transfers
practice entries to a real account. It loads neither ads nor analytics.

The signup link uses the fixed `/?start=demo#landing-auth` destination. A bounded
same-tab navigation hint keeps the first-title context through registration and
email verification; it contains no sample titles, ratings or notes. Existing
review and Discover destinations and account-recovery actions take precedence.
For an empty account, the existing launchpad guides the member into Add Anything
after an explicit click. Searching, selecting and saving remain separate actions.
Existing accounts keep their own library and onboarding preferences.

Success is evaluated through the existing aggregate activation milestones:
verified accounts, first title, five titles, and later returns. No new visitor
tracking, event stream, database schema, or attribution claim is introduced.

For local browser QA, `python -m tests.manual_mobile_preview --empty --quick-capture`
provides an empty synthetic account and local metadata responses. `/demo` can be
used anonymously; the fixture's `preview` account uses `local-preview-only`.

## Add anything search reliability

Quick Capture renders each media source independently. Each source has a
15-second client deadline (including body parsing), and failed sources can be
retried individually without repeating successful lookups. OMDB's HTTP-200
error bodies distinguish a recognized title miss from service/quota failures.
Successful result buttons keep their DOM identity and selection index as other
sources arrive. No source retries automatically.

Editing the query, choosing a different media category, or closing the dialog
aborts outstanding requests and invalidates their render state. Session identity
checks also reject late responses that arrive after cancellation. Typing and
changing categories do not issue searches; the user submits Search explicitly.
Manual entry is above the results and remains available while requests run.

Searches use the existing authenticated metadata proxies. Choosing a result or
manual entry fills the existing category form, preserves its draft-replacement
confirmation and completion intent, and requires an explicit save. No library
record, database schema, or public sharing preference is changed by searching.

## Public reviews to personal library

The public review directory puts member reviews directly after its title and
filters. Title searches and category filters share the same eligibility and
ordering on the server and in the browser. Review quality, active authors, and
version-bound moderation are checked before pagination. The existing public
review API retains its array response; the directory uses a paginated feed
with explicit continuation state. Search-result URLs and directories without
search-ready reviews are not indexed.

Initial cards are server rendered and remain visible as the browser initializes.
Filtering replaces them only after a successful response; failed requests keep
the previous cards with an explicit retry. Category changes cancel superseded
requests, and generation checks reject late responses. Writing guidance lives
on the existing review guide, linked from the directory.

Save links open a separate, unindexed preview page. Guests can return to that
page after same-tab login, registration, and email verification through the
existing 24-hour navigation hint. Previewing only reads the current user's
library. Adding requires explicit confirmation, and the server rechecks public
eligibility and the previewed metadata version. A title match in that category
is reused without editing it. A new item contains allowlisted public metadata,
starts unfinished and unrated, and has no review or public-review selection.
The source author's notes, ratings, and completion state are never copied.

After saving, an owner-scoped dashboard link opens the exact library item.
Ambiguous or invalid identifiers are rejected; interrupted navigation respects
the member's next action. Read responses accept missing stored creator/year
metadata so older imports can still open; creation validation is unchanged.
There are no database schema changes or new analytics events.
The directory and save pages remain ad-free.

For disposable browser QA, run
`python -m tests.manual_mobile_preview --reviews`. This creates only temporary
synthetic data. The fixture's `preview` account uses `local-preview-only` as its
password; `/qa` also provides a local authenticated entry point. Stop the
fixture with Ctrl+C.

## Discover to first save

The homepage now links directly to existing editorial trails. Discover's search
and format filters run in the browser without sending search text or creating a
new analytics stream. All recommendations and source links remain readable
without JavaScript or an account; filters appear only when their script runs.

A guest's save link carries an allowlisted Discover destination through login.
The destination is held for at most 24 hours in session storage, so signup and
email verification can continue in the same tab. A separate tab or browser may
not retain that intent; the original tab remains the place to resume. A denied
storage setting still allows a return after login on the current page.

Returning performs a read-only preview. Saving always requires a submit, and an
expired session retains only selected public catalog keys for a retry. Existing
title matches are reused without changing ratings, reviews, or completion.
The confirmation opens the saved collection through the owner's authenticated
collection list. Navigation never publishes a collection or queues a title.

The signed-out homepage also now processes email-verification and password-reset
links before choosing the normal login form. It continues to ignore stale local
authentication data when deciding whether to show the private dashboard.

## Expanded Discover guides

Three existing trails now have complete public decision guides:
`one-evening-well-spent`, `finding-your-feet`, and
`beautifully-strange-worlds`. Their reviewed editorial data lives in
`app/discover_guides.py`; existing catalog keys and saved-title metadata remain
in `app/discover_catalog.py`. Each guide adds a practical comparison, cross-media
analysis, starting notes, related reading, and four verified primary sources.
The full reading experience is server rendered, with
page anchors and source notes available without JavaScript or authentication.

Only those three trail details are promoted to `index, follow` and included in
the sitemap. The remaining seven stay `noindex, follow` and excluded. Article
structured data identifies OmniTrackr as the organization author/publisher;
`dateModified`, the visible review date, and sitemap `lastmod` use the guide's
explicit `reviewed` date, currently `2026-09-24`. The original publication date
remains `2026-09-08`. Change the review date when the guide is substantively
reviewed; do not replace it with the current request date. Directory and monthly
edition indexing policy is unchanged.

The visible method note discloses AI assistance and separates factual source
checks from editorial judgments. Source notes describe what is supported and
flag regional access or additional plot detail when relevant. This release
corrects Blue's official link from the wrong album (`id=13`) to `id=5`, updates
Florence's publisher URL and removes its unsupported one-hour estimate, explains
Before Sunset's sequel context, and uses the specific Earthsea author page,
original Mushishi broadcaster page, and direct Piranesi publisher page. Reading
and game commitments describe the experience rather than guaranteed durations.

The guides retain the existing save-panel selectors and authenticated API.
Preview, same-tab auth return, explicit title selection, duplicate matching,
private collection creation, and preservation of existing personal fields are
unchanged. There are no database/schema changes, new events, or new ad slots.
Release verification passed 129 focused Python tests and all 227 frontend
tests. Disposable browser checks covered desktop and 390/320px mobile reading,
section links, guest sign-in return, selected saves, repeat-save matching, and
opening the private collection. Independent source review found no actionable
factual or spoiler issues. The content-quality policy now reflects the guides'
AI assistance and source-checking method. See `docs/public-content-review.md`
for the publication decision and limits of AdSense readiness evidence.

## Welcome Back Deck

After a successful login following at least three full days away, the login
response gives that browser a short-lived eligibility signal. It is kept in
session storage for no more than 24 hours and is removed when the member opens
an item, dismisses the deck, logs out, or no longer qualifies. The signal is not
stored as a server-side visit history.

Members with at least five built-in library items can receive one private deck
composed from the existing Today’s Pick, Library Pulse, Next Up, and Activity
Journal data. While it is active, it replaces Today’s Pick and Library Pulse;
it does not add a fourth permanent decision surface. There are no email or push
reminders, streaks, public return profiles, or ad placements in this flow.

The site-health panel reports daily aggregate totals for decks shown, items
opened, and decks dismissed. The aggregate rows have no user, session, media,
IP, search, or page-history fields. Their purpose is to determine whether the
return experience is useful enough to keep, simplify, or remove.

## Analytics boundary

Google Analytics is loaded only by the standalone public landing page. It is not
loaded by the authenticated dashboard. The loader exits before requesting a
Google script when supported Global Privacy Control or Do Not Track signals are
enabled, disables Google signals and ad-personalization signals, and requests IP
anonymization.

Aggregate activation data comes from OmniTrackr's own account and library
records, not Google Analytics. Successful-login measurement stores only the most
recent successful login timestamp and a running count. These values are included
in the account's JSON export metadata. Welcome Back engagement is retained only
as anonymous day-level totals and cannot be joined back to an account.

## Advertising readiness

AdSense approval is never guaranteed by code or content changes. Before an
application or re-review:

1. Confirm production `ads.txt`, publisher metadata, canonical URLs, and sitemap output.
2. Confirm ads remain restricted to the server and client allowlists and never load in the private dashboard.
3. Confirm the public Privacy and Advertising pages match production behavior.
4. Configure and verify the Google-certified CMP required before serving personalized ads to visitors in the EEA, United Kingdom, or Switzerland. The Google Privacy & messaging option is one supported route; repository tests cannot verify account-side configuration.
5. Review public pages for original reader value, accurate claims, working navigation, and adequate moderation.
6. Use Search Console and AdSense feedback to choose follow-up work instead of adding speculative pages.

## Automated public-review quality and safety

The review directory reuses the existing opt-in review field and has two display
tiers rather than a second publishing workflow. Community-ready reviews require
at least 80 trimmed characters, varied language, and the public safety checks.
Search-ready reviews additionally require at least 240 characters, 35 words,
and either two complete thoughts or 55 words. Obvious links, contact details,
promotional phrases, placeholder text, and mechanically repeated filler fail the
relevant public tier without changing the saved library review.

Only search-ready reviews receive standalone detail pages, Review structured
data, sitemap URLs, prominent ordering, or ad eligibility. Community-ready
reviews remain browseable and reportable as summaries. The shared review
directory stays ad-free; only qualifying standalone review details may load ads.

Public reports reuse the signed, HTTP-only visitor cookie already used by public
collections. The database stores its one-way hash and a fixed reason, not an IP
address, fingerprint, or free-text report. One browser can report an exact review
version once, and the endpoint is limited to two submissions per IP address per hour. Three
independent reports temporarily unlist that content hash and create an in-app
notification for the author. Nothing is deleted. Editing the review changes its
hash, restores the revision automatically, and resets its current report count
when a new report is received. Aggregate report and unlisting counts appear in
the existing site-health panel; review text and reporter identity do not.

## Automated public-collection readiness and safety

Collections remain private until their owner deliberately publishes them. The
existing share-ready floor requires 300 trimmed introduction characters and at
least three available titles. One collection readiness result then controls the
editor status, gallery, detail-page indexability, and sitemap inclusion. Public
discovery additionally requires a meaningful title, at least 45 introduction
words, complete thoughts, varied language, and the shared checks against links,
contact details, promotional bait, and placeholder text. Curator notes are
included in the safety check but remain optional.

A collection that meets only the share-ready floor keeps its direct URL with a
`noindex` directive. A discovery-ready collection enters the existing gallery
automatically; there is no routine approval queue and no paid moderation
service. The optional trusted-operator configuration remains only for aggregate
site health and exceptional emergency blocking.

Collection reports reuse the signed public-visitor cookie and store only a fixed
reason, timestamp, and one-way visitor hash. Free-text allegations are rejected.
One browser can report the current collection version once, and the endpoint is
limited to two submissions per IP address per hour. Three independent reports
temporarily unlist that exact content hash and notify the owner. Nothing is
deleted. An owner edit clears the current report state, reruns readiness, and
restores the new version when it qualifies.

## Private progress checkpoints

TV, anime, and books have a separate private stopping point. The progress editor
saves the last watched episode (optional season; season 0 means specials), or the
last read page/chapter, plus an optional 300-character reminder. Explicit Save
and Clear actions affect only the checkpoint. They never change completion,
ratings, reviews, episode/season metadata, or Journal history. Recently updated
unfinished checkpoints lead Continue; Next Up keeps its manual order. Relevant
Welcome Back cards also display the saved stopping point.

Storage adds the `progress_checkpoints` table through the existing model startup
path without rewriting existing media. Its owner/category/item key is unique.
Owner/media row locks and conditional revisions serialize writes; SQLite reserves
the owner write transaction. Old tabs receive a conflict, and retries repeat the
same request without advancing the revision twice. Clear retains an empty
revision record so stale writes and old backups cannot resurrect a cleared place.
Deleting an owned title removes its checkpoint; account deletion cascades.

The authenticated `/progress/{category}/{item_id}` API and dashboard responses
use private/no-store caching. Checkpoints do not enter public or friend media
schemas, shared collections, reviews, or copied recommendations. Editor drafts
stay in memory and are discarded on account change or page exit. Progress has no
ad slot or new analytics stream.

JSON backup version 1.3 includes `progress_checkpoints`. Restore matches an owned
title and complete edition identity (year, plus author for books, including nulls),
requires exactly one match, and creates only absent checkpoints. Ambiguous,
malformed, missing-title, existing, and previously cleared checkpoints are skipped
and counted in the import result. Database IDs, revisions, and saved timestamps
from the file are not trusted; restored checkpoints receive a new local revision
and restore time. Older backups remain valid. The existing media import merge
behavior is unchanged. The public demo uses fictional in-memory checkpoints and
restores its examples on reset/reload.

## Compact daily dashboard

Search, Add Anything, and the horizontally scrollable category navigation sit
above daily suggestions. Account controls stay in the document flow, including
the Friends toggle, so they cannot cover the library controls on a phone.
Choosing a category brings its heading into view, including custom categories.
Continue shows two recent unfinished titles, with all reflection suggestions
available under Make it memorable. Today's Pick shares the same panel, and the
Welcome Back flow still replaces those suggestions when appropriate.

Next Up initially shows three entries. Manage queue expands the full list and
its existing reorder controls; Remove remains available in the preview. Expansion
is in-memory UI state and survives refreshes and progress saves. The saved queue
order changes only after an explicit queue action. Keyboard focus follows the
same entry after a reorder or the next available control after removal. Account
cleanup clears the preview, private suggestion copy, and expansion state.
An empty queue stays hidden. With no unfinished titles, the unfiltered Today's
Pick also stays hidden; a selected category with no matches keeps its filter
available. A new account therefore sees its launchpad without extra empty cards.

Suggestion and queue Open actions use the existing exact-ID library navigation,
including its pagination lookup, hidden-category checks, and edit protection.
Queue entry IDs remain separate from media IDs. Journal's Open library action
continues to open the category because historic entries can outlive their titles.

This release changes frontend behavior and public copy; it adds no database
schema or migrations. Public homepage examples now identify themselves as
examples and show supported checkpoints, completion states, journal counts, and
Tasteprint text, without game-hour tracking or episode percentage claims.

For a disposable dashboard walkthrough, run
`.\.venv\Scripts\python.exe -m tests.manual_mobile_preview --daily-dashboard --quick-capture`
and open `http://127.0.0.1:8765/qa`. The eight-entry queue includes an unavailable
entry, and the checkpointed book has 51 same-title editions ahead of it in normal
browsing. Verify Continue and Next Up both open the target edition identified on
the fixture page, then check expansion, reordering, progress refresh, and mobile
navigation. The fixture creates a temporary SQLite database and does not load
the project's `.env`.

Dashboard release verification, September 24, 2026: all 227 frontend tests and
97 focused public-page/SEO/static-security tests passed, along with JavaScript
syntax and diff checks. Disposable browser checks covered desktop and 390/320px
mobile layouts, both themes, exact edition navigation beyond the first page,
queue reorder and progress refresh, category navigation, Notifications and
Friends controls, and public homepage examples. A background 401 cleared the
private dashboard and progress draft. An empty library showed only onboarding;
adding its first title activated suggestions, and removing its only queue entry
returned focus to Add Anything while preserving the saved movie. No production
data was used and nothing was deployed.

## Inspectable Import Studio

The September 24, 2026 import update makes existing CSV migration easier to
inspect before a member commits a batch. Music's `listened` column is now read
as completion, matching the downloadable template. Generic ratings keep the
distinction between an explicit zero and an empty cell; the latter is unrated.
Malformed or out-of-range values are reported as invalid rows instead of being
silently clamped or discarded. Explicit column mappings take precedence over
automatic aliases, including mapped blank or false values.

The preview exposes converted ratings, completion, and private review text.
Outcome filtering and pagination cover the whole accepted file, rather than
only the first 100 rows. Changing the file or its interpretation invalidates
the preview; older responses must not restore a stale confirmation. A completed
import retains a result summary and offers navigation to the affected library
categories. These results are transient UI state, not another history store.

The write contract remains additive: preview performs no writes, the user
explicitly confirms the matching file and options, and ready records commit in
one transaction. Duplicates are rechecked against the member's current library
when applying. Existing records and their personal fields are never updated by
CSV import. Reviews remain private, and this release adds no schema or migration.

The expanded `/export-import-guide` uses fictional music and book CSV samples
with expected ratings, completion, duplicate, and invalid-row outcomes. It
documents category-specific duplicate matching, UTF-8 CSV/TSV requirements,
the 5 MB / 5,000-row limits, and the difference between CSV migration and JSON
restore. MyAnimeList support is explicitly described as CSV-column support;
native XML is not accepted. Goodreads read dates set completion but are not
preserved as dated journal entries. Letterboxd review text and repeated diary
visits are not migrated by that adapter. CSV episode totals do not create
progress checkpoints; checkpoints belong to the separate JSON backup path.

Release verification, September 24, 2026: all 139 focused backend, SEO/security,
static-security, and public-guide checks passed against isolated SQLite. All 254
frontend checks passed, including stale responses, file changes, inline
confirmation, timeouts covering the response body, logout cleanup, and deferred
library refresh after an older request. Backend coverage includes every media
category, explicit mappings, rows beyond 100, duplicate preservation, atomic
rollback, and the guide's published CSV examples.

A disposable browser walkthrough read 106 synthetic rows, located both invalid
rows at the end through filtering, showed zero separately from an unrated value,
rendered literal private-note text, cancelled and confirmed the inline prompt,
then added 103 titles while skipping one duplicate and two invalid rows. Opening
Books showed the two correct entries; repeating the preview produced zero ready
rows and 104 duplicates. Final renderer/layout checks at desktop, 390px, and
320px covered dark/light themes, expanded notes, and no Import Studio horizontal
overflow. The mobile checks caught and corrected inherited table widths,
file-picker overflow, and light-mode title contrast. An independent integration
review caught a lost refresh behind an older library request; regression tests
now cover all six category loaders and their Refresh/sort controls.

The PostgreSQL per-account import lock has no live PostgreSQL concurrency test
in this environment; SQLite tests establish retry, isolation, and rollback
behavior. No production database, existing account data, or schema was changed,
and nothing was deployed.

## Cohesive library appearance

The September 24, 2026 visual refresh gives the application a shared violet and
teal palette, quieter surfaces, and consistent typography in light and dark
mode. The header keeps library search and Add Anything prominent. Navigation
groups the six built-in media libraries separately from Journal, Postcards,
Collections, Statistics, Discover, and custom tabs; both groups remain usable
on narrow screens.

All six library categories share labeled add forms, a consistent search/sort
toolbar, clearer desktop tables, and mobile cards. Existing IDs and interaction
hooks remain in place for searching, sorting, pagination, editing, completion,
reviews, and progress. Shared dialog styling covers account settings, Import
Studio, quick capture, collections, and the native progress dialog, including
fields, disabled controls, focus indicators, and status messages in both themes.

The presentation is scoped through `body.app-shell` in `app-theme.css`,
`library-theme.css`, and `dialog-theme.css`. Existing features and keyboard
shortcuts remain available. Small frontend fixes keep disclosure state, Quick
Capture handoffs, and custom-tab selection aligned with the new markup. It adds
no backend endpoints, API contracts, data migrations, or schema changes.

Release verification: all 269 frontend tests passed, including regressions for
native-hidden add forms, keyboard disclosure state, Quick Capture handoffs for
all six categories, and custom tabs sharing built-in names. The 98 focused SEO,
static-security, and public-guide checks passed using isolated SQLite with
dotenv disabled. JavaScript syntax and patch whitespace checks passed.

Browser review used the disposable synthetic library at 320px, 390px, 768px,
and 1440px. Checks covered light/dark appearance, desktop tables and mobile
cards, sidebar layout, search, detail expansion, unchanged-value edit/save,
keyboard add-form toggles, and account, Import Studio, Quick Capture, and
progress dialogs. Manual entry and metadata selection both opened the correct
add form with title focus. Custom-tab identity is covered by frontend tests;
the manager's existing raw-fetch path failed in the local HTTP fixture, so its
full browser flow was not validated. No production data or schema was touched,
and nothing was deployed.

## Library quick filters

The September 24, 2026 library update adds completion, Unrated, and Has saved
progress filters to the six built-in categories. Completion labels match each
category. Unrated means a null rating; zero remains a rated score. Saved progress
is available only for TV, anime, and books and requires an owned checkpoint with
an active unit. Cleared checkpoint revision rows do not qualify.

`GET /library/page/{category}` accepts `completion=all|unfinished|finished`,
`unrated`, and `has_progress`. Filters combine with text search before counting,
sorting, focus priority, and pagination. Existing responses remain compatible.
Each category keeps its view in page memory; Clear search & filters preserves
sorting. Explicit item navigation and opening an imported category clear that
destination's filters. Logout and authentication changes clear browsing state,
and old responses cannot replace a newer view or restart an expired session.

An active inline edit blocks filter changes. Pending list reads temporarily
disable row actions so a new edit cannot be replaced by the response. Saving or
clearing progress refreshes an active saved-progress view after any older read,
with navigation, authentication, and edit guards. These controls are read-only;
they add no migrations, bulk changes, analytics events, or publishing changes.

The public demo and Guides page show Books → Read → Unrated using a fictional
title. This is a usability improvement, not evidence of AdSense approval.

Release verification: all 296 frontend tests and 88 focused backend tests passed,
including filtering, library performance, progress lifecycle/integration, static
security, and public-guide accuracy. JavaScript syntax and patch whitespace
checks passed. Backend runs used isolated SQLite with dotenv disabled.
Disposable browser checks covered desktop, 768px tablet and 320px mobile;
light/dark filters; pagination beyond 50 titles; category state; empty states;
exact-item navigation; editing an unrated title to a zero rating; and saving a
checkpoint while preserving the filtered view. The private note remained intact.
The demo passed desktop/320px checks, empty-state keyboard reset, and signup
handoff tests. Progress clearing and request races are covered by automated
tests. No production data or schema was accessed or changed; nothing was deployed.

## Verification

Run the full suite against an isolated database. Set these before importing the
app, because startup creates tables and runs migrations:

```powershell
$env:PYTHON_DOTENV_DISABLED = '1'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:ENVIRONMENT = 'development'
$env:SECRET_KEY = 'omnitrackr-isolated-test-key-not-for-deployment'
$env:TESTING = 'true'
.\.venv\Scripts\python.exe -m pytest
```

Run browser-side contract tests:

```powershell
$uiTests = Get-ChildItem tests -Filter *.cjs | Select-Object -ExpandProperty FullName
node --test $uiTests
```

For a disposable collection walkthrough, run
`.\.venv\Scripts\python.exe -m tests.manual_mobile_preview --empty --collections`.
Open `http://localhost:8765/collections/public/1`, sign in as `preview` with the
fixture password `local-preview-only`, and select titles before saving. Its
temporary SQLite data and per-run session secret are separate from production.

For checkpoint browser QA, use
`.\.venv\Scripts\python.exe -m tests.manual_mobile_preview --empty --quick-capture --progress`
and open `http://127.0.0.1:8765/qa`. The fixture contains synthetic private TV,
anime, and book checkpoints. Check save, clear, mobile dialog layout, Continue,
Next Up, and `/demo`. Checkpoint backend, integration, and UI regressions live in
the `tests/test_progress*` files.

Checkpoint release verification, September 24, 2026: a fresh, complete backend
run passed all 758 tests. All 208 frontend tests, JavaScript syntax checks, and
`git diff --check` also passed. The follow-up review found and fixed same-tab
session expiry leaving an idle progress dialog open: `clearAuth()` now immediately
closes it and erases its private draft, with a regression using the real auth
cleanup function. Auth asset versions were updated in both entry templates.

Browser checks used the disposable SQLite fixture: desktop episode saves,
mobile chapter saves, queue refresh, unchanged media details, and demo save,
clear, reset, and mobile layout. A separate browser expiry check confirmed that
a background 401 closes the native progress dialog and empties its title and
reminder fields. Reproduce it by opening `/qa/expire` in a second fixture tab
while leaving an unsaved progress draft open in the first. The in-app browser
could not automate the native
confirmation for clearing private progress; its request/revision behavior is
covered by the API and frontend tests. PostgreSQL schema compilation passed for
the new table and indexes, but no PostgreSQL runtime was available for execution
tests. No production database or account was used, and nothing was deployed.

Focused growth and trust checks live in `tests/test_auth.py`,
`tests/test_collections.py`, `tests/test_collection_save.py`, `tests/test_first_session.py`, `tests/test_statistics.py`,
`tests/test_public_reviews.py`, `tests/test_seo_security.py`, and
`tests/test_static_security.py`.
