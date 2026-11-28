// "Your week": seven day tiles, Monday to Sunday, that light up when the member logs anything; a
// weekly pace they pick; kept weeks in a row; last week's recap on Mondays; and an optional Sunday
// nudge. The server decides who sees it and counts everything (app/your_week.py). Server text is
// only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 4 * 1000;
  const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const DAY_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const HISTORY_WORDS = {
    kept: 'kept', rest: 'a week off', missed: 'not kept', active: 'something logged', quiet: 'nothing logged',
  };
  const state = { epoch: 0, card: null, request: null, loadedAt: 0, seenDay: '', observer: null, busy: false, showPaces: false, shown: false };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  // Minutes east of UTC, so the week runs Monday to Sunday on the member's own clock.
  const tz = () => -new Date().getTimezoneOffset();

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

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text || '';
  }

  function setStatus(text) { setText('yourWeekStatus', text); }

  function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }

  function weeksWord(n) { return n === 1 ? 'week' : 'weeks'; }

  function parseDay(iso) {
    const [year, month, day] = String(iso || '').split('-').map(Number);
    const when = new Date(year, (month || 1) - 1, day || 1);
    return Number.isNaN(when.getTime()) ? null : when;
  }

  function shortDate(iso) {
    const when = parseDay(iso);
    return when ? when.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';
  }

  // Days the member can still log on, today included unless today is already lit.
  function daysOpen(card) {
    const days = Array.isArray(card.days) ? card.days : [];
    return days.filter(day => day.future || (day.today && !day.logged)).length;
  }

  function isSunday(card) {
    const days = Array.isArray(card.days) ? card.days : [];
    return Boolean(days[6] && days[6].today);
  }

  // ------------------------------------------------ the words

  function headline(card) {
    const goal = card.goal;
    if (card.status === 'setup') {
      const active = Number(card.active_weeks) || 0;
      return active >= 2 ? `You logged something in ${active} of the last 8 weeks` : 'Make it a weekly thing';
    }
    if (card.status === 'kept') return 'Week kept';
    if (card.status === 'rest') return 'Taking this week off';
    if (goal.kind === 'finish') return 'Nothing finished yet this week';
    const logged = Number(card.logged_days) || 0;
    return logged ? `${logged} of ${goal.target} days so far` : 'Nothing logged yet this week';
  }

  function summary(card) {
    const goal = card.goal;
    const runBefore = Number(card.run_before) || 0;
    const run = Number(card.run) || 0;
    if (card.status === 'setup') {
      return 'Pick a pace and this card keeps count, Monday to Sunday. It only counts what you already do here, and nothing is lost if you skip a week.';
    }
    if (card.status === 'kept') {
      return run >= 2 ? `That’s ${run} weeks in a row. Anything else you log this week is a bonus.`
        : 'That’s your first one. Anything else you log this week is a bonus.';
    }
    if (card.status === 'rest') {
      return runBefore >= 1 ? `Your run of ${plural(runBefore, 'week', 'weeks')} waits for you. It picks up again on Monday.`
        : 'Nothing to keep this week. It starts again on Monday.';
    }
    const makes = runBefore >= 1 ? ` Keep it and that’s ${runBefore + 1} in a row.` : '';
    const needed = Number(card.needed) || 0;
    const open = daysOpen(card);
    if (goal.kind === 'finish') {
      if (isSunday(card)) return `Last day of the week. Finish one thing today and it’s kept.${makes}`;
      return `Finish one thing by Sunday and the week is kept: a movie, a season, a book, an album.${makes}`;
    }
    if (needed > open) {
      return card.can_rest
        ? 'This week is out of reach now. Log what you like, or take it as a week off and keep your run.'
        : 'This week is out of reach now. Log what you like; next week starts fresh on Monday.';
    }
    if (isSunday(card)) return `Last day of the week. Log one thing today and it’s kept.${makes}`;
    if (needed === 1) {
      return goal.target === 1
        ? `Log anything by Sunday night and the week is kept: an episode, a chapter, a rating, a new title.${makes}`
        : `One more day keeps your week.${makes}`;
    }
    return `${needed} days with something logged keep your week, and ${open} are still open.${makes}`;
  }

  // ------------------------------------------------ pieces

  function renderDays(card) {
    const list = $('yourWeekDays');
    if (!list) return;
    list.replaceChildren();
    (card.days || []).forEach((day, index) => {
      const item = el('li', 'your-week__day');
      if (day.logged) item.classList.add('is-logged');
      if (day.today) item.classList.add('is-today');
      if (day.future) item.classList.add('is-future');
      item.append(el('span', 'your-week__day-name', day.today ? 'Today' : DAY_NAMES[index]));
      const mark = el('span', 'your-week__day-mark', day.logged ? '✓' : String(parseDay(day.date)?.getDate() || ''));
      mark.setAttribute('aria-hidden', 'true');
      item.append(mark);
      const words = day.logged ? 'logged' : day.future ? 'still to come' : day.today ? 'nothing yet' : 'nothing logged';
      item.append(el('span', 'sr-only', `${DAY_LONG[index]} ${shortDate(day.date)}: ${words}`));
      list.append(item);
    });
  }

  function renderRun(card) {
    const number = $('yourWeekRunNumber');
    const label = $('yourWeekRunLabel');
    const list = $('yourWeekHistory');
    if (!number || !label || !list) return;
    const run = Number(card.run) || 0;
    const shown = card.status === 'kept' ? run : Number(card.run_before) || 0;
    if (card.goal && shown > 0) {
      number.hidden = false;
      number.textContent = String(shown);
      const best = Number(card.best) || 0;
      label.textContent = `${weeksWord(shown)} in a row${best > shown ? ` · best ${best}` : ''}`;
    } else if (card.goal && Number(card.best) > 0) {
      number.hidden = true;
      label.textContent = `Best run: ${plural(Number(card.best), 'week', 'weeks')}`;
    } else {
      number.hidden = true;
      label.textContent = 'The last 8 weeks';
    }
    list.replaceChildren();
    (card.history || []).forEach(week => {
      const item = el('li', `your-week__week is-${week.state}`);
      item.title = `Week of ${shortDate(week.week_start)}: ${HISTORY_WORDS[week.state] || ''}`;
      item.append(el('span', 'sr-only', item.title));
      list.append(item);
    });
  }

  function cover(item) {
    const box = el('span', 'your-week__cover');
    box.setAttribute('aria-hidden', 'true');
    const image = typeof item.image === 'string' && /^https?:\/\//.test(item.image) ? item.image : '';
    const letter = (String(item.title || '').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase();
    if (image) {
      const img = document.createElement('img');
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => { img.remove(); box.textContent = letter; }, { once: true });
      box.append(img);
    } else {
      box.textContent = letter;
    }
    return box;
  }

  function renderCovers(list, items) {
    list.replaceChildren();
    (items || []).forEach(item => {
      const row = el('li', 'your-week__cover-item');
      row.dataset.format = item.category || '';
      row.append(cover(item), el('span', 'your-week__cover-title', item.title));
      list.append(row);
    });
  }

  function renderTouched(card) {
    const box = $('yourWeekTouched');
    const list = $('yourWeekTouchedList');
    if (!box || !list) return;
    const items = Array.isArray(card.touched) ? card.touched : [];
    box.hidden = !items.length || card.status === 'setup';
    if (!box.hidden) renderCovers(list, items);
  }

  function renderPaces(card) {
    const box = $('yourWeekPaces');
    const list = $('yourWeekPaceList');
    if (!box || !list) return;
    const open = card.status === 'setup' || state.showPaces;
    box.hidden = !open;
    setText('yourWeekPacesTitle', card.goal ? 'Change your pace' : 'Pick a pace');
    list.replaceChildren();
    (card.goals || []).forEach(goal => {
      const button = el('button', 'your-week__pace');
      button.type = 'button';
      button.dataset.goal = goal.key;
      const current = card.goal && card.goal.key === goal.key;
      button.setAttribute('aria-pressed', current ? 'true' : 'false');
      button.append(el('span', 'your-week__pace-label', goal.label), el('span', 'your-week__pace-hint', goal.hint));
      list.append(button);
    });
    const change = $('yourWeekChange');
    if (change) {
      change.hidden = !card.goal;
      change.setAttribute('aria-expanded', state.showPaces ? 'true' : 'false');
      change.textContent = state.showPaces ? 'Keep my pace' : 'Change pace';
    }
    const stop = $('yourWeekStop');
    if (stop) stop.hidden = !(card.goal && state.showPaces);
  }

  function pushSupported() {
    return Boolean(window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window
      && 'Notification' in window && window.omniPush);
  }

  function renderNudge(card) {
    const box = $('yourWeekNudge');
    const text = $('yourWeekNudgeText');
    const email = $('yourWeekEmail');
    const push = $('yourWeekPush');
    const off = $('yourWeekNudgeOff');
    if (!box || !text || !email || !push || !off) return;
    const remind = card.remind || {};
    box.hidden = !card.goal;
    if (!card.goal) return;
    const on = [remind.email ? 'by email' : '', remind.push ? 'on your device' : ''].filter(Boolean);
    email.hidden = Boolean(remind.email) || !remind.offer_email;
    push.hidden = Boolean(remind.push) || !pushSupported();
    off.hidden = !on.length;
    [email, push, off].forEach(button => { button.disabled = false; });
    if (on.length) {
      text.textContent = `Sunday nudge is on, ${on.join(' and ')}. It only comes at 6 pm on Sunday when one more day would keep your week.`;
    } else {
      text.textContent = 'Want a nudge? If your week isn’t kept by 6 pm on Sunday and one more day would do it, we’ll send one. Nothing comes on weeks you’ve already kept.';
    }
    if (email.hidden && push.hidden && off.hidden) box.hidden = true;
  }

  function renderRecap(card) {
    const box = $('yourWeekRecap');
    if (!box) return;
    const recap = card.recap;
    box.hidden = !recap;
    if (!recap) return;
    setText('yourWeekRecapEyebrow', `Last week · ${recap.label}`);
    let title;
    if (recap.kept) title = recap.run >= 2 ? `Kept. That’s ${recap.run} weeks in a row.` : 'Kept. That’s your first one.';
    else if (recap.rest) title = 'A week off. Your run is still there.';
    else title = 'Not kept, and that’s fine. This week is a new one.';
    setText('yourWeekRecapTitle', title);
    const bits = [plural(Number(recap.days) || 0, 'day', 'days') + ' with something logged'];
    if (recap.finishes) bits.push(`${recap.finishes} finished`);
    setText('yourWeekRecapSummary', bits.join(' · '));
    const covers = $('yourWeekRecapCovers');
    if (covers) {
      const items = Array.isArray(recap.finished) ? recap.finished : [];
      covers.hidden = !items.length;
      renderCovers(covers, items);
      if (recap.more) covers.append(el('li', 'your-week__cover-more', `+${recap.more} more`));
    }
  }

  // ------------------------------------------------ the card

  function render(card) {
    const section = $('yourWeek');
    if (!section) return;
    state.card = card || null;
    if (!card) {
      section.hidden = true;
      return;
    }
    section.dataset.status = card.status;
    setText('yourWeekEyebrow', `Your week · ${card.label}`);
    setText('yourWeekTitle', headline(card));
    setText('yourWeekSummary', summary(card));
    renderRecap(card);
    renderDays(card);
    renderRun(card);
    renderTouched(card);
    renderPaces(card);
    renderNudge(card);
    const rest = $('yourWeekRest');
    if (rest) rest.hidden = !card.can_rest || state.showPaces;
    const unrest = $('yourWeekUnrest');
    if (unrest) unrest.hidden = card.status !== 'rest';
    // "Hide this card" stays pressed (disabled) once it has hidden the card; a card brought
    // back from /#your-week or the Steady badge without a reload needs it working again.
    const hide = $('yourWeekHide');
    if (hide) hide.disabled = false;
    const wasHidden = section.hidden;
    section.hidden = false;
    if (wasHidden && window.location.hash === '#your-week') {
      window.requestAnimationFrame(() => section.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    }
    watchSeen(section, card);
  }

  // Counted as seen once a day, when most of the card is on screen.
  function watchSeen(section, card) {
    if (state.observer) state.observer.disconnect();
    const today = card.today;
    if (state.seenDay === today) return;
    const report = () => {
      if (state.seenDay === today) return;
      state.seenDay = today;
      send('POST', '/api/your-week/seen', { tz: tz() }).catch(() => { state.seenDay = ''; });
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

  // A button press: post, then draw the card the server sends back.
  async function act(button, path, body, done) {
    if (state.busy) return;
    state.busy = true;
    if (button) button.disabled = true;
    setStatus('');
    const epoch = state.epoch;
    try {
      const data = await send('POST', path, { tz: tz(), ...body });
      if (epoch !== state.epoch) return;
      if (typeof done === 'function') done(data);
      if (Object.prototype.hasOwnProperty.call(data, 'card')) render(data.card);
    } catch (error) {
      setStatus(error.message);
    } finally {
      state.busy = false;
      if (button && button.isConnected) button.disabled = false;
    }
  }

  function pickGoal(key, button) {
    const first = !(state.card && state.card.goal);
    act(button, '/api/your-week/goal', { goal: key }, data => {
      state.showPaces = false;
      const goal = data.card && data.card.goal;
      if (!goal) return;
      setStatus(first ? `Done. Counting from this Monday: ${goal.label.toLowerCase()}.` : `Pace changed: ${goal.label.toLowerCase()}.`);
    });
  }

  async function turnOnPush(button) {
    button.disabled = true;
    let result = 'off';
    try {
      result = window.omniPush.state() === 'on' ? 'on' : await window.omniPush.turnOn('your_week');
    } catch (error) {
      result = 'off';
    }
    if (result !== 'on') {
      button.disabled = false;
      setStatus(result === 'blocked' ? 'Notifications are blocked for OmniTrackr in this browser’s settings.' : 'Notifications didn’t turn on. Please try again.');
      return;
    }
    await act(button, '/api/your-week/remind', { push: true }, () => setStatus('Done. On Sundays this device gets the nudge, only when it’s needed.'));
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    // Opened from a link to the card (/#your-week, the Steady badge): ask once to bring a hidden card back.
    const show = window.location.hash === '#your-week' && !state.shown;
    if (show) state.shown = true;
    const request = (show
      ? send('POST', '/api/your-week/show', { tz: tz() })
      : fetch(`${apiBase()}/api/your-week?tz=${encodeURIComponent(tz())}`, fetchOptions({ headers: { Accept: 'application/json' } }))
        .then(response => (response.ok ? response.json() : null)))
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
    state.busy = false;
    state.showPaces = false;
    state.shown = false;
    if (state.observer) state.observer.disconnect();
    const section = $('yourWeek');
    if (section) section.hidden = true;
    ['yourWeekDays', 'yourWeekHistory', 'yourWeekTouchedList', 'yourWeekPaceList', 'yourWeekRecapCovers'].forEach(id => $(id)?.replaceChildren());
    setStatus('');
  }

  function wire() {
    $('yourWeekPaceList')?.addEventListener('click', event => {
      const button = event.target.closest('[data-goal]');
      if (button) pickGoal(button.dataset.goal, button);
    });
    $('yourWeekChange')?.addEventListener('click', () => {
      state.showPaces = !state.showPaces;
      if (state.card) render(state.card);
    });
    $('yourWeekStop')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/goal', { goal: null }, () => {
      state.showPaces = false;
      setStatus('Stopped. The weeks you kept stay on your badge.');
    }));
    $('yourWeekRest')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/rest', {}, () => setStatus('This week is off. Your run carries on next Monday.')));
    $('yourWeekUnrest')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/rest', { undo: true }));
    $('yourWeekRecapDone')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/recap', {}));
    $('yourWeekEmail')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/remind', { email: true }, () => setStatus('Done. The Sunday email only comes when one more day would keep your week.')));
    $('yourWeekPush')?.addEventListener('click', event => turnOnPush(event.currentTarget));
    $('yourWeekNudgeOff')?.addEventListener('click', event => act(event.currentTarget, '/api/your-week/remind', { email: false, push: false }, () => setStatus('The Sunday nudge is off.')));
    $('yourWeekHide')?.addEventListener('click', event => {
      const button = event.currentTarget;
      button.disabled = true;
      send('POST', '/api/your-week/hide').then(() => {
        const section = $('yourWeek');
        if (section) section.hidden = true;
        state.card = null;
        if (typeof showNotice === 'function') showNotice('Your week is hidden. Open it again any time from the Steady badge or omnitrackr.xyz/#your-week.', 'info');
      }).catch(error => { button.disabled = false; setStatus(error.message); });
    });
    window.addEventListener('hashchange', () => {
      if (window.location.hash !== '#your-week') return;
      state.shown = false;
      refresh(true);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  document.addEventListener('visibilitychange', () => {
    // A tab left open overnight shows the new day when it comes back.
    if (document.visibilityState !== 'visible' || !state.card) return;
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    if (state.card.today !== today) refresh(true);
  });

  window.OmniYourWeek = { refresh, reset, render };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { refresh, reset, render, headline, summary, daysOpen, state };
  }
})();
