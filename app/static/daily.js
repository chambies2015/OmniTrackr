// OmniTrackr Daily (/daily): guess one title a day from six clues.
// Each guess is checked by POST /api/daily/{n}/guess, which returns the next clue,
// or the answer once the game is over. Games, streaks and results are kept only in
// this browser (localStorage); nothing about the player is stored on the server.
(function () {
  'use strict';

  const KEY = 'omnitrackr_daily';
  const MAX_GUESSES = 6;
  const KEEP_GAMES = 400;
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book']);
  const SLUG = /^[a-z0-9-]{1,130}$/;

  // ---- Stored games ---------------------------------------------------------

  function cleanGame(raw, number) {
    if (!raw || typeof raw !== 'object') return null;
    const guesses = Array.isArray(raw.guesses) ? raw.guesses.slice(0, MAX_GUESSES)
      .filter(g => g && typeof g.t === 'string').map(g => ({ t: g.t.slice(0, 120), ok: g.ok === true })) : [];
    const clues = Array.isArray(raw.clues) ? raw.clues.filter(c => typeof c === 'string').slice(0, MAX_GUESSES) : [];
    const answer = raw.answer && typeof raw.answer === 'object' && typeof raw.answer.title === 'string' ? raw.answer : null;
    const done = raw.done === true && !!answer;
    return {
      n: number, daily: raw.daily === true, guesses, clues, done,
      won: done && guesses.some(g => g.ok), answer: done ? answer : null,
    };
  }

  function normalizeStore(raw) {
    const store = { v: 1, games: {} };
    if (!raw || typeof raw !== 'object' || !raw.games || typeof raw.games !== 'object') return store;
    Object.keys(raw.games).forEach(key => {
      const number = Number(key);
      if (!Number.isInteger(number) || number < 1) return;
      const game = cleanGame(raw.games[key], number);
      if (game) store.games[number] = game;
    });
    return store;
  }

  function read() {
    try {
      return normalizeStore(JSON.parse(localStorage.getItem(KEY) || 'null'));
    } catch (error) {
      return normalizeStore(null);
    }
  }

  function write(store) {
    const numbers = Object.keys(store.games).map(Number).sort((a, b) => b - a);
    numbers.slice(KEEP_GAMES).forEach(number => { delete store.games[number]; });
    try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (error) { /* private mode: this tab still works */ }
  }

  function newGame(number, firstClue, isDaily) {
    return { n: number, daily: !!isDaily, guesses: [], clues: firstClue ? [firstClue] : [], done: false, won: false, answer: null };
  }

  // Applies one checked guess to the game. `result` is the API response.
  function applyResult(game, text, result) {
    if (game.done || !result) return game;
    game.guesses.push({ t: String(text || '').slice(0, 120), ok: result.correct === true });
    if (result.done && result.answer) {
      game.done = true;
      game.won = result.correct === true;
      game.answer = result.answer;
    } else if (typeof result.clue === 'string') {
      game.clues.push(result.clue);
    }
    return game;
  }

  function simplify(text) {
    return String(text || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
      .replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').trim().replace(/^(the|a|an) /, '');
  }

  function alreadyTried(game, text) {
    const wanted = simplify(text);
    return !!wanted && game.guesses.some(g => g.t && simplify(g.t) === wanted);
  }

  // ---- Results and stats ----------------------------------------------------

  function squares(game) {
    return game.guesses.map(g => (g.ok ? '🟩' : g.t ? '🟥' : '⬛')).join('');
  }

  function shareText(game, emoji, origin) {
    const score = game.won ? `${game.guesses.length}/${MAX_GUESSES}` : `X/${MAX_GUESSES}`;
    const site = String(origin || 'https://omnitrackr.xyz').replace(/^https?:\/\//, '');
    return `OmniTrackr Daily #${game.n} ${emoji || ''} ${score}\n${squares(game)}\n${site}/daily`.replace('  ', ' ');
  }

  // Only puzzles played on their own day count towards the streak, like a newspaper puzzle.
  function stats(store, todayNumber) {
    const games = Object.values(store.games).filter(g => g.daily && g.done);
    const wins = games.filter(g => g.won);
    const won = new Set(wins.map(g => g.n));
    const distribution = [0, 0, 0, 0, 0, 0];
    wins.forEach(g => { if (g.guesses.length >= 1 && g.guesses.length <= MAX_GUESSES) distribution[g.guesses.length - 1] += 1; });
    let start = todayNumber;
    const today = store.games[todayNumber];
    if (!(today && today.daily && today.done)) start -= 1;
    let current = 0;
    for (let n = start; n >= 1 && won.has(n); n -= 1) current += 1;
    let best = 0;
    let run = 0;
    [...won].sort((a, b) => a - b).forEach((n, index, list) => {
      run = index > 0 && list[index - 1] === n - 1 ? run + 1 : 1;
      best = Math.max(best, run);
    });
    return {
      played: games.length, wins: wins.length,
      winRate: games.length ? Math.round((wins.length / games.length) * 100) : 0,
      current, best, distribution,
    };
  }

  function countdown(seconds) {
    const s = Math.max(0, Math.floor(seconds));
    const pad = value => String(value).padStart(2, '0');
    return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  }

  // ---- Page -----------------------------------------------------------------

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function safeUrl(value, external) {
    if (typeof value !== 'string') return null;
    if (/^\/(?!\/)/.test(value)) return value;
    return external && /^https:\/\//i.test(value) ? value : null;
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
      if (typeof window.reportFunnelEvent === 'function') { window.reportFunnelEvent(event); return; }
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function setup(tool) {
    const number = Number(tool.dataset.number);
    const todayNumber = Number(tool.dataset.todayNumber) || number;
    const isToday = tool.dataset.today === 'true';
    const signedIn = tool.dataset.signedIn === 'true';
    const emoji = tool.dataset.emoji || '';
    const kind = tool.dataset.kind;
    const form = tool.querySelector('[data-daily-form]');
    const input = form.querySelector('input');
    const status = tool.querySelector('[data-daily-status]');
    const skip = tool.querySelector('[data-daily-skip]');
    const resultBox = tool.querySelector('[data-daily-result]');
    const firstClue = tool.querySelector('[data-daily-clues] li');
    const firstClueText = firstClue ? firstClue.lastChild.textContent : '';
    let store = read();
    let game = store.games[number] || newGame(number, firstClueText, isToday);
    let busy = false;
    let nextSeconds = Number(tool.dataset.nextSeconds) || 0;
    const loadedAt = Date.now();

    function save() {
      store = read();
      store.games[number] = game;
      write(store);
    }

    function renderClues() {
      const list = tool.querySelector('[data-daily-clues]');
      list.textContent = '';
      game.clues.forEach((clue, index) => {
        const item = el('li');
        item.appendChild(el('span', 'dy-clue-n', `Clue ${index + 1}`));
        item.appendChild(document.createTextNode(clue));
        if (index === game.clues.length - 1 && index > 0 && !game.done) item.className = 'dy-clue--new';
        list.appendChild(item);
      });
      if (game.done && game.answer && Array.isArray(game.answer.clues)) {
        game.answer.clues.slice(game.clues.length).forEach((clue, index) => {
          const item = el('li', 'dy-clue--extra');
          item.appendChild(el('span', 'dy-clue-n', `Clue ${game.clues.length + index + 1}`));
          item.appendChild(document.createTextNode(clue));
          list.appendChild(item);
        });
      }
    }

    function renderHistory() {
      const squaresBox = tool.querySelector('[data-daily-squares]');
      squaresBox.textContent = '';
      for (let i = 0; i < MAX_GUESSES; i += 1) {
        const guess = game.guesses[i];
        squaresBox.appendChild(el('span', `dy-square ${guess ? (guess.ok ? 'is-right' : guess.t ? 'is-wrong' : 'is-skip') : ''}`));
      }
      const history = tool.querySelector('[data-daily-history]');
      history.textContent = '';
      game.guesses.forEach(guess => {
        const row = el('li', guess.ok ? 'is-right' : guess.t ? 'is-wrong' : 'is-skip');
        row.textContent = guess.ok ? `✓ ${guess.t}` : guess.t ? `✗ ${guess.t}` : 'Skipped';
        history.appendChild(row);
      });
      const left = MAX_GUESSES - game.guesses.length;
      const leftLabel = tool.querySelector('[data-daily-left]');
      if (leftLabel) leftLabel.textContent = `(${left} ${left === 1 ? 'guess' : 'guesses'} left)`;
    }

    function statBlock() {
      const s = stats(read(), todayNumber);
      const box = el('div', 'dy-stats');
      box.appendChild(el('h3', '', 'Your stats'));
      const grid = el('dl', 'dy-stats__grid');
      [['Played', s.played], ['Win %', s.winRate], ['Streak', s.current], ['Best streak', s.best]].forEach(([label, value]) => {
        const cell = el('div');
        cell.appendChild(el('dd', '', value));
        cell.appendChild(el('dt', '', label));
        grid.appendChild(cell);
      });
      box.appendChild(grid);
      const most = Math.max(1, ...s.distribution);
      const bars = el('ol', 'dy-bars');
      bars.setAttribute('aria-label', 'Wins by number of guesses');
      s.distribution.forEach((count, index) => {
        const row = el('li');
        row.appendChild(el('span', 'dy-bars__n', index + 1));
        const bar = el('span', 'dy-bars__bar', count);
        bar.style.width = `${Math.max(8, Math.round((count / most) * 100))}%`;
        if (game.won && game.daily && game.guesses.length === index + 1) bar.classList.add('is-current');
        row.appendChild(bar);
        bars.appendChild(row);
      });
      box.appendChild(bars);
      box.appendChild(el('p', 'muted', 'Only puzzles played on their own day count towards your streak. Stats are kept in this browser.'));
      return box;
    }

    async function share(button, note) {
      const text = shareText(game, emoji, window.location.origin);
      report('daily_shared');
      try {
        if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent || '')) {
          await navigator.share({ text });
          return;
        }
        await navigator.clipboard.writeText(text);
        note.textContent = 'Result copied. Paste it anywhere; it does not give the answer away.';
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        note.textContent = text;
      }
      button.blur();
    }

    async function addToLibrary(button, note) {
      button.disabled = true;
      note.textContent = 'Adding…';
      try {
        const response = await fetch('/api/daily/add', {
          method: 'POST', credentials: 'same-origin', headers: authHeaders(), body: JSON.stringify({ id: game.answer.id }),
        });
        if (response.status === 401) {
          window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
          return;
        }
        if (!response.ok) throw new Error(String(response.status));
        const result = await response.json();
        button.textContent = result.state === 'created' ? 'Added ✓' : 'In your library ✓';
        note.textContent = result.state === 'created' ? `Added “${result.title}” to your library. ` : `“${result.title}” is already in your library. `;
        const href = safeUrl(result.library_url);
        if (href) {
          const link = el('a', '', 'Open it');
          link.href = href;
          note.appendChild(link);
        }
      } catch (error) {
        button.disabled = false;
        note.textContent = 'Could not add it right now. Try again in a moment.';
      }
    }

    function saveForGuest(button, note) {
      const answer = game.answer;
      const list = window.OmniGuestList;
      if (!list || !KINDS.has(answer.kind) || !SLUG.test(answer.slug || '')) {
        note.textContent = 'Create a free library to keep it.';
        return;
      }
      const result = list.add(answer.kind, answer.slug, answer.title);
      const saved = list.read().some(item => item.kind === answer.kind && item.slug === answer.slug);
      button.textContent = saved ? 'Saved to your list ✓' : 'Save to my list';
      button.disabled = saved;
      note.textContent = '';
      if (saved) {
        note.appendChild(document.createTextNode('Saved in this browser. '));
        const link = el('a', '', 'Create a free account');
        link.href = '/#signup';
        note.appendChild(link);
        note.appendChild(document.createTextNode(' and it moves into your new library.'));
      } else {
        note.textContent = result && result.full ? 'Your list is full (30 titles).' : 'This browser could not save your list.';
      }
    }

    function renderResult() {
      if (!game.done || !game.answer) {
        resultBox.hidden = true;
        form.hidden = false;
        return;
      }
      form.hidden = true;
      const answer = game.answer;
      resultBox.textContent = '';
      const tries = game.guesses.length;
      resultBox.appendChild(el('p', `dy-result__verdict ${game.won ? 'is-won' : 'is-lost'}`, game.won
        ? (tries === 1 ? 'First try. Impressive.' : `You got it in ${tries}.`)
        : 'Not this time. The answer was:'));
      const card = el('div', 'dy-answer-card');
      const image = safeUrl(answer.image, true);
      if (image) {
        const art = el('img', 'dy-answer-card__art');
        art.src = image;
        art.alt = '';
        art.width = 100;
        art.height = 150;
        art.loading = 'lazy';
        art.referrerPolicy = 'no-referrer';
        card.appendChild(art);
      }
      const text = el('div', 'dy-answer-card__text');
      text.appendChild(el('h2', '', answer.title));
      text.appendChild(el('p', 'eyebrow', [answer.label, answer.year, answer.creator].filter(Boolean).join(' · ')));
      if (answer.note) text.appendChild(el('p', '', answer.note));
      card.appendChild(text);
      resultBox.appendChild(card);

      const actions = el('div', 'dy-row dy-actions');
      const note = el('p', 'dy-status');
      note.setAttribute('role', 'status');
      const shareButton = el('button', 'button', 'Share my result');
      shareButton.type = 'button';
      shareButton.addEventListener('click', () => share(shareButton, note));
      actions.appendChild(shareButton);
      const keep = el('button', 'button button--ghost', signedIn ? 'Add to my library' : 'Save to my list');
      keep.type = 'button';
      keep.addEventListener('click', () => (signedIn ? addToLibrary(keep, note) : saveForGuest(keep, note)));
      actions.appendChild(keep);
      const titleUrl = safeUrl(answer.title_url);
      if (titleUrl) {
        const link = el('a', 'button button--ghost', 'What members think');
        link.href = titleUrl;
        actions.appendChild(link);
      }
      resultBox.appendChild(actions);
      resultBox.appendChild(note);
      const preview = el('pre', 'dy-share-preview', shareText(game, emoji, window.location.origin));
      preview.setAttribute('aria-label', 'Your result');
      resultBox.appendChild(preview);
      resultBox.appendChild(statBlock());
      if (isToday && nextSeconds) {
        const next = el('p', 'dy-next');
        next.appendChild(document.createTextNode('Next puzzle in '));
        const clock = el('strong', '', countdown(nextSeconds));
        next.appendChild(clock);
        resultBox.appendChild(next);
        const timer = setInterval(() => {
          const left = nextSeconds - (Date.now() - loadedAt) / 1000;
          if (left <= 0) {
            clearInterval(timer);
            next.textContent = 'A new puzzle is ready. ';
            const link = el('a', '', 'Play it');
            link.href = '/daily';
            next.appendChild(link);
            return;
          }
          clock.textContent = countdown(left);
        }, 1000);
      } else {
        const next = el('p', 'dy-next');
        const link = el('a', '', 'Play today’s puzzle →');
        link.href = '/daily';
        next.appendChild(link);
        resultBox.appendChild(next);
      }
      resultBox.hidden = false;
    }

    function render() {
      renderClues();
      renderHistory();
      renderResult();
    }

    async function submit(text) {
      if (busy || game.done) return;
      if (text && alreadyTried(game, text)) {
        status.textContent = 'You already tried that one.';
        return;
      }
      busy = true;
      status.textContent = text ? 'Checking…' : 'Getting the next clue…';
      try {
        const response = await fetch(`/api/daily/${number}/guess`, {
          method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
          body: JSON.stringify({ guess: text, attempt: game.guesses.length }),
        });
        if (!response.ok) throw new Error(String(response.status));
        const result = await response.json();
        if (!game.guesses.length) game.daily = isToday;
        applyResult(game, text, result);
        save();
        input.value = '';
        status.textContent = game.done ? '' : text ? `Not “${text}”. Here is another clue.` : 'Here is another clue.';
        render();
        if (game.done) resultBox.focus();
        else input.focus();
      } catch (error) {
        status.textContent = 'Could not check that guess. Try again in a moment.';
      } finally {
        busy = false;
      }
    }

    form.addEventListener('submit', event => {
      event.preventDefault();
      const text = input.value.trim();
      if (text) submit(text);
    });
    skip.addEventListener('click', () => submit(''));

    // Suggestions from titles members track, the puzzle's own format first.
    const datalist = tool.querySelector('#dailySuggestions');
    let timer = null;
    let lastQuery = '';
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2 || query === lastQuery) return;
      timer = setTimeout(async () => {
        lastQuery = query;
        try {
          const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query)}`, { headers: { Accept: 'application/json' } });
          if (!response.ok) return;
          const data = await response.json();
          const results = (data && Array.isArray(data.results) ? data.results : [])
            .sort((a, b) => (a.kind === kind ? 0 : 1) - (b.kind === kind ? 0 : 1));
          datalist.textContent = '';
          const seen = new Set();
          results.forEach(result => {
            if (typeof result.title !== 'string' || seen.has(result.title.toLowerCase())) return;
            seen.add(result.title.toLowerCase());
            const option = el('option');
            option.value = result.title;
            datalist.appendChild(option);
          });
        } catch (error) { /* suggestions are optional */ }
      }, 200);
    });

    // On archive pages, finishing the game also opens the answer section.
    const spoiler = document.querySelector('[data-daily-spoiler]');
    if (spoiler && game.done) spoiler.open = true;

    render();
  }

  const api = { normalizeStore, newGame, applyResult, alreadyTried, squares, shareText, stats, countdown, simplify, KEY };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document && document.addEventListener) {
    const start = () => {
      const tool = document.getElementById('dailyTool');
      if (tool) setup(tool);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }
})();
