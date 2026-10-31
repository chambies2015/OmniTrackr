// Taste quiz (/taste-quiz) and, on the dashboard, moving a visitor's answers into
// their new library. Answers are kept in this browser until they are saved:
// members save at the end of the quiz, visitors at their first log-in.
(function () {
  'use strict';

  const KEY = 'omnitrackr_taste_quiz';
  const ANSWERS = new Set(['loved', 'liked', 'meh', 'want', 'skip']);
  const KINDS = new Set(['movie', 'tv', 'anime', 'game']);
  const ID = /^(movie|tv|anime|game)\/[a-z0-9-]{1,130}$/;
  const FINISH_AFTER = 5;
  const LOADERS = ['loadMovies', 'loadTVShows', 'loadAnime', 'loadVideoGames', 'loadMusic', 'loadBooks', 'loadManga', 'loadPodcasts', 'loadAudiobooks'];
  const LABELS = { loved: 'Loved it', liked: 'Liked it', meh: 'Not for me', want: 'Want to' };

  // ------------------------------------------------------------ storage
  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!data || typeof data !== 'object') return null;
      const answers = {};
      Object.entries(data.answers || {}).forEach(([id, answer]) => {
        if (ID.test(id) && ANSWERS.has(answer)) answers[id] = answer;
      });
      const kinds = Array.isArray(data.kinds) ? data.kinds.filter(kind => KINDS.has(kind)) : [];
      return { answers, kinds, pending: data.pending === true };
    } catch (error) {
      return null;
    }
  }

  function write(state) {
    try {
      if (state) localStorage.setItem(KEY, JSON.stringify(state));
      else localStorage.removeItem(KEY);
    } catch (error) { /* private mode: the quiz still works for this visit */ }
  }

  function answerList(answers) {
    return Object.entries(answers).filter(([, answer]) => answer !== 'skip').map(([id, answer]) => ({ id, answer }));
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  function report(event) {
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  async function postJson(url, body) {
    const response = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: authHeaders(), body: JSON.stringify(body) });
    const data = await response.json().catch(() => null);
    return { ok: response.ok, status: response.status, data };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function safeImage(url) {
    if (typeof url !== 'string') return null;
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
    } catch (error) {
      return null;
    }
  }

  // image is passed on its own: for deck cards it comes from the art API, never from page data.
  function art(item, className, image) {
    const box = el('div', `${className} tq-art--${item.kind}`);
    if (image) {
      const img = el('img');
      img.src = image; img.alt = ''; img.loading = 'lazy'; img.decoding = 'async';
      img.referrerPolicy = 'no-referrer'; img.width = 200; img.height = 300;
      img.addEventListener('error', () => { img.remove(); box.classList.add('is-empty'); });
      box.appendChild(img);
    } else {
      box.classList.add('is-empty');
    }
    box.appendChild(el('span', 'tq-art__initial', (item.title || '?').slice(0, 1).toUpperCase())).setAttribute('aria-hidden', 'true');
    return box;
  }

  // ------------------------------------------------------------ the quiz page
  function setupQuiz(root) {
    let deck = [];
    try { deck = JSON.parse(document.getElementById('tasteQuizDeck').textContent || '[]'); } catch (error) { deck = []; }
    deck = deck.filter(card => card && ID.test(card.id) && KINDS.has(card.kind));
    const covers = new Map();
    if (!deck.length) return;
    const signedIn = root.dataset.signedIn === 'true';
    const screens = {};
    root.querySelectorAll('[data-tq-screen]').forEach(node => { screens[node.dataset.tqScreen] = node; });
    const find = selector => root.querySelector(selector);
    const artRequested = new Set();
    let order = [];
    let position = 0;
    let state = read() || { answers: {}, kinds: [], pending: false };

    function show(name) {
      Object.entries(screens).forEach(([key, node]) => { node.hidden = key !== name; });
    }

    function chosenKinds() {
      return Array.from(root.querySelectorAll('input[name="kind"]:checked')).map(input => input.value).filter(kind => KINDS.has(kind));
    }

    function save() {
      state.pending = answerList(state.answers).length > 0;
      write(state);
    }

    function counted() {
      return answerList(state.answers).length;
    }

    // Artwork comes from the API, never from the page, and only for deck cards.
    function loadArt(card, onImage) {
      if (!card) return;
      if (covers.has(card.id)) { if (onImage) onImage(); return; }
      if (artRequested.has(card.id)) return;
      artRequested.add(card.id);
      fetch(`/api/taste-quiz/art/${card.id}`, { headers: { Accept: 'application/json' } })
        .then(response => (response.ok ? response.json() : null))
        .then(data => {
          const image = safeImage(data && data.image);
          if (!image) return;
          covers.set(card.id, image);
          if (order[position] === card && !screens.play.hidden) renderCard();
          if (onImage) onImage();
        })
        .catch(() => { /* the initial letter stays */ });
    }

    function renderCard() {
      const card = order[position];
      const holder = find('[data-tq-card]');
      holder.replaceChildren();
      if (!card) return;
      holder.appendChild(art(card, 'tq-card__art', covers.get(card.id)));
      const text = el('div', 'tq-card__text');
      text.appendChild(el('p', 'tq-card__meta', [card.label, card.year, card.creator].filter(Boolean).join(' · ')));
      text.appendChild(el('h2', 'tq-card__title', card.title));
      const previous = state.answers[card.id];
      if (previous && previous !== 'skip') text.appendChild(el('p', 'tq-card__previous', `Your answer: ${LABELS[previous]}`));
      holder.appendChild(text);
      const done = Object.keys(state.answers).filter(id => order.some(item => item.id === id)).length;
      find('[data-tq-bar]').style.width = `${Math.round((done / order.length) * 100)}%`;
      find('[data-tq-count]').textContent = `${position + 1} of ${order.length}`;
      find('[data-tq-action="back"]').disabled = position === 0;
      const finish = find('[data-tq-action="finish"]');
      finish.hidden = counted() < FINISH_AFTER;
      root.querySelectorAll('[data-tq-answer]').forEach(button => {
        button.setAttribute('aria-pressed', String(state.answers[card.id] === button.dataset.tqAnswer));
      });
      loadArt(card);
      loadArt(order[position + 1]);
      loadArt(order[position + 2]);
    }

    function start(resume) {
      const kinds = chosenKinds();
      state.kinds = kinds.length ? kinds : Array.from(KINDS);
      order = deck.filter(card => state.kinds.includes(card.kind));
      if (!order.length) order = deck.slice();
      position = 0;
      if (resume) {
        const next = order.findIndex(card => !state.answers[card.id]);
        position = next === -1 ? order.length - 1 : next;
      }
      save();
      show('play');
      renderCard();
      find('[data-tq-answer="loved"]').focus({ preventScroll: true });
      report('quiz_started');
    }

    function answer(value) {
      const card = order[position];
      if (!card || !ANSWERS.has(value)) return;
      state.answers[card.id] = value;
      save();
      if (position >= order.length - 1) {
        finish();
        return;
      }
      position += 1;
      renderCard();
    }

    function shelf(results) {
      const box = find('[data-tq-shelf]');
      box.replaceChildren();
      const favorites = deck.filter(card => ['loved', 'liked'].includes(state.answers[card.id]))
        .sort((a, b) => (state.answers[a.id] === 'loved' ? 0 : 1) - (state.answers[b.id] === 'loved' ? 0 : 1)).slice(0, 8);
      favorites.forEach(card => {
        const item = el('div', 'tq-shelf__item');
        const cover = art(card, 'tq-shelf__art', covers.get(card.id));
        item.appendChild(cover);
        if (!covers.has(card.id)) loadArt(card, () => { if (cover.isConnected) cover.replaceWith(art(card, 'tq-shelf__art', covers.get(card.id))); });
        item.appendChild(el('span', 'tq-shelf__label', state.answers[card.id] === 'loved' ? '♥ Loved' : 'Liked'));
        item.title = card.title;
        box.appendChild(item);
      });
      box.hidden = !favorites.length || !results;
    }

    function pickButton(pick) {
      const button = el('button', 'button tq-pick__save');
      button.type = 'button';
      if (signedIn) {
        button.textContent = 'Add to my library';
        button.addEventListener('click', async () => {
          button.disabled = true;
          button.textContent = 'Adding…';
          try {
            const { ok, status, data } = await postJson('/api/pick/add', { id: pick.id, source: 'taste-quiz' });
            if (status === 401) { window.location.href = `/?next=${encodeURIComponent('/taste-quiz')}#landing-auth`; return; }
            button.textContent = ok ? (data && data.state === 'existing' ? 'Already in your library ✓' : 'Added ✓') : 'Try again';
            button.disabled = ok;
          } catch (error) {
            button.textContent = 'Try again';
            button.disabled = false;
          }
        });
        return button;
      }
      const list = window.OmniGuestList;
      const saved = () => !!(list && list.read().some(item => item.kind === pick.kind && item.slug === pick.slug));
      const paint = () => {
        button.textContent = saved() ? 'Saved to your list ✓' : 'Save to my list';
        button.setAttribute('aria-pressed', String(saved()));
      };
      button.addEventListener('click', () => {
        if (!list) return;
        if (saved()) list.remove(pick.kind, pick.slug);
        else if (list.add(pick.kind, pick.slug, pick.title).added) report('quiz_saved');
        paint();
      });
      paint();
      return button;
    }

    function renderPicks(picks) {
      const holder = find('[data-tq-picks]');
      holder.replaceChildren();
      find('[data-tq-picks-title]').hidden = !picks.length;
      picks.forEach(pick => {
        const item = el('li', 'tq-pick');
        item.appendChild(art(pick, 'tq-pick__art', safeImage(pick.image)));
        const body = el('div', 'tq-pick__body');
        body.appendChild(el('p', 'tq-pick__because', `Because you ${pick.because_answer === 'loved' ? 'loved' : pick.because_answer === 'want' ? 'want to try' : 'liked'} ${pick.because}`));
        const heading = el('h4', 'tq-pick__title');
        if (typeof pick.url === 'string' && pick.url.startsWith('/titles/')) {
          const link = el('a', '', pick.title);
          link.href = pick.url;
          heading.appendChild(link);
        } else {
          heading.textContent = pick.title;
        }
        body.appendChild(heading);
        body.appendChild(el('p', 'tq-pick__meta', [pick.label, pick.year, pick.creator].filter(Boolean).join(' · ')));
        body.appendChild(el('p', 'tq-pick__why', pick.why));
        const actions = el('div', 'tq-pick__actions');
        actions.appendChild(pickButton(pick));
        if (typeof pick.guide === 'string' && pick.guide.startsWith('/if-you-liked/')) {
          const guide = el('a', 'tq-pick__guide', `More like ${pick.because}`);
          guide.href = pick.guide;
          actions.appendChild(guide);
        }
        body.appendChild(actions);
        item.appendChild(body);
        holder.appendChild(item);
      });
    }

    function link(text, href, primary) {
      const node = el('a', primary ? 'button' : 'tq-link', text);
      node.href = href;
      return node;
    }

    async function finish() {
      const answers = answerList(state.answers);
      show('result');
      const summary = find('[data-tq-summary]');
      const actions = find('[data-tq-actions]');
      actions.replaceChildren();
      find('[data-tq-picks]').replaceChildren();
      find('[data-tq-picks-title]').hidden = true;
      shelf(false);
      screens.result.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (!answers.length) {
        find('[data-tq-result-title]').textContent = 'Nothing rings a bell?';
        summary.textContent = 'That happens. Pick for me suggests one title at a time with a reason to try it, or search for a favorite from your library.';
        actions.append(link('Try Pick for me', '/pick', true), link(signedIn ? 'Open my library' : 'Browse Discover', signedIn ? '/' : '/discover'));
        return;
      }
      const seen = answers.filter(item => item.answer !== 'want').length;
      const wants = answers.length - seen;
      summary.textContent = 'Finding picks for you…';
      let result;
      try {
        result = signedIn
          ? await postJson('/api/taste-quiz/save', { answers, kinds: state.kinds, source: 'quiz' })
          : await postJson('/api/taste-quiz/suggestions', { answers, kinds: state.kinds });
      } catch (error) {
        result = { ok: false };
      }
      if (signedIn && result.status === 401) {
        // Signed out in another tab: keep the answers for the next log-in.
        state.pending = true; write(state);
        summary.textContent = 'Log in again and your answers will be added to your library.';
        actions.append(link('Log in', `/?next=${encodeURIComponent('/taste-quiz')}#landing-auth`, true));
        return;
      }
      if (!result.ok || !result.data) {
        summary.textContent = signedIn
          ? 'Your answers couldn\'t be saved just now. They\'re kept in this browser and will be added next time you open your library.'
          : 'Picks couldn\'t load just now. Your answers are kept in this browser, so try again in a moment.';
        actions.append(link('Try Pick for me', '/pick', true));
        return;
      }
      const picks = Array.isArray(result.data.suggestions) ? result.data.suggestions : [];
      if (signedIn) {
        state.pending = false;
        write(state);
        const added = (result.data.added || []).length;
        const existing = (result.data.existing || []).length;
        const parts = [];
        if (added) parts.push(`Added ${added} title${added === 1 ? '' : 's'} to your library`);
        if (existing) parts.push(`${existing} ${existing === 1 ? 'was' : 'were'} already there and ${existing === 1 ? 'wasn\'t' : 'weren\'t'} changed`);
        find('[data-tq-result-title]').textContent = added ? 'Your library is off to a great start' : 'Here\'s where to go next';
        summary.textContent = `${parts.join('; ') || 'Your library is unchanged'}.${picks.length ? ' Here are a few picks based on your answers.' : ''}`;
        actions.append(link('Open my library', '/', true), link('Pick for me', '/pick'));
      } else {
        find('[data-tq-result-title]').textContent = 'Your library is ready to save';
        const bits = [];
        if (seen) bits.push(`${seen} you've seen`);
        if (wants) bits.push(`${wants} on your want list`);
        summary.textContent = `${bits.join(' and ')}. Create a free account and they move into your library at your first log-in, ratings included.`;
        actions.append(link('Save my library, free', '/#signup', true), link('Log in', '/#landing-auth'));
      }
      shelf(true);
      renderPicks(picks);
    }

    function back() {
      if (position === 0) return;
      position -= 1;
      renderCard();
    }

    root.addEventListener('click', event => {
      const target = event.target.closest && event.target.closest('[data-tq-answer], [data-tq-action]');
      if (!target || !root.contains(target)) return;
      if (target.dataset.tqAnswer) { answer(target.dataset.tqAnswer); return; }
      const action = target.dataset.tqAction;
      if (action === 'start') start(false);
      else if (action === 'resume') start(true);
      else if (action === 'back') back();
      else if (action === 'finish') finish();
      else if (action === 'restart') {
        state = { answers: {}, kinds: state.kinds, pending: false };
        write(state);
        show('intro');
        find('[data-tq-resume]').hidden = true;
        find('[data-tq-action="start"]').focus();
      }
    });

    document.addEventListener('keydown', event => {
      if (screens.play.hidden || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      const keys = { 1: 'loved', 2: 'liked', 3: 'meh', 4: 'want', 5: 'skip', 0: 'skip' };
      if (keys[event.key]) { event.preventDefault(); answer(keys[event.key]); }
      else if (event.key === 'Backspace') { event.preventDefault(); back(); }
    });

    // Offer to pick up a quiz left part-way through.
    const answeredBefore = Object.keys(state.answers).length;
    if (answeredBefore && answeredBefore < deck.length) {
      if (state.kinds.length) {
        root.querySelectorAll('input[name="kind"]').forEach(input => { input.checked = state.kinds.includes(input.value); });
      }
      const resume = find('[data-tq-resume]');
      resume.replaceChildren(document.createTextNode(`You answered ${answeredBefore} title${answeredBefore === 1 ? '' : 's'} last time. `));
      const button = el('button', 'tq-link', 'Carry on where you left off');
      button.type = 'button';
      button.dataset.tqAction = 'resume';
      resume.appendChild(button);
      resume.hidden = false;
    }
  }

  // ------------------------------------------------------------ dashboard: move saved answers in
  function signedInDashboard() {
    if (document.documentElement.dataset.publicShell === 'true') return false;
    // The start page (/start) is only ever served to a signed-in member.
    if (typeof document.getElementById === 'function' && document.getElementById('startFlow')) return true;
    if (!document.getElementById('mainContainer')) return false;
    try { return typeof getUser === 'function' && !!getUser(); } catch (error) { return false; }
  }

  function toast(message) {
    const node = el('div', 'guest-import-toast', message);
    node.setAttribute('role', 'status');
    document.body.appendChild(node);
    setTimeout(() => node.remove(), 7000);
  }

  let importing = false;
  async function importAnswers() {
    const state = read();
    if (importing || !state || !state.pending || !signedInDashboard()) return null;
    const answers = answerList(state.answers);
    if (!answers.length) { write(null); return null; }
    importing = true;
    try {
      const base = typeof API_BASE === 'string' ? API_BASE : '';
      const { ok, status, data } = await postJson(`${base}/api/taste-quiz/save`, { answers, kinds: state.kinds, source: 'guest' });
      if (!ok) {
        if (status === 422 || status === 400) write(null);
        return null;
      }
      // Keep the answers (for a retake) but mark them saved.
      const latest = read() || state;
      latest.pending = false;
      write(latest);
      const added = (data && data.added || []).length;
      if (added) {
        toast(`Added ${added} title${added === 1 ? '' : 's'} from your taste quiz to your library.`);
        LOADERS.forEach(name => { if (typeof window[name] === 'function') { try { window[name](); } catch (error) { /* ignore */ } } });
        if (typeof window.refreshForYou === 'function') window.refreshForYou();
      }
      return data;
    } catch (error) {
      return null; // Try again next visit.
    } finally {
      importing = false;
    }
  }

  function init() {
    const root = document.getElementById('tasteQuiz');
    if (root) setupQuiz(root);
    else setTimeout(importAnswers, 900);
  }

  const api = { read, write, answerList, importAnswers, KEY };
  window.OmniTasteQuiz = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
