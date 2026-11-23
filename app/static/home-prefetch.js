// Home start-up requests, sent while the page is still loading.
//
// Each home card asks for its own data, but only once its script has run. On a phone
// that is after every script on the page has downloaded and run: about 1.5 s in on a
// warm cache and 3 to 5 s on a cold one, and the requests then queue up behind each
// other. This file is the first of the page's scripts at the end of the body and asks
// for the same addresses straight away, while the scripts after it download. When a
// card's script later asks for one of them, it is handed that answer instead of
// waiting for a new one. (In the head it slowed the page: the requests competed with
// the page itself for a phone's bandwidth.)
//
// The rules that keep this invisible to the cards:
// - each answer is handed out once, and only for 30 seconds;
// - any write (other than the visit pings below) drops every answer not yet handed out,
//   so nothing read before a change is shown after it;
// - only successful answers are handed out: on an error the script asks again and
//   deals with it exactly as before;
// - cards that read the visit count (badges, the weekly-email offer, support notes) are
//   left alone, because the visit ping that bumps it is sent once the page has loaded.
// An address that no script asked for on two visits in a row is left out for a week.
(function () {
  'use strict';

  if (typeof window === 'undefined' || window.OmniHomePrefetch || typeof window.fetch !== 'function') return;
  if (window.location.pathname !== '/') return;

  let token = null;
  try {
    token = window.localStorage.getItem('omnitrackr_token');
    if (!token && !window.localStorage.getItem('omnitrackr_user')) return;
  } catch (_) {
    return; // Without storage the page recovers the session first; nothing to start early.
  }

  const FRESH_MS = 30000;
  const SKIP_KEY = 'omnitrackr_home_prefetch_skip';
  const SKIP_DAYS = 7;
  // Writes that change nothing these answers depend on.
  const HARMLESS_WRITE = /^\/(account\/visit|api\/visit|api\/[\w/-]+\/(event|seen))$/;

  const pad = n => String(n).padStart(2, '0');
  const now = new Date();
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const tz = -now.getTimezoneOffset();

  // [name, address]. The addresses are exactly what the cards ask for on a plain home
  // visit; a card that asks for something else simply misses and fetches as usual.
  const ADDRESSES = [
    ['library-movies', '/library/page/movies?offset=0&limit=50&completion=all&unrated=false&has_progress=false'],
    ['pulse', '/statistics/pulse/'],
    ['today-pick', '/statistics/today/?offset=0'],
    ['streaming', '/api/streaming'],
    ['together', `/api/together?tz=${tz}`],
    ['break', `/api/break/home?today=${today}`],
    ['swaps', `/api/swaps?tz=${tz}`],
    ['year-so-far', '/api/year-in-review-so-far'],
    ['friends', '/friends'],
    ['site-stats-access', '/api/site-stats/access'],
    ['for-you-picks', '/api/for-you/picks'],
    ['starter-picks', '/api/for-you/starter-picks'],
    ['coming-up', '/api/for-you/coming-up'],
    ['goals', `/api/goals?year=${now.getFullYear()}`],
    ['friend-feed', '/api/friend-feed?limit=1'],
    ['review-inbox', '/api/review-inbox'],
    ['challenge', '/api/challenge'],
    ['seasonal', '/api/seasonal/current'],
    ['on-this-day', `/activity/on-this-day/?tz_offset_minutes=${now.getTimezoneOffset()}`],
    ['new-year', '/api/new-year-challenge'],
    ['awards', '/api/awards/card'],
    ['advent', '/api/advent-calendar'],
    ['notifications', '/notifications/count'],
    ['friend-recs', '/api/friend-recs/inbox'],
    ['tab-visibility', '/account/tab-visibility'],
    ['custom-tabs', '/custom-tabs/'],
    ['privacy', '/account/privacy'],
    ['insights', '/statistics/insights/'],
    ['first-week', '/api/for-you/first-week'],
    ['next-up', '/next-up/'],
    ['stats-home', '/statistics/home/'],
    ['week-one', `/api/week-one?today=${today}`],
    ['backlog-draw', `/api/backlog-draw?today=${today}`],
    ['your-week', `/api/your-week?tz=${tz}`],
    ['rankings', '/api/rankings/card'],
    ['taste-match', '/api/taste-match/friends'],
    ['supporter', '/api/supporter'],
    ['library-tags', '/library/tags?category=movies'],
    ['library-views', '/library/views/movies'],
    ['library-recommenders', '/library/recommenders?category=movies'],
  ];

  function readSkips() {
    try {
      const value = JSON.parse(window.localStorage.getItem(SKIP_KEY) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (_) {
      return {};
    }
  }

  const skips = readSkips();
  const weekAgo = Date.now() - SKIP_DAYS * 86400000;
  const skipped = name => {
    const entry = skips[name];
    return Boolean(entry && entry.misses >= 2 && entry.at > weekAgo);
  };

  const nativeFetch = window.fetch;
  const startedAt = Date.now();
  const waiting = new Map(); // address -> { name, promise }
  const claimed = new Set();
  let dropped = false;

  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  ADDRESSES.forEach(([name, address]) => {
    if (skipped(name)) return;
    const promise = nativeFetch.call(window, address, { credentials: 'same-origin', headers }).catch(() => null);
    waiting.set(address, { name, promise });
  });
  if (!waiting.size) return;

  function dropAll() {
    dropped = true;
    waiting.clear();
  }

  function abortError() {
    try {
      return new DOMException('The operation was aborted.', 'AbortError');
    } catch (_) {
      const error = new Error('The operation was aborted.');
      error.name = 'AbortError';
      return error;
    }
  }

  function handOver(entry, input, init) {
    const signal = init && init.signal;
    const answer = entry.promise.then(response => (response && response.ok ? response : nativeFetch.call(window, input, init)));
    if (!signal) return answer;
    if (signal.aborted) return Promise.reject(abortError());
    return new Promise((resolve, reject) => {
      const onAbort = () => reject(abortError());
      signal.addEventListener('abort', onAbort, { once: true });
      answer.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort));
    });
  }

  window.fetch = function (input, init) {
    try {
      const fromRequest = typeof Request !== 'undefined' && input instanceof Request;
      const method = String((init && init.method) || (fromRequest ? input.method : 'GET')).toUpperCase();
      const url = new URL(fromRequest ? input.url : String(input), window.location.href);
      if (url.origin === window.location.origin) {
        if (method !== 'GET' && method !== 'HEAD') {
          if (!HARMLESS_WRITE.test(url.pathname)) dropAll();
        } else if (method === 'GET' && !fromRequest && waiting.size && (!init || !init.credentials || init.credentials !== 'omit')) {
          const address = url.pathname + url.search;
          const entry = waiting.get(address);
          if (entry) {
            waiting.delete(address);
            if (Date.now() - startedAt <= FRESH_MS) {
              claimed.add(entry.name);
              return handOver(entry, input, init);
            }
          }
        }
      }
    } catch (_) {
      // Anything unexpected goes to the network as usual.
    }
    return nativeFetch.call(window, input, init);
  };

  // Remember what no script asked for, once the start-up is over. A visit where hardly
  // anything was asked for (another tab opened by link, a quick reload) teaches nothing.
  function settle() {
    if (settle.done) return;
    settle.done = true;
    const unclaimed = dropped ? [] : Array.from(waiting.values(), entry => entry.name);
    waiting.clear();
    if (claimed.size < 5) return;
    const next = readSkips();
    claimed.forEach(name => { delete next[name]; });
    unclaimed.forEach(name => {
      const entry = next[name];
      next[name] = { misses: entry && entry.at > weekAgo ? Math.min((entry.misses || 0) + 1, 9) : 1, at: Date.now() };
    });
    try {
      window.localStorage.setItem(SKIP_KEY, JSON.stringify(next));
    } catch (_) {
      // Only a hint for next time.
    }
  }
  window.setTimeout(settle, FRESH_MS);
  window.addEventListener('pagehide', settle, { once: true });

  window.OmniHomePrefetch = {
    addresses: () => ADDRESSES.slice(),
    pending: () => Array.from(waiting.keys()),
    claimed: () => Array.from(claimed),
  };
})();
