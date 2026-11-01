/* "A person opened this page": one small report per page view for the owner's
   Site stats (POST /api/visit, see app/site_traffic.py). It sends only the page
   path, the referring address and a utm_source tag. Nothing is sent for tabs
   that are never shown, prerendered pages, or browsers run by automation. */
(function () {
  'use strict';

  var SHOWN_FOR_MS = 800;
  var sent = false;
  var timer = null;

  function automated() {
    try {
      return navigator.webdriver === true;
    } catch (error) {
      return false;
    }
  }

  function payload() {
    var utm = '';
    try {
      utm = new URLSearchParams(window.location.search).get('utm_source') || '';
    } catch (error) { /* old browser: no tag */ }
    return JSON.stringify({
      path: window.location.pathname.slice(0, 300),
      referrer: (document.referrer || '').slice(0, 500),
      utm: utm.slice(0, 120),
    });
  }

  function send() {
    if (sent || document.visibilityState !== 'visible') return;
    sent = true;
    var body = payload();
    try {
      if (navigator.sendBeacon && typeof Blob === 'function'
          && navigator.sendBeacon('/api/visit', new Blob([body], { type: 'application/json' }))) return;
      if (typeof fetch === 'function') {
        fetch('/api/visit', { method: 'POST', body: body, keepalive: true, credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' } }).catch(function () {});
      }
    } catch (error) { /* analytics only */ }
  }

  function arm() {
    clearTimeout(timer);
    if (!sent && document.visibilityState === 'visible') timer = setTimeout(send, SHOWN_FOR_MS);
  }

  if (automated()) return;
  // A prerendered or background tab reports once it is actually shown.
  document.addEventListener('visibilitychange', arm);
  arm();
})();
