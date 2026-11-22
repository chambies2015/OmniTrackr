// A top ten someone shared from Rankings (/ranked/<token>, app/routers/ranked_share.py). Anyone can
// rank the same titles here, two at a time, and see how close their order is. A visitor keeps theirs
// by signing up: the order waits in this browser and moves into the new library when they come back
// signed in (POST /api/rankings/take). The member who shared it gets copy, share and story-image
// buttons. Text from the page is only ever set as textContent.
(function () {
  'use strict';

  const KEY = 'omnitrackr_ranked_take';
  const KEEP_MS = 3 * 24 * 60 * 60 * 1000;
  const TOKEN = /^[A-Za-z0-9_-]{16,32}$/;

  // ---------------------------------------------------------------- the ranking itself (no DOM)

  // A binary insertion sort run one question at a time, the way the Rankings tab places a title.
  function start(items) {
    const queue = items.slice();
    const first = queue.shift();
    return { order: first ? [first] : [], queue, low: 0, high: first ? 1 : 0, asked: 0 };
  }

  function current(game) {
    if (!game.queue.length || !game.order.length) return null;
    const mid = Math.floor((game.low + game.high) / 2);
    return { placing: game.queue[0], against: game.order[mid], mid };
  }

  function copy(game) {
    return { order: game.order.slice(), queue: game.queue.slice(), low: game.low, high: game.high, asked: game.asked };
  }

  // choice: 'placing' (the new one is better), 'against' (the one already placed is better) or 'tie'.
  function answer(game, choice) {
    const ask = current(game);
    if (!ask) return game;
    const next = copy(game);
    next.asked += 1;
    let at = null;
    if (choice === 'tie') at = ask.mid + 1;
    else if (choice === 'placing') next.high = ask.mid;
    else next.low = ask.mid + 1;
    if (at === null && next.low >= next.high) at = next.low;
    if (at !== null) {
      next.order.splice(at, 0, next.queue.shift());
      next.low = 0;
      next.high = next.order.length;
    }
    return next;
  }

  function done(game) {
    return game.queue.length === 0;
  }

  // About how many more picks: the stretch left for this title, then about log2(n+1) for each still waiting.
  function left(game) {
    if (done(game)) return 0;
    let total = Math.max(1, Math.ceil(Math.log2(game.high - game.low + 1)));
    for (let i = 1; i < game.queue.length; i += 1) total += Math.max(1, Math.ceil(Math.log2(game.order.length + i + 1)));
    return total;
  }

  // The share of pairs both orders put the same way round, 0 to 100. Items carry their place on the shared list.
  function agreement(order) {
    let same = 0;
    let pairs = 0;
    for (let i = 0; i < order.length; i += 1) {
      for (let j = i + 1; j < order.length; j += 1) {
        pairs += 1;
        if (order[i].position < order[j].position) same += 1;
      }
    }
    return pairs ? Math.round((same / pairs) * 100) : 0;
  }

  function verdict(percent) {
    if (percent >= 90) return 'You could swap lists and nobody would notice.';
    if (percent >= 70) return 'Mostly the same order. A couple of arguments to have.';
    if (percent >= 45) return 'You agree on some and fight about the rest.';
    return 'Close to opposite. That is a conversation worth having.';
  }

  function shuffled(items, random = Math.random) {
    const list = items.slice();
    for (let i = list.length - 1; i > 0; i -= 1) {
      const j = Math.floor(random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  }

  // ---------------------------------------------------------------- what waits in the browser

  function readTake(token, now = Date.now()) {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!data || data.v !== 1 || data.token !== token || !TOKEN.test(token)) return null;
      if (!Number.isFinite(data.at) || data.at > now || now - data.at > KEEP_MS) return null;
      const titles = Array.isArray(data.titles) ? data.titles.filter(title => typeof title === 'string' && title.length <= 500).slice(0, 10) : [];
      return titles.length >= 2 ? { token, titles, pending: data.pending === true } : null;
    } catch (error) {
      return null;
    }
  }

  function storeTake(token, titles, pending) {
    try {
      localStorage.setItem(KEY, JSON.stringify({ v: 1, token, titles: titles.slice(0, 10), at: Date.now(), pending: Boolean(pending) }));
      return true;
    } catch (error) {
      return false;
    }
  }

  function clearTake() {
    try { localStorage.removeItem(KEY); } catch (error) { /* nothing kept */ }
  }

  // ---------------------------------------------------------------- the page

  function count(event) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting only */ }
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

  function art(item, className) {
    const box = el('span', className);
    box.setAttribute('aria-hidden', 'true');
    if (typeof item.image === 'string' && item.image.startsWith('https://')) {
      const img = document.createElement('img');
      img.src = item.image;
      img.alt = '';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => { img.remove(); box.textContent = item.title.slice(0, 1).toUpperCase(); }, { once: true });
      box.appendChild(img);
    } else {
      box.textContent = item.title.slice(0, 1).toUpperCase();
    }
    return box;
  }

  function headers() {
    const result = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) result.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return result;
  }

  function plural(number, one, many) {
    return `${number} ${number === 1 ? one : many}`;
  }

  function init(root) {
    const stage = root.querySelector('[data-rk-stage]');
    if (!stage) return;
    const token = root.dataset.token || '';
    const member = root.dataset.member === 'true';
    const owner = root.dataset.owner === 'true';
    const noun = root.dataset.noun || 'title';
    const nouns = root.dataset.nouns || 'titles';
    const verb = root.dataset.verb || 'finished';
    const by = root.dataset.by || '';
    const signup = root.dataset.signup || '/#signup';
    const items = [...root.querySelectorAll('[data-rk-item]')].map(node => ({
      position: Number(node.dataset.position),
      title: node.dataset.title || '',
      image: node.dataset.image || '',
      meta: node.dataset.meta || '',
    })).filter(item => item.title && Number.isInteger(item.position));
    if (items.length < 2 || !TOKEN.test(token)) return;
    let picked = new Set();
    let game = null;
    let history = [];
    let started = false;

    function show(...nodes) {
      stage.replaceChildren(...nodes);
    }

    function intro() {
      const go = button('button', 'Rank these yourself', pick);
      const line = el('p', 'rk-hint', `Takes about a minute for all ${items.length}. Skip the ones you haven't ${verb}.`);
      show(go, line);
    }

    function pick() {
      const list = el('ul', 'rk-pick');
      const startButton = button('button', '', begin);
      const refresh = () => {
        startButton.disabled = picked.size < 2;
        startButton.textContent = picked.size < 2 ? `Tick at least two ${nouns}` : `Rank these ${picked.size}`;
      };
      items.forEach(item => {
        const li = el('li');
        const toggle = button('rk-pick__item', '', node => {
          if (picked.has(item.position)) picked.delete(item.position);
          else picked.add(item.position);
          node.setAttribute('aria-pressed', picked.has(item.position) ? 'true' : 'false');
          refresh();
        });
        toggle.setAttribute('aria-pressed', picked.has(item.position) ? 'true' : 'false');
        toggle.appendChild(art(item, 'rk-pick__art'));
        toggle.appendChild(el('span', 'rk-pick__title', item.title));
        li.appendChild(toggle);
        list.appendChild(li);
      });
      const all = button('rk-quiet', `I've ${verb} all of them`, () => {
        picked = new Set(items.map(item => item.position));
        list.querySelectorAll('.rk-pick__item').forEach(node => node.setAttribute('aria-pressed', 'true'));
        refresh();
      });
      refresh();
      const row = el('div', 'rk-actions');
      row.append(startButton, all);
      show(el('p', 'rk-step', `Which have you ${verb}?`), list, row);
      list.querySelector('button')?.focus({ preventScroll: true });
    }

    function begin() {
      const chosen = items.filter(item => picked.has(item.position));
      if (chosen.length < 2) return;
      game = start(shuffled(chosen));
      history = [];
      if (!started) { started = true; count('rank_take_started'); }
      duel();
    }

    function side(item, choice) {
      const node = button(`rk-duel__pick rk-duel__pick--${choice}`, '', () => choose(choice));
      node.appendChild(art(item, 'rk-duel__art'));
      const words = el('span', 'rk-duel__copy');
      words.appendChild(el('strong', '', item.title));
      if (item.meta) words.appendChild(el('small', '', item.meta));
      node.appendChild(words);
      node.setAttribute('aria-label', `${item.title}${item.meta ? `, ${item.meta}` : ''}`);
      return node;
    }

    function choose(choice) {
      history.push(game);
      game = answer(game, choice);
      if (done(game)) result();
      else duel(true);
    }

    function duel(keepFocus) {
      const ask = current(game);
      if (!ask) { result(); return; }
      const wrap = el('div', 'rk-duel');
      const question = el('p', 'rk-step', 'Which did you like more?');
      const pair = el('div', 'rk-duel__pair');
      pair.append(side(ask.placing, 'placing'), el('span', 'rk-duel__or', 'or'), side(ask.against, 'against'));
      const foot = el('div', 'rk-duel__foot');
      foot.appendChild(button('rk-quiet', 'Too close to call', () => choose('tie')));
      if (history.length) {
        foot.appendChild(button('rk-quiet', 'Undo', () => {
          game = history.pop();
          duel(true);
        }));
      }
      const togo = left(game);
      foot.appendChild(el('span', 'rk-duel__left', `Pick ${game.asked + 1} · about ${togo} to go`));
      wrap.append(question, pair, foot);
      wrap.addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        const target = event.key === 'ArrowLeft' ? 'placing' : event.key === 'ArrowRight' ? 'against' : '';
        if (!target) return;
        event.preventDefault();
        choose(target);
      });
      show(wrap);
      if (keepFocus) wrap.querySelector('.rk-duel__pick--placing')?.focus({ preventScroll: true });
    }

    function orderList(order, label, other) {
      const box = el('div', 'rk-compare__col');
      box.appendChild(el('h3', '', label));
      const list = el('ol', 'rk-compare__list');
      order.forEach((item, index) => {
        const li = el('li', other && other[index] === item ? 'is-same' : '');
        li.appendChild(el('span', 'rk-compare__place', String(index + 1)));
        li.appendChild(art(item, 'rk-compare__art'));
        li.appendChild(el('span', 'rk-compare__title', item.title));
        list.appendChild(li);
      });
      box.appendChild(list);
      return box;
    }

    function listName() {
      return by ? `${by}'s top ${items.length} ${nouns}` : `this top ${items.length} of ${nouns}`;
    }

    function result() {
      const mine = game.order;
      const theirs = mine.slice().sort((a, b) => a.position - b.position);
      const percent = agreement(mine);
      count('rank_take_finished');
      storeTake(token, mine.map(item => item.title), false);
      const wrap = el('div', 'rk-result');
      const score = el('p', 'rk-result__score');
      score.appendChild(el('strong', '', `${percent}%`));
      score.appendChild(document.createTextNode(' of the head-to-heads go the same way'));
      wrap.appendChild(score);
      wrap.appendChild(el('p', 'rk-result__verdict', verdict(percent)));
      const top = mine[0];
      wrap.appendChild(el('p', 'rk-result__line', top.position === 1
        ? `You both put ${top.title} first.`
        : `Your number one, ${top.title}, is number ${top.position} on this list.`));
      const compare = el('div', 'rk-compare');
      compare.append(orderList(mine, 'Your order', theirs), orderList(theirs, by ? `${by}'s order` : 'Their order', mine));
      wrap.appendChild(compare);
      const actions = el('div', 'rk-actions');
      if (!member) {
        const keep = el('a', 'button', 'Keep my ranking');
        keep.href = signup;
        keep.addEventListener('click', () => {
          storeTake(token, mine.map(item => item.title), true);
          count('rank_signup_clicked');
        });
        actions.appendChild(keep);
      } else if (!owner) {
        actions.appendChild(button('button', 'Add them to my library', node => save(mine.map(item => item.title), node)));
      }
      actions.appendChild(button('button button--ghost', 'Share my result', node => shareResult(percent, node)));
      actions.appendChild(button('rk-quiet', 'Start again', () => { picked = new Set(mine.map(item => item.position)); pick(); }));
      wrap.appendChild(actions);
      if (!member) {
        wrap.appendChild(el('p', 'rk-hint', `Keep it and your ${plural(mine.length, noun, nouns)} go into a free OmniTrackr library as ${verb}, already in your order.`));
      } else if (!owner) {
        wrap.appendChild(el('p', 'rk-hint', `They go into your library as ${verb}. Anything you already have stays exactly as it is.`));
      }
      wrap.appendChild(el('p', 'rk-status', ''));
      show(wrap);
      wrap.querySelector('.rk-result__score')?.setAttribute('tabindex', '-1');
      wrap.querySelector('.rk-result__score')?.focus({ preventScroll: false });
    }

    async function shareResult(percent, node) {
      const url = `${window.location.origin}${window.location.pathname}`;
      const text = `I ranked ${listName()} myself and we agree on ${percent}% of the head-to-heads. Your turn:`;
      count('rank_result_shared');
      if (navigator.share) {
        try { await navigator.share({ title: document.title, text, url }); return; } catch (error) {
          if (error && error.name === 'AbortError') return;
        }
      }
      try {
        await navigator.clipboard.writeText(`${text} ${url}`);
        flash(node, 'Copied ✓');
      } catch (error) {
        window.prompt('Copy this:', `${text} ${url}`);
      }
    }

    function flash(node, text) {
      const original = node.dataset.label || node.textContent;
      node.dataset.label = original;
      node.textContent = text;
      setTimeout(() => { node.textContent = original; }, 2200);
    }

    function savedView(data) {
      const wrap = el('div', 'rk-saved');
      wrap.appendChild(el('p', 'rk-step', 'Saved to your library'));
      const parts = [];
      if (data.added) parts.push(`Added ${plural(data.added, data.noun || noun, data.nouns || nouns)} as ${verb}.`);
      if (data.existing) parts.push(data.existing === 1 ? 'One was already in your library and stayed as it was.' : `${data.existing} were already in your library and stayed as they were.`);
      if (data.ranked) parts.push(`Your ${data.nouns || nouns} ranking starts with these ${data.count}, in your order.`);
      else {
        if (data.queued) parts.push(`${data.queued === 1 ? 'One is' : `${data.queued} are`} waiting in your Rankings tab, ready to place among the ${data.nouns || nouns} you'd already ranked.`);
        if (data.already_ranked) parts.push(`${data.already_ranked === 1 ? 'One was' : `${data.already_ranked} were`} in your ranking already.`);
      }
      if (data.unfinished) parts.push(`${plural(data.unfinished, 'title isn\'t', 'titles aren\'t')} marked finished in your library, so ${data.unfinished === 1 ? 'it waits' : 'they wait'} until you finish ${data.unfinished === 1 ? 'it' : 'them'}.`);
      wrap.appendChild(el('p', 'rk-result__line', parts.join(' ')));
      const open = el('a', 'button', 'Open your Rankings');
      open.href = '/#rankings';
      const row = el('div', 'rk-actions');
      row.appendChild(open);
      wrap.appendChild(row);
      return wrap;
    }

    async function save(titles, node) {
      if (node) node.disabled = true;
      const status = stage.querySelector('.rk-status');
      if (status) status.textContent = 'Saving…';
      let response;
      try {
        response = await fetch('/api/rankings/take', { method: 'POST', credentials: 'same-origin', headers: headers(), body: JSON.stringify({ token, titles }) });
      } catch (error) {
        if (status) status.textContent = 'Couldn’t reach OmniTrackr. Check your connection and try again.';
        if (node) node.disabled = false;
        return false;
      }
      let data = {};
      try { data = await response.json(); } catch (error) { data = {}; }
      if (response.status === 401) {
        if (status) status.textContent = 'Log in again to save this.';
        if (node) node.disabled = false;
        return false;
      }
      if (!response.ok) {
        clearTake();
        const detail = typeof data.detail === 'string' ? data.detail : 'That didn’t save. Please try again.';
        if (status) status.textContent = detail;
        else show(el('p', 'rk-status', detail));
        if (node) node.disabled = false;
        return false;
      }
      clearTake();
      show(savedView(data));
      stage.querySelector('.rk-step')?.setAttribute('tabindex', '-1');
      stage.querySelector('.rk-step')?.focus({ preventScroll: false });
      return true;
    }

    const waiting = readTake(token);
    if (member && !owner && waiting && waiting.pending) {
      show(el('p', 'rk-status', 'Saving the ranking you made before signing up…'));
      save(waiting.titles).then(ok => { if (!ok && !stage.querySelector('.rk-status')?.textContent) intro(); });
    } else {
      intro();
    }
  }

  function initOwner(root) {
    const panel = root.querySelector('[data-rk-owner]');
    if (!panel) return;
    const status = panel.querySelector('[data-rk-owner-status]');
    const say = text => { if (status) status.textContent = text; };
    const url = `${window.location.origin}${window.location.pathname}`;
    const copyButton = panel.querySelector('[data-rk-copy]');
    const shareButton = panel.querySelector('[data-rk-share]');
    const storyButton = panel.querySelector('[data-rk-story]');
    if (shareButton && navigator.share) shareButton.hidden = false;
    copyButton?.addEventListener('click', async () => {
      count('rank_link_shared');
      try { await navigator.clipboard.writeText(url); say('Link copied.'); } catch (error) { window.prompt('Copy this link:', url); }
    });
    shareButton?.addEventListener('click', async () => {
      count('rank_link_shared');
      try { await navigator.share({ title: document.title, url }); } catch (error) { /* closed */ }
    });
    storyButton?.addEventListener('click', async () => {
      const src = storyButton.dataset.src || '';
      if (!src.startsWith('/ranked/')) return;
      storyButton.disabled = true;
      say('Getting your image ready…');
      try {
        const response = await fetch(src, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        const name = `omnitrackr-top-${root.dataset.format || 'ten'}.png`;
        const file = typeof File === 'function' ? new File([blob], name, { type: 'image/png' }) : null;
        count('rank_link_shared');
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          try { await navigator.share({ files: [file], title: document.title }); say(''); } catch (error) {
            say(error && error.name === 'AbortError' ? '' : 'Sharing didn’t open, so try again or long-press the image.');
          }
        } else {
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = name;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(link.href), 4000);
          say('Image saved.');
        }
      } catch (error) {
        say('The image didn’t load. Please try again.');
      }
      storyButton.disabled = false;
    });
  }

  const api = { start, current, answer, done, left, agreement, verdict, shuffled, readTake, storeTake, clearTake, KEY };
  if (typeof window !== 'undefined') window.OmniRankedShare = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    const boot = () => {
      const root = document.getElementById('rankedShare');
      if (!root) return;
      init(root);
      initOwner(root);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})();
