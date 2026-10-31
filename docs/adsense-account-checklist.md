# AdSense account checklist

## October 27, 2026: what to do before the next review request

The October 27 crawl found the code side in good shape (see
`docs/public-content-review.md`). What's left happens in Google's dashboards:

1. Deploy October-Updates, then do steps 1 and 2 below once (CSP errors, ads.txt,
   www redirect) if they haven't been checked since October 8.
2. On or after November 1, open `https://omnitrackr.xyz/discover/monthly/november-2026`
   signed out. It should load with six picks. Click each "source" link once; if
   any is dead, tell Claude and it will be swapped.
3. In Search Console, resubmit `https://omnitrackr.xyz/sitemap.xml` and use URL
   Inspection, then Request indexing, on the November edition, `/best-of`,
   `/best-of/2026/movies`, `/holidays` and `/challenges/november-2026`.
4. Search Console, Pages: note how many pages are indexed and how many say
   "Crawled – currently not indexed". Short title pages will move to "Excluded by
   'noindex' tag" over the next few weeks. That's expected.
5. Make sure the consent message (step 4 below) is published. Without it, Google
   can't serve ads to EEA and UK visitors.
6. Request review around **November 23, 2026**, and only if most of the guide
   pages from step 3 here and step 3 below show as indexed. If they don't, wait
   another two weeks and check again. Each request made before Google has indexed
   the guides has ended in the same "low value content" answer.

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
   `/guides`, `/media-tracking`, `/compare`, `/about`, `/content-quality`
   (now the reader-facing editorial standards), `/in-order`, `/in-order/star-wars`,
   `/if-you-liked`, and `/if-you-liked/interstellar`.
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
cite their sources. Since October 16, 2026 all ten Discover trails are full,
indexed guides. Keep adding one monthly edition each month, and give Google a
few weeks to index the new guides before requesting another review.

Since October 17, 2026 the header menu and the homepage lead with these guides
(Discover, In order, If you liked, Daily), and the About and Editorial standards
pages speak to readers about who runs the site, how guides are written with AI
assistance and checked, and how the site is paid for. A reviewer who lands on the
homepage now reaches the written guides in one click.
