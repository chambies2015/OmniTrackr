# Public content review — September 17, 2026

## Follow-up — October 28, 2026: crawl after people pages, discussions, polls, manga and podcasts

Crawled the sitemap and every followed link again (137 pages with an empty database, 435
with fourteen sample members across all eight media types, public profiles and two
discussion threads). The pages added since October 27 were mostly gated already: people
and studio pages, discussion threads and weekly roundups each need member writing before
they are indexed, discussion boards, polls and widgets are noindex, and no indexed page
shares a title or description with another. Four things needed fixing:

- **"Various" got a person page.** Members type "Various", "Various Artists" or "Unknown"
  when there isn't one name. Those were treated as a person, so `/people/various` lumped
  unrelated albums and books together and was indexed, linked from title pages and listed
  in the sitemap. A short list of fill-in names (`people_pages.PLACEHOLDER_SLUGS`) now has
  no page (404), no link and no directory or sitemap entry. Credits stored before the
  change are skipped too. Library entries are not touched.
- **Sign-in links were followed.** The "Sign in to write a review" link on title pages,
  the discussion sign-in link and the group poll sign-up links had no `rel="nofollow"`,
  so crawlers queued about fifty `/?next=` homepage variants. They now match the rest of
  the site.
- **Public copy still listed six media types.** About, FAQ, Contact, Guides, Use cases,
  Compare, the homepage description and structured data, and llms.txt now name manga and
  podcasts. About also lists the best-of lists, the holiday guide, monthly challenges and
  the member pages (title pages, people pages, discussions), with a note that thin member
  pages stay out of search.
- **The privacy policy didn't cover the new public features.** It now lists manga and
  podcast fields, discussion posts and group poll votes, and says that public reviews,
  public profiles and discussion posts can be read by anyone and may appear in search.
  Updated date: October 28, 2026.

No user data, URL with real content, or ad placement changed.

## Follow-up — October 27, 2026: fresh crawl after the late-October features

Crawled the sitemap and every followed link again (140 pages with an empty database,
170 with sample members and reviews), covering what shipped since October 20: best-of
lists, the holiday hub, the title page refresh, where to watch, shared lists and clubs,
friend recommendation links, tier lists and the dashboard refresh. Shared lists, club
pages, recommendation links, invite and recap links are all signed-in or noindex. Every
unknown slug returns a real 404 page. No indexed page shares a title or description
with another. ads.txt, sellers.json, robots.txt and the privacy policy's Google ads
section are unchanged and correct. Two things needed fixing:

- **Title pages with one short review.** A title page became indexable and joined the
  sitemap with one search-ready review, which can be about 40 words. Everything else on that page (description, facts, streaming links)
  is borrowed from Wikipedia, TVmaze and others. Title pages now need 150 words of
  search-ready member writing in total, the same bar review pages have used since
  October 20 (`title_pages.is_indexable`). Several short reviews add up. Shorter
  pages still load and still show their reviews; they are just noindex and out of
  the sitemap. Ads already needed 150 words, so ad placement is unchanged.
- **The monthly edition was about to go stale.** The November challenge was written,
  but the newest Discover edition was October's. From November 1 a reviewer would
  have found October billed as the current edition. The November 2026 edition, "The
  long way round" (six pre-2000 picks that pair with the November challenge), is now
  in `MONTHLY_EDITIONS`. Editions now publish on their `published_date`
  (`discover_catalog.published_editions`): before that date an edition has no page,
  sitemap entry, footer or homepage link, or Pick for Me entry, so future editions can
  be written ahead and go live by themselves. The November challenge links the edition
  once it is live.

No user data, URL or ad placement changed. Source links for the November picks were
found through search because the review environment can't open most sites: Criterion
Channel, the Apple TV listing for Columbo, the Crunchyroll store, Double Fine's itch.io
page, milesdavis.com and Faber. Check them once after November 1.

## Follow-up — October 20, 2026: thin-page audit

Crawled every public URL the site links to, plus the sitemap, twice: once with an
empty database and once with sample members, reviews, profiles and collections.
For each page the crawl recorded the status code, robots meta, X-Robots-Tag,
canonical, sitemap membership, and how much of the main text no other page shares.
Almost everything was already handled: empty directories, Release Radar, title
pages without member reviews, query-string variants, share links and 404s are
noindex or canonicalised, and no indexed page shares a title or meta description
with another. Two page types still let thin pages into search:

