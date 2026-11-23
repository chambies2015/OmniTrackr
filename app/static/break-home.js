// "Break planner" on the member home (app/break_plan.py, /break). Before a holiday it offers to plan the days
// off; with a plan it shows the first day coming up, then each day's part with a tick, and after the break how
// it went. The card only shows when one of those applies. Server text is only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 30 * 1000;
  const HIDDEN_KEY = 'omnitrackr_break_offer_hidden';
  const state = { epoch: 0, data: null, request: null, loadedAt: 0, busy: false, seenOn: '' };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);

  function pad(n) { return String(n).padStart(2, '0'); }
  function todayIso(now = new Date()) { return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`; }

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function hiddenOffers() {
    try {
      const value = JSON.parse(localStorage.getItem(HIDDEN_KEY) || '[]');
      return Array.isArray(value) ? value.filter(key => typeof key === 'string').slice(-20) : [];
    } catch (error) { return []; }
  }
  function hideOffer(key) {
    try { localStorage.setItem(HIDDEN_KEY, JSON.stringify([...hiddenOffers().filter(entry => entry !== key), key])); } catch (error) { /* this visit only */ }
  }

  function plural(n, one, many) { return `${n} ${n === 1 ? one : many || `${one}s`}`; }

  // ------------------------------------------------------------------ words for each state (also used by tests)

  function headline(card) {
    if (!card) return { eyebrow: '', title: '', summary: '' };
    const totals = card.totals || {};
    if (card.state === 'offer') {
      const when = card.starts_in <= 0 ? 'It starts today' : card.starts_in === 1 ? 'It starts tomorrow' : `It's ${card.span}`;
      return {
        eyebrow: 'Break planner',
        title: card.short === 'Thanksgiving' ? 'Got Thanksgiving off?' : `Got time off for ${card.short}?`,
        summary: `${when}. Say how much time you have each day and we'll fill the days from your list.`,
      };
    }
    if (card.state === 'upcoming') {
      const days = card.starts_in === 1 ? 'tomorrow' : `in ${plural(card.starts_in, 'day')}`;
      return {
        eyebrow: `Break planner · ${card.span}`,
        title: `${card.name} starts ${days}`,
        summary: totals.titles ? `${plural(totals.titles, 'title')} over ${plural(card.day_count, 'day')}, about ${totals.hours}. Here's day one.`
          : 'Nothing planned yet. Open the plan to fill it.',
      };
    }
    if (card.state === 'during') {
      const left = (card.today_items || []).filter(item => !item.done).length;
      return {
        eyebrow: `${card.name} · day ${card.day_number} of ${card.day_count}`,
        title: left ? 'On your break today' : (card.today_items || []).length ? 'Today\'s done' : 'A free day on your break',
        summary: `${totals.done || 0} of ${totals.stretches || 0} ticked off so far${totals.finished ? `, ${plural(totals.finished, 'title')} finished` : ''}.`,
      };
    }
    return {
      eyebrow: `${card.name} · ${card.span}`,
      title: totals.done ? 'How your break went' : 'Your break is over',
      summary: totals.done
        ? `You ticked off ${totals.done} of ${totals.stretches} and finished ${plural(totals.finished || 0, 'title')}, about ${totals.done_hours}.`
        : 'Nothing got ticked off. If you did watch or read something, tick it on the plan.',
    };
  }

  function itemLine(item) {
    return item.unit === 'block' ? item.label : `${item.label} · ${item.length}`;
  }

  // ------------------------------------------------------------------ drawing

  function cover(item) {
    const frame = el('span', 'break-home__cover');
    frame.setAttribute('aria-hidden', 'true');
    const letter = () => {
      frame.classList.add('break-home__cover--letter');
      frame.textContent = (String(item.title || '?').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase();
    };
    if (typeof item.image === 'string' && /^https:\/\//.test(item.image)) {
      const img = el('img');
      img.src = item.image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.width = 40;
      img.height = 60;
      img.addEventListener('error', () => { img.remove(); letter(); }, { once: true });
      frame.appendChild(img);
    } else {
      letter();
    }
    return frame;
  }

  function row(item, card, tickable) {
    const li = el('li', `break-home__item${item.done ? ' break-home__item--done' : ''}`);
    li.dataset.category = item.category || '';
    if (tickable) {
      const tick = el('button', 'break-home__tick', '✓');
      tick.type = 'button';
      tick.dataset.planId = String(card.id);
      tick.dataset.itemId = String(item.id);
      tick.setAttribute('aria-pressed', String(Boolean(item.done)));
      tick.setAttribute('aria-label', item.done ? `${item.title}: done` : `Tick off ${item.title}, ${item.label}`);
      if (item.done) tick.disabled = true;
      li.appendChild(tick);
    } else {
      li.appendChild(cover(item));
    }
    const body = el('div', 'break-home__body');
    body.append(el('span', 'break-home__kind', item.kind_label || ''), el('strong', 'break-home__name', item.title),
      el('span', 'break-home__what', itemLine(item)));
    li.appendChild(body);
    return li;
  }

  function link(text, href, className) {
    const node = el('a', className || 'break-home__btn', text);
    node.href = href;
    return node;
  }

  function render(card) {
    state.data = card;
    const section = $('breakHome');
    const list = $('breakHomeList');
    const actions = $('breakHomeActions');
    if (!section || !list || !actions) return;
    if (!card || (card.state === 'offer' && hiddenOffers().includes(card.key))) {
      section.hidden = true;
      list.replaceChildren();
      actions.replaceChildren();
      return;
    }
    const words = headline(card);
    $('breakHomeEyebrow').textContent = words.eyebrow;
    $('breakHomeTitle').textContent = words.title;
    $('breakHomeSummary').textContent = words.summary;
    section.dataset.state = card.state;
    const more = $('breakHomeMore');
    list.replaceChildren();
    actions.replaceChildren();
    if (card.state === 'offer') {
      more.hidden = true;
      const go = link('Plan it', `/break?preset=${encodeURIComponent(card.key)}`, 'break-home__btn break-home__btn--primary');
      go.addEventListener('click', () => {
        try {
          navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event: 'break_home_offer_clicked' })], { type: 'application/json' }));
        } catch (error) { /* analytics only */ }
      });
      const later = el('button', 'break-home__quiet', 'Not now');
      later.type = 'button';
      later.addEventListener('click', () => { hideOffer(card.key); render(null); });
      actions.append(go, later);
    } else if (card.state === 'upcoming') {
      more.hidden = false;
      more.textContent = 'Open the plan';
      (card.first_day || []).forEach(item => list.appendChild(row(item, card, false)));
    } else if (card.state === 'during') {
      more.hidden = false;
      more.textContent = 'The whole plan';
      (card.today_items || []).forEach(item => list.appendChild(row(item, card, true)));
      if (!(card.today_items || []).length && (card.tomorrow || []).length) {
        list.appendChild(el('li', 'break-home__note', 'Nothing planned today. Tomorrow:'));
        card.tomorrow.forEach(item => list.appendChild(row(item, card, false)));
      }
      if (!(card.today_items || []).length && !(card.tomorrow || []).length) {
        actions.appendChild(link('Fill today from my list', '/break', 'break-home__btn break-home__btn--primary'));
      }
      noteSeen();
    } else {
      more.hidden = false;
      more.textContent = 'See it all';
      (card.finished || []).forEach(item => list.appendChild(row(item, card, false)));
      actions.appendChild(link(card.finished && card.finished.length ? 'Score them' : 'Open the plan', '/break', 'break-home__btn break-home__btn--primary'));
      const done = el('button', 'break-home__quiet', 'Done with this');
      done.type = 'button';
      done.addEventListener('click', () => hideWrap(card, done));
      actions.appendChild(done);
    }
    section.hidden = false;
    if (window.OmniHomeLayout && typeof window.OmniHomeLayout.schedule === 'function') window.OmniHomeLayout.schedule();
  }

  function setStatus(text) {
    const node = $('breakHomeStatus');
    if (node) node.textContent = text || '';
  }

  async function post(path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ today: todayIso(), ...(body || {}) }),
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      throw new Error(typeof detail === 'string' ? detail : 'That didn’t save. Please try again.');
    }
    return data;
  }

  function noteSeen() {
    const today = todayIso();
    if (state.seenOn === today) return;
    state.seenOn = today;
    post('/api/break/seen').catch(() => {});
  }

  async function tick(button) {
    if (state.busy) return;
    const planId = Number(button.dataset.planId);
    const itemId = Number(button.dataset.itemId);
    if (!Number.isSafeInteger(planId) || planId <= 0 || !Number.isSafeInteger(itemId) || itemId <= 0) return;
    state.busy = true;
    button.disabled = true;
    setStatus('');
    const epoch = state.epoch;
    try {
      const data = await post(`/api/break/${planId}/items/${itemId}/done`);
      if (epoch !== state.epoch) return;
      const name = button.closest('li')?.querySelector('.break-home__name')?.textContent || 'it';
      await refresh(true);
      setStatus(data.ticked && data.ticked.finished ? `Finished ${name}. Score it on the plan.` : `Ticked off ${name}.`);
      if (typeof window.refreshLibraryPulse === 'function') Promise.resolve(window.refreshLibraryPulse()).catch(() => {});
    } catch (error) {
      setStatus(error.message);
      if (button.isConnected) button.disabled = false;
    } finally {
      state.busy = false;
    }
  }

  async function hideWrap(card, button) {
    button.disabled = true;
    try {
      await post(`/api/break/${Number(card.id)}/hide-wrap`);
      render(null);
    } catch (error) {
      setStatus(error.message);
      button.disabled = false;
    }
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/break/home?today=${encodeURIComponent(todayIso())}`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data.card || null); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.data = null;
    state.request = null;
    state.loadedAt = 0;
    state.busy = false;
    const section = $('breakHome');
    if (section) section.hidden = true;
    $('breakHomeList')?.replaceChildren();
    $('breakHomeActions')?.replaceChildren();
    setStatus('');
  }

  function wire() {
    $('breakHomeList')?.addEventListener('click', event => {
      const button = event.target.closest('.break-home__tick');
      if (button && !button.disabled) tick(button);
    });
    // The dashboard's first batch of cards can run before this deferred script, so ask once here too.
    refresh();
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { headline, itemLine, todayIso, state };
  if (typeof document === 'undefined') return;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  window.OmniBreak = { refresh, reset, render };
})();
