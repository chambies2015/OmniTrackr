// "Your first week": a home-screen card for an account's first seven days. It lays out the member's
// week (new episodes and release days of titles they saved), offers shows airing this week when
// their week is empty, and lets them ask for one reminder email on a day something of theirs is out.
// The server decides who sees it (app/week_one.py). Server text is only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 60 * 1000;
  const PENDING_RETRY_MS = 12 * 1000;
  const MAX_PENDING_RETRIES = 2;
  const WEEK_DAYS = 7;
  const LOADERS = {
    movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime', 'video-games': 'loadVideoGames',
  };
  const state = { epoch: 0, card: null, request: null, loadedAt: 0, seenDay: '', observer: null, retries: 0, retryTimer: null, busy: false };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  // Same-site paths only ("//host" is another site).
  const localPath = url => typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/\\');

  // The card is only for an account's first seven days, so established members skip the request.
  // Two days of slack: the server trusts the browser's date within a day of UTC's.
  function pastFirstWeek() {
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      const made = user && typeof user.created_at === 'string' ? user.created_at : '';
      if (!made) return false;
      const time = Date.parse(/(?:[zZ]|[+-]\d\d:?\d\d)$/.test(made) ? made : `${made}Z`);
      return Number.isFinite(time) && Date.now() - time > (WEEK_DAYS + 2) * 24 * 60 * 60 * 1000;
    } catch (error) {
      return false;
    }
  }

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  async function send(method, path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method,
      headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      throw new Error(typeof detail === 'string' ? detail : 'That didn’t work. Please try again.');
    }
    return data;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function pad(n) { return String(n).padStart(2, '0'); }

  // The member's own date, so "today" on the card is their today, not the server's.
  function localToday(now = new Date()) {
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  function parseDay(iso) {
    const [year, month, day] = String(iso || '').split('-').map(Number);
    const when = new Date(year, (month || 1) - 1, day || 1);
    return Number.isNaN(when.getTime()) ? null : when;
  }

  function daysFrom(iso, today) {
    const a = parseDay(iso);
    const b = parseDay(today);
    if (!a || !b) return null;
    return Math.round((a - b) / 86400000);
  }

  function dayName(iso, today, style = 'long') {
    const diff = daysFrom(iso, today);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Tomorrow';
    const when = parseDay(iso);
    return when ? when.toLocaleDateString(undefined, { weekday: style }) : '';
  }

  // "today", "tomorrow" or "on Sunday", for the middle of a sentence.
  function whenWords(iso, today) {
    const name = dayName(iso, today);
    if (name === 'Today' || name === 'Tomorrow') return name.toLowerCase();
    return name ? `on ${name}` : '';
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text || '';
  }

  function setStatus(text) { setText('weekOneStatus', text); }

  function pushSupported() {
    return Boolean(window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window
      && 'Notification' in window && window.omniPush);
  }

  async function pushPossible() {
    if (!pushSupported()) return false;
    try {
      if (Notification.permission === 'denied') return false;
      if (window.omniPush.state() === null || window.omniPush.state() === undefined) await window.omniPush.refresh();
      return window.omniPush.state() === 'off';
    } catch (error) {
      return false;
    }
  }

  function cover(src, title) {
    const wrap = el('span', 'week-one__cover');
    if (typeof src === 'string' && /^https?:\/\//.test(src)) {
      const img = el('img');
      img.src = src;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => { img.remove(); wrap.textContent = (title || '?').slice(0, 1).toUpperCase(); }, { once: true });
      wrap.append(img);
    } else {
      wrap.textContent = (title || '?').slice(0, 1).toUpperCase();
    }
    return wrap;
  }

  // ------------------------------------------------ the week

  function openItem(item, button) {
    if (item.item_id && typeof openLibraryItem === 'function') {
      openLibraryItem({ category: item.category, id: item.item_id, title: item.title },
        { button, reasonElement: $('weekOneStatus') });
      return;
    }
    if (localPath(item.url)) window.location.assign(item.url);
  }

  function itemRow(item) {
    const row = el('li', 'week-one__item');
    row.dataset.format = item.category || '';
    const clickable = Boolean(item.item_id) || localPath(item.url);
    const body = el(clickable ? 'button' : 'span', 'week-one__item-body');
    if (clickable) {
      body.type = 'button';
      body.setAttribute('aria-label', `${item.title}, ${item.kind === 'episode' ? item.what : 'release day'}. Open it`);
      body.addEventListener('click', () => openItem(item, body));
    }
    const words = el('span', 'week-one__item-words');
    words.append(el('strong', 'week-one__item-title', item.title),
      el('span', 'week-one__item-what', item.kind === 'episode' ? item.what : 'Out'));
    body.append(cover(item.image, item.title), words);
    row.append(body);
    return row;
  }

  function renderDays(card) {
    const list = $('weekOneDays');
    if (!list) return;
    list.replaceChildren();
    (card.days || []).forEach((day, index) => {
      const column = el('li', 'week-one__day');
      if (index === 0) column.classList.add('is-today');
      if (!(day.items || []).length) column.classList.add('is-empty');
      const head = el('p', 'week-one__day-head');
      const when = parseDay(day.date);
      head.append(el('span', 'week-one__day-name', index === 0 ? 'Today' : dayName(day.date, card.today, 'short')),
        el('span', 'week-one__day-date', when ? String(when.getDate()) : ''));
      column.append(head);
      const items = el('ul', 'week-one__items');
      (day.items || []).forEach(item => items.append(itemRow(item)));
      if (day.more) items.append(el('li', 'week-one__more', `+${day.more} more`));
      if (!(day.items || []).length) items.append(el('li', 'week-one__none', 'Nothing yet'));
      column.append(items);
      list.append(column);
    });
    list.hidden = !card.count;
  }

  function renderDots(card) {
    const dots = $('weekOneDots');
    if (!dots) return;
    dots.replaceChildren();
    for (let n = 1; n <= WEEK_DAYS; n += 1) {
      const dot = el('li', `week-one__dot${n < card.day ? ' is-past' : ''}${n === card.day ? ' is-now' : ''}`);
      dot.setAttribute('aria-label', n === card.day ? `Day ${n}, today` : `Day ${n}`);
      dots.append(dot);
    }
  }

  // ------------------------------------------------ shows airing this week

  async function saveShow(show, button) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    button.textContent = 'Saving…';
    try {
      const data = await send('POST', '/api/week-one/save', { key: show.key, today: localToday() });
      button.textContent = data.state === 'existing' ? 'Already saved' : 'Saved';
      button.classList.add('is-done');
      setStatus(data.state === 'existing'
        ? `${show.title} is already in your library.`
        : `Saved ${show.title}. Its episodes will show up in your week.`);
      const loader = window[LOADERS[show.category]];
      if (typeof loader === 'function') { try { loader(); } catch (error) { /* shows up on the next visit */ } }
      state.retries = 0;
      refresh(true);
    } catch (error) {
      button.disabled = false;
      button.textContent = 'I’m watching it';
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  function renderSuggestions(card) {
    const box = $('weekOneSuggest');
    const list = $('weekOneSuggestList');
    if (!box || !list) return;
    list.replaceChildren();
    const picks = card.suggestions || [];
    picks.forEach(show => {
      const row = el('li', 'week-one__pick');
      row.dataset.format = show.category;
      row.append(cover(show.image, show.title));
      const words = el('div', 'week-one__pick-words');
      words.append(el('strong', 'week-one__pick-title', show.title));
      const next = show.next || {};
      const line = [show.label, `${next.what || 'New episode'} ${whenWords(next.date, card.today)}`];
      words.append(el('span', 'week-one__pick-meta', line.filter(Boolean).join(' · ')));
      const extra = [show.network, show.members ? `${show.members} members follow it` : ''].filter(Boolean).join(' · ');
      if (extra) words.append(el('span', 'week-one__pick-meta week-one__pick-meta--soft', extra));
      row.append(words);
      const button = el('button', 'week-one__btn week-one__btn--small', 'I’m watching it');
      button.type = 'button';
      button.setAttribute('aria-label', `I'm watching ${show.title}: save it to your library`);
      button.addEventListener('click', () => saveShow(show, button));
      row.append(button);
      list.append(row);
    });
    box.hidden = !picks.length;
  }

  async function saveRelease(release, button) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    button.textContent = 'Saving…';
    try {
      const data = await send('POST', '/api/week-one/save-release', {
        category: release.category, window: release.window, key: release.key, today: localToday(),
      });
      button.textContent = data.state === 'existing' ? 'Already saved' : 'Saved';
      button.classList.add('is-done');
      setStatus(data.state === 'existing'
        ? `${release.title} is already in your library.`
        : `Saved ${release.title}. Its release day is on your week.`);
      const loader = window[LOADERS[release.library_category]];
      if (typeof loader === 'function') { try { loader(); } catch (error) { /* shows up on the next visit */ } }
      refresh(true);
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Want to see';
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  function renderReleases(card) {
    const box = $('weekOneReleases');
    const list = $('weekOneReleaseList');
    if (!box || !list) return;
    list.replaceChildren();
    const releases = card.releases || [];
    releases.forEach(release => {
      const row = el('li', 'week-one__pick');
      row.dataset.format = release.library_category || '';
      row.append(cover(release.image, release.title));
      const words = el('div', 'week-one__pick-words');
      words.append(el('strong', 'week-one__pick-title', release.title),
        el('span', 'week-one__pick-meta', [release.label, `Out ${whenWords(release.date, card.today)}`].filter(Boolean).join(' · ')));
      row.append(words);
      const button = el('button', 'week-one__btn week-one__btn--small', 'Want to see');
      button.type = 'button';
      button.setAttribute('aria-label', `Save ${release.title} to your library`);
      button.addEventListener('click', () => saveRelease(release, button));
      row.append(button);
      list.append(row);
    });
    box.hidden = !releases.length;
  }

  // ------------------------------------------------ the reminder

  function tzMinutes() {
    return -new Date().getTimezoneOffset();
  }

  async function remind(card, button) {
    button.disabled = true;
    try {
      const data = await send('PUT', '/api/week-one/reminder', { day: card.remind_day, today: localToday(), tz: tzMinutes() });
      card.reminder = data.reminder;
      renderRemind(card);
    } catch (error) {
      button.disabled = false;
      setStatus(error.message);
    }
  }

  async function cancel(card, button) {
    button.disabled = true;
    try {
      await send('DELETE', '/api/week-one/reminder');
      card.reminder = null;
      renderRemind(card);
      setStatus('Reminder cancelled.');
    } catch (error) {
      button.disabled = false;
      setStatus(error.message);
    }
  }

  async function turnOnPush(button) {
    button.disabled = true;
    let result = 'off';
    try { result = await window.omniPush.turnOn('week_one'); } catch (error) { result = 'off'; }
    if (result === 'on') {
      send('POST', '/api/week-one/push').catch(() => {});
      button.hidden = true;
      setStatus('Notifications are on for this device. You’ll get one on the day each episode is out.');
    } else {
      button.disabled = false;
      setStatus(result === 'blocked' ? 'Notifications are blocked for OmniTrackr in this browser’s settings.' : 'Notifications didn’t turn on. Please try again.');
    }
  }

  async function renderRemind(card) {
    const box = $('weekOneRemind');
    const text = $('weekOneRemindText');
    const email = $('weekOneEmail');
    const push = $('weekOnePush');
    const cancelButton = $('weekOneCancel');
    if (!box || !text || !email || !push || !cancelButton) return;
    const reminder = card.reminder;
    email.hidden = true;
    cancelButton.hidden = true;
    email.disabled = false;
    cancelButton.disabled = false;
    if (reminder && reminder.status === 'set') {
      text.textContent = `Reminder set. We’ll email you ${whenWords(reminder.date, card.today)} at about 5 pm with what’s out. Just the one email.`;
      cancelButton.hidden = false;
    } else if (reminder && reminder.status === 'sent') {
      text.textContent = 'Your reminder went out. Want another? Pick a day from a show’s next episode.';
    } else if (card.remind_day && card.offer && card.offer.email) {
      const name = dayName(card.remind_day, card.today);
      text.textContent = 'Want a nudge on the day? One email, nothing after it and nothing to unsubscribe from.';
      email.textContent = name === 'Tomorrow' ? 'Email me tomorrow' : `Email me on ${name}`;
      email.hidden = false;
    } else {
      text.textContent = card.remind_day ? 'Want a nudge on the day?' : '';
    }
    const offerPush = Boolean(card.offer && card.offer.push) && card.count > 0 && await pushPossible();
    if (state.card !== card) return;  // a newer refresh or a sign-out got here first
    push.hidden = !offerPush;
    push.disabled = false;
    if (offerPush && !text.textContent) text.textContent = 'Want a heads-up on the day?';
    box.hidden = email.hidden && push.hidden && cancelButton.hidden && !(reminder && reminder.status === 'sent');
  }

  // ------------------------------------------------ the card

  function render(card) {
    const section = $('weekOne');
    if (!section) return;
    state.card = card || null;
    if (!card) {
      section.hidden = true;
      return;
    }
    setText('weekOneEyebrow', `Your first week · Day ${card.day} of ${WEEK_DAYS}`);
    if (card.count) {
      setText('weekOneTitle', card.count === 1 ? 'One thing from your library this week' : `${card.count} things from your library this week`);
      setText('weekOneSummary', 'New episodes and release days of the titles you saved. Come back on the day to mark them off.');
    } else {
      setText('weekOneTitle', 'Nothing of yours is out this week yet');
      setText('weekOneSummary', (card.suggestions || []).length
        ? 'What you saved so far is finished or between seasons. Add a show you’re watching and this week fills in.'
        : 'What you saved so far is finished or between seasons. Add a show you’re watching or a game you’re waiting for, and this week fills in.');
    }
    renderDots(card);
    renderDays(card);
    renderSuggestions(card);
    renderReleases(card);
    renderRemind(card);
    const wasHidden = section.hidden;
    section.hidden = false;
    // The start page links straight here ("See my week").
    if (wasHidden && window.location.hash === '#week-one') {
      window.requestAnimationFrame(() => section.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    }
    watchSeen(section, card);
    if (card.pending && state.retries < MAX_PENDING_RETRIES) {
      window.clearTimeout(state.retryTimer);
      const epoch = state.epoch;
      state.retryTimer = window.setTimeout(() => {
        if (epoch !== state.epoch) return;
        state.retries += 1;
        refresh(true);
      }, PENDING_RETRY_MS);
    }
  }

  // Counted as seen once half the card is on screen; a later day of the week counts as coming back.
  function watchSeen(section, card) {
    if (state.observer) state.observer.disconnect();
    const today = card.today;
    if (state.seenDay === today) return;
    const report = () => {
      if (state.seenDay === today) return;
      state.seenDay = today;
      send('POST', '/api/week-one/seen', { today: localToday() }).catch(() => { state.seenDay = ''; });
    };
    if (typeof IntersectionObserver !== 'function') {
      report();
      return;
    }
    state.observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        state.observer.disconnect();
        report();
      }
    }, { threshold: 0.4 });
    state.observer.observe(section);
  }

  function refresh(force = false) {
    if (!signedIn() || pastFirstWeek()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/week-one?today=${encodeURIComponent(localToday())}`,
      fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data.card); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.card = null;
    state.request = null;
    state.loadedAt = 0;
    state.seenDay = '';
    state.retries = 0;
    window.clearTimeout(state.retryTimer);
    if (state.observer) state.observer.disconnect();
    const section = $('weekOne');
    if (section) section.hidden = true;
    ['weekOneDays', 'weekOneDots', 'weekOneSuggestList', 'weekOneReleaseList'].forEach(id => $(id)?.replaceChildren());
    setStatus('');
  }

  function wire() {
    $('weekOneEmail')?.addEventListener('click', event => { if (state.card) remind(state.card, event.currentTarget); });
    $('weekOneCancel')?.addEventListener('click', event => { if (state.card) cancel(state.card, event.currentTarget); });
    $('weekOnePush')?.addEventListener('click', event => turnOnPush(event.currentTarget));
    $('weekOneHide')?.addEventListener('click', event => {
      const button = event.currentTarget;
      button.disabled = true;
      send('POST', '/api/week-one/hide').then(() => {
        const section = $('weekOne');
        if (section) section.hidden = true;
        state.card = null;
      }).catch(error => { button.disabled = false; setStatus(error.message); });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  document.addEventListener('visibilitychange', () => {
    // A tab left open overnight shows the new day's week when it comes back.
    if (document.visibilityState === 'visible' && state.card && state.card.today !== localToday()) refresh(true);
  });

  window.OmniWeekOne = { refresh, reset, render };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { refresh, reset, render, localToday, pastFirstWeek, localPath, dayName, daysFrom, whenWords, state };
  }
})();
