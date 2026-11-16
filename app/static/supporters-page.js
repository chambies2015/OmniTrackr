// /supporters: count visits and Ko-fi button presses (anonymous daily counters, nothing about the visitor),
// a line with the member's own numbers when signed in, a Ko-fi bar on phones, and the "Try it on" preview,
// which only changes classes on this page.
(function () {
  'use strict';

  const PLACE = /^[a-z_]{1,16}$/;

  function beacon(url, body) {
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([JSON.stringify(body)], { type: 'application/json' }));
    } catch (error) { /* counting is optional */ }
  }

  // Where this visit came from: ?from= on our own links, else this site or somewhere outside.
  function visitSource(search, referrer, origin) {
    const from = new URLSearchParams(search || '').get('from');
    if (from && PLACE.test(from)) return from;
    try {
      if (referrer && new URL(referrer).origin === origin) return 'site';
    } catch (error) { /* unreadable referrer */ }
    return 'outside';
  }

  function memberLine(me) {
    if (!me || typeof me !== 'object') return '';
    const titles = Number(me.titles) || 0;
    const days = Number(me.days) || 0;
    if (me.supporter) return 'You already support OmniTrackr. Thank you! Your perks are in Account → Supporter.';
    if (titles < 5) return '';
    const visits = days >= 5 ? ` and opened it on ${days.toLocaleString()} different days` : '';
    const line = `you've tracked ${titles.toLocaleString()} titles on OmniTrackr${visits}.`;
    if (typeof me.since === 'string' && me.since) return `Since ${me.since}, ${line}`;
    return line.charAt(0).toUpperCase() + line.slice(1);
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { visitSource, memberLine };
    return;
  }

  try {
    const key = 'ot-supporters-seen';
    if (!window.sessionStorage.getItem(key)) {
      window.sessionStorage.setItem(key, '1');
      beacon('/api/support/event', { event: 'page_seen', place: visitSource(window.location.search, document.referrer, window.location.origin) });
    }
  } catch (error) { /* storage blocked: skip the count rather than count twice */ }

  document.querySelectorAll('[data-kofi]').forEach(link => {
    link.addEventListener('click', () => {
      beacon('/api/funnel', { event: 'supporters_kofi_clicked' });
      const place = link.getAttribute('data-kofi-place');
      if (place && PLACE.test(place)) beacon('/api/support/event', { event: 'page_kofi', place });
    });
  });

  const meLine = document.querySelector('[data-support-me]');
  if (meLine) {
    fetch('/api/support/me', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(response => (response.ok ? response.json() : null))
      .then(me => {
        const text = memberLine(me);
        if (!text) return;
        meLine.textContent = text;
        meLine.hidden = false;
      })
      .catch(() => { /* signed out or offline: the page reads the same without it */ });
  }

  const sticky = document.querySelector('[data-support-sticky]');
  const heroActions = document.querySelector('[data-support-hero-actions]');
  if (sticky && heroActions && typeof IntersectionObserver === 'function') {
    document.body.classList.add('has-sticky');
    new IntersectionObserver(entries => {
      entries.forEach(entry => { sticky.hidden = entry.isIntersecting || entry.boundingClientRect.top > 0; });
    }).observe(heroActions);
  }

  const NAME = /^[a-z_]{1,16}$/;
  const profile = document.querySelector('[data-try-profile]');
  const banner = document.querySelector('[data-try-banner]');
  const frame = document.querySelector('[data-try-frame]');
  const app = document.querySelector('[data-try-app]');
  const night = document.querySelector('[data-try-night]');
  const stage = document.querySelector('.support-try__stage');
  if (!profile || !banner || !frame || !app || !stage) return;

  const picked = { theme: 'default', accent: 'violet', banner: 'aurora', frame: 'halo' };

  function swapClass(node, prefix, value) {
    Array.from(node.classList).filter(name => name.startsWith(prefix)).forEach(name => node.classList.remove(name));
    if (value) node.classList.add(prefix + value);
  }

  function render() {
    swapClass(profile, 'support-try__profile--', picked.accent);
    swapClass(app, 'support-try__app--', picked.theme);
    app.classList.toggle('support-try__app--light', !!night && !night.checked);
    banner.hidden = picked.banner === 'none';
    if (picked.banner !== 'none') swapClass(banner, 'profile-banner--', picked.banner);
    swapClass(frame, 'avatar-frame--', picked.frame === 'none' ? '' : picked.frame);
    const art = frame.querySelector('.avatar-frame__art');
    if (art) art.hidden = picked.frame === 'none';
  }

  document.querySelectorAll('[data-try]').forEach(button => {
    button.addEventListener('click', () => {
      const kind = button.getAttribute('data-try');
      const value = button.getAttribute('data-value');
      if (!Object.prototype.hasOwnProperty.call(picked, kind) || !NAME.test(value || '')) return;
      picked[kind] = value;
      document.querySelectorAll(`[data-try="${kind}"]`).forEach(other => other.setAttribute('aria-pressed', other === button ? 'true' : 'false'));
      render();
    });
  });
  if (night) night.addEventListener('change', render);
  stage.classList.add('is-ready');
  render();
})();
