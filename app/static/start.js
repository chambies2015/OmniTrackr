// Start page (/start): quick add, search, and the hand-off to the first-week steps.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const ANSWER_WORDS = { seen: 'as seen', want: 'to your want-to list' };
  const KEYS = { ArrowLeft: 'skip', ArrowUp: 'want', ArrowRight: 'seen' };
  const SAVED_BEFORE_SIGNUP = ['omnitrackr_guest_list', 'omnitrackr_taste_quiz', 'omnitrackr_taste_compare'];

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

  function metaLine(card) {
    return [card.label, card.year, card.creator].filter(Boolean).join(' · ');
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
      screen: null,
      deck: [],
      position: 0,
      shown: new Set(),
      deckRequest: 0,
      saving: false,
      lastSave: null,
      art: new Map(),
      searchRequest: 0,
      celebrated: Number(initial.total || 0) >= Number(initial.goal || 5),
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
      if (state.total >= state.goal) {
        count.textContent = state.total === state.goal ? 'Five saved. That\'s the goal.' : `${state.total} saved. Past the goal.`;
      } else if (!state.total) {
        count.textContent = `0 of ${state.goal} saved`;
      } else {
        count.textContent = `${state.total} of ${state.goal} saved · ${state.goal - state.total} to go`;
      }
      root.classList.toggle('is-goal-met', state.total >= state.goal);
    }

    function addToShelf(result) {
      state.shelf = [{
        kind: result.kind, category: result.category, item_id: result.item_id,
        title: result.title, image: result.image, seen: result.seen,
      }].concat(state.shelf.filter(item => !(item.category === result.category && item.item_id === result.item_id)));
    }

    // ---------------------------------------------------------------- screens
    function show(name) {
      state.screen = name;
      root.classList.toggle('is-working', name === 'quick' || name === 'search');
      root.classList.toggle('is-finished', name === 'done');
      findAll('[data-st-screen]').forEach(screen => { screen.hidden = screen.dataset.stScreen !== name; });
      if (name === 'quick' && !state.deck.length) loadDeck();
      if (name === 'search') window.setTimeout(() => document.getElementById('stSearch').focus(), 0);
      if (name === 'done') {
        renderNext();
        const done = find('[data-st-screen="done"]');
        window.setTimeout(() => done.focus({ preventScroll: true }), 0);
      }
      if (name === 'quick') window.setTimeout(() => find('[data-st-answer="seen"]').focus({ preventScroll: true }), 0);
    }

    function maybeCelebrate() {
      if (state.total >= state.goal && !state.celebrated) {
        state.celebrated = true;
        window.setTimeout(() => show('done'), 900);
      }
    }

    // ---------------------------------------------------------------- quick add
    function chosenKinds() {
      return findAll('.st-formats input:checked').map(input => input.value);
    }

    async function loadDeck() {
      const kinds = chosenKinds();
      const card = find('[data-st-card]');
      if (!kinds.length) {
        state.deck = [];
        state.position = 0;
        renderCard('Pick at least one format above.');
        return;
      }
      const ticket = ++state.deckRequest;
      card.replaceChildren(el('p', 'st-card__empty', 'Finding popular titles…'));
      setAnswering(false);
      const { ok, data } = await request(`/api/start/deck?kinds=${encodeURIComponent(kinds.join(','))}`).catch(() => ({ ok: false, data: {} }));
      if (ticket !== state.deckRequest) return;
      if (!ok) {
        renderCard('Couldn\'t load titles just now. Try again in a moment, or search instead.');
        return;
      }
      state.deck = (data.cards || []).filter(item => !state.shown.has(item.id));
      state.position = 0;
      renderCard();
    }

    function setAnswering(enabled) {
      findAll('[data-st-answer]').forEach(button => { button.disabled = !enabled; });
    }

    function cardArt(card) {
      const frame = el('div', `st-art st-art--${card.kind}`);
      const initial = el('span', 'st-art__initial', (card.title || '?').slice(0, 1).toUpperCase());
      frame.appendChild(initial);
      const place = image => {
        if (!image) return;
        const img = el('img');
        img.alt = '';
        img.referrerPolicy = 'no-referrer';
        img.decoding = 'async';
        img.addEventListener('load', () => frame.classList.add('has-image'));
        img.addEventListener('error', () => img.remove());
        img.src = image;
        frame.appendChild(img);
      };
      if (card.image) place(card.image);
      else fetchArt(card).then(place);
      return frame;
    }

    function fetchArt(card) {
      if (card.members) return Promise.resolve(null); // Member-saved titles came with whatever art exists.
      if (!state.art.has(card.id)) {
        state.art.set(card.id, request(`/api/start/art/${card.kind}/${encodeURIComponent(card.slug)}`)
          .then(({ ok, data }) => (ok && typeof data.image === 'string' && /^https?:\/\//.test(data.image) ? data.image : null))
          .catch(() => null));
      }
      return state.art.get(card.id);
    }

    function renderCard(emptyMessage) {
      const holder = find('[data-st-card]');
      const card = state.deck[state.position];
      if (!card) {
        holder.replaceChildren(el('p', 'st-card__empty', emptyMessage
          || 'That\'s every title we have for these formats. Tick another format above, or search for something specific.'));
        setAnswering(false);
        return;
      }
      state.shown.add(card.id);
      const text = el('div', 'st-card__text');
      text.append(el('p', 'st-card__meta', metaLine(card)), el('h2', 'st-card__title', card.title));
      if (card.members) text.appendChild(el('p', 'st-card__note', `In ${card.members} members' libraries`));
      const left = state.deck.length - state.position - 1;
      text.appendChild(el('p', 'st-card__left', left > 0 ? `${left} more after this one` : 'Last one for these formats'));
      holder.replaceChildren(cardArt(card), text);
      setAnswering(true);
      // Warm the next card's artwork so the deck never waits on it.
      const next = state.deck[state.position + 1];
      if (next && !next.image) fetchArt(next);
    }

    function status(message, undo) {
      const line = find('[data-st-status]');
      line.replaceChildren(document.createTextNode(message));
      if (undo) {
        const button = el('button', 'st-link', 'Undo');
        button.type = 'button';
        button.addEventListener('click', undo);
        line.append(' ', button);
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

    async function answerCard(answer) {
      const card = state.deck[state.position];
      if (!card || state.saving) return;
      if (answer === 'skip') {
        state.position += 1;
        status('');
        renderCard();
        return;
      }
      state.saving = true;
      setAnswering(false);
      const result = await save(card, answer, 'quick');
      state.saving = false;
      if (result.error) {
        status(result.error);
        setAnswering(true);
        return;
      }
      state.position += 1;
      renderCard();
      if (result.state === 'created') {
        const saved = { ...result, position: state.position - 1 };
        status(`Saved ${result.title} ${ANSWER_WORDS[answer]}.`, () => undo(saved));
      } else {
        status(`${result.title} was already in your library, so it stays as it was.`);
      }
      maybeCelebrate();
    }

    async function undo(saved) {
      const { ok, data } = await post('/api/start/undo', { category: saved.category, item_id: saved.item_id })
        .catch(() => ({ ok: false, data: {} }));
      if (!ok) {
        status(data.detail || 'Couldn\'t undo that. You can remove it from your library.');
        return;
      }
      state.total = Number(data.total || 0);
      state.shelf = state.shelf.filter(item => !(item.category === saved.category && item.item_id === saved.item_id));
      if (state.total < state.goal) state.celebrated = false;
      renderGoal();
      status(`Took ${saved.title} back out.`);
      if (state.screen === 'quick' && state.deck[saved.position]) {
        state.position = saved.position;
        renderCard();
      }
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
          maybeCelebrate();
        });
        actions.appendChild(button);
      });
      item.append(art, text, actions);
      return item;
    }

    async function runSearch(text) {
      const list = find('[data-st-results]');
      const query = text.trim();
      const ticket = ++state.searchRequest;
      if (query.length < 2) {
        list.replaceChildren();
        return;
      }
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
      if (state.screen === 'choose') maybeCelebrate();
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
      const answer = event.target.closest('[data-st-answer]');
      if (answer) {
        answerCard(answer.dataset.stAnswer);
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

    document.addEventListener('keydown', event => {
      if (state.screen !== 'quick' || event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (target && (target.tagName === 'INPUT' && target.type !== 'checkbox' || target.tagName === 'TEXTAREA')) return;
      const answer = KEYS[event.key];
      if (!answer) return;
      event.preventDefault();
      answerCard(answer);
    });

    // Titles saved before sign-up move in through the dashboard's own scripts, which call this.
    window.refreshForYou = refreshState;
    if (savedBeforeSignup()) window.setTimeout(refreshState, 4000);

    renderGoal();
    show(state.total >= state.goal ? 'done' : 'choose');
  }

  const start = () => { const root = document.getElementById('startFlow'); if (root) setup(root); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
