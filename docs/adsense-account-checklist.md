# AdSense account checklist

The steps here can only be done in Google's dashboards. Do them in order
after the October 8, 2026 reviewer-pass changes are deployed. Code-side
context is in `docs/public-content-review.md`.

## 1. Check the deploy (5 minutes)

1. Sign out, or use a private window. Open https://omnitrackr.xyz/media-tracking
   and open the browser console (F12, then Console).
2. You should see no red "Content Security Policy" errors that mention
   googlesyndication, doubleclick, adtrafficquality, or fundingchoicesmessages.
   A blocked request from an ad blocker is fine. A CSP error is not.
3. Open https://omnitrackr.xyz/ads.txt. It should show exactly
   `google.com, pub-7271682066779719, DIRECT, f08c47fec0942fa0`.

## 2. Pick one host name

All canonical tags, the sitemap, and robots.txt use `https://omnitrackr.xyz`
without www, but the README links `https://www.omnitrackr.xyz/`.

1. Open both addresses. One of them should redirect (301) to the other.
2. If both load without a redirect, add the redirect in Render (Settings,
   then Custom Domains) so `www` goes to the bare domain. Don't add it in app
   code, because Render may already redirect the other way, and the two
   redirects would loop.
3. In AdSense, under Sites, the site should be listed as `omnitrackr.xyz`.

## 3. Search Console

AdSense reviewers judge content Google can crawl. Getting pages indexed is the
single most useful thing to check before applying again.

1. Add a Domain property for `omnitrackr.xyz` if it doesn't exist (this needs
   a DNS TXT record).
2. Under Sitemaps, submit `https://omnitrackr.xyz/sitemap.xml`.
3. Under Pages, see how many pages are indexed. Use URL Inspection, then
   Request indexing, on these pages: `/`, `/discover`, the three Discover guides
   (`/discover/one-evening-well-spent`, `/discover/finding-your-feet`,
   `/discover/beautifully-strange-worlds`), `/discover/monthly/october-2026`,
   `/guides`, `/media-tracking`, `/compare`, and `/about`.
4. If most of these show "Discovered/Crawled – currently not indexed", wait
   until they are indexed before you apply again. If you apply sooner, the
   result will probably be another "low value content" rejection.

## 4. Consent message (Privacy & messaging)

Google requires a certified consent platform to serve ads to visitors in the
EEA, the UK, and Switzerland. Google's own message is free, and the site's
CSP now allows it.

1. In AdSense, go to Privacy & messaging, then European regulations, and
   create a message for `omnitrackr.xyz`.
2. Choose the "Consent" or "Manage options" buttons. Link the privacy policy
   (`https://omnitrackr.xyz/privacy`), then publish.
3. Optional: under US state regulations, publish the opt-out message too.
4. The message only appears on pages that load the ad script. These are
   signed-out views of the guide pages, standalone reviews, title pages, and
   Release Radar. You won't see it on the homepage or the dashboard.

## 5. Ads setup

No manual ad units exist in the code, so ads depend on Auto ads.

1. Under Ads, then By site, edit `omnitrackr.xyz` and turn on Auto ads.
   Leave "Ad load" at a moderate level.
2. Check Policy center to confirm there are no open issues.

## 6. Request review again

1. Do this once steps 1–5 are done and the key pages in step 3 are indexed.
2. In Sites, open `omnitrackr.xyz`, tick "I confirm I have fixed the issues",
   and request a review.
3. If it's rejected again, note the exact wording and date. Also note which
   pages Search Console shows as indexed. Those two facts show whether the next
   fix is about indexing or about content.

## What helps approval

OmniTrackr is mostly an app, and much of its public text explains how to use
the app. AdSense tends to judge sites like this by how much stand-alone content
they have for people who will never sign up. The best content to grow is the
authored Discover guides and monthly editions, because they are reviewed and
cite their sources. Seven Discover trails are still short and noindexed. Turning
them into full guides, like the three finished ones, adds the most original,
indexable content for the effort.
