# Growth and trust operations

This is the canonical engineering note for OmniTrackr activation, retention,
analytics boundaries, and advertising readiness. Product claims and policy text
remain authoritative on the public Privacy, Advertising, Roadmap, and Changelog
pages.

## Activation path

Trusted collection moderators can view aggregate activation stages in the
existing site-health panel. No separate event stream is created.

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

## Analytics boundary

Google Analytics is loaded only by the standalone public landing page. It is not
loaded by the authenticated dashboard. The loader exits before requesting a
Google script when supported Global Privacy Control or Do Not Track signals are
enabled, disables Google signals and ad-personalization signals, and requests IP
anonymization.

Aggregate activation data comes from OmniTrackr's own account and library
records, not Google Analytics. Successful-login measurement stores only the most
recent successful login timestamp and a running count. These values are included
in the account's JSON export metadata.

## Advertising readiness

AdSense approval is never guaranteed by code or content changes. Before an
application or re-review:

1. Confirm production `ads.txt`, publisher metadata, canonical URLs, and sitemap output.
2. Confirm ads remain restricted to the server and client allowlists and never load in the private dashboard.
3. Confirm the public Privacy and Advertising pages match production behavior.
4. Configure and verify the Google-certified CMP required before serving personalized ads to visitors in the EEA, United Kingdom, or Switzerland. The Google Privacy & messaging option is one supported route; repository tests cannot verify account-side configuration.
5. Review public pages for original reader value, accurate claims, working navigation, and adequate moderation.
6. Use Search Console and AdSense feedback to choose follow-up work instead of adding speculative pages.

## Verification

Run the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run browser-side contract tests:

```powershell
node --test tests/*.cjs
```

Focused growth and trust checks live in `tests/test_auth.py`,
`tests/test_collections.py`, `tests/test_first_session.py`,
`tests/test_seo_security.py`, and `tests/test_static_security.py`.
