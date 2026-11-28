// A member's shared "On your services" list (/on-my-services/<token>, app/routers/services_share.py).
// Visitors tick the services they have and see which of the titles they could watch too; what they
// tick stays in this browser. Titles save to the browser-only guest list (guest-list.js handles those
// buttons) or, for members, straight into the library. The member who shared it gets copy, share and
// story-image buttons. Text from the page is only ever set as textContent.
(function () {
  'use strict';

  const KEY = 'omnitrackr_my_services';
  const ID = /^[a-z]{2,16}$/;

  // ---------------------------------------------------------------- matching (no DOM)

  function and(parts) {
    if (parts.length <= 1) return parts.join('');
    return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
  }

  // The services of yours a title is on, in the order the title lists them.
  function overlap(all, mine) {
    const have = new Set(mine);
    return all.filter(service => have.has(service));
  }

  function resultText(matched, total, ticked) {
    if (!ticked) return '';
    if (!matched) return `None of these ${total} are on your services yet. Sign up and we’ll tell you when one arrives.`;
    if (matched === total) return `You can watch all ${total} of these on your services.`;
    return `You can watch ${matched} of these ${total} on your services.`;
  }

  function readMine() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      return Array.isArray(saved) ? saved.filter(value => typeof value === 'string' && ID.test(value)).slice(0, 40) : null;
    } catch (error) {
      return null;
    }
  }

  function storeMine(ids) {
    try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, 40))); } catch (error) { /* this visit only */ }
  }

  // ---------------------------------------------------------------- the page

  function count(event) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting only */ }
  }

  function setup(root) {
    const grid = root.querySelector('[data-svc-grid]');
    const tiles = Array.from(root.querySelectorAll('[data-svc-item]'));
    const chips = Array.from(root.querySelectorAll('input[name="svcMine"]'));
    const result = root.querySelector('[data-svc-result]');
    const names = {};
    chips.forEach(chip => { names[chip.value] = chip.parentElement.textContent.trim(); });
    let counted = false;

    function mine() {
      return chips.filter(chip => chip.checked).map(chip => chip.value);
    }

    function mark() {
      const picked = mine();
      let matched = 0;
      tiles.forEach(tile => {
        const all = (tile.dataset.all || '').split(' ').filter(Boolean);
        const yours = overlap(all, picked);
        const line = tile.querySelector('[data-svc-you]');
        tile.classList.toggle('is-yours', yours.length > 0);
        if (yours.length) matched += 1;
        if (line) {
          line.hidden = !yours.length;
          line.textContent = yours.length ? `You can watch it on ${and(yours.map(id => names[id] || id))}` : '';
        }
      });
      root.classList.toggle('has-picks', picked.length > 0);
      if (result) result.textContent = resultText(matched, tiles.length, picked.length);
    }

    function apply(ids) {
      const wanted = new Set(ids);
      chips.forEach(chip => { chip.checked = wanted.has(chip.value); });
      mark();
    }

    chips.forEach(chip => chip.addEventListener('change', () => {
      const picked = mine();
      storeMine(picked);
      mark();
      if (!counted && picked.length) { counted = true; count('svc_services_ticked'); }
    }));

    const saved = readMine();
    if (saved && saved.length) {
      apply(saved);
    } else if (root.dataset.member === 'true' && root.dataset.owner !== 'true' && chips.length) {
      // A member who picked services on their own home card sees them ticked here.
      fetch('/api/streaming', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(response => (response.ok ? response.json() : null))
        .then(data => {
          if (!data || !Array.isArray(data.chosen) || mine().length) return;
          const byName = {};
          Object.keys(names).forEach(id => { byName[names[id]] = id; });
          apply(data.chosen.map(name => byName[name]).filter(Boolean));
        })
        .catch(() => { /* they can tick them */ });
    }

    // The member's own services, as chips over the grid.
    const filters = Array.from(root.querySelectorAll('[data-svc-filter]'));
    filters.forEach(filter => filter.addEventListener('click', () => {
      const service = filter.dataset.svcFilter;
      filters.forEach(other => other.setAttribute('aria-pressed', String(other === filter)));
      tiles.forEach(tile => {
        tile.hidden = Boolean(service) && !(tile.dataset.mine || '').split(' ').includes(service);
      });
    }));

    // Members add a title straight to their library.
    root.querySelectorAll('[data-svc-add]').forEach(button => button.addEventListener('click', () => {
      if (button.disabled || !window.OmniSiteSave) return;
      button.disabled = true;
      window.OmniSiteSave.addToLibrary(button.dataset.kind, button.dataset.slug).then(outcome => {
        if (outcome.signedOut) { window.location.href = '/#login'; return; }
        button.classList.add('is-done');
        button.setAttribute('aria-label', button.getAttribute('aria-label').replace(/^Save /, 'Saved ').replace(/ to my list$/, ' to your library'));
        count('svc_title_saved');
      }).catch(() => {
        button.disabled = false;
        const idle = button.querySelector('.svc-save__idle');
        if (idle) idle.textContent = 'Try again';
      });
    }));

    // Guests: guest-list.js saves and unsaves; this only counts the first save of each title.
    if (grid) {
      grid.addEventListener('click', event => {
        const button = event.target.closest ? event.target.closest('[data-guest-kind]') : null;
        if (button && button.getAttribute('aria-pressed') !== 'true') count('svc_title_saved');
      }, true);
    }
    root.querySelectorAll('[data-svc-signup]').forEach(link => link.addEventListener('click', () => count('svc_signup_clicked')));
    root.querySelectorAll('.x-dock a[href="/#signup"]').forEach(link => link.addEventListener('click', () => count('svc_signup_clicked')));

    setupOwner(root);
  }

  function setupOwner(root) {
    const box = root.querySelector('[data-svc-owner]');
    if (!box) return;
    const status = box.querySelector('[data-svc-owner-status]');
    const say = text => { if (status) status.textContent = text; };
    const url = window.location.origin + window.location.pathname;
    const copy = box.querySelector('[data-svc-copy]');
    const share = box.querySelector('[data-svc-share]');
    const story = box.querySelector('[data-svc-story]');
    const off = box.querySelector('[data-svc-off]');
    if (copy) copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(url);
        say('Link copied.');
        count('svc_link_shared');
      } catch (error) {
        say(`Copy this link: ${url}`);
      }
    });
    if (share && navigator.share) {
      share.hidden = false;
      share.addEventListener('click', async () => {
        try {
          await navigator.share({ title: document.title, url });
          count('svc_link_shared');
        } catch (error) { /* closed the share sheet */ }
      });
    }
    // The home card can be hidden for three weeks, so the link can be ended from its own page too.
    if (off) off.addEventListener('click', async () => {
      if (off.disabled) return;
      off.disabled = true;
      say('Turning the link off…');
      const headers = { Accept: 'application/json' };
      try {
        const token = window.localStorage.getItem('omnitrackr_token');
        if (token) headers.Authorization = `Bearer ${token}`;
      } catch (error) { /* the session cookie is enough */ }
      try {
        const response = await fetch('/api/streaming/share/off', { method: 'POST', credentials: 'same-origin', headers });
        if (response.status === 401) { window.location.href = '/#login'; return; }
        if (!response.ok) throw new Error(String(response.status));
        box.querySelectorAll('.svc-actions button').forEach(button => { button.disabled = true; button.hidden = true; });
        say('The link is off. Anyone who opens it now sees that it isn’t shared anymore. You can make a new one from your home card.');
      } catch (error) {
        off.disabled = false;
        say('That didn’t work. Try again in a minute.');
      }
    });
    if (story) story.addEventListener('click', async () => {
      const src = story.dataset.src || '';
      if (!/^\/on-my-services\/[A-Za-z0-9_-]{16,32}\/story\.png$/.test(src)) return;
      story.disabled = true;
      say('Getting your image ready…');
      try {
        const response = await fetch(src, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        const file = typeof File === 'function' ? new File([blob], 'omnitrackr-on-my-services.png', { type: 'image/png' }) : null;
        count('svc_link_shared');
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          try { await navigator.share({ files: [file], title: document.title }); say(''); } catch (error) {
            say(error && error.name === 'AbortError' ? '' : 'Sharing didn’t open, so try again or long-press the image.');
          }
        } else {
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = 'omnitrackr-on-my-services.png';
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(link.href), 4000);
          say('Image saved. Add it to a story and put the link on it.');
        }
      } catch (error) {
        say('The image didn’t load. Try again in a minute.');
      } finally {
        story.disabled = false;
      }
    });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { overlap, resultText, readMine, storeMine, and, KEY };
    return;
  }
  const start = () => { const root = document.getElementById('servicesShare'); if (root) setup(root); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