- **Review pages with short reviews.** A review became indexable and joined the
  sitemap at 35 words and 240 characters. On its own page that review sits under
  roughly 450 words of shared layout and four excerpts from other reviews, so about
  a tenth of the page was its own. A review's page is now indexed and listed in the
  sitemap only at 150 words, the same bar ads already used
  (`reviews._review_is_indexable`). Shorter reviews keep their page, so shared
  links work, and still appear in listings, on title pages and on profiles. The
  `/reviews` listings still count them toward their three-review threshold.
- **Profiles with a bio and favorites only.** A profile counted as indexable with
  any bio (two characters was enough) and six titles rated 8 or higher. That page
  is a list of names. Profiles are now indexable only with a search-ready review or
  a discoverable collection.

No user data, page URL, visibility setting or ad placement changed. The live site
could not be reached from the audit environment, so after deploy, check in Search
Console that short review pages drop out over the following weeks.

## Follow-up — October 17, 2026: point the site at its writing, and speak to readers

An audit of every public page (sitemap URLs plus linked trust pages, 80 in all,
measured from server-rendered HTML) found the written guides were in good shape
but hard to reach, and several trust pages were written to an AdSense reviewer
rather than to a reader.

- **Navigation.** The header led with Release Radar, Public reviews and
  Collections, which are often empty or thin for a new site, while the 22
  ad-eligible In order and If you liked guides were linked only from the footer.
  The header now leads with Discover, In order, If you liked and Daily; reviews,
  collections and the FAQ stay in the footer. The homepage gains a server-rendered
  "New from the guides" section (`app/editorial_index.py`) with the newest guides
  and their checked dates, and the HTML site map lists every guide.
- **Reviewer-directed copy.** About talked about "CSP handling, sitemap coverage,
  robots.txt rules", the content policy addressed "reviewers, search engines" and
  "thin app shells", and the site map called itself a directory for "crawlers".
  Google's helpful-content guidance treats text written for search engines as a
  negative signal. About now says what the site is, what can be read without an
  account, who runs it, how guides are written, and how it is paid for. The
  content policy is now reader-facing **Editorial standards** (same URL), now
  indexable but still outside the sitemap like the other trust pages.
- **Disclosure consistency.** Some guides said "reviewed by the editors" and the
  Daily said puzzles are "written by hand", while the policy says guides are
  written with AI assistance and do not claim a human review team. User-facing
  copy now says "with AI assistance" everywhere, including monthly editions and
  past puzzles, and no longer says "hand-written". Dan confirmed on October 18
  that he reviews the guides, so the guides, About and Editorial standards say
  they are reviewed by the site owner before publishing. Dan also reviewed the
  Daily puzzles and asked for the AI-assistance lines to be removed, so pages
  now credit OmniTrackr and the site owner's review only.
- **Daily archive.** `/daily/archive` was indexed with about 16 words of listing
  text and did not load its stylesheet. It now loads it, shows each puzzle's
  first clue (already public) and explains the puzzles. Past puzzle pages keep
  the rules to one paragraph (the full rules stay on `/daily`) so each page is
  mostly its own answer, and link the If you liked / In order guide about the
  answer inside the spoiler.

No database, user data, ad placement or ad eligibility change. Live check after
deploy: the homepage shows "New from the guides", and `/about` and
`/content-quality` read as described.

## Follow-up — October 16, 2026: all ten Discover trails are full guides

The seven remaining short trails (Notice the details, Small adventures, Clever
mysteries, Found family, Weather and windows, Make something, Distant futures)
are now complete decision guides like the first three: a comparison table,
three analysis sections, two notes per pick, two related trails and a dated
source list. That adds roughly 5,900 words of original editorial text. Adding a
trail to `GUIDES` makes it indexable, lists it in the sitemap with its review
date, gives it Article structured data and an "In-depth guide" label on
`/discover`. No ad placement, catalog title, saved-title metadata or user data
changed. Discover guides stay outside the ad loader.

