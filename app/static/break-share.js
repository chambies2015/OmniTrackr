// A shared break plan (/break/s/<token>, app/routers/break_plan.py). Visitors can save titles from it
// (guest-list.js handles those buttons) and plan the same days once they have an account: pressing
// "Plan these days" remembers the link in this browser for three days, so coming back signed in goes
// straight on to /break?from=<token>. Members add titles to their library from here. The member who
// shared it gets copy, send, story-picture and turn-off buttons. Page text is only set as textContent.
(function () {
  'use strict';

  const PENDING = 'omnitrackr_break_from';
  const KEEP_MS = 3 * 86400000;
  const TOKEN = /^[A-Za-z0-9_-]{16,40}$/;

  // ---------------------------------------------------------------- no DOM (also used by tests)

  function readPending(now = Date.now(), storage = globalThis.localStorage) {
    try {
      const value = JSON.parse(storage.getItem(PENDING) || 'null');
      if (!value || value.v !== 1 || !TOKEN.test(String(value.token || '')) || !Number.isFinite(value.at)) return null;
      if (value.at > now + 60000 || now - value.at > KEEP_MS) return null;
      return value;
    } catch (error) {
      return null;
    }
  }

  function storePending(token, now = Date.now(), storage = globalThis.localStorage) {
    if (!TOKEN.test(String(token || ''))) return false;
    try {
      storage.setItem(PENDING, JSON.stringify({ v: 1, token, at: now }));
      return true;
    } catch (error) {
      return false;
    }
  }

  function clearPending(storage = globalThis.localStorage) {
    try { storage.removeItem(PENDING); } catch (error) { /* nothing kept */ }
  }

  function meterShare(done, total) {
    const all = Number(total) || 0;
    if (all <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((Number(done) || 0) / all * 100)));
  }

  const api = { readPending, storePending, clearPending, meterShare, PENDING, KEEP_MS };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
    return;
  }
  window.OmniBreakShare = api;

  // ---------------------------------------------------------------- the page

  const sent = new Set();
  function count(event) {
    if (sent.has(event)) return;
    sent.add(event);
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting only */ }
  }

  function headers() {
    const found = { Accept: 'application/json' };
    try {
      const token = window.localStorage.getItem('omnitrackr_token');
      if (token) found.Authorization = `Bearer ${token}`;
    } catch (error) { /* the session cookie is enough */ }
    return found;
  }

  function today() {
    const now = new Date();
    const pad = value => String(value).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  function setup(root) {
    const token = root.dataset.token || '';
    const member = root.dataset.member === 'true';
    const owner = root.dataset.owner === 'true';

    root.querySelectorAll('[data-bs-meter]').forEach(meter => {
      meter.style.setProperty('--bs-fill', `${meterShare(meter.dataset.done, meter.dataset.total)}%`);
    });

    if (!member) {
      root.querySelectorAll('[data-bs-plan]').forEach(link => link.addEventListener('click', () => {
        storePending(token);
        count('break_signup_clicked');
      }));
      root.querySelectorAll('.x-dock a[href="/#signup"]').forEach(link => link.addEventListener('click', () => {
        storePending(token);
        count('break_signup_clicked');
      }));
      // guest-list.js saves and unsaves; this only counts a save.
      root.addEventListener('click', event => {
        const button = event.target.closest ? event.target.closest('[data-guest-kind]') : null;
        if (button && button.getAttribute('aria-pressed') !== 'true') count('break_title_saved');
      }, true);
      return;
    }

    if (!owner) {
      const pending = readPending();
      const from = root.dataset.from || '';
      // Back from signing up after "Plan these days": carry on to the planner with this plan's days.
      if (pending && pending.token === token && root.dataset.hasPlan === 'true') clearPending();
      else if (pending && pending.token === token && /^\/break\?from=[A-Za-z0-9_-]{16,40}$/.test(from)) {
        window.location.replace(from);
        return;
      }
      root.querySelectorAll('[data-bs-same]').forEach(link => link.addEventListener('click', () => count('break_same_days_clicked')));
      root.querySelectorAll('[data-bs-add]').forEach(button => button.addEventListener('click', () => {
        if (button.disabled || !window.OmniSiteSave) return;
        button.disabled = true;
        window.OmniSiteSave.addToLibrary(button.dataset.kind, button.dataset.slug).then(outcome => {
          if (outcome && outcome.signedOut) { window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#login`; return; }
          button.classList.add('is-done');
          button.setAttribute('aria-label', button.getAttribute('aria-label').replace(/^Save /, 'Saved ').replace(/ to my list$/, ' to your list'));
          count('break_title_saved');
        }).catch(() => {
          button.disabled = false;
          const idle = button.querySelector('.bs-save__idle');
          if (idle) idle.textContent = 'Try again';
        });
      }));
      return;
    }

    const box = root.querySelector('[data-bs-owner]');
    if (!box) return;
    const status = box.querySelector('[data-bs-status]');
    const say = text => { if (status) status.textContent = text; };
    const url = window.location.origin + window.location.pathname;
    const copy = box.querySelector('[data-bs-copy]');
    const share = box.querySelector('[data-bs-share]');
    const story = box.querySelector('[data-bs-story]');
    const off = box.querySelector('[data-bs-off]');
    if (copy) copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(url);
        say('Link copied.');
        count('break_link_shared');
      } catch (error) {
        say(`Copy this link: ${url}`);
      }
    });
    if (share && navigator.share) {
      share.hidden = false;
      share.addEventListener('click', async () => {
        try {
          await navigator.share({ title: document.title, url });
          count('break_link_shared');
        } catch (error) { /* closed the share sheet */ }
      });
    }
    if (story) story.addEventListener('click', async () => {
      const src = story.dataset.src || '';
      if (!/^\/break\/s\/[A-Za-z0-9_-]{16,40}\/story\.png$/.test(src)) return;
      story.disabled = true;
      say('Getting your picture ready…');
      try {
        const response = await fetch(src, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        const file = typeof File === 'function' ? new File([blob], 'omnitrackr-break-plan.png', { type: 'image/png' }) : null;
        count('break_story_saved');
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          try { await navigator.share({ files: [file], title: document.title }); say(''); } catch (error) {
            say(error && error.name === 'AbortError' ? '' : 'Sharing didn’t open, so try again or long-press the picture.');
          }
        } else {
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = 'omnitrackr-break-plan.png';
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(link.href), 4000);
          say('Picture saved. Add it to a story and put the link on it.');
        }
      } catch (error) {
        say('The picture didn’t load. Try again in a minute.');
      } finally {
        story.disabled = false;
      }
    });
    if (off) off.addEventListener('click', async () => {
      const plan = Number(box.dataset.plan);
      if (off.disabled || !Number.isSafeInteger(plan) || plan <= 0) return;
      off.disabled = true;
      say('Turning the link off…');
      try {
        const response = await fetch(`/api/break/${plan}/share?today=${today()}`, { method: 'DELETE', credentials: 'same-origin', headers: headers() });
        if (response.status === 401) { window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#login`; return; }
        if (!response.ok) throw new Error(String(response.status));
        box.querySelectorAll('.bs-actions button').forEach(button => { button.disabled = true; button.hidden = true; });
        say('The link is off. Anyone who opens it now sees that it isn’t shared anymore. You can make a new one from your plan.');
      } catch (error) {
        off.disabled = false;
        say('That didn’t work. Try again in a minute.');
      }
    });
  }

  const start = () => { const root = document.getElementById('breakShare'); if (root) setup(root); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
