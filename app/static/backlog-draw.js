// "Draw from your backlog": a home-screen card that deals three titles the member saved and never
// started, lets them keep one, pick a night for it (calendar event, one evening email), and asks
// how it went afterwards. The server decides what's dealt and who sees it (app/backlog_draw.py).
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 60 * 1000;
  const HIDE_DAYS = 14;
  const HIDE_KEY = 'omnitrackr_backlog_draw_hidden';
  const SEEN_KEY = 'omnitrackr_backlog_draw_seen';
  const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const state = {
    epoch: 0, card: null, request: null, loadedAt: 0, seenDay: '', observer: null,
    hand: null, deal: 0, scoring: false, finished: null, busy: false,
  };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  const localPath = url => typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/\\');

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

  function button(className, text, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    node.addEventListener('click', event => onClick(event.currentTarget));
    return node;
  }

  function pad(n) { return String(n).padStart(2, '0'); }
  function isoDay(when) { return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`; }
  function localToday(now = new Date()) { return isoDay(now); }
  function addDays(iso, days) {
    const [year, month, day] = String(iso).split('-').map(Number);
    return isoDay(new Date(year, month - 1, day + days));
  }
  function weekday(iso) {
    const [year, month, day] = String(iso).split('-').map(Number);
    return DAY_NAMES[new Date(year, month - 1, day).getDay()];
  }
  // Minutes east of UTC, the way the server wants them.
  function tzMinutes() { return -new Date().getTimezoneOffset(); }

  // "Tonight", "Tomorrow" or the day's name, from the member's own today.
  function nightWords(night, today) {
    if (!night) return '';
    if (night === today) return 'Tonight';
    if (night === addDays(today, 1)) return 'Tomorrow';
    return weekday(night);
  }

  function hourWords(hour) {
    const h = Number(hour) || 18;
    return `${h % 12 || 12} ${h < 12 ? 'am' : 'pm'}`;
  }

  function setStatus(text) {
    const status = $('backlogDrawStatus');
    if (status) status.textContent = text || '';
  }

  // ------------------------------------------------ hiding (this browser, a couple of weeks)

  function accountKey() {
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      return String((user && (user.id || user.username)) || 'me');
    } catch (error) {
      return 'me';
    }
  }

  function hiddenUntil() {
    try {
      const saved = JSON.parse(localStorage.getItem(HIDE_KEY) || '{}');
      return Number(saved && saved[accountKey()]) || 0;
    } catch (error) {
      return 0;
    }
  }

  function hideHere() {
    try {
      const saved = JSON.parse(localStorage.getItem(HIDE_KEY) || '{}') || {};
      saved[accountKey()] = Date.now() + HIDE_DAYS * 24 * 60 * 60 * 1000;
      localStorage.setItem(HIDE_KEY, JSON.stringify(saved));
    } catch (error) { /* hidden for this page view only */ }
  }

  // ------------------------------------------------ pieces

  function cover(card, className = 'backlog-draw__cover') {
    const wrap = el('span', className);
    const initial = (card.title || '?').slice(0, 1).toUpperCase();
    if (typeof card.image === 'string' && /^https:\/\//.test(card.image)) {
      const img = el('img');
      img.src = card.image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => { img.remove(); wrap.textContent = initial; }, { once: true });
      wrap.append(img);
    } else {
      wrap.textContent = initial;
      wrap.classList.add('is-blank');
    }
    return wrap;
  }

  function meta(card) {
    return [card.label, card.year, card.length].filter(Boolean).join(' · ');
  }

  function titleNode(card, className) {
    if (localPath(card.url)) {
      const link = el('a', className, card.title);
      link.href = card.url;
      return link;
    }
    return el('span', className, card.title);
  }

  function header(eyebrow, title, summary) {
    $('backlogDrawEyebrow').textContent = eyebrow;
    $('backlogDrawTitle').textContent = title;
    $('backlogDrawSummary').textContent = summary || '';
  }

  function showHide(show) {
    const hide = $('backlogDrawHide');
    if (hide) hide.hidden = !show;
  }

  // ------------------------------------------------ deal

  function renderDeal(card) {
    const body = $('backlogDrawBody');
    const total = Number(card.total) || 0;
    header('From your backlog', 'Draw your next one',
      `${total} title${total === 1 ? '' : 's'} you saved ${total === 1 ? 'is' : 'are'} still waiting. Deal three, keep one, and give it a night.`);
    showHide(true);
    const table = el('div', 'backlog-draw__table');
    for (let i = 0; i < 3; i += 1) {
      const back = el('div', 'backlog-draw__card is-down');
      back.setAttribute('aria-hidden', 'true');
      back.append(el('span', 'backlog-draw__back'));
      table.append(back);
    }
    const actions = el('div', 'backlog-draw__actions');
    actions.append(button('backlog-draw__btn backlog-draw__btn--primary', 'Deal three', node => dealCards(node, 0)));
    body.replaceChildren(table, actions);
  }

  function renderHand(cards) {
    const body = $('backlogDrawBody');
    header('From your backlog', 'Keep one',
      'Three from your list. Keep the one you’re in the mood for, or deal again.');
    showHide(true);
    const table = el('ol', 'backlog-draw__table backlog-draw__table--up');
    table.setAttribute('aria-label', 'Three titles from your list');
    cards.forEach((card, index) => {
      const item = el('li', 'backlog-draw__card is-down');
      item.style.setProperty('--deal-delay', `${index * 110}ms`);
      const face = el('div', 'backlog-draw__face');
      if (card.tag) face.append(el('span', 'backlog-draw__tag', card.tag));
      face.append(cover(card));
      const text = el('div', 'backlog-draw__text');
      text.append(titleNode(card, 'backlog-draw__name'), el('span', 'backlog-draw__meta', meta(card)));
      const waited = el('span', 'backlog-draw__waited', card.waited);
      text.append(waited);
      if (card.queued) text.append(el('span', 'backlog-draw__waited', 'On your Next Up'));
      face.append(text);
      const keep = button('backlog-draw__btn backlog-draw__keep', 'Keep this one', node => keepCard(node, card));
      keep.setAttribute('aria-label', `Keep ${card.title}`);
      face.append(keep);
      item.append(face);
      table.append(item);
    });
    const actions = el('div', 'backlog-draw__actions');
    actions.append(button('backlog-draw__quiet', 'Deal again', node => dealCards(node, state.deal + 1)));
    body.replaceChildren(table, actions);
    // Face down first, then flip them over one after another.
    window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
      table.querySelectorAll('.backlog-draw__card').forEach(node => node.classList.remove('is-down'));
    }));
  }

  async function dealCards(node, number) {
    if (state.busy) return;
    state.busy = true;
    node.disabled = true;
    setStatus('');
    try {
      const data = await send('POST', '/api/backlog-draw/deal', { today: localToday(), deal: number });
      state.deal = Number(data.deal) || 0;
      state.hand = Array.isArray(data.cards) ? data.cards : [];
      if (state.hand.length) renderHand(state.hand);
    } catch (error) {
      node.disabled = false;
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  async function keepCard(node, card) {
    if (state.busy) return;
    state.busy = true;
    node.disabled = true;
    try {
      const data = await send('POST', '/api/backlog-draw/pick', {
        today: localToday(), deal: state.deal, category: card.category, item_id: card.id,
      });
      state.hand = null;
      render(data.card);
    } catch (error) {
      node.disabled = false;
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  // ------------------------------------------------ the kept card

  function pickBlock(card, done = false) {
    const box = el('div', 'backlog-draw__kept');
    box.append(cover(card.pick, 'backlog-draw__cover backlog-draw__cover--kept'));
    const text = el('div', 'backlog-draw__text');
    text.append(titleNode(card.pick, 'backlog-draw__name'), el('span', 'backlog-draw__meta', meta(card.pick)));
    if (done) {
      box.append(text);
      return box;
    }
    if (card.pick.waited) text.append(el('span', 'backlog-draw__waited', card.pick.waited));
    if (localPath(card.pick.url)) {
      const where = el('a', 'backlog-draw__link', `Where to ${card.pick.verb || 'find'} it`);
      where.href = `${card.pick.url}#where-title`;
      text.append(where);
    }
    box.append(text);
    return box;
  }

  function nightChoices(today) {
    const days = [0, 1];
    for (let offset = 2; offset < 7; offset += 1) {
      const name = weekday(addDays(today, offset));
      if (name === 'Friday' || name === 'Saturday' || name === 'Sunday') days.push(offset);
    }
    for (let offset = 2; days.length < 4 && offset < 7; offset += 1) if (!days.includes(offset)) days.push(offset);
    return days.sort((a, b) => a - b).map(offset => addDays(today, offset));
  }

  function lateTonight(card) {
    return new Date().getHours() >= (Number(card.remind_hour) || 18);
  }

  async function plan(node, body) {
    if (state.busy) return;
    state.busy = true;
    if (node) node.disabled = true;
    setStatus('');
    try {
      const data = await send('POST', '/api/backlog-draw/plan', { today: localToday(), tz: tzMinutes(), ...body });
      render(data.card);
    } catch (error) {
      if (node) node.disabled = false;
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  function renderPlanned(card) {
    const today = localToday();
    const pick = card.pick;
    const when = nightWords(card.night, today);
    header('Your night in', when ? `${when}: ${pick.title}` : `You kept ${pick.title}`,
      when ? 'It’s a plan. Come back after and tick it off.' : 'When are you having it? Pick a night and it’s a plan.');
    showHide(false);
    const body = $('backlogDrawBody');
    const layout = el('div', 'backlog-draw__plan');
    layout.append(pickBlock(card));

    const side = el('div', 'backlog-draw__side');
    const chipsLabel = el('p', 'backlog-draw__label', card.night ? 'Night' : 'When’s it happening?');
    chipsLabel.id = 'backlogDrawNightLabel';
    const chips = el('div', 'backlog-draw__chips');
    chips.setAttribute('role', 'group');
    chips.setAttribute('aria-labelledby', 'backlogDrawNightLabel');
    nightChoices(today).forEach(night => {
      const chip = button('backlog-draw__chip', nightWords(night, today), node => {
        if (card.night === night) return;
        plan(node, { night, email: Boolean(card.reminder && card.reminder.status === 'set' && !(night === today && lateTonight(card))) });
      });
      chip.setAttribute('aria-pressed', String(card.night === night));
      chips.append(chip);
    });
    side.append(chipsLabel, chips);

    if (card.night) {
      const remind = el('div', 'backlog-draw__remind');
      const calendar = el('a', 'backlog-draw__btn', card.calendar ? 'Added to calendar · again' : 'Add to my calendar');
      calendar.href = `${apiBase()}/api/backlog-draw/calendar.ics`;
      calendar.setAttribute('download', 'omnitrackr-night-in.ics');
      calendar.addEventListener('click', () => {
        window.setTimeout(() => { state.loadedAt = 0; refresh(true); }, 1500);
      });
      remind.append(calendar);
      const reminder = card.reminder;
      if (reminder && reminder.status === 'set') {
        remind.append(el('span', 'backlog-draw__note', `We’ll email you at ${hourWords(card.remind_hour)} ${when === 'Tonight' ? 'today' : `on ${when === 'Tomorrow' ? 'tomorrow' : when}`}.`));
        remind.append(button('backlog-draw__quiet', 'Cancel the email', node => plan(node, { night: card.night, email: false })));
      } else if (reminder && reminder.status === 'sent') {
        remind.append(el('span', 'backlog-draw__note', 'Your email went out.'));
      } else if (card.email_offer && !(card.night === today && lateTonight(card))) {
        remind.append(button('backlog-draw__btn', `Email me at ${hourWords(card.remind_hour)} that day`,
          node => plan(node, { night: card.night, email: true })));
      }
      side.append(remind);
    }
    layout.append(side);

    const foot = el('div', 'backlog-draw__actions backlog-draw__actions--split');
    foot.append(button('backlog-draw__quiet', `${pick.finish_words || 'Finished it'} already`, () => { state.scoring = true; renderAfter(card, true); }));
    foot.append(button('backlog-draw__quiet', 'Put it back and deal again', node => answer(node, { action: 'put_back' })));
    body.replaceChildren(layout, foot);
  }

  // ------------------------------------------------ how it went

  function scoreRow(onScore, onSkip) {
    const wrap = el('div', 'backlog-draw__score');
    const label = el('p', 'backlog-draw__label', 'Give it a score');
    label.id = 'backlogDrawScoreLabel';
    const row = el('div', 'backlog-draw__chips backlog-draw__chips--score');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-labelledby', 'backlogDrawScoreLabel');
    for (let score = 1; score <= 10; score += 1) {
      const chip = button('backlog-draw__chip backlog-draw__chip--score', String(score), node => onScore(node, score));
      chip.setAttribute('aria-label', `${score} out of 10`);
      row.append(chip);
    }
    wrap.append(label, row);
    if (onSkip) wrap.append(button('backlog-draw__quiet', 'No score', node => onSkip(node)));
    return wrap;
  }

  async function answer(node, body) {
    if (state.busy) return null;
    state.busy = true;
    if (node) node.disabled = true;
    setStatus('');
    try {
      const data = await send('POST', '/api/backlog-draw/answer', { today: localToday(), ...body });
      return data;
    } catch (error) {
      if (node) node.disabled = false;
      setStatus(error.message);
      return null;
    } finally {
      state.busy = false;
    }
  }

  async function finish(node, card, rating) {
    const data = await answer(node, rating ? { action: 'finished', rating } : { action: 'finished' });
    if (!data) return;
    state.scoring = false;
    state.finished = { pick: card.pick, rating: data.title ? data.title.rating : rating || null, next: data.card };
    renderFinished(state.finished);
  }

  function renderAfter(card, early = false) {
    const pick = card.pick;
    const today = localToday();
    const was = card.night && card.night !== today ? `${weekday(card.night)} was ${pick.title} night.` : '';
    header('Your night in', early ? `${pick.title}: done?` : `How was ${pick.title}?`,
      early ? 'Tick it off and give it a score while it’s fresh.' : `${was} Tick it off, or give it another night.`.trim());
    showHide(false);
    const body = $('backlogDrawBody');
    const layout = el('div', 'backlog-draw__plan');
    layout.append(pickBlock(card));
    const side = el('div', 'backlog-draw__side');
    if (state.scoring) {
      side.append(scoreRow((node, score) => finish(node, card, score), node => finish(node, card, null)));
    } else {
      const choices = el('div', 'backlog-draw__answers');
      choices.append(button('backlog-draw__btn backlog-draw__btn--primary', pick.finish_words || 'Finished it', () => {
        state.scoring = true;
        renderAfter(card, early);
      }));
      choices.append(button('backlog-draw__btn', 'Didn’t get to it', async node => {
        const data = await answer(node, { action: 'later' });
        if (data) render(data.card);
      }));
      choices.append(button('backlog-draw__btn', 'Not for me', async node => {
        const data = await answer(node, { action: 'not_for_me' });
        if (data) {
          setStatus(`${pick.title} stays in your library, but it won’t be dealt again.`);
          render(data.card);
        }
      }));
      side.append(choices);
    }
    layout.append(side);
    const foot = el('div', 'backlog-draw__actions');
    if (early || state.scoring) {
      foot.append(button('backlog-draw__quiet', 'Back', () => { state.scoring = false; render(state.card); }));
    }
    body.replaceChildren(layout, foot);
  }

  function renderFinished(done) {
    const pick = done.pick;
    header('Your night in', `${pick.title}: done`,
      done.rating ? `${done.rating}/10, and one more off your list.` : 'One more off your list.');
    showHide(false);
    const body = $('backlogDrawBody');
    const layout = el('div', 'backlog-draw__plan backlog-draw__plan--done');
    layout.append(pickBlock({ pick }, true));
    const side = el('div', 'backlog-draw__side');
    if (!done.rating && done.drawId) {
      side.append(scoreRow(async (node, score) => {
        const data = await answer(node, { action: 'rate', rating: score, draw_id: done.drawId });
        if (!data) return;
        done.rating = score;
        done.next = data.card;
        renderFinished(done);
      }));
    }
    const next = done.next;
    const actions = el('div', 'backlog-draw__answers');
    if (next && next.state === 'deal') {
      actions.append(button('backlog-draw__btn backlog-draw__btn--primary', 'Draw the next one', () => {
        state.finished = null;
        render(next);
      }));
    } else {
      actions.append(button('backlog-draw__btn', 'Close', () => {
        state.finished = null;
        render(next || null);
      }));
    }
    side.append(actions);
    layout.append(side);
    body.replaceChildren(layout);
  }

  // ------------------------------------------------ the card

  function setTodaysPickHidden(hidden) {
    const pick = $('todaysPick');
    if (pick && hidden) pick.setAttribute('hidden', '');
  }

  function render(card) {
    const section = $('backlogDraw');
    if (!section) return;
    state.card = card || null;
    if (!card || (['deal'].includes(card.state) && hiddenUntil() > Date.now())) {
      const wasShown = !section.hidden;
      section.hidden = true;
      if (wasShown && typeof refreshTodaysPick === 'function') refreshTodaysPick();
      return;
    }
    if (card.state === 'finished') {
      state.finished = { pick: card.pick, rating: card.rating, drawId: card.draw_id, next: Number(card.total) >= 3 ? { state: 'deal', total: card.total } : null };
      renderFinished(state.finished);
    } else if (card.state === 'after') {
      renderAfter(card);
    } else if (card.state === 'planned') {
      if (state.scoring) renderAfter(card, true);
      else renderPlanned(card);
    } else if (state.hand && state.hand.length) {
      renderHand(state.hand);
    } else {
      renderDeal(card);
    }
    const wasHidden = section.hidden;
    section.hidden = false;
    setTodaysPickHidden(true);
    if (wasHidden && window.location.hash === '#backlog-draw') {
      window.requestAnimationFrame(() => section.scrollIntoView({ block: 'start', behavior: 'smooth' }));
    }
    watchSeen(section);
  }

  // One "seen" a day per browser, however often home reloads.
  function seenStored() {
    try {
      const saved = JSON.parse(localStorage.getItem(SEEN_KEY) || '{}');
      return (saved && saved[accountKey()]) || '';
    } catch (error) {
      return '';
    }
  }

  function storeSeen(day) {
    try {
      const saved = JSON.parse(localStorage.getItem(SEEN_KEY) || '{}') || {};
      saved[accountKey()] = day;
      localStorage.setItem(SEEN_KEY, JSON.stringify(saved));
    } catch (error) { /* counted again next load at worst */ }
  }

  // Counted once a day when half the card is on screen. The first look after their night counts as coming back.
  function watchSeen(section) {
    if (state.observer) state.observer.disconnect();
    const today = localToday();
    if (state.seenDay === today || seenStored() === today) return;
    const report = () => {
      if (state.seenDay === today) return;
      state.seenDay = today;
      storeSeen(today);
      send('POST', '/api/backlog-draw/seen', { today }).catch(() => { state.seenDay = ''; storeSeen(''); });
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
    if (!signedIn()) return Promise.resolve();
    // Mid-deal or mid-score, a background refresh would throw the member's cards away.
    if (!force && (state.hand || state.scoring || state.finished)) return state.request || Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    // Hidden here: only a kept card can show, so the server skips counting the backlog.
    const hidden = hiddenUntil() > Date.now() ? '&hidden=1' : '';
    const request = fetch(`${apiBase()}/api/backlog-draw?today=${encodeURIComponent(localToday())}${hidden}`,
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
    state.hand = null;
    state.deal = 0;
    state.scoring = false;
    state.finished = null;
    state.busy = false;
    if (state.observer) state.observer.disconnect();
    const section = $('backlogDraw');
    if (section) section.hidden = true;
    $('backlogDrawBody')?.replaceChildren();
    setStatus('');
  }

  function active() {
    const section = $('backlogDraw');
    return Boolean(section && !section.hidden);
  }

  function wire() {
    $('backlogDrawHide')?.addEventListener('click', event => {
      const node = event.currentTarget;
      node.disabled = true;
      hideHere();
      send('POST', '/api/backlog-draw/hide').catch(() => {});
      state.hand = null;
      render(state.card);
      node.disabled = false;
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  document.addEventListener('visibilitychange', () => {
    // A tab left open past the night asks how it went when it comes back.
    if (document.visibilityState === 'visible' && state.card && state.card.today !== localToday()) refresh(true);
  });

  window.OmniBacklogDraw = { refresh, reset, render, active };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { refresh, reset, render, active, localToday, addDays, weekday, nightWords, nightChoices, hourWords, state };
  }
})();
