# Public content review — September 17, 2026

## Follow-up — September 24, 2026: three Discover guides

Expanded three existing trails into public decision guides: **One evening, well
spent**, **Finding your feet**, and **Beautifully strange worlds**. Each now has
a comparison of pace, commitment and fit; original cross-media analysis;
practical starting notes; two related trails; and a dated source list. All
editorial reading is server rendered and available without an account or
JavaScript. No new recommendation titles or saved-title metadata were added.

Verified all twelve primary sources and corrected specific catalog problems:
Blue's official album link used `id=13` (Shadows and Light); it now uses `id=5`.
Florence uses its current publisher URL and no longer promises an unsupported
one-hour completion time. Before Sunset identifies its Before Sunrise sequel
context. Earthsea links to the author's individual book page, the original 2005
Mushishi series links to its original broadcaster, and Piranesi links directly
to its publisher. Comparisons distinguish interpretation from verified facts,
qualify variable reading/game pace, and avoid revealing mystery solutions.

The guides and updated content-quality policy explicitly disclose AI assistance,
identify OmniTrackr as the publishing organization, and explain source checking.
Each guide describes what its sources support. They do not
claim firsthand experience or a human editorial review team. Their visible
review date, Article `dateModified`, and sitemap `lastmod` are September 24,
2026; the original publication date remains September 8, 2026.

Only these three completed guides become indexable and enter the sitemap. The
other seven trail detail pages remain `noindex, follow` and excluded from the
sitemap; the Discover directory and monthly edition retain their existing
policy. Existing preview, authentication return, selection, and private save
behavior are unchanged. No database migration, production data operation, new
tracking, or new advertising placement is part of this release.

Release verification passed 129 focused Python tests and all 227 frontend tests.
Disposable browser checks covered desktop and 390/320px layouts, page anchors,
guest sign-in return, selected saves, existing matches, repeat saves without
duplicates, and opening the resulting private collection. Browser QA caught and
fixed inherited table header colors and mobile label positioning. Content and
source review found no actionable factual or spoiler issues. This
is a content improvement, not evidence that Google will index the pages or
approve AdSense; production Search Console and account review feedback remain
the appropriate evidence for the next revision.

## Follow-up — September 22, 2026

Read the live homepage and Discover experience, inspected the content and
authentication routes, and rechecked Google's content and navigation guidance.
The repository already contains ten editorial trails, a monthly edition, public
review quality gates, and deliberate consolidation of overlapping search pages.
The clearest actionable gap was the route from public reading to a saved library:
sign-in discarded the chosen trail, and a successful save led to the generic
dashboard. A separate initialization bug also skipped verification/reset links
on the anonymous homepage.

This update promotes existing Discover content on the homepage, makes trails
searchable by title/creator/theme and format, preserves the Discover destination
through same-tab authentication, fixes verification/reset dispatch, and opens the
saved collection directly. Original editorial text, source links, public opt-in
rules, indexability, and advertising eligibility remain as before. No new database
schema, production data operation, or advertising inventory was introduced.

This is a usability and activation improvement, not evidence of AdSense approval.
After deployment, use actual Search Console coverage and the account's current
AdSense feedback to select the next content revision. Account review decisions,
traffic, and consent configuration were not accessible in this audit.

## Scope and findings

This is a source-based first pass, not an exhaustive live-site or Search Console
audit and not a diagnosis of Google's private review decision.

The public inventory includes the landing page, demo/sample library, Discover
trails and monthly editions, guides and tracking hub, category guides, templates,
comparison/use-case pages, community reviews/collections, and policy/support pages.
Existing SEO tests already enforce noindex and exclusion from the sitemap for
overlapping category guides, comparison, templates, checklist, and several support
pages. Preserve that policy; do not create another consolidation mechanism.

| Area inspected | Decision |
| --- | --- |
| `/guides` | Correct stale instructions and make operational steps concrete. |
| `/media-tracking` | Replace search-oriented filler and contradictory starter quantities with a fictional worked example. |
| Category guides, checklist, templates | Existing specialized support pages; no duplicate articles or new indexable URLs added. |
| `/compare` | Follow-up: named competitor comparisons need primary-source verification before revising or promoting. |
| Discover and public collections | Preserve the existing collection workflow while replacing its unavailable human approval step with deterministic readiness and version-bound reports. |
| Public reviews | Keep one opt-in feed, distinguish community-ready summaries from search-ready inventory, and use automated version-bound reports because no manual review team is available. |

## Implemented

- Ratings: 0–10, with blank distinct from zero, checked against `app/schemas.py`.
- Per-item Public Review control, not a global account publishing toggle.
- Tab visibility distinguished from friend privacy and public review sharing.
- Completion checkbox distinguished from paused/dropped state conventions.
- CSV preview/migration distinguished from JSON backup workflow.
- Hub example: recommended film, paused anime, finished-but-unrated book; no claim
  that these are real user experiences or records.
- Existing URLs, section anchors, indexability, and backend behavior preserved.
- Search, structured-data, sitemap, prominent-ordering, and ad eligibility now
  require the shared search-ready review result; ordinary community-ready reviews
  remain browseable.
- Fixed-reason signed-browser reports automatically unlist one exact review
  version after three independent reports. Editing restores a revision without a
  manual queue, and no saved review is deleted.
- Public collections reuse their existing quality floor, gallery, content hash,
  signed visitor identity, and report route. A shared readiness result now gates
  gallery and sitemap eligibility automatically; three independent reports
  unlist only the current version, and an edit reruns the checks.

## Follow-up priorities

1. Verify named competitor claims against official documentation; avoid blanket
   claims that OmniTrackr is better for every reader.
2. Review the age and accuracy of hub screenshots against the current UI.
3. Inspect each Discover edition for distinct editorial reasoning, useful limits,
   and accurate links rather than increasing the number of collections blindly.
4. Use actual Search Console/account feedback, if made available, to distinguish
   discovery/indexing problems from content shortcomings.

Google's guidance favors original reader value, reduced duplication, and clear
navigation. It does not make these changes an approval guarantee:
https://support.google.com/adsense/answer/10015918?hl=en

The safety follow-ups add bounded report state without rewriting existing
reviews or collections, changing opt-in choices, or exposing private library
data.
