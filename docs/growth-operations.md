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

## Verification

Run the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run browser-side contract tests:

```powershell
$uiTests = Get-ChildItem tests -Filter *.cjs | Select-Object -ExpandProperty FullName
node --test $uiTests
```

Focused growth and trust checks live in `tests/test_auth.py`,
`tests/test_collections.py`, `tests/test_first_session.py`, `tests/test_statistics.py`,
`tests/test_public_reviews.py`, `tests/test_seo_security.py`, and
`tests/test_static_security.py`.
