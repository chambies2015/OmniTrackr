// Start page (/start): a poster wall of popular titles, search, and the hand-off to the first-week steps.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const PAGE = 18;
  const ART_AT_ONCE = 4;
  const SAVED_BEFORE_SIGNUP = ['omnitrackr_guest_list', 'omnitrackr_taste_quiz', 'omnitrackr_taste_compare'];
  const BADGES = { seen: '✓ Seen', want: '＋ Want to', have: 'In your library' };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  async function request(path, options = {}) {
    const init = { credentials: 'same-origin', cache: 'no-store', ...options };
    if (init.body && !init.headers) init.headers = { 'Content-Type': 'application/json' };
    const response = await fetch(path, init);
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    return { ok: response.ok, status: response.status, data };
  }

  function post(path, body, extra = {}) {
    return request(path, { method: 'POST', body: JSON.stringify(body), ...extra });
  }

  function recordStep(step) {
    // keepalive lets the request finish while the browser moves on to the next page.
    return post('/api/start/step', { step }, { keepalive: true }).catch(() => null);
  }

  function setup(root) {
    const find = selector => root.querySelector(selector);
    const findAll = selector => Array.from(root.querySelectorAll(selector));
    let initial = {};
    try { initial = JSON.parse(document.getElementById('startState').textContent || '{}'); } catch (error) { initial = {}; }
    const state = {
      total: Number(initial.total || 0),
      goal: Number(initial.goal || 5),
      shelf: Array.isArray(initial.shelf) ? initial.shelf : [],
      firstWeek: initial.first_week || {},
      week: null, // the home screen's first-week card, for the "your week" step
      weekLoaded: false,
      screen: null,
      deck: [],
      shownCount: 0,
      deckRequest: 0,
      saved: new Map(), // card id -> {answer, category, item_id, title}
      busy: new Set(),
      art: new Map(),
      artQueue: [],
      artRunning: 0,
      searchRequest: 0,
    };

    // ---------------------------------------------------------------- progress
    function slotArt(item) {
      const slot = el('li', `st-slot is-filled st-slot--${item.kind}`);
      slot.title = item.title;
      if (item.image) {
        const img = el('img');
        img.src = item.image;
        img.alt = '';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('error', () => img.replaceWith(el('span', 'st-slot__initial', (item.title || '?').slice(0, 1).toUpperCase())));
        slot.appendChild(img);
      } else {
        slot.appendChild(el('span', 'st-slot__initial', (item.title || '?').slice(0, 1).toUpperCase()));
      }
      return slot;
    }

    function renderGoal() {
      const slots = find('[data-st-slots]');
      const filled = state.shelf.slice(0, state.goal).reverse();
      slots.replaceChildren(...filled.map(slotArt));
      for (let index = filled.length; index < state.goal; index += 1) {
        const empty = el('li', 'st-slot');
        empty.appendChild(el('span', 'st-slot__number', index + 1));
        slots.appendChild(empty);
      }
      const count = find('[data-st-count]');
      const met = state.total >= state.goal;
      if (met) {
        count.textContent = state.total === state.goal ? 'Five saved. That\'s the goal.' : `${state.total} saved. Past the goal.`;
      } else if (!state.total) {
        count.textContent = `0 of ${state.goal} saved`;
      } else {
        count.textContent = `${state.total} of ${state.goal} saved · ${state.goal - state.total} to go`;
      }
      root.classList.toggle('is-goal-met', met);
      find('.st-bar__done').hidden = !met || state.screen === 'done';
      find('.st-bar__skip').hidden = met;
    }

    function addToShelf(result) {
      state.shelf = [{
        kind: result.kind, category: result.category, item_id: result.item_id,
        title: result.title, image: result.image, seen: result.seen,
      }].concat(state.shelf.filter(item => !(item.category === result.category && item.item_id === result.item_id)));
    }

    function status(message) {
      find('[data-st-status]').textContent = message || '';
    }

    // ---------------------------------------------------------------- screens
    function show(name) {
      state.screen = name;
      root.classList.toggle('is-finished', name === 'done');
      findAll('[data-st-screen]').forEach(screen => { screen.hidden = screen.dataset.stScreen !== name; });
      if (name === 'pick' && !state.deck.length) loadDeck();
      if (name === 'done') {
        renderNext();
        loadWeek();
        const done = find('[data-st-screen="done"]');
        window.setTimeout(() => done.focus({ preventScroll: true }), 0);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      renderGoal();
    }

    // ---------------------------------------------------------------- the poster wall
    function chosenKinds() {
      return findAll('.st-formats input:checked').map(input => input.value);
    }

    async function loadDeck() {
      const kinds = chosenKinds();
      const grid = find('[data-st-grid]');
      const more = find('[data-st-more]');
      if (!kinds.length) {
        state.deck = [];
        state.shownCount = 0;
        grid.replaceChildren(el('li', 'st-grid__empty', 'Pick at least one format above.'));
        more.hidden = true;
        return;
      }
      const ticket = ++state.deckRequest;
      grid.setAttribute('aria-busy', 'true');
      if (!grid.children.length || grid.querySelector('.st-grid__empty')) {
        grid.replaceChildren(...Array.from({ length: 12 }, () => el('li', 'st-tile st-tile--ghost')));
      }
      const { ok, data } = await request(`/api/start/deck?kinds=${encodeURIComponent(kinds.join(','))}`).catch(() => ({ ok: false, data: {} }));
      if (ticket !== state.deckRequest) return;
      grid.removeAttribute('aria-busy');
      if (!ok) {
        grid.replaceChildren(el('li', 'st-grid__empty', 'Couldn\'t load titles just now. Try again in a moment, or search instead.'));
        more.hidden = true;
        return;
      }
      state.deck = data.cards || [];
      state.shownCount = 0;
      grid.replaceChildren();
      showMore();
    }

    function showMore() {
      const grid = find('[data-st-grid]');
      const next = state.deck.slice(state.shownCount, state.shownCount + PAGE);
      if (!next.length && !state.shownCount) {
        grid.replaceChildren(el('li', 'st-grid__empty', 'You already have every popular title in these formats. Tick another format, or search for something specific.'));
      }
      next.forEach(card => grid.appendChild(tile(card)));
      state.shownCount += next.length;
      const more = find('[data-st-more]');
      more.hidden = state.shownCount >= state.deck.length;
    }

    // Covers nobody has looked up yet load a few at a time, as their posters scroll into view.
    function fetchArt(card) {
      if (!state.art.has(card.id)) {
        state.art.set(card.id, new Promise(resolve => {
          state.artQueue.push({ card, resolve });
          pumpArt();
        }));
      }
      return state.art.get(card.id);
    }

    function pumpArt() {
      while (state.artRunning < ART_AT_ONCE && state.artQueue.length) {
        const { card, resolve } = state.artQueue.shift();
        state.artRunning += 1;
        request(`/api/start/art/${card.kind}/${encodeURIComponent(card.slug)}`)
          .then(({ ok, data }) => (ok && typeof data.image === 'string' && /^https?:\/\//.test(data.image) ? data.image : null))
          .catch(() => null)
          .then(image => { state.artRunning -= 1; resolve(image); pumpArt(); });
      }
    }

    const artWatcher = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        artWatcher.unobserve(entry.target);
        const load = entry.target.stLoadArt;
        if (load) load();
      });
    }, { rootMargin: '200px 0px' }) : null;

    function posterArt(card) {
      const frame = el('span', `st-art st-art--${card.kind}`);
      frame.appendChild(el('span', 'st-art__initial', (card.title || '?').slice(0, 1).toUpperCase()));
      const place = image => {
        if (!image) return;
        const img = el('img');
        img.alt = '';
        img.referrerPolicy = 'no-referrer';
        img.decoding = 'async';
        img.loading = 'lazy';
        img.addEventListener('load', () => frame.classList.add('has-image'));
        img.addEventListener('error', () => img.remove());
        img.src = image;
        frame.appendChild(img);
      };
      if (card.image) place(card.image);
      else if (!card.members) {
        const load = () => fetchArt(card).then(place);
        if (artWatcher) { frame.stLoadArt = load; artWatcher.observe(frame); } else load();
      }
      return frame;
    }

    function describe(card) {
      return [card.label, card.year].filter(Boolean).join(' · ');
    }

    function tile(card) {
      const item = el('li', 'st-tile');
      item.dataset.id = card.id;
      const poster = el('button', 'st-tile__poster');
      poster.type = 'button';
      poster.dataset.stTap = 'seen';
      poster.append(posterArt(card), el('span', 'st-tile__badge'));
      const text = el('span', 'st-tile__text');
      text.append(el('strong', '', card.title), el('span', '', describe(card)));
      const want = el('button', 'st-tile__want', '＋ Want to');
      want.type = 'button';
      want.dataset.stTap = 'want';
      item.append(poster, text, want);
      item.stCard = card;
      paint(item);
      return item;
    }

    function paint(item) {
      const card = item.stCard;
      const saved = state.saved.get(card.id);
      const answer = saved ? saved.answer : '';
      item.dataset.saved = answer;
      item.querySelector('.st-tile__badge').textContent = answer ? BADGES[answer] : '';
      const poster = item.querySelector('.st-tile__poster');
      const want = item.querySelector('.st-tile__want');
      const name = `${card.title}${card.year ? ` (${card.year})` : ''}`;
      poster.setAttribute('aria-pressed', answer === 'seen' ? 'true' : 'false');
      want.setAttribute('aria-pressed', answer === 'want' ? 'true' : 'false');
      if (answer === 'have') {
        poster.setAttribute('aria-label', `${name} is already in your library`);
        poster.disabled = true;
        want.hidden = true;
      } else {
        poster.disabled = false;
        poster.setAttribute('aria-label', answer ? `Take ${name} back out of your library` : `Seen ${name}: save it as finished`);
        want.hidden = answer === 'seen';
        want.textContent = answer === 'want' ? 'Saved ✓' : '＋ Want to';
        want.setAttribute('aria-label', answer === 'want' ? `Take ${name} back out of your list` : `Want to: save ${name} for later`);
      }
    }

    async function save(item, answer, via) {
      const { ok, data } = await post('/api/start/save', { id: item.id, answer, via })
        .catch(() => ({ ok: false, data: {} }));
      if (!ok) return { error: data.detail || `Couldn't save ${item.title}. Try again.` };
      state.total = Number(data.total || state.total);
      if (data.state === 'created') addToShelf(data);
      renderGoal();
      return data;
    }

    async function tap(item, answer) {
      const card = item.stCard;
      if (!card || state.busy.has(card.id)) return;
      state.busy.add(card.id);
      item.classList.add('is-busy');
      const saved = state.saved.get(card.id);
      try {
        if (saved && saved.answer !== 'have') {
          if (await undo(saved)) {
            state.saved.delete(card.id);
            status(`Took ${saved.title} back out.`);
          }
        } else if (!saved) {
          const result = await save(card, answer, 'quick');
          if (result.error) {
            status(result.error);
          } else if (result.state === 'created') {
            state.saved.set(card.id, { answer, category: result.category, item_id: result.item_id, title: result.title });
            status(`Saved ${result.title}${answer === 'want' ? ' to watch, play or read later' : ' as finished'}.`);
          } else {
            state.saved.set(card.id, { answer: 'have', title: result.title });
            status(`${result.title} was already in your library, so it stays as it was.`);
          }
        }
      } finally {
        state.busy.delete(card.id);
        item.classList.remove('is-busy');
        paint(item);
      }
    }

    async function undo(saved) {
      const { ok, data } = await post('/api/start/undo', { category: saved.category, item_id: saved.item_id })
        .catch(() => ({ ok: false, data: {} }));
      if (!ok) {
        status(data.detail || 'Couldn\'t undo that. You can remove it from your library.');
        return false;
      }
      state.total = Number(data.total || 0);
      state.shelf = state.shelf.filter(item => !(item.category === saved.category && item.item_id === saved.item_id));
      renderGoal();
      return true;
    }

    // ---------------------------------------------------------------- search
    function resultRow(result) {
      const item = el('li', 'st-result');
      const art = el('div', `st-result__art st-art--${result.kind}`);
      if (result.image) {
        const img = el('img');
        img.src = result.image;
        img.alt = '';
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('error', () => img.remove());
        art.appendChild(img);
      } else {
        art.appendChild(el('span', 'st-art__initial', (result.title || '?').slice(0, 1).toUpperCase()));
      }
      const text = el('div', 'st-result__text');
      text.append(el('strong', '', result.title), el('span', '', [result.label, result.year].filter(Boolean).join(' · ')));
      const actions = el('div', 'st-result__actions');
      [['want', 'Want to'], ['seen', 'Seen it']].forEach(([answer, label]) => {
        const button = el('button', `st-mini st-mini--${answer}`, label);
        button.type = 'button';
        button.addEventListener('click', async () => {
          actions.querySelectorAll('button').forEach(other => { other.disabled = true; });
          const saved = await save({ id: `${result.kind}/${result.slug}`, title: result.title }, answer, 'search');
          if (saved.error) {
            actions.querySelectorAll('button').forEach(other => { other.disabled = false; });
            item.querySelector('.st-result__error')?.remove();
            text.appendChild(el('p', 'st-result__error', saved.error));
            return;
          }
          actions.replaceChildren(el('span', 'st-result__saved', saved.state === 'created'
            ? (answer === 'seen' ? 'Saved as seen ✓' : 'Saved to want to ✓') : 'Already in your library'));
        });
        actions.appendChild(button);
      });
      item.append(art, text, actions);
      return item;
    }

    function searching(on) {
      find('[data-st-found]').hidden = !on;
      find('[data-st-browse]').hidden = on;
    }

    async function runSearch(text) {
      const list = find('[data-st-results]');
      const query = text.trim();
      const ticket = ++state.searchRequest;
      if (query.length < 2) {
        list.replaceChildren();
        searching(false);
        return;
      }
      searching(true);
      const { ok, data } = await request(`/api/titles/search?q=${encodeURIComponent(query)}`).catch(() => ({ ok: false, data: {} }));
      if (ticket !== state.searchRequest) return;
      const results = ok ? (data.results || []) : [];
      if (!results.length) {
        list.replaceChildren(el('li', 'st-result st-result--none', ok
          ? `Nothing called "${query}" yet. Try a shorter name, or use Add anything in your library.`
          : 'Search isn\'t answering right now. Try again in a moment.'));
        return;
      }
      list.replaceChildren(...results.map(resultRow));
    }

    // ---------------------------------------------------------------- first-week hand-off
    function nextStep({ done, title, text, action }) {
      const item = el('li', `st-next__step${done ? ' is-done' : ''}`);
      item.appendChild(el('span', 'st-next__icon', done ? '✓' : ''));
      const body = el('div', 'st-next__body');
      body.append(el('strong', '', title), el('p', '', text));
      if (action && !done) body.appendChild(action);
      item.appendChild(body);
      return item;
    }

    function libraryLink(entry, label) {
      const link = el('a', 'st-mini st-mini--seen', label);
      link.href = `/?library_category=${encodeURIComponent(entry.category)}&library_item=${encodeURIComponent(entry.item_id)}`;
      link.addEventListener('click', () => { recordStep('next_step'); });
      return link;
    }

    function inviteAction() {
      const wrap = el('div', 'st-next__action');
      const button = el('button', 'st-mini st-mini--seen', 'Get my invite link');
      button.type = 'button';
      button.addEventListener('click', async () => {
        button.disabled = true;
        const { ok, data } = await post('/api/friends/invite-link', {}).catch(() => ({ ok: false, data: {} }));
        if (!ok || typeof data.url !== 'string') {
          button.disabled = false;
          wrap.appendChild(el('p', 'st-result__error', data.detail || 'Couldn\'t make a link just now. Try again.'));
          return;
        }
        recordStep('next_step');
        const field = el('input', 'st-invite');
        field.readOnly = true;
        field.value = data.url;
        field.setAttribute('aria-label', 'Your invite link');
        const note = el('p', 'st-next__note', 'Anyone who signs up with it becomes your friend on OmniTrackr straight away.');
        wrap.replaceChildren(field, note);
        if (navigator.share) {
          navigator.share({ text: data.text, url: data.url }).catch(() => null);
        } else if (navigator.clipboard) {
          navigator.clipboard.writeText(data.url).then(() => { note.textContent = 'Copied. Anyone who signs up with it becomes your friend on OmniTrackr straight away.'; }).catch(() => null);
        }
        field.select();
      });
      wrap.appendChild(button);
      return wrap;
    }

    // ---------------------------------------------------------------- your week (the home screen's first-week card)
    function pad(n) { return String(n).padStart(2, '0'); }

    function localToday(now = new Date()) {
      return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    }

    function whenWords(iso, today) {
      const [y, m, d] = String(iso || '').split('-').map(Number);
      const [ty, tm, td] = String(today || '').split('-').map(Number);
      const when = new Date(y, (m || 1) - 1, d || 1);
      const diff = Math.round((when - new Date(ty, (tm || 1) - 1, td || 1)) / 86400000);
      if (diff === 0) return 'today';
      if (diff === 1) return 'tomorrow';
      return `on ${when.toLocaleDateString(undefined, { weekday: 'long' })}`;
    }

    async function loadWeek() {
      if (state.weekLoaded) return;
      state.weekLoaded = true;
      const { ok, data } = await request(`/api/week-one?today=${encodeURIComponent(localToday())}`).catch(() => ({ ok: false, data: {} }));
      if (!ok || !data.card) return;
      state.week = data.card;
      if (state.screen === 'done') renderNext();
      post('/api/week-one/start-seen', { today: localToday() }).catch(() => null);
    }

    function weekLink(label) {
      const link = el('a', 'st-mini st-mini--seen', label);
      link.href = '/#week-one';
      link.addEventListener('click', () => { recordStep('next_step'); });
      return link;
    }

    function remindAction(week) {
      const wrap = el('div', 'st-next__action');
      const label = whenWords(week.remind_day, week.today);
      const button = el('button', 'st-mini st-mini--seen', label === 'tomorrow' ? 'Email me tomorrow' : `Email me ${label}`);
      button.type = 'button';
      button.addEventListener('click', async () => {
        button.disabled = true;
        const minutes = -new Date().getTimezoneOffset();
        const { ok, data } = await request('/api/week-one/reminder', {
          method: 'PUT', body: JSON.stringify({ day: week.remind_day, today: localToday(), tz: minutes, place: 'start' }),
        }).catch(() => ({ ok: false, data: {} }));
        if (!ok) {
          button.disabled = false;
          wrap.appendChild(el('p', 'st-result__error', typeof data.detail === 'string' ? data.detail : 'Couldn\'t set it just now. Try again.'));
          return;
        }
        recordStep('next_step');
        state.week = { ...week, reminder: data.reminder };
        renderNext();
      });
      wrap.appendChild(button);
      return wrap;
    }

    function weekStep() {
      const week = state.week;
      if (!week) return null;
      const items = (week.days || []).flatMap(day => day.items || []);
      if (items.length) {
        const first = items[0];
        const when = whenWords(first.date, week.today);
        const title = first.kind === 'episode' ? `${first.title} ${first.what} is out ${when}` : `${first.title} comes out ${when}`;
        const more = items.length > 1 ? ` Your home screen lays out all ${items.length} for the week.` : '';
        if (week.reminder && week.reminder.status === 'set') {
          return { done: true, title: `Reminder set for ${whenWords(week.reminder.date, week.today).replace(/^on /, '')}`,
            text: `One email that day at about 5 pm with what's out. Nothing after it.${more}` };
        }
        if (week.remind_day && week.offer && week.offer.email) {
          return { title, text: `Want a nudge on the day? One email, nothing after it.${more}`, action: remindAction(week) };
        }
        return { title, text: `Your home screen lays out your week, day by day.${more}`, action: weekLink('See my week') };
      }
      const names = (week.suggestions || []).slice(0, 2).map(show => show.title);
      if (names.length) {
        return { title: 'Watching a show right now?',
          text: `${names.join(' and ')} ${names.length === 1 ? 'has a' : 'have'} new episode${names.length === 1 ? '' : 's'} this week, among others. Save what you're watching and your home screen lays out your week.`,
          action: weekLink('See this week') };
      }
      if ((week.releases || []).length) {
        return { title: 'Out this week', text: `${week.releases[0].title} and more come out in the next few days. Save one and its release day goes on your week.`,
          action: weekLink('See this week') };
      }
      return null;
    }

    function emailAction() {
      const button = el('button', 'st-mini st-mini--seen', 'Turn it on');
      button.type = 'button';
      button.addEventListener('click', async () => {
        button.disabled = true;
        const { ok, data } = await request('/api/for-you/email', { method: 'PUT', body: JSON.stringify({ enabled: true, source: 'start' }) })
          .catch(() => ({ ok: false, data: {} }));
        if (!ok) {
          button.disabled = false;
          button.after(el('p', 'st-result__error', data.detail || 'Couldn\'t turn it on. Try again.'));
          return;
        }
        recordStep('next_step');
        state.firstWeek = { ...state.firstWeek, weekly_email: true };
        renderNext();
      });
      return button;
    }

    function renderNext() {
      const list = find('[data-st-next]');
      const week = state.firstWeek || {};
      const steps = [];
      const thisWeek = weekStep();
      if (thisWeek) steps.push(thisWeek);
      const seen = state.shelf.find(item => item.seen);
      const any = state.shelf[0];
      if (seen) {
        steps.push({ title: `Rate ${seen.title}`, text: 'Ratings are what your picks and stats learn from. One is enough to start.',
          action: libraryLink(seen, 'Rate it') });
      } else if (any) {
        steps.push({ title: `Leave a note on ${any.title}`, text: 'Say why you saved it. Future you will be glad you did.',
          action: libraryLink(any, 'Add a note') });
      }
      if (week.show !== false) {
        steps.push({ done: Boolean(week.friend), title: week.friend ? 'Friend added' : 'Bring a friend',
          text: week.friend ? 'You can see what they track in your friends feed.'
            : 'Share your invite link. When they join you\'re friends automatically and can compare tastes.',
          action: inviteAction() });
        if (week.email_available && week.verified) {
          steps.push({ done: Boolean(week.weekly_email), title: week.weekly_email ? 'Weekly email on' : 'Get a weekly email',
            text: week.weekly_email ? 'It comes when something you track is coming out. One click unsubscribes.'
              : 'One short email when something you saved has a new season, sequel or release date.',
            action: emailAction() });
        }
      }
      list.replaceChildren(...steps.map(nextStep));
      const title = find('[data-st-done-title]');
      title.textContent = state.total > state.goal ? `${state.total} titles saved. Your library is off the ground` : 'Your library is off the ground';
    }

    // ---------------------------------------------------------------- refresh
    async function refreshState() {
      const { ok, data } = await request('/api/start/state').catch(() => ({ ok: false, data: {} }));
      if (!ok) return;
      state.total = Number(data.total || 0);
      state.shelf = Array.isArray(data.shelf) ? data.shelf : state.shelf;
      state.firstWeek = data.first_week || state.firstWeek;
      renderGoal();
      if (state.screen === 'done') renderNext();
    }

    function savedBeforeSignup() {
      try {
        return SAVED_BEFORE_SIGNUP.some(key => {
          const value = localStorage.getItem(key);
          return value && value !== '[]' && value !== 'null';
        });
      } catch (error) {
        return false;
      }
    }

    // ---------------------------------------------------------------- wiring
    root.addEventListener('click', event => {
      const go = event.target.closest('[data-st-go]');
      if (go) {
        event.preventDefault();
        show(go.dataset.stGo);
        return;
      }
      const tapped = event.target.closest('[data-st-tap]');
      if (tapped) {
        const item = tapped.closest('.st-tile');
        if (item) tap(item, tapped.dataset.stTap);
        return;
      }
      if (event.target.closest('[data-st-more]')) {
        showMore();
        return;
      }
      if (event.target.closest('[data-st-clear]')) {
        const input = document.getElementById('stSearch');
        input.value = '';
        runSearch('');
        input.focus();
        return;
      }
      const step = event.target.closest('[data-st-step]');
      if (step) {
        recordStep(step.dataset.stStep);
        return;
      }
      if (event.target.closest('[data-st-library]')) {
        recordStep('next_step');
        return;
      }
      if (event.target.closest('[data-st-skip]')) {
        event.preventDefault();
        recordStep('skipped').finally(() => window.location.assign('/'));
      }
    });

    let chipTimer = null;
    root.querySelector('.st-formats').addEventListener('change', () => {
      window.clearTimeout(chipTimer);
      chipTimer = window.setTimeout(loadDeck, 250);
    });

    let searchTimer = null;
    const searchInput = document.getElementById('stSearch');
    searchInput.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => runSearch(searchInput.value), 200);
    });
    find('[data-st-search-form]').addEventListener('submit', event => {
      event.preventDefault();
      runSearch(searchInput.value);
    });

    // Titles saved before sign-up move in through the dashboard's own scripts, which call this.
    window.refreshForYou = refreshState;
    if (savedBeforeSignup()) window.setTimeout(refreshState, 4000);

    show(state.total >= state.goal ? 'done' : 'pick');
  }

  const start = () => { const root = document.getElementById('startFlow'); if (root) setup(root); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
