// Shows the Year in Review banner on the dashboard in December and January only.
(function () {
  'use strict';
  const banner = document.getElementById('yearInReviewBanner');
  if (!banner) return;
  const month = new Date().getMonth();
  if (month !== 11 && month !== 0) return;
  fetch('/api/year-in-review-season', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(response => (response.ok ? response.json() : null))
    .then(season => {
      if (!season || !season.year) return;
      const link = document.getElementById('yearInReviewBannerLink');
      const title = document.getElementById('yearInReviewBannerTitle');
      if (link) link.href = season.url;
      if (title) title.textContent = `Your ${season.year} in media is ready`;
      banner.hidden = false;
    })
    .catch(() => { /* the banner simply stays hidden */ });
}());