Source links were checked on October 16. Six official pages could not be read
from the review environment (robots rules or blocking) and were kept because
they are the official pages the trails already cite: Brian Eno's shop, Lauryn
Hill, Phoebe Bridgers, BBC Programmes, Ursula K. Le Guin, and the Peacock and
Netflix listings vary by region. Three trail sources were replaced in the guide
source list with pages that could be read: the Independent Cinema Office for
Knives Out, the New Zealand Film Commission for Hunt for the Wilderpeople, and
the Warner Bros. Discovery announcement for Scavengers Reign.

## Follow-up — October 12, 2026: category tracker guides indexed

Dan chose to let search engines index the six category tracker guides
(`/movie-tracker`, `/tv-show-tracker`, `/anime-tracker`, `/game-tracker`,
`/book-tracker`, `/music-tracker`) and `/use-cases`, and to list them in the
sitemap. They match real search demand ("anime tracker", "game backlog
tracker"). They stay outside `AD_ELIGIBLE_TEMPLATES`, so ad inventory is
unchanged. Templates, checklist, statistics guide, roadmap and changelog keep
`noindex, follow`. This supersedes the October 8 note below for those seven pages.

## Follow-up — October 8, 2026: AdSense reviewer pass

Reviewed the public site from the code as an AdSense reviewer would reach it
(the live site and AdSense account were not reachable from the review
environment). Three code-side gaps were fixed; the account-side steps are in
`docs/adsense-account-checklist.md`.

- **Ads and the consent message were blocked by our own CSP.** Google supports
  only a strict nonce-based CSP for AdSense
  (https://support.google.com/adsense/answer/16283098). The previous allowlist
  admitted `adsbygoogle.js` but blocked the frames, ad-quality requests, and
  Privacy & messaging (CMP) scripts it loads. Pages that carry the ad loader now
  get `script-src 'nonce-…' 'strict-dynamic'` with Google's fallbacks, open
  `frame-src`/`connect-src` to https, and a nonce on every script tag. All other
  pages keep the existing strict policy unchanged.
- **Trust pages were noindexed.** `/privacy`, `/terms`, and `/contact` are now
  indexable (still outside the sitemap), so crawlers see the same site identity
  visitors do. The source-checked `/compare` page is indexable and in the sitemap.
  Overlapping category guides, templates, checklist, roadmap, and changelog keep
  their `noindex, follow` policy.
- **Empty directories read as "under construction".** With no qualifying member
  content, `/collections/explore`, `/reviews`, and `/titles` said "opening soon"
  or "being curated" while linked from the main navigation. They now show the
  authored Discover guides and latest monthly edition instead. Indexing rules for
  those directories are unchanged.

No database, user data, ad placement, or ad-eligibility change is part of this
release. Live verification still needed after deploy: open an ad-eligible page
signed out and confirm the browser console shows no CSP violations from
googlesyndication, doubleclick, adtrafficquality, or fundingchoicesmessages.

## Follow-up — September 24, 2026: public guide reading paths

Reorganized `/guides` around starting a library, importing a list, saving a
checkpoint, and choosing an audience. Sixteen existing guide/support pages now
share a reading layout, compact public navigation, keyboard skip links, section
jumps, and grouped footer links. Existing URLs and bookmarked section IDs remain.

Rewrote `/compare` using official IMDb, Letterboxd, Trakt, and Goodreads sources.
IMDb and Letterboxd now have separate rows; IMDb supports TV lists. The page
separates documented features from editorial fit, discloses AI assistance and
OmniTrackr's interest, and describes manual progress, absent account sync, limited
CSV fields, duplicate matching, and the difference between CSV and JSON restore.
It recommends a small trial before moving a history. No pricing claims were added.

Source review also clarified a privacy distinction: unchecked Public Review
prevents public review publication, but friends can read item notes when category
sharing permits it. The guides now explain that boundary and point to journal
entries and checkpoint reminders for personal context. No sharing behavior changed.

This completes the named-comparison follow-up below. Indexability, sitemap
eligibility, and advertising eligibility remain unchanged; `/compare` stays
`noindex, follow`. No new article URLs, ad placements, database changes, or
production data operations are part of this release. Verification details are
recorded in `docs/growth-operations.md`.

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

1. Recheck named competitor claims when their official documentation changes;
   the September 24 comparison refresh establishes the source-checked baseline.
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
