// One-tap sharing for public pages: the phone's share sheet where available,
// otherwise copy the link. Buttons: <button data-share data-share-title="...">Share</button>
(function () {
  'use strict';

  function canonicalUrl() {
    const link = document.querySelector('link[rel="canonical"]');
    const href = link && link.href ? link.href : window.location.href;
    try {
      const url = new URL(href, window.location.origin);
      url.hash = '';
      return url.href;
    } catch (error) {
      return window.location.href;
    }
  }

  function report() {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event: 'share_clicked' })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function flash(button, text) {
    const original = button.dataset.shareLabel || button.textContent;
    button.dataset.shareLabel = original;
    button.textContent = text;
    setTimeout(() => { button.textContent = original; }, 2200);
  }

  async function share(button) {
    const url = canonicalUrl();
    const title = button.dataset.shareTitle || document.title;
    report();
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return 'shared';
      } catch (error) {
        if (error && error.name === 'AbortError') return 'cancelled';
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      flash(button, 'Link copied ✓');
      return 'copied';
    } catch (error) {
      window.prompt('Copy this link:', url);
      return 'prompted';
    }
  }

  if (typeof document !== 'undefined') document.addEventListener('click', event => {
    const button = event.target.closest && event.target.closest('[data-share]');
    if (!button) return;
    event.preventDefault();
    share(button);
  });

  if (typeof window !== 'undefined') window.OmniShare = { share, canonicalUrl };
  if (typeof module !== 'undefined' && module.exports) module.exports = { share, canonicalUrl };
})();
