// Rankings: "which did you like more?" about two finished titles at a time, so a member's films, books,
// games and the rest fall into order (app/rankings.py). Three places use it: the home card (a title
// finished this week first), the Rankings tab (the whole ranking, by hand too) and a dialog the finish
// ritual opens. The server picks every question and checks every answer. Server text is only ever set
// as textContent, and links only ever point at this site.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 60 * 1000;
  const HIDE_DAYS = 7;
  const HIDE_KEY = 'omnitrackr_rankings_hidden';
  const SEEN_KEY = 'omnitrackr_rankings_seen';
  const FORMAT_KEY = 'omnitrackr_rankings_format';
  const WAITING_SHOWN = 24;
  const state = {
    epoch: 0, card: null, request: null, loadedAt: 0, observer: null, seenDay: '',
    homeBusy: false, homePlaced: null,
    tab: null, tabCategory: '', tabRequest: 0, tabSeen: false, waitingAll: false,
    dialogCategory: '', dialogReturn: null, focusShare: false,
  };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  const localPath = url => typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/\\');
  const httpsImage = url => typeof url === 'string' && url.startsWith('https://');

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  // Resolves to { ok, status, data }. A 409 carries the question that is current now.
  async function call(method, path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method,
      headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    return { ok: response.ok, status: response.status, data };
  }

  function problem(result) {
    const detail = Array.isArray(result.data?.detail) ? result.data.detail[0]?.msg : result.data?.detail;
    return typeof detail === 'string' && detail ? detail : 'That didn’t work. Please try again.';
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(className, text, onClick, label) {
    const node = el('button', className, text);
    node.type = 'button';
    if (label) node.setAttribute('aria-label', label);
    node.addEventListener('click', event => onClick(event.currentTarget));
    return node;
  }

  function plural(count, singular, many) {
    return `${count} ${count === 1 ? singular : many}`;
  }

  function art(item, className) {
    const box = el('span', className);
    box.setAttribute('aria-hidden', 'true');
    if (httpsImage(item.image)) {
      const img = document.createElement('img');
      img.src = item.image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('error', () => { img.remove(); box.textContent = (item.title || '?').slice(0, 1).toUpperCase(); }, { once: true });
      box.appendChild(img);
    } else {
      box.textContent = (item.title || '?').slice(0, 1).toUpperCase();
    }
    return box;
  }

  function meta(item) {
    return [item.year, item.creator].filter(Boolean).join(' · ');
  }

  function setStatus(id, text) {
    const node = $(id);
    if (!node) return;
    node.classList.remove('rank-status--sr');
    node.textContent = text || '';
  }

  // Said to screen readers only: the same words are already on screen, bigger.
  function announce(id, text) {
    const node = $(id);
    if (!node) return;
    node.classList.add('rank-status--sr');
    node.textContent = text || '';
  }

  function count(where) {
    call('POST', '/api/rankings/seen', { where }).catch(() => {});
  }

  // ------------------------------------------------------------------ the question

  // One question: the title being placed on the left, the one it's measured against on the right.
  // `options.onResult(body)` gets {question} or {placed}; a 409 renders the current question instead.
  function duel(question, options) {
    const wrap = el('div', 'rank-duel');
    wrap.dataset.category = question.category;
    const pair = el('div', 'rank-duel__pair');
    const busy = { on: false };

    async function choose(choice, pressed) {
      if (busy.on) return;
      busy.on = true;
      wrap.classList.add('is-busy');
      wrap.setAttribute('aria-busy', 'true');
      if (pressed) pressed.classList.add('is-chosen');
      wrap.querySelectorAll('button').forEach(node => { node.disabled = true; });
      try {
        const result = await call('POST', '/api/rankings/answer', {
          category: question.category, placing_id: question.placing.id, against_id: question.against.id,
          choice, source: options.source,
        });
        if (result.ok) {
          options.onResult(result.data);
          return;
        }
        if (result.status === 409) {
          options.onResult({ question: result.data.question || null, stale: true });
          return;
        }
        options.onError(problem(result));
      } catch (error) {
        options.onError('Couldn’t reach OmniTrackr. Check your connection and try again.');
      }
      busy.on = false;
      wrap.classList.remove('is-busy');
      wrap.removeAttribute('aria-busy');
      if (pressed) pressed.classList.remove('is-chosen');
      wrap.querySelectorAll('button').forEach(node => { node.disabled = false; });
    }

    function side(item, choice, tag) {
      const pick = el('button', `rank-pick rank-pick--${choice}`);
      pick.type = 'button';
      pick.dataset.choice = choice;
      const words = [item.title, item.year].filter(Boolean).join(', ');
      pick.setAttribute('aria-label', `${words}. ${tag}. I liked this one more.`);
      pick.appendChild(art(item, 'rank-pick__art'));
      const copy = el('span', 'rank-pick__copy');
      copy.appendChild(el('span', 'rank-pick__tag', tag));
      copy.appendChild(el('strong', 'rank-pick__title', item.title));
      const line = meta(item);
      if (line) copy.appendChild(el('span', 'rank-pick__meta', line));
      if (item.score) copy.appendChild(el('span', 'rank-pick__score', `You scored it ${item.score}`));
      pick.appendChild(copy);
      pick.addEventListener('click', () => choose(choice, pick));
      return pick;
    }

    const placingTag = question.ranked ? 'Placing now' : 'First pick';
    const againstTag = question.against.position ? `Your #${question.against.position}` : 'Also finished';
    pair.append(side(question.placing, 'placing', placingTag), el('span', 'rank-duel__vs', 'or'), side(question.against, 'against', againstTag));
    pair.querySelector('.rank-duel__vs').setAttribute('aria-hidden', 'true');
    wrap.appendChild(pair);

    const foot = el('div', 'rank-duel__foot');
    foot.appendChild(button('rank-btn rank-btn--quiet', 'Too close to call', node => choose('tie', node)));
    foot.appendChild(button('rank-btn rank-btn--quiet', 'Skip this one', async node => {
      node.disabled = true;
      try {
        const result = await call('POST', '/api/rankings/skip', { category: question.category, item_id: question.placing.id });
        if (result.ok) options.onResult({ question: result.data.question || null, skipped: true });
        else { options.onError(problem(result)); node.disabled = false; }
      } catch (error) {
        options.onError('Couldn’t reach OmniTrackr. Check your connection and try again.');
        node.disabled = false;
      }
    }, `Skip ${question.placing.title} for now`));
    const left = Number(question.left) || 0;
    const progress = el('span', 'rank-duel__left');
    if (question.ranked) {
      progress.textContent = left <= 1 ? 'Last pick for this one' : `About ${left} more picks`;
      const dots = el('span', 'rank-duel__dots');
      dots.setAttribute('aria-hidden', 'true');
      const done = Math.max(0, (Number(question.step) || 1) - 1);
      for (let i = 0; i < Math.min(10, done + left); i += 1) dots.appendChild(el('i', i < done ? 'is-done' : ''));
      progress.prepend(dots);
    } else {
      progress.textContent = 'Your first pick starts the list';
    }
    foot.appendChild(progress);
    wrap.appendChild(foot);

    // Arrow keys pick a side while the question has focus (the buttons work with Tab and Enter too).
    wrap.addEventListener('keydown', event => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.key === 'ArrowLeft' ? 'placing' : event.key === 'ArrowRight' ? 'against' : '';
      if (!target) return;
      const pick = wrap.querySelector(`.rank-pick--${target}`);
      if (!pick || pick.disabled) return;
      event.preventDefault();
      pick.focus();
      choose(target, pick);
    });
    return wrap;
  }

  // ------------------------------------------------------------------ sharing a top ten (/ranked/<token>)

  function countFunnel(event) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting only */ }
  }

  const sharePath = path => typeof path === 'string' && /^\/ranked\/[A-Za-z0-9_-]{16,32}$/.test(path);

  async function shareLink(path, title, statusId) {
    if (!sharePath(path)) return;
    const url = `${window.location.origin}${path}`;
    countFunnel('rank_link_shared');
    if (navigator.share) {
      try { await navigator.share({ title, url }); return; } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setStatus(statusId, 'Link copied. Paste it anywhere.');
    } catch (error) {
      window.prompt('Copy this link:', url);
    }
  }

  async function saveStory(path, category, statusId, node) {
    if (!sharePath(path)) return;
    if (node) node.disabled = true;
    setStatus(statusId, 'Getting your image ready…');
    try {
      const response = await fetch(`${path}/story.png`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(String(response.status));
      const blob = await response.blob();
      const name = `omnitrackr-top-${category || 'ten'}.png`;
      const file = typeof File === 'function' ? new File([blob], name, { type: 'image/png' }) : null;
      countFunnel('rank_link_shared');
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        try { await navigator.share({ files: [file] }); setStatus(statusId, ''); } catch (error) {
          setStatus(statusId, error && error.name === 'AbortError' ? '' : 'Sharing didn’t open. Please try again.');
        }
      } else {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 4000);
        setStatus(statusId, 'Image saved. It’s sized for stories.');
      }
    } catch (error) {
      setStatus(statusId, 'The image didn’t load. Please try again.');
    }
    if (node) node.disabled = false;
  }

  // A title that lands in the top ten offers the link: straight to the share sheet when there is one,
  // otherwise to the Rankings tab, where the link is made.
  function shareAction(placed, statusId, before, here) {
    if (!placed || placed.position > 10 || placed.total < 3) return null;
    return button('rank-btn rank-btn--quiet', 'Share your top ten', () => {
      if (before) before();
      if (sharePath(placed.shared)) { shareLink(placed.shared, `My top ten ${placed.nouns}`, statusId); return; }
      const box = $('rankShare');
      if (here && box && !box.hidden) {
        if (box.scrollIntoView) box.scrollIntoView({ block: 'center', behavior: 'smooth' });
        box.querySelector('button')?.focus({ preventScroll: true });
        return;
      }
      state.focusShare = true;
      openTab(placed.category);
    });
  }

  function renderShare(detail) {
    const box = $('rankShare');
    if (!box) return;
    if (!detail || detail.ranked.length < 3) { box.hidden = true; box.replaceChildren(); return; }
    const share = detail.share || {};
    box.hidden = false;
    const copy = el('div', 'rank-share__copy');
    const row = el('div', 'rank-share__actions');
    if (sharePath(share.path)) {
      copy.appendChild(el('p', 'rank-share__title', `Your top ten ${detail.nouns} are shared by link`));
      const opened = Number(share.opened) || 0;
      copy.appendChild(el('p', 'rank-share__text', `Anyone with it sees your current top ten in order, never your scores, and can rank the same ten to see how much you agree.${opened ? ` Opened ${plural(opened, 'time', 'times')} so far.` : ''}`));
      row.appendChild(button('rank-btn rank-btn--primary rank-btn--small', navigator.share ? 'Share link' : 'Copy link',
        () => shareLink(share.path, `My top ten ${detail.nouns}`, 'rankShareStatus')));
      row.appendChild(button('rank-btn rank-btn--small', 'Save image for stories', node => saveStory(share.path, detail.category, 'rankShareStatus', node)));
      const open = el('a', 'rank-link', 'See the page');
      open.href = share.path;
      open.target = '_blank';
      open.rel = 'noopener';
      row.appendChild(open);
      row.appendChild(button('rank-link rank-link--button', 'Turn the link off', async node => {
        node.disabled = true;
        const result = await call('POST', '/api/rankings/share/off', { category: detail.category }).catch(() => null);
        node.disabled = false;
        if (!result || !result.ok) { setStatus('rankShareStatus', result ? problem(result) : 'Couldn’t reach OmniTrackr.'); return; }
        detail.share = result.data.share;
        renderShare(detail);
        setStatus('rankShareStatus', 'The link is off. Anyone who opens it now sees that it isn’t shared anymore.');
      }));
    } else if (share.allowed === false) {
      copy.appendChild(el('p', 'rank-share__title', `Share your top ten ${detail.nouns}`));
      copy.appendChild(el('p', 'rank-share__text', 'This shelf is hidden or private, so it can’t have a share link. You can change that in Settings, under Privacy.'));
    } else {
      copy.appendChild(el('p', 'rank-share__title', `Share your top ten ${detail.nouns}`));
      copy.appendChild(el('p', 'rank-share__text', 'Get a link that shows your top ten in order, never your scores. Friends can rank the same ten themselves and see how close they are to you. It works without a public profile, and you can turn it off any time.'));
      row.appendChild(button('rank-btn rank-btn--primary rank-btn--small', 'Get a share link', async node => {
        node.disabled = true;
        const result = await call('POST', '/api/rankings/share', { category: detail.category }).catch(() => null);
        node.disabled = false;
        if (!result || !result.ok) { setStatus('rankShareStatus', result ? problem(result) : 'Couldn’t reach OmniTrackr.'); return; }
        detail.share = result.data.share;
        renderShare(detail);
        setStatus('rankShareStatus', 'Your link is ready.');
        $('rankShare')?.querySelector('.rank-share__actions button')?.focus({ preventScroll: true });
      }));
    }
    const status = el('p', 'rank-status');
    status.id = 'rankShareStatus';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    box.replaceChildren(copy, ...(row.children.length ? [row] : []), status);
    if (state.focusShare) {
      state.focusShare = false;
      if (box.scrollIntoView) box.scrollIntoView({ block: 'center', behavior: 'smooth' });
      box.querySelector('button')?.focus({ preventScroll: true });
    }
  }

  // Where a title landed, with its neighbours, and what to do next.
  function placedView(placed, actions) {
    const wrap = el('div', 'rank-placed');
    const medal = el('p', `rank-placed__medal${placed.position <= 3 ? ` rank-placed__medal--${placed.position}` : ''}`);
    medal.appendChild(el('span', 'rank-placed__hash', '#'));
    medal.appendChild(el('strong', '', String(placed.position)));
    medal.setAttribute('aria-hidden', 'true');
    const copy = el('div', 'rank-placed__copy');
    const title = placed.title ? placed.title.title : 'It';
    const noun = placed.noun || 'title';
    const head = el('p', 'rank-placed__head');
    head.appendChild(el('strong', '', title));
    const nouns = placed.nouns || 'titles';
    let words;
    if (placed.total <= 1) words = ` is the first ${noun} in your ranking.`;
    else if (placed.position === 1) words = ` takes the top spot among your ${placed.total} ${nouns}.`;
    else words = ` comes in at #${placed.position} of your ${placed.total} ${nouns}.`;
    head.appendChild(document.createTextNode(words));
    copy.appendChild(head);
    const around = el('p', 'rank-placed__around');
    if (placed.above && placed.below) around.textContent = `Just below ${placed.above.title}, just above ${placed.below.title}.`;
    else if (placed.above) around.textContent = `Just below ${placed.above.title}.`;
    else if (placed.below) around.textContent = `Just above ${placed.below.title}.`;
    else around.textContent = 'Finish another and it gets company.';
    copy.appendChild(around);
    const row = el('div', 'rank-placed__actions');
    actions.forEach(action => row.appendChild(action));
    copy.appendChild(row);
    wrap.append(medal, copy);
    return wrap;
  }

  function placedWords(placed) {
    const title = placed.title ? placed.title.title : 'That title';
    return `${title} placed at number ${placed.position} of ${placed.total} ${placed.total === 1 ? placed.noun : placed.nouns}.`;
  }

  function emptyView(text, extra) {
    const box = el('div', 'rank-empty');
    box.appendChild(el('p', '', text));
    if (extra) box.appendChild(extra);
    return box;
  }

  // ------------------------------------------------------------------ the home card

  function hiddenUntil() {
    try { return Number(localStorage.getItem(HIDE_KEY)) || 0; } catch (error) { return 0; }
  }
  function hideHere() {
    try { localStorage.setItem(HIDE_KEY, String(Date.now() + HIDE_DAYS * 86400000)); } catch (error) { /* this visit only */ }
  }
  function today() {
    const now = new Date();
    return `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`;
  }

  function cardSummary(card) {
    const q = card.question;
    if (card.status === 'fresh') return `You finished ${q.placing.title} this week. A few picks put it in its place among your ${q.nouns}.`;
    if (card.status === 'placing') return `You're part-way through placing ${q.placing.title} among your ${q.nouns}.`;
    if (card.status === 'start') {
      return `Pick the one you liked more and your ${q.nouns} fall into order, two at a time. You've ${q.finished > 2 ? `got ${q.finished} to sort` : 'got two to start with'}.`;
    }
    return `${plural(q.ranked, q.noun, q.nouns)} ranked so far. Keep going and your top ten sorts itself out.`;
  }

  function renderCard(card) {
    const section = $('rankDuel');
    const body = $('rankDuelBody');
    if (!section || !body) return;
    state.card = card;
    const hidden = hiddenUntil() > Date.now();
    if (state.homePlaced) return;  // the member is reading where their last one landed
    if (!card || !card.question || hidden) {
      section.hidden = true;
      body.replaceChildren();
      return;
    }
    const q = card.question;
    section.dataset.status = card.status;
    $('rankDuelEyebrow').textContent = `Rankings · ${q.label}`;
    $('rankDuelTitle').textContent = card.status === 'fresh' ? 'Where does it rank?' : 'Which did you like more?';
    $('rankDuelSummary').textContent = cardSummary(card);
    body.replaceChildren(duel(q, { source: 'home', onResult: homeResult, onError: text => setStatus('rankDuelStatus', text) }));
    setStatus('rankDuelStatus', '');
    section.hidden = false;
    watchSeen(section);
    window.OmniHomeLayout?.schedule?.();
  }

  function homeResult(body) {
    const section = $('rankDuel');
    const target = $('rankDuelBody');
    if (!section || !target) return;
    // Answered here this visit: the home screen keeps the card out instead of tucking it away mid-game.
    section.dataset.engaged = 'true';
    if (body.question) {
      state.card = { ...(state.card || {}), status: 'placing', question: body.question };
      section.dataset.status = 'placing';
      $('rankDuelSummary').textContent = cardSummary(state.card);
      target.replaceChildren(duel(body.question, { source: 'home', onResult: homeResult, onError: text => setStatus('rankDuelStatus', text) }));
      setStatus('rankDuelStatus', body.stale ? 'That one had already moved on, so here is the current question.' : '');
      target.querySelector('.rank-pick--placing')?.focus({ preventScroll: true });
      return;
    }
    if (body.placed) {
      state.homePlaced = body.placed;
      section.dataset.status = 'placed';
      $('rankDuelTitle').textContent = 'Placed';
      $('rankDuelSummary').textContent = '';
      const next = button('rank-btn rank-btn--primary', 'Rank another', () => {
        state.homePlaced = null;
        refresh(true).then(() => $('rankDuelBody')?.querySelector('.rank-pick--placing')?.focus({ preventScroll: true }));
      });
      const all = button('rank-btn', `See all your ${body.placed.nouns}`, () => openTab(body.placed.category));
      const shared = shareAction(body.placed, 'rankDuelStatus');
      target.replaceChildren(placedView(body.placed, shared ? [next, all, shared] : [next, all]));
      announce('rankDuelStatus', placedWords(body.placed));
      next.focus({ preventScroll: true });
      if (state.tab && state.tabCategory === body.placed.category) state.tab = null;
      return;
    }
    // Skipped the last one, or nothing left to compare.
    state.homePlaced = null;
    refresh(true);
  }

  function watchSeen(section) {
    if (state.seenDay === today()) return;
    try { if (localStorage.getItem(SEEN_KEY) === today()) { state.seenDay = today(); return; } } catch (error) { /* count anyway */ }
    const report = () => {
      state.seenDay = today();
      try { localStorage.setItem(SEEN_KEY, today()); } catch (error) { /* counted once per visit then */ }
      count('home');
    };
    if (typeof IntersectionObserver !== 'function') { report(); return; }
    if (state.observer) state.observer.disconnect();
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
    if (!force && state.homePlaced) return Promise.resolve();
    // Part-way through an answer, a background refresh would swap the question under the member's finger.
    if (!force && $('rankDuelBody')?.querySelector('.rank-duel.is-busy')) return state.request || Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/rankings/card`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) renderCard(data.card); })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.card = null;
    state.request = null;
    state.loadedAt = 0;
    state.homePlaced = null;
    state.tab = null;
    state.tabCategory = '';
    state.waitingAll = false;
    if (state.observer) state.observer.disconnect();
    const section = $('rankDuel');
    if (section) { section.hidden = true; delete section.dataset.status; delete section.dataset.engaged; }
    $('rankDuelBody')?.replaceChildren();
    setStatus('rankDuelStatus', '');
  }

  // ------------------------------------------------------------------ the tab

  function storedFormat() {
    try { return localStorage.getItem(FORMAT_KEY) || ''; } catch (error) { return ''; }
  }
  function storeFormat(category) {
    try { localStorage.setItem(FORMAT_KEY, category); } catch (error) { /* remembered this visit */ }
  }

  function pickFormat(formats, wanted) {
    const usable = formats.filter(item => item.finished >= 1);
    const named = usable.find(item => item.category === wanted);
    if (named) return named.category;
    const placing = usable.find(item => item.placing);
    if (placing) return placing.category;
    const best = usable.slice().sort((a, b) => (b.waiting > 0) - (a.waiting > 0) || b.finished - a.finished)[0];
    return best ? best.category : (formats[0] ? formats[0].category : 'movies');
  }

  async function load(category) {
    if (!signedIn()) return;
    const board = $('rankBoard');
    if (!board) return;
    if (!state.tabSeen) { state.tabSeen = true; count('tab'); }
    const request = ++state.tabRequest;
    const wanted = category || state.tabCategory || storedFormat();
    board.setAttribute('aria-busy', 'true');
    try {
      const path = wanted ? `/api/rankings?category=${encodeURIComponent(wanted)}` : '/api/rankings';
      let result = await call('GET', path);
      if (result.ok && (!result.data.detail || !result.data.formats.some(item => item.category === wanted))) {
        const chosen = pickFormat(result.data.formats || [], wanted);
        result = await call('GET', `/api/rankings?category=${encodeURIComponent(chosen)}`);
      }
      if (request !== state.tabRequest) return;
      if (!result.ok) { setStatus('rankListStatus', problem(result)); return; }
      state.tab = result.data;
      state.tabCategory = result.data.detail.category;
      storeFormat(state.tabCategory);
      renderTab();
    } catch (error) {
      if (request === state.tabRequest) setStatus('rankListStatus', 'Couldn’t load your rankings. Check your connection and try again.');
    } finally {
      if (request === state.tabRequest) board.setAttribute('aria-busy', 'false');
    }
  }

  function renderFormats(data) {
    const holder = $('rankFormats');
    if (!holder) return;
    holder.replaceChildren(...data.formats.map(item => {
      const chip = el('button', 'rank-format');
      chip.type = 'button';
      chip.dataset.format = item.category;
      chip.setAttribute('aria-pressed', String(item.category === state.tabCategory));
      chip.appendChild(el('span', 'rank-format__label', item.label));
      chip.appendChild(el('span', 'rank-format__count', item.finished ? `${item.ranked}/${item.finished}` : '0'));
      chip.setAttribute('aria-label', `${item.label}: ${item.ranked} of ${item.finished} finished ranked`);
      chip.addEventListener('click', () => {
        if (item.category === state.tabCategory) return;
        state.waitingAll = false;
        load(item.category);
      });
      return chip;
    }));
  }

  function renderTab() {
    const data = state.tab;
    if (!data) return;
    const detail = data.detail;
    renderFormats(data);
    const summary = $('rankHeroSummary');
    if (summary) {
      summary.textContent = data.ranked
        ? `${plural(data.ranked, 'title', 'titles')} ranked so far. Pick the one you liked more, two at a time, and the rest fall into place. Placing a title among a hundred others takes about seven picks.`
        : 'Pick the one you liked more, two at a time, and everything you’ve finished falls into order. Placing a title among a hundred others takes about seven picks.';
    }
    renderAsk(detail.question, detail);
    renderList(detail);
    renderWaiting(detail);
    renderLeftOut(detail);
  }

  function renderAsk(question, detail) {
    const body = $('rankAskBody');
    const title = $('rankAskTitle');
    if (!body) return;
    setStatus('rankAskStatus', '');
    if (!question) {
      if (title) title.textContent = detail.ranked.length ? 'All caught up' : 'Nothing to compare yet';
      const text = detail.ranked.length
        ? `Every ${detail.noun} you've ${detail.verb} is ranked. Finish another and it'll ask where it goes.`
        : `Rankings compare two ${detail.nouns} you've ${detail.verb}. Mark a couple finished in your library and the first question shows up here.`;
      const go = button('rank-btn', `Open your ${detail.label.toLowerCase()}`, () => {
        if (typeof navigateLibraryTab === 'function') navigateLibraryTab(detail.category);
        else if (typeof switchTab === 'function') switchTab(detail.category);
      });
      body.replaceChildren(emptyView(text, detail.ranked.length ? null : go));
      return;
    }
    if (title) title.textContent = question.ranked ? `Where does ${question.placing.title} go?` : 'Which did you like more?';
    body.replaceChildren(duel(question, { source: 'tab', onResult: tabResult, onError: text => setStatus('rankAskStatus', text) }));
  }

  function tabResult(result) {
    if (result.question) {
      renderAsk(result.question, state.tab.detail);
      if (result.stale) setStatus('rankAskStatus', 'That one had already moved on, so here is the current question.');
      $('rankAskBody')?.querySelector('.rank-pick--placing')?.focus({ preventScroll: true });
      if (result.skipped) load(state.tabCategory);
      return;
    }
    if (result.placed) {
      const placed = result.placed;
      const next = button('rank-btn rank-btn--primary', 'Next one', () => load(state.tabCategory).then(() => {
        $('rankAskBody')?.querySelector('.rank-pick--placing')?.focus({ preventScroll: true });
      }));
      const again = button('rank-btn rank-btn--quiet', 'Not right? Place it again', () => placeAgain(placed.category, placed.title.id));
      $('rankAskTitle').textContent = 'Placed';
      const shared = shareAction(placed, 'rankAskStatus', null, true);
      $('rankAskBody').replaceChildren(placedView(placed, [next, ...(placed.title ? [again] : []), ...(shared ? [shared] : [])]));
      announce('rankAskStatus', placedWords(placed));
      next.focus({ preventScroll: true });
      refreshListOnly(placed.title && placed.title.id);
      state.card = null;
      return;
    }
    load(state.tabCategory);
  }

  // After a placement the list updates under the result, without replacing the result itself.
  async function refreshListOnly(highlight) {
    const request = ++state.tabRequest;
    try {
      const result = await call('GET', `/api/rankings?category=${encodeURIComponent(state.tabCategory)}`);
      if (!result.ok || request !== state.tabRequest) return;
      state.tab = result.data;
      renderFormats(result.data);
      renderList(result.data.detail, highlight);
      renderWaiting(result.data.detail);
      renderLeftOut(result.data.detail);
    } catch (error) { /* the list catches up next time */ }
  }

  async function placeAgain(category, itemId) {
    const result = await call('POST', '/api/rankings/place', { category, item_id: itemId, source: 'tab' }).catch(() => null);
    if (!result || !result.ok) { setStatus('rankAskStatus', result ? problem(result) : 'Couldn’t reach OmniTrackr.'); return; }
    if (result.data.placed) { tabResult({ placed: result.data.placed }); return; }
    renderAsk(result.data.question, state.tab.detail);
    $('rankAskBody')?.querySelector('.rank-pick--placing')?.focus({ preventScroll: true });
    refreshListOnly();
  }

  async function act(path, body, okText) {
    setStatus('rankListStatus', '');
    try {
      const result = await call('POST', path, body);
      if (!result.ok) { setStatus('rankListStatus', problem(result)); return false; }
      if (okText) setStatus('rankListStatus', okText);
      return result.data;
    } catch (error) {
      setStatus('rankListStatus', 'Couldn’t reach OmniTrackr. Check your connection and try again.');
      return false;
    }
  }

  function rowActions(item, index, total, detail) {
    const tools = el('span', 'rank-row__tools');
    const up = button('rank-icon', '↑', async () => {
      if (await act('/api/rankings/move', { category: detail.category, item_id: item.id, position: index }, `${item.title} moved up to #${index}.`)) {
        await refreshListOnly(item.id);
        document.querySelector(`#rankListBody [data-id="${item.id}"] .rank-icon--up`)?.focus();
      }
    }, `Move ${item.title} up`);
    up.classList.add('rank-icon--up');
    up.disabled = index === 0;
    const down = button('rank-icon', '↓', async () => {
      if (await act('/api/rankings/move', { category: detail.category, item_id: item.id, position: index + 2 }, `${item.title} moved down to #${index + 2}.`)) {
        await refreshListOnly(item.id);
        document.querySelector(`#rankListBody [data-id="${item.id}"] .rank-icon--down`)?.focus();
      }
    }, `Move ${item.title} down`);
    down.classList.add('rank-icon--down');
    down.disabled = index >= total - 1;
    const again = button('rank-icon', '⟲', () => {
      placeAgain(detail.category, item.id);
      $('rankAsk')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, `Place ${item.title} again`);
    again.title = 'Place it again';
    const off = button('rank-icon rank-icon--off', '✕', async () => {
      if (await act('/api/rankings/remove', { category: detail.category, item_id: item.id }, `${item.title} is off the ranking. It's waiting with the others.`)) {
        load(detail.category);
      }
    }, `Take ${item.title} off the ranking`);
    off.title = 'Take it off the ranking';
    tools.append(up, down, again, off);
    return tools;
  }

  function titleLink(item, className) {
    if (item.url && localPath(item.url)) {
      const link = el('a', className, item.title);
      link.href = item.url;
      return link;
    }
    return el('span', className, item.title);
  }

  function renderList(detail, highlight) {
    const body = $('rankListBody');
    const title = $('rankListTitle');
    if (!body) return;
    if (title) title.textContent = detail.ranked.length ? `Your ${detail.nouns}, best first` : `Your ${detail.nouns}`;
    renderTools(detail);
    renderShare(detail);
    if (!detail.ranked.length) {
      body.replaceChildren(emptyView(`Nothing ranked yet. Answer the question ${window.matchMedia?.('(min-width: 900px)').matches ? 'on the left' : 'above'} and your first two ${detail.nouns} go in.`));
      return;
    }
    const podium = el('ol', 'rank-podium');
    const rest = el('ol', 'rank-rows');
    rest.start = 4;
    detail.ranked.forEach((item, index) => {
      if (index < 3) {
        const spot = el('li', `rank-podium__spot rank-podium__spot--${index + 1}`);
        spot.dataset.id = item.id;
        spot.appendChild(el('span', 'rank-podium__place', `#${index + 1}`));
        spot.appendChild(art(item, 'rank-podium__art'));
        const copy = el('span', 'rank-podium__copy');
        copy.appendChild(titleLink(item, 'rank-podium__title'));
        const line = meta(item);
        if (line) copy.appendChild(el('span', 'rank-podium__meta', line));
        spot.appendChild(copy);
        spot.appendChild(rowActions(item, index, detail.ranked.length, detail));
        if (highlight && item.id === highlight) spot.classList.add('is-new');
        podium.appendChild(spot);
        return;
      }
      const row = el('li', 'rank-row');
      row.dataset.id = item.id;
      row.appendChild(el('span', 'rank-row__place', String(index + 1)));
      row.appendChild(art(item, 'rank-row__art'));
      const copy = el('span', 'rank-row__copy');
      copy.appendChild(titleLink(item, 'rank-row__title'));
      const line = [meta(item), item.score ? `scored ${item.score}` : ''].filter(Boolean).join(' · ');
      if (line) copy.appendChild(el('span', 'rank-row__meta', line));
      row.appendChild(copy);
      row.appendChild(rowActions(item, index, detail.ranked.length, detail));
      if (highlight && item.id === highlight) row.classList.add('is-new');
      rest.appendChild(row);
    });
    body.replaceChildren(podium, ...(rest.children.length ? [rest] : []));
    const fresh = body.querySelector('.is-new');
    if (fresh && fresh.scrollIntoView && highlight) fresh.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function renderTools(detail) {
    const tools = $('rankListTools');
    if (!tools) return;
    tools.replaceChildren();
    if (detail.ranked.length < 3) return;
    const profile = detail.profile || {};
    const label = el('label', 'rank-switch');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = Boolean(detail.public);
    box.disabled = !profile.enabled;
    label.appendChild(box);
    label.appendChild(el('span', '', 'Show my top ten on my profile'));
    box.addEventListener('change', async () => {
      box.disabled = true;
      try {
        const result = await call('PUT', '/api/rankings/settings', { category: detail.category, public: box.checked });
        if (!result.ok) { box.checked = !box.checked; setStatus('rankListStatus', problem(result)); }
        else {
          detail.public = result.data.public;
          setStatus('rankListStatus', result.data.public
            ? `Your top ${detail.nouns} are on your public profile. Only the order shows, never your scores.`
            : `Your top ${detail.nouns} are off your profile.`);
        }
      } catch (error) {
        box.checked = !box.checked;
        setStatus('rankListStatus', 'Couldn’t reach OmniTrackr. Check your connection and try again.');
      }
      box.disabled = false;
    });
    tools.appendChild(label);
    if (!profile.enabled) {
      const setUp = el('a', 'rank-link', 'Turn on your public profile first');
      setUp.href = '/#public-profile';
      tools.appendChild(setUp);
    } else if (profile.path && localPath(profile.path)) {
      const see = el('a', 'rank-link', 'See your profile');
      see.href = `${profile.path}#profile-ranked`;
      tools.appendChild(see);
    }
    const top = Math.min(10, detail.ranked.length);
    tools.appendChild(button('rank-btn rank-btn--small', `Save top ${top} as a list`, async node => {
      node.disabled = true;
      const data = await act('/api/rankings/collection', { category: detail.category, top },
        '');
      node.disabled = false;
      if (!data) return;
      const status = $('rankListStatus');
      if (!status) return;
      status.replaceChildren(document.createTextNode(`Saved “${data.name}” to your Collections. Open it there to share it by link. `));
      const open = button('rank-link rank-link--button', 'Open Collections', () => {
        if (typeof navigateLibraryTab === 'function') navigateLibraryTab('collections');
        else if (typeof switchTab === 'function') switchTab('collections');
      });
      status.appendChild(open);
    }));
  }

  function chip(item, label, onClick) {
    const li = el('li', 'rank-chip');
    li.appendChild(art(item, 'rank-chip__art'));
    li.appendChild(el('span', 'rank-chip__title', item.title));
    li.appendChild(button('rank-chip__btn', label, onClick, `${label}: ${item.title}`));
    return li;
  }

  function renderWaiting(detail) {
    const section = $('rankWaiting');
    const list = $('rankWaitingList');
    const more = $('rankWaitingMore');
    if (!section || !list) return;
    // The title the question is about is up there already; the rest wait their turn.
    const asking = detail.question && detail.question.placing ? detail.question.placing.id : null;
    const all = detail.waiting || [];
    const waiting = all.filter(item => item.id !== asking);
    const total = Math.max(0, (Number(detail.waiting_total) || 0) - (all.length !== waiting.length ? 1 : 0));
    section.hidden = !waiting.length;
    $('rankWaitingTitle').textContent = `Waiting to be ranked (${total})`;
    const shown = state.waitingAll ? waiting : waiting.slice(0, WAITING_SHOWN);
    list.replaceChildren(...shown.map(item => chip(item, 'Rank it', () => {
      placeAgain(detail.category, item.id);
      $('rankAsk')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    })));
    if (more) {
      more.hidden = state.waitingAll || waiting.length <= WAITING_SHOWN;
      more.onclick = () => { state.waitingAll = true; renderWaiting(detail); };
    }
  }

  function renderLeftOut(detail) {
    const section = $('rankLeftOut');
    const list = $('rankLeftOutList');
    if (!section || !list) return;
    const items = detail.left_out || [];
    section.hidden = !items.length;
    $('rankLeftOutTitle').textContent = `Left out (${items.length})`;
    list.replaceChildren(...items.map(item => chip(item, 'Put back', async () => {
      if (await act('/api/rankings/restore', { category: detail.category, item_id: item.id }, `${item.title} is back with the others.`)) {
        load(detail.category);
      }
    })));
  }

  function openTab(category) {
    if (category) { state.tabCategory = category; storeFormat(category); }
    state.tab = null;
    if (typeof navigateLibraryTab === 'function') navigateLibraryTab('rankings');
    else if (typeof switchTab === 'function') switchTab('rankings');
    const tab = $('rankings-tab');
    if (tab && tab.scrollIntoView) tab.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  // ------------------------------------------------------------------ the dialog (from the finish ritual)

  function dialogResult(body) {
    const target = $('rankDialogBody');
    if (!target) return;
    if (body.question) {
      target.replaceChildren(duel(body.question, { source: 'finish', onResult: dialogResult, onError: text => setStatus('rankDialogStatus', text) }));
      setStatus('rankDialogStatus', body.stale ? 'That one had already moved on, so here is the current question.' : '');
      target.querySelector('.rank-pick--placing')?.focus();
      return;
    }
    if (body.placed) {
      $('rankDialogTitle').textContent = 'Placed';
      const done = button('rank-btn rank-btn--primary', 'Done', () => closeDialog());
      const all = button('rank-btn', `See all your ${body.placed.nouns}`, () => { closeDialog(); openTab(body.placed.category); });
      const shared = shareAction(body.placed, 'rankDialogStatus', () => { if (!sharePath(body.placed.shared)) closeDialog(); });
      target.replaceChildren(placedView(body.placed, shared ? [done, all, shared] : [done, all]));
      announce('rankDialogStatus', placedWords(body.placed));
      done.focus();
      state.tab = null;
      refresh(true);
      return;
    }
    closeDialog();
  }

  function closeDialog() {
    const dialog = $('rankDialog');
    if (dialog && dialog.open) dialog.close();
  }

  // Place one title the member picked (from the finish dialog, or anywhere else that wants to ask).
  async function place(category, itemId, source = 'finish') {
    const dialog = $('rankDialog');
    if (!dialog || !signedIn()) return false;
    const id = Number(itemId);
    if (!category || !Number.isInteger(id) || id < 1) return false;
    $('rankDialogTitle').textContent = 'Where does it rank?';
    $('rankDialogBody').replaceChildren(el('p', 'rank-empty', 'One moment…'));
    setStatus('rankDialogStatus', '');
    state.dialogReturn = document.activeElement;
    if (!dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
    }
    try {
      const result = await call('POST', '/api/rankings/place', { category, item_id: id, source });
      if (!result.ok) {
        $('rankDialogBody').replaceChildren(emptyView(problem(result)));
        return false;
      }
      const placedFirst = result.data.placed;
      if (placedFirst) $('rankDialogEyebrow').textContent = `Rankings · ${placedFirst.label}`;
      else if (result.data.question) $('rankDialogEyebrow').textContent = `Rankings · ${result.data.question.label}`;
      dialogResult(result.data);
      return true;
    } catch (error) {
      $('rankDialogBody').replaceChildren(emptyView('Couldn’t reach OmniTrackr. Check your connection and try again.'));
      return false;
    }
  }

  // ------------------------------------------------------------------ wiring

  // /#rankings (the Ranker badge, "Rank N more titles"): on a fresh load and, from the home screen, on
  // a click that only changes the hash. The hash is cleared so the same link works a second time.
  function openFromHash() {
    if (window.location.hash !== '#rankings' || !signedIn()) return false;
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
    openTab();
    return true;
  }

  function wire() {
    $('rankDuelHide')?.addEventListener('click', () => {
      hideHere();
      const section = $('rankDuel');
      if (section) section.hidden = true;
      state.homePlaced = null;
      window.OmniHomeLayout?.schedule?.();
    });
    const dialog = $('rankDialog');
    $('rankDialogClose')?.addEventListener('click', closeDialog);
    dialog?.addEventListener('click', event => { if (event.target === dialog) closeDialog(); });
    dialog?.addEventListener('close', () => {
      // Placing from the dialog can change the ranking the tab is showing.
      if (typeof currentTab === 'string' && currentTab === 'rankings') load(state.tabCategory);
      const back = state.dialogReturn;
      state.dialogReturn = null;
      if (back && typeof back.focus === 'function' && document.contains(back)) back.focus();
    });
    if (window.location.hash === '#rankings') setTimeout(openFromHash, 0);
    window.addEventListener('hashchange', openFromHash);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true });
  else wire();

  window.OmniRankings = { refresh, reset, load, place, openTab, render: renderCard };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { refresh, reset, load, place, openTab, openFromHash, renderCard, duel, placedView, placedWords, cardSummary, pickFormat, state };
  }
})();
