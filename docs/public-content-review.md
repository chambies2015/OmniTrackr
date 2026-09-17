# Public content review — September 17, 2026

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
| Discover and public collections/reviews | Preserve existing editorial/community content and publishing controls; not individually evaluated in this pass. |

## Implemented

- Ratings: 0–10, with blank distinct from zero, checked against `app/schemas.py`.
- Per-item Public Review control, not a global account publishing toggle.
- Tab visibility distinguished from friend privacy and public review sharing.
- Completion checkbox distinguished from paused/dropped state conventions.
- CSV preview/migration distinguished from JSON backup workflow.
- Hub example: recommended film, paused anime, finished-but-unrated book; no claim
  that these are real user experiences or records.
- Existing URLs, section anchors, indexability, and backend behavior preserved.

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

No user data, routes, ads configuration, or publishing permissions were changed.
