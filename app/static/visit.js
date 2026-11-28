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

  // A visitor who came from a web search gets a one-day cookie naming only the first
  // part of the page they landed on (say "in-order"), so Site stats can count how many
  // search visitors go on to save a title or sign up (app/search_journey.py). The
  // first landing of the day wins. Hosts mirror SEARCH_HOST in that file.
  var SEARCH_HOST = /(?:^|\.)(?:google\.[a-z.]{2,8}|bing\.com|duckduckgo\.com|yahoo\.[a-z.]{2,8}|ecosia\.org|search\.brave\.com|yandex\.[a-z.]{2,8}|baidu\.com|startpage\.com|qwant\.com|kagi\.com)$/;
  var SEARCH_COOKIE = 'omnitrackr_from_search';

  function markSearchLanding() {
    try {
      if (!document.referrer || document.cookie.indexOf(SEARCH_COOKIE + '=') !== -1) return;
      var host = new URL(document.referrer).hostname.toLowerCase().replace(/^www\./, '');
      if (!SEARCH_HOST.test(host)) return;
      var part = window.location.pathname.split('/')[1] || 'home';
      if (!/^[a-z0-9-]{1,40}$/.test(part)) part = 'other';
      document.cookie = SEARCH_COOKIE + '=' + part + '; Max-Age=86400; Path=/; SameSite=Lax'
        + (window.location.protocol === 'https:' ? '; Secure' : '');
    } catch (error) { /* analytics only */ }
  }

  function send() {
    if (sent || document.visibilityState !== 'visible') return;
    sent = true;
    markSearchLanding();
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
