// Compare tastes (/u/<name>/match): rate a few of a member's titles and see how close
// your taste is. On the dashboard, the same file moves a visitor's answers into their
// new library after sign-up. Server text is only ever set as textContent.
(function () {
  'use strict';

  const KEY = 'omnitrackr_taste_compare';
  const ANSWERS = new Set(['loved', 'liked', 'meh', 'want', 'skip']);
  const RATED = new Set(['loved', 'liked', 'meh']);
  const ID = /^[a-z-]{4,12}:\d{1,10}$/;
  const LABELS = { loved: 'Loved it', liked: 'Liked it', meh: 'Not for me', want: 'Want to try' };
  const LOADERS = ['loadMovies', 'loadTVShows', 'loadAnime', 'loadVideoGames', 'loadMusic', 'loadBooks', 'loadManga', 'loadPodcasts', 'loadAudiobooks'];

  // ------------------------------------------------------------ storage
  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!data || typeof data !== 'object' || !Number.isInteger(data.owner) || data.owner < 1) return null;
      const answers = {};
      Object.entries(data.answers || {}).forEach(([id, answer]) => {
        if (ID.test(id) && ANSWERS.has(answer)) answers[id] = answer;
      });
      const name = typeof data.name === 'string' ? data.name.slice(0, 50) : '';
      const link = typeof data.link === 'string' && data.link.startsWith('/u/') ? data.link : '';
      return { owner: data.owner, name, link, answers, pending: data.pending === true };
    } catch (error) {
      return null;
    }
  }

  function write(state) {
    try {
      if (state) localStorage.setItem(KEY, JSON.stringify(state));
      else localStorage.removeItem(KEY);
    } catch (error) { /* private mode: the comparison still works for this visit */ }
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

  async function request(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', headers: authHeaders(), ...options });
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    return { ok: response.ok, status: response.status, data };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function rating(value) {
    return Number.isInteger(value) ? String(value) : Number(value).toFixed(1);
  }

  function plural(count, one, many) {
    return `${count} ${count === 1 ? one : many}`;
  }

  function meta(item) {
    const parts = [item.label];
    if (item.year) parts.push(String(item.year));
    if (item.creator) parts.push(item.creator);
    return parts.join(' · ');
  }

  function art(item, className) {
    if (!item.image) return el('div', `${className} ${className}--empty`, (item.title || '?').slice(0, 1).toUpperCase());
    const img = el('img', className);
    img.src = item.image;
    img.alt = '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.addEventListener('error', () => img.replaceWith(el('div', `${className} ${className}--empty`, (item.title || '?').slice(0, 1).toUpperCase())), { once: true });
    return img;
  }

  // ------------------------------------------------------------ result
  function scoreBlock(data, line) {
    const head = el('div', 'compare-score');
    const hasScore = data.score !== null && data.score !== undefined;
    const dial = el('div', `compare-score__dial${hasScore ? '' : ' compare-score__dial--empty'}`, hasScore ? `${data.score}%` : '?');
    dial.setAttribute('aria-hidden', 'true');
    if (hasScore) dial.style.setProperty('--compare-score', String(data.score));
    const copy = el('div', 'compare-score__copy');
    copy.appendChild(el('p', 'compare-score__tier', hasScore ? `${data.tier} · ${data.score}%` : 'Not enough to go on yet'));
    copy.appendChild(el('p', 'compare-score__line', line));
    head.append(dial, copy);
    return head;
  }

  function section(title, items, detail) {
    if (!items || !items.length) return null;
    const wrap = el('section', 'compare-section');
    wrap.appendChild(el('h3', 'compare-section__title', title));
    const list = el('ul', 'compare-list');
    items.forEach(item => {
      const row = el('li', 'compare-item');
      row.appendChild(art(item, 'compare-item__art'));
      const copy = el('div', 'compare-item__copy');
      copy.append(el('span', 'compare-item__title', item.title), el('span', 'compare-item__meta', meta(item)));
      row.appendChild(copy);
      const text = detail(item);
      if (text) row.appendChild(el('span', 'compare-item__ratings', text));
      list.appendChild(row);
    });
    wrap.appendChild(list);
    return wrap;
  }

  function shareText(score, name) {
    return score === null || score === undefined
      ? `How does your taste compare with ${name}'s? Find out on OmniTrackr:`
      : `I'm a ${score}% taste match with ${name} on OmniTrackr. How about you?`;
  }

  async function shareResult(button, text, path) {
    const url = new URL(path, window.location.origin).href;
    report('compare_shared');
    if (navigator.share) {
      try { await navigator.share({ title: 'Compare tastes on OmniTrackr', text, url }); return; } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(`${text} ${url}`);
      const original = button.textContent;
      button.textContent = 'Copied ✓';
      setTimeout(() => { button.textContent = original; }, 2200);
    } catch (error) {
      window.prompt('Copy this:', `${text} ${url}`);
    }
  }

  function guestSummary(data, name) {
    if (data.score === null || data.score === undefined) {
      const more = data.needed_for_score || 1;
      return `Rate ${plural(more, 'more title', 'more titles')} you've seen to get a score with ${name}.`;
    }
    return `Based on ${plural(data.rated_count, 'title', 'titles')} you've both seen.`;
  }

  function memberSummary(data, name) {
    if (data.score !== null && data.score !== undefined) {
      return `You share ${plural(data.shared_count, 'title', 'titles')} with ${name}, and both rated ${data.rated_count}.`;
    }
    if (!data.shared_count) return `Nothing in common with ${name} yet. Rate a few of their titles to get a score.`;
    return `You share ${plural(data.shared_count, 'title', 'titles')}. ` +
      `Rate ${plural(data.needed_for_score, 'more', 'more')} you both have to see a score.`;
  }

  function renderGuest(root, data, ctx) {
    const name = ctx.name;
    root.replaceChildren();
    root.appendChild(el('p', 'site-eyebrow', `You and ${name}`));
    root.appendChild(scoreBlock(data, guestSummary(data, name)));
    [
      section('You agree on', data.agreed, item => `You: ${item.your_label} · ${name}: ${rating(item.their_rating)}/10`),
      section('Where you split', data.disagreements, item => `You: ${item.your_label} · ${name}: ${rating(item.their_rating)}/10`),
      section(`${name}'s favorites to try next`, data.their_picks, item => `${name}: ${rating(item.their_rating)}/10`),
    ].filter(Boolean).forEach(part => root.appendChild(part));

    const save = el('div', 'compare-save site-card');
    save.appendChild(el('h3', null, 'Keep your answers'));
    const saved = answerList(ctx.answers).length;
    save.appendChild(el('p', null, saved
      ? `Make a free library and the ${plural(saved, 'title', 'titles')} you just rated go straight into it. Then you can compare with anyone's whole library, not just this deck.`
      : 'Make a free library, rate what you finish, and compare with anyone\'s whole library.'));
    const actions = el('div', 'compare-save__actions');
    const join = el('a', 'site-btn site-btn--primary', 'Save my answers, free');
    join.href = '/#signup';
    join.addEventListener('click', () => report('compare_signup_clicked'));
    const share = el('button', 'site-btn site-btn--ghost', 'Share my result');
    share.type = 'button';
    share.addEventListener('click', () => shareResult(share, shareText(data.score, name), ctx.link));
    actions.append(join, share);
    save.appendChild(actions);
    root.appendChild(save);
    root.appendChild(restartButton(ctx));
  }

  function renderMember(root, data, ctx, added) {
    const name = ctx.name;
    root.replaceChildren();
    root.appendChild(el('p', 'site-eyebrow', `You and ${name}`));
    root.appendChild(scoreBlock(data, memberSummary(data, name)));
    if (added) root.appendChild(el('p', 'compare-note', `Added ${plural(added, 'title', 'titles')} to your library.`));
    const overlap = (data.categories || []).filter(category => category.shared > 0);
    if (overlap.length) {
      const chips = el('p', 'compare-chips');
      overlap.forEach(category => chips.appendChild(el('span', 'compare-chip', `${category.label} ${category.shared}`)));
      root.appendChild(chips);
    }
    [
      section('You both loved', data.both_loved, item => `You ${rating(item.your_rating)} · ${name} ${rating(item.their_rating)}`),
      section('Where you split', data.disagreements, item => `You ${rating(item.your_rating)} · ${name} ${rating(item.their_rating)}`),
      section(`${name}'s favorites you haven't tracked`, data.their_picks, item => `${name} ${rating(item.their_rating)}`),
      section(`Worth telling ${name} about`, data.your_picks, item => `You ${rating(item.your_rating)}`),
    ].filter(Boolean).forEach(part => root.appendChild(part));
    if (data.private_categories && data.private_categories.length) {
      root.appendChild(el('p', 'compare-note', `${name} keeps ${data.private_categories.join(', ')} private, so those are left out.`));
    }
    const actions = el('div', 'compare-save__actions');
    const share = el('button', 'site-btn site-btn--ghost', 'Share my result');
    share.type = 'button';
    share.addEventListener('click', () => shareResult(share, shareText(data.score, name), ctx.link));
    const profile = el('a', 'site-btn site-btn--ghost', `${name}'s profile`);
    profile.href = ctx.profile;
    actions.append(share, profile);
    root.appendChild(actions);
  }

  function restartButton(ctx) {
    const again = el('button', 'compare-link', 'Rate them again');
    again.type = 'button';
    again.dataset.compareAction = 'restart';
    return again;
  }

  // ------------------------------------------------------------ the deck
  function setupCompare(root) {
    let cards = [];
    try { cards = JSON.parse((root.querySelector('#compareDeck') || {}).textContent || '[]'); } catch (error) { cards = []; }
    if (!Array.isArray(cards)) cards = [];
    const ctx = {
      owner: Number(root.dataset.ownerId),
      name: root.dataset.ownerName || 'them',
      link: root.dataset.link || window.location.pathname,
      profile: root.dataset.profile || '/',
      signedIn: root.dataset.signedIn === 'true',
      minAnswers: Number(root.dataset.minAnswers) || 3,
      answers: {},
    };
    const stored = read();
    if (!ctx.signedIn && stored && stored.owner === ctx.owner) ctx.answers = { ...stored.answers };
    let index = 0;
    const screens = {};
    root.querySelectorAll('[data-compare-screen]').forEach(node => { screens[node.dataset.compareScreen] = node; });
    const q = selector => root.querySelector(selector);

    function show(name) {
      Object.entries(screens).forEach(([key, node]) => { node.hidden = key !== name; });
      if (name === 'result' && screens.result) {
        screens.result.focus({ preventScroll: true });
        screens.result.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    }

    function ratedCount() {
      return Object.values(ctx.answers).filter(answer => RATED.has(answer)).length;
    }

    function drawCard() {
      const card = cards[index];
      const holder = q('[data-compare-card]');
      if (!card || !holder) return;
      holder.replaceChildren(art(card, 'compare-card__art'));
      const copy = el('div', 'compare-card__copy');
      copy.appendChild(el('p', 'compare-card__label', meta(card)));
      copy.appendChild(el('h2', 'compare-card__title', card.title));
      const previous = ctx.answers[card.id];
      if (previous && previous !== 'skip') copy.appendChild(el('p', 'compare-card__previous', `Your answer: ${LABELS[previous]}`));
      holder.appendChild(copy);
      const bar = q('[data-compare-bar]');
      if (bar) bar.style.width = `${Math.round((index / cards.length) * 100)}%`;
      const count = q('[data-compare-count]');
      if (count) count.textContent = `${index + 1} of ${cards.length}`;
      const back = q('[data-compare-action="back"]');
      if (back) back.disabled = index === 0;
      const finish = q('[data-compare-action="finish"]');
      if (finish) finish.hidden = ratedCount() < ctx.minAnswers;
    }

    function persist() {
      if (ctx.signedIn) return;
      write({ owner: ctx.owner, name: ctx.name, link: ctx.link, answers: ctx.answers, pending: answerList(ctx.answers).length > 0 });
    }

    async function finish() {
      const result = screens.result;
      if (!result) return;
      show('result');
      result.replaceChildren(el('p', 'compare-loading', `Lining you up with ${ctx.name}…`));
      const answers = answerList(ctx.answers);
      const base = typeof API_BASE === 'string' ? API_BASE : '';
      try {
        if (ctx.signedIn) {
          const { ok, data } = await request(`${base}/api/taste-match/u/${ctx.owner}/answers`, {
            method: 'POST', body: JSON.stringify({ answers, source: 'deck' }),
          });
          if (!ok || !data || !data.match) throw new Error('save failed');
          renderMember(result, data.match, ctx, (data.added || []).length);
        } else {
          const { ok, data } = await request(`${base}/api/taste-match/u/${ctx.owner}/guess`, {
            method: 'POST', body: JSON.stringify({ answers }),
          });
          if (!ok || !data) throw new Error('guess failed');
          renderGuest(result, data, ctx);
        }
      } catch (error) {
        result.replaceChildren(el('p', 'compare-note', 'Something went wrong working out your match. Give it another try in a moment.'));
        result.appendChild(restartButton(ctx));
      }
    }

    function answer(value) {
      const card = cards[index];
      if (!card || !ANSWERS.has(value)) return;
      ctx.answers[card.id] = value;
      persist();
      if (index + 1 >= cards.length) { finish(); return; }
      index += 1;
      drawCard();
    }

    async function loadLibrary() {
      const box = q('[data-compare-library]');
      if (!ctx.signedIn || !box) return;
      const base = typeof API_BASE === 'string' ? API_BASE : '';
      try {
        const { ok, data } = await request(`${base}/api/taste-match/u/${ctx.owner}`);
        if (!ok || !data) return;
        renderMember(box, data, ctx, 0);
        box.hidden = false;
      } catch (error) { /* the deck still works */ }
    }

    function updateIntro() {
      const lead = q('[data-compare-intro-lead]');
      if (!lead) return;
      if (!cards.length) {
        lead.textContent = ctx.signedIn
          ? `You already track every title in ${ctx.name}'s deck, so your score comes from your libraries.`
          : `${ctx.name} hasn't rated enough titles to compare with yet.`;
        return;
      }
      const done = Object.keys(ctx.answers).filter(id => cards.some(card => card.id === id)).length;
      lead.textContent = done && !ctx.signedIn
        ? `You've answered ${done} of ${cards.length} already. Pick up where you left off.`
        : ctx.signedIn
          ? `Rate ${plural(cards.length, 'title', 'titles')} of ${ctx.name}'s you haven't tracked. Your answers go into your library.`
          : `${plural(cards.length, 'title', 'titles')} to rate. Skip anything you haven't seen; ${ctx.minAnswers} answers are enough for a score.`;
    }

    root.addEventListener('click', event => {
      const target = event.target.closest('[data-compare-answer], [data-compare-action]');
      if (!target || !root.contains(target)) return;
      if (target.dataset.compareAnswer) { answer(target.dataset.compareAnswer); return; }
      const action = target.dataset.compareAction;
      if (action === 'start') {
        const next = cards.findIndex(card => !ctx.answers[card.id]);
        index = next >= 0 ? next : 0;
        show('play');
        drawCard();
      } else if (action === 'back' && index > 0) {
        index -= 1;
        drawCard();
      } else if (action === 'finish') {
        finish();
      } else if (action === 'restart') {
        ctx.answers = {};
        persist();
        index = 0;
        show('play');
        drawCard();
      }
    });
    document.addEventListener('keydown', event => {
      if (!screens.play || screens.play.hidden || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) return;
      const keys = { 1: 'loved', 2: 'liked', 3: 'meh', 4: 'want', 5: 'skip' };
      if (keys[event.key]) { event.preventDefault(); answer(keys[event.key]); }
    });
    updateIntro();
    loadLibrary();
  }

  // ------------------------------------------------------------ owner's link
  function setupOwner() {
    const input = document.getElementById('compareLink');
    if (!input) return;
    const copy = document.querySelector('[data-compare-copy]');
    if (copy) copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(input.value); } catch (error) { input.select(); }
      copy.textContent = 'Copied ✓';
      setTimeout(() => { copy.textContent = 'Copy link'; }, 2200);
    });
    const share = document.querySelector('[data-compare-share-link]');
    if (share) share.addEventListener('click', () => shareResult(share, 'How does your taste compare with mine? Find out on OmniTrackr:', new URL(input.value).pathname));
  }

  // ------------------------------------------------------------ after sign-up
  function signedInDashboard() {
    if (document.documentElement.dataset.publicShell === 'true') return false;
    // The start page (/start) is only ever served to a signed-in member.
    if (typeof document.getElementById === 'function' && document.getElementById('startFlow')) return true;
    if (!document.getElementById('mainContainer')) return false;
    try { return typeof getUser === 'function' && !!getUser(); } catch (error) { return false; }
  }

  function toast(message, href, linkText) {
    const node = el('div', 'guest-import-toast', message);
    node.setAttribute('role', 'status');
    if (href) {
      const link = el('a', null, linkText);
      link.href = href;
      node.append(' ', link);
    }
    document.body.appendChild(node);
    setTimeout(() => node.remove(), 9000);
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
      const { ok, status, data } = await request(`${base}/api/taste-match/u/${state.owner}/answers`, {
        method: 'POST', body: JSON.stringify({ answers, source: 'guest' }),
      });
      if (!ok) {
        // The link was switched off, or it's the member's own link: nothing to move.
        if ([400, 404, 422].includes(status)) write(null);
        return null;
      }
      write(null);
      const added = (data && data.added || []).length;
      if (added) {
        const match = data.match || {};
        const score = match.score !== null && match.score !== undefined ? ` You're a ${match.score}% match with ${state.name}.` : '';
        toast(`Added ${plural(added, 'title', 'titles')} from comparing tastes.${score}`, state.link || null, 'See the full comparison');
        LOADERS.forEach(name => { if (typeof window[name] === 'function') { try { window[name](); } catch (error) { /* ignore */ } } });
      }
      return data;
    } catch (error) {
      return null; // Try again next visit.
    } finally {
      importing = false;
    }
  }

  // The dashboard may still be restoring the session, or the visitor may log in without a reload.
  function waitForMember(attempt) {
    const state = read();
    if (!state || !state.pending) return;
    if (signedInDashboard()) { importAnswers(); return; }
    if (attempt < 30) setTimeout(() => waitForMember(attempt + 1), 2000);
  }

  function init() {
    const root = document.getElementById('tasteCompare');
    if (root) setupCompare(root);
    setupOwner();
    if (!root && !document.getElementById('compareLink')) waitForMember(0);
  }

  const api = { read, write, answerList, importAnswers, KEY };
  window.OmniTasteCompare = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
