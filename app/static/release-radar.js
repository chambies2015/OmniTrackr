/* Release Radar: client-side filters and one-click tracking.
   The page is complete without JavaScript; this only adds filtering and turns
   the sign-in links into "Track this" buttons for signed-in members. */
(() => {
  const normalize = value => String(value || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();

  // ---- Period picker ------------------------------------------------------
  const jump = document.querySelector('[data-radar-jump]');
  if (jump) {
    jump.addEventListener('change', () => {
      const target = jump.value;
      if (/^\/release-radar\/(movies|tv|anime|games)(\/[a-z0-9-]{4,20})?$/.test(target)) window.location.assign(target);
    });
  }

  // ---- Filters ------------------------------------------------------------
  const filters = document.getElementById('radar-filters');
  const list = document.getElementById('radar-list');
  const owned = new Set();
  function applyFilters() {
    if (!filters || !list) return;
    const search = normalize(filters.querySelector('[data-radar-filter="search"]')?.value).trim().split(/\s+/).filter(Boolean);
    const genre = filters.querySelector('[data-radar-filter="genre"]')?.value || '';
    const platform = filters.querySelector('[data-radar-filter="platform"]')?.value || '';
    const hideMine = Boolean(filters.querySelector('[data-radar-filter="hide-mine"]')?.checked);
    let shown = 0;
    const cards = Array.from(list.querySelectorAll('.radar-card'));
    for (const card of cards) {
      const visible = search.every(term => (card.dataset.search || '').includes(term))
        && (!genre || (card.dataset.genres || '').split('|').includes(genre))
        && (!platform || (card.dataset.platforms || '').split('|').includes(platform))
        && !(hideMine && owned.has(card.dataset.key));
      card.hidden = !visible;
      if (visible) shown++;
    }
    for (const week of list.querySelectorAll('.radar-week')) {
      week.hidden = !week.querySelector('.radar-card:not([hidden])');
    }
    const results = document.getElementById('radar-results');
    if (results) results.textContent = `${shown} of ${cards.length} titles`;
    const empty = document.getElementById('radar-empty');
    if (empty) empty.hidden = shown > 0;
  }
  if (filters && list) {
    filters.addEventListener('input', applyFilters);
    filters.addEventListener('change', applyFilters);
    filters.querySelector('[data-radar-reset]')?.addEventListener('click', () => {
      filters.querySelectorAll('input[type="search"], select').forEach(el => { el.value = ''; });
      filters.querySelectorAll('input[type="checkbox"]').forEach(el => { el.checked = false; });
      applyFilters();
      filters.querySelector('input[type="search"]')?.focus();
    });
    filters.hidden = false;
    applyFilters();
  }

  // ---- Tracking -----------------------------------------------------------
  const live = document.createElement('p');
  live.className = 'visually-hidden';
  live.setAttribute('role', 'status');
  live.setAttribute('aria-live', 'polite');
  document.body.append(live);

  function headers() {
    const result = {'Content-Type': 'application/json'};
    try { const token = localStorage.getItem('omnitrackr_token'); if (token) result.Authorization = `Bearer ${token}`; } catch (_) {}
    return result;
  }

  function markSaved(link) {
    link.classList.add('is-saved');
    link.setAttribute('aria-disabled', 'true');
    link.textContent = '✓ In your library';
  }

  async function track(link) {
    if (link.classList.contains('is-saved') || link.classList.contains('is-busy')) return;
    const card = link.closest('.radar-card');
    link.classList.add('is-busy');
    try {
      const response = await fetch('/api/release-radar/save', {
        method: 'POST', headers: headers(), credentials: 'same-origin',
        body: JSON.stringify({category: card.dataset.category, window: card.dataset.window, key: card.dataset.key}),
      });
      if (response.status === 401) { window.location.assign(link.dataset.signin); return; }
      if (!response.ok) throw new Error('save failed');
      const result = await response.json();
      owned.add(card.dataset.key);
      markSaved(link);
      live.textContent = result.state === 'created'
        ? `${result.title} added to your library and your Release Radar collection.`
        : `${result.title} was already in your library; it is now in your Release Radar collection too.`;
    } catch (_) {
      live.textContent = 'Could not save that title. Please try again.';
      link.classList.add('radar-add--error');
    } finally {
      link.classList.remove('is-busy');
    }
  }

  const links = Array.from(document.querySelectorAll('[data-radar-add]'));
  if (!links.length) return;
  const groups = new Map();
  for (const link of links) {
    const card = link.closest('.radar-card');
    if (!card || !card.dataset.window) continue;
    const id = `${card.dataset.category}/${card.dataset.window}`;
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(link);
  }

  (async () => {
    let signedIn = false;
    for (const [id, groupLinks] of groups) {
      if (!/^(movies|tv|anime|games)\/[a-z0-9-]{4,20}$/.test(id)) continue;
      let response;
      try {
        response = await fetch(`/api/release-radar/${id}/library`, {headers: headers(), credentials: 'same-origin'});
      } catch (_) { return; }
      if (response.status === 401) return; // Guests keep the sign-in links.
      if (!response.ok) continue;
      signedIn = true;
      const data = await response.json();
      const keys = new Set(Array.isArray(data.keys) ? data.keys : []);
      for (const link of groupLinks) {
        link.dataset.signin = link.getAttribute('href');
        link.setAttribute('role', 'button');
        link.setAttribute('href', '#');
        const key = link.closest('.radar-card').dataset.key;
        if (keys.has(key)) { owned.add(key); markSaved(link); }
        link.addEventListener('click', event => { event.preventDefault(); track(link); });
        link.addEventListener('keydown', event => { if (event.key === ' ') { event.preventDefault(); track(link); } });
      }
    }
    if (signedIn) {
      const wrap = document.querySelector('[data-radar-mine-wrap]');
      if (wrap) wrap.hidden = false;
      applyFilters();
    }
  })();
})();
