// Tier list maker (/tier-list). The board lives only in this browser (localStorage);
// titles come from ready-made sets (GET /api/tier-list/templates), the members'
// title search (GET /api/titles/search), free text, or a member's own ratings
// (GET /api/tier-list/library). Everything is drawn with textContent only. The
// exported picture is drawn on a canvas, with posters fetched through the
// same-origin /api/tier-list/image proxy so the canvas can be saved.
// Nov 2026: a ranked board can become a link (/api/tier-list/shares). The edit
// key for each link this browser made waits in localStorage (LINKS_KEY), so a
// visitor without an account can update or delete it, and signing up claims it.
// Opening /tier-list?remix=<token> starts the same titles unranked and shows how
// closely the new ranking agrees with the original.
(function () {
  'use strict';

  const KEY = 'omnitrackr_tier_list';
  const LINKS_KEY = 'omnitrackr_tier_links';
  const MAX_LINKS = 30;
  const MIN_SHARED = 3;
  const TOKEN = /^[A-Za-z0-9_-]{16,32}$/;
  const TIERS = ['S', 'A', 'B', 'C', 'D'];
  const TIER_COLORS = { S: '#f472b6', A: '#fb923c', B: '#facc15', C: '#4ade80', D: '#60a5fa' };
  const KIND_LABELS = {
    movie: 'Movie', tv: 'TV show', anime: 'Anime', game: 'Video game', album: 'Album', book: 'Book',
    manga: 'Manga', podcast: 'Podcast', audiobook: 'Audiobook',
  };
  const KINDS = new Set(Object.keys(KIND_LABELS));
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const MAX_ITEMS = 150;
  const MAX_LABEL = 24;

  function report(event) {
    report.sent = report.sent || new Set();
    if (report.sent.has(event)) return;
    report.sent.add(event);
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  // ---- State -------------------------------------------------------------

  function safeImage(url) {
    return typeof url === 'string' && /^https?:\/\//i.test(url) && url.length < 1000 ? url : null;
  }

  function cleanItem(raw) {
    if (!raw || typeof raw.title !== 'string' || !raw.title.trim()) return null;
    const kind = KINDS.has(raw.kind) ? raw.kind : null;
    return {
      title: raw.title.trim().slice(0, 200),
      kind,
      year: Number.isInteger(raw.year) ? raw.year : null,
      image: safeImage(raw.image),
      slug: kind && typeof raw.slug === 'string' && SLUG.test(raw.slug) ? raw.slug : null,
    };
  }

  function emptyState() {
    const tiers = {};
    TIERS.forEach(tier => { tiers[tier] = []; });
    return {
      name: 'My tier list', labels: Object.assign({}, ...TIERS.map(t => ({ [t]: t }))), tiers, pool: [], items: {}, next: 1,
      link: null, template: null, source: null,
    };
  }

  function titleKey(item) {
    return `${String(item.title || '').toLowerCase()}|${item.kind || ''}|${item.year || 0}`;
  }

  // The shared list a board was started from: who made it and where each title sat.
  function cleanSource(raw) {
    if (!raw || typeof raw !== 'object' || typeof raw.token !== 'string' || !TOKEN.test(raw.token)) return null;
    const ranks = {};
    if (raw.ranks && typeof raw.ranks === 'object') {
      Object.keys(raw.ranks).slice(0, MAX_ITEMS).forEach(key => {
        const value = raw.ranks[key];
        if (typeof key === 'string' && key.length < 260 && Number.isInteger(value) && value >= 0 && value < TIERS.length) ranks[key] = value;
      });
    }
    return {
      token: raw.token,
      name: typeof raw.name === 'string' ? raw.name.slice(0, 80) : 'their tier list',
      by: typeof raw.by === 'string' ? raw.by.slice(0, 60) : '',
      ranks,
    };
  }

  function sourceFromShare(data) {
    const ranks = {};
    TIERS.forEach((tier, index) => ((data.tiers && data.tiers[tier]) || []).forEach(raw => {
      const item = cleanItem(raw);
      if (item) ranks[titleKey(item)] = index;
    }));
    return cleanSource({ token: data.token, name: data.name, by: data.by, ranks });
  }

  // How a board compares with the shared list it was started from.
  function agreement(state) {
    const result = { compared: 0, same: 0, close: 0, score: 0, apart: [] };
    const source = state.source;
    if (!source) return result;
    TIERS.forEach((tier, index) => state.tiers[tier].forEach(id => {
      const item = state.items[id];
      const theirs = item ? source.ranks[titleKey(item)] : undefined;
      if (theirs === undefined) return;
      result.compared += 1;
      const gap = Math.abs(theirs - index);
      if (gap === 0) result.same += 1;
      else if (gap === 1) result.close += 1;
      else result.apart.push({ title: item.title, mine: tier, theirs: TIERS[theirs], gap });
    }));
    result.apart.sort((a, b) => b.gap - a.gap);
    result.apart = result.apart.slice(0, 2);
    result.score = result.compared ? Math.round(((result.same + result.close * 0.5) / result.compared) * 100) : 0;
    return result;
  }

  function normalizeState(raw) {
    const state = emptyState();
    if (!raw || typeof raw !== 'object') return state;
    if (typeof raw.name === 'string') state.name = raw.name.slice(0, 80);
    const items = raw.items && typeof raw.items === 'object' ? raw.items : {};
    const used = new Set();
    function take(ids) {
      const out = [];
      (Array.isArray(ids) ? ids : []).forEach(id => {
        if (typeof id !== 'string' || used.has(id) || !items[id] || used.size >= MAX_ITEMS) return;
        const item = cleanItem(items[id]);
        if (!item) return;
        used.add(id);
        state.items[id] = item;
        out.push(id);
      });
      return out;
    }
    TIERS.forEach(tier => {
      state.tiers[tier] = take(raw.tiers && raw.tiers[tier]);
      const label = raw.labels && raw.labels[tier];
      if (typeof label === 'string' && label.trim()) state.labels[tier] = label.trim().slice(0, MAX_LABEL);
    });
    state.pool = take(raw.pool);
    state.next = Math.max(Number.isInteger(raw.next) ? raw.next : 1, used.size + 1);
    if (typeof raw.link === 'string' && TOKEN.test(raw.link)) state.link = raw.link;
    if (typeof raw.template === 'string' && /^[a-z0-9-]{1,60}$/.test(raw.template)) state.template = raw.template;
    state.source = cleanSource(raw.source);
    return state;
  }

  function count(state) {
    return Object.keys(state.items).length;
  }

  function ranked(state) {
    return TIERS.reduce((total, tier) => total + state.tiers[tier].length, 0);
  }

  function sameTitle(a, b) {
    return a.title.toLowerCase() === b.title.toLowerCase() && (a.kind || '') === (b.kind || '') && (a.year || 0) === (b.year || 0);
  }

  // Adds a title to a tier (or the pool). Returns its id, or null when it is a duplicate or the board is full.
  function addItem(state, raw, tier) {
    const item = cleanItem(raw);
    if (!item || count(state) >= MAX_ITEMS) return null;
    if (Object.values(state.items).some(existing => sameTitle(existing, item))) return null;
    const id = `t${state.next++}`;
    state.items[id] = item;
    (TIERS.includes(tier) ? state.tiers[tier] : state.pool).push(id);
    return id;
  }

  function locate(state, id) {
    for (const tier of TIERS) {
      const index = state.tiers[tier].indexOf(id);
      if (index !== -1) return { zone: tier, list: state.tiers[tier], index };
    }
    const index = state.pool.indexOf(id);
    return index === -1 ? null : { zone: 'pool', list: state.pool, index };
  }

  // Moves a title into a tier or 'pool', before `beforeId` when given, otherwise at the end.
  function moveItem(state, id, zone, beforeId) {
    const from = locate(state, id);
    if (!from) return false;
    const target = zone === 'pool' ? state.pool : state.tiers[zone];
    if (!target) return false;
    from.list.splice(from.index, 1);
    const at = beforeId && beforeId !== id ? target.indexOf(beforeId) : -1;
    if (at === -1) target.push(id);
    else target.splice(at, 0, id);
    return true;
  }

  function removeItem(state, id) {
    const from = locate(state, id);
    if (!from) return false;
    from.list.splice(from.index, 1);
    delete state.items[id];
    return true;
  }

  function fromTemplate(template, name) {
    const state = emptyState();
    state.name = (name || template.board || template.name || 'My tier list').slice(0, 80);
    if (typeof template.key === 'string' && /^[a-z0-9-]{1,60}$/.test(template.key)) state.template = template.key;
    (template.items || []).forEach(item => addItem(state, item, item.tier));
    return state;
  }

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? normalizeState(JSON.parse(raw)) : null;
    } catch (error) {
      return null;
    }
  }

  function save(state) {
    try {
      if (count(state)) localStorage.setItem(KEY, JSON.stringify(state));
      else localStorage.removeItem(KEY);
    } catch (error) { /* private mode: the board still works until the tab closes */ }
  }

  // Links this browser made: [{ token, key, name, at, claimed }], newest first.
  function readLinks() {
    try {
      const raw = JSON.parse(localStorage.getItem(LINKS_KEY));
      return (Array.isArray(raw) ? raw : []).filter(link => link && typeof link.token === 'string' && TOKEN.test(link.token)
        && (link.key === null || (typeof link.key === 'string' && link.key.length <= 80))).slice(0, MAX_LINKS);
    } catch (error) {
      return [];
    }
  }

  function writeLinks(links) {
    try {
      if (links.length) localStorage.setItem(LINKS_KEY, JSON.stringify(links.slice(0, MAX_LINKS)));
      else localStorage.removeItem(LINKS_KEY);
    } catch (error) { /* the link still works; this browser just forgets it can edit it */ }
  }

  function rememberLink(link) {
    const links = readLinks().filter(entry => entry.token !== link.token);
    links.unshift({ token: link.token, key: link.key || null, name: String(link.name || '').slice(0, 80), at: Date.now(), claimed: !!link.claimed });
    writeLinks(links);
  }

  function forgetLink(token) {
    writeLinks(readLinks().filter(entry => entry.token !== token));
  }

  function linkKey(token) {
    const found = readLinks().find(entry => entry.token === token);
    return found ? found.key : null;
  }

  // What a link stores: the ranked titles only (the "not ranked yet" pool stays private).
  function sharePayload(state) {
    const tiers = {};
    TIERS.forEach(tier => {
      tiers[tier] = state.tiers[tier].map(id => state.items[id]).filter(Boolean)
        .map(item => ({ title: item.title, kind: item.kind, year: item.year, slug: item.slug, image: item.image }));
    });
    return { name: state.name, labels: Object.assign({}, state.labels), tiers, template: state.template || null,
      source: state.source ? state.source.token : null };
  }

  // ---- Export image --------------------------------------------------------

  const EXPORT = { width: 1200, pad: 32, label: 132, tileW: 86, tileH: 128, gap: 8, header: 96, footer: 64 };

  function exportLayout(state) {
    const perRow = Math.floor((EXPORT.width - EXPORT.pad * 2 - EXPORT.label - EXPORT.gap) / (EXPORT.tileW + EXPORT.gap));
    const rows = TIERS.map(tier => {
      const lines = Math.max(1, Math.ceil(state.tiers[tier].length / perRow));
      return { tier, lines, height: lines * (EXPORT.tileH + EXPORT.gap) + EXPORT.gap };
    });
    const height = EXPORT.header + rows.reduce((total, row) => total + row.height + 6, 0) + EXPORT.footer;
    return { perRow, rows, height };
  }

  function proxied(url) {
    return `/api/tier-list/image?url=${encodeURIComponent(url)}`;
  }

  function loadImage(src, timeout) {
    return new Promise(resolve => {
      const image = new Image();
      let done = false;
      const finish = value => { if (!done) { done = true; resolve(value); } };
      image.onload = () => finish(image);
      image.onerror = () => finish(null);
      image.src = src;
      setTimeout(() => finish(null), timeout);
    });
  }

  function wrapText(ctx, text, maxWidth, maxLines) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = '';
    words.forEach(word => {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width <= maxWidth || !line) line = test;
      else { lines.push(line); line = word; }
    });
    if (line) lines.push(line);
    if (lines.length > maxLines) {
      lines.length = maxLines;
      lines[maxLines - 1] = `${lines[maxLines - 1].replace(/.{0,2}$/, '')}…`;
    }
    return lines;
  }

  function drawTextTile(ctx, item, x, y) {
    const gradient = ctx.createLinearGradient(x, y, x + EXPORT.tileW, y + EXPORT.tileH);
    gradient.addColorStop(0, '#312e81');
    gradient.addColorStop(1, '#1e1b4b');
    ctx.fillStyle = gradient;
    ctx.fillRect(x, y, EXPORT.tileW, EXPORT.tileH);
    ctx.fillStyle = '#ffffff';
    ctx.font = '600 13px Inter, Arial, sans-serif';
    ctx.textAlign = 'center';
    wrapText(ctx, item.title, EXPORT.tileW - 12, 6).forEach((line, index) => {
      ctx.fillText(line, x + EXPORT.tileW / 2, y + 22 + index * 17);
    });
    ctx.textAlign = 'left';
  }

  async function renderImage(state, documentRef) {
    const layout = exportLayout(state);
    const canvas = documentRef.createElement('canvas');
    canvas.width = EXPORT.width;
    canvas.height = layout.height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#0b0a18';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 34px Poppins, Inter, Arial, sans-serif';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText(state.name || 'My tier list', EXPORT.pad, 62, EXPORT.width - EXPORT.pad * 2);

    const ids = TIERS.flatMap(tier => state.tiers[tier]);
    const images = {};
    await Promise.all(ids.map(async id => {
      const item = state.items[id];
      if (item && item.image) images[id] = await loadImage(proxied(item.image), 8000);
    }));

    let y = EXPORT.header;
    layout.rows.forEach(row => {
      ctx.fillStyle = TIER_COLORS[row.tier];
      ctx.fillRect(EXPORT.pad, y, EXPORT.label, row.height);
      ctx.fillStyle = '#16141f';
      ctx.fillRect(EXPORT.pad + EXPORT.label, y, EXPORT.width - EXPORT.pad * 2 - EXPORT.label, row.height);
      ctx.fillStyle = '#0b0a18';
      const label = state.labels[row.tier] || row.tier;
      ctx.font = label.length <= 2 ? '800 44px Poppins, Inter, Arial, sans-serif' : '700 18px Inter, Arial, sans-serif';
      ctx.textAlign = 'center';
      const labelLines = wrapText(ctx, label, EXPORT.label - 16, 3);
      const lineHeight = label.length <= 2 ? 44 : 22;
      const top = y + row.height / 2 - ((labelLines.length - 1) * lineHeight) / 2 + lineHeight / 3;
      labelLines.forEach((line, index) => ctx.fillText(line, EXPORT.pad + EXPORT.label / 2, top + index * lineHeight));
      ctx.textAlign = 'left';
      state.tiers[row.tier].forEach((id, index) => {
        const column = index % layout.perRow;
        const line = Math.floor(index / layout.perRow);
        const x = EXPORT.pad + EXPORT.label + EXPORT.gap + column * (EXPORT.tileW + EXPORT.gap);
        const tileY = y + EXPORT.gap + line * (EXPORT.tileH + EXPORT.gap);
        const image = images[id];
        if (image) {
          const scale = Math.max(EXPORT.tileW / image.width, EXPORT.tileH / image.height);
          const sw = EXPORT.tileW / scale;
          const sh = EXPORT.tileH / scale;
          try {
            ctx.drawImage(image, (image.width - sw) / 2, (image.height - sh) / 2, sw, sh, x, tileY, EXPORT.tileW, EXPORT.tileH);
          } catch (error) {
            drawTextTile(ctx, state.items[id], x, tileY);
          }
        } else {
          drawTextTile(ctx, state.items[id], x, tileY);
        }
      });
      y += row.height + 6;
    });
    ctx.fillStyle = '#a5b4fc';
    ctx.font = '600 18px Inter, Arial, sans-serif';
    ctx.fillText('Made with OmniTrackr', EXPORT.pad, layout.height - 26);
    ctx.fillStyle = '#8b90a8';
    ctx.textAlign = 'right';
    ctx.fillText(state.link ? `omnitrackr.xyz/tier-list/s/${state.link}` : 'omnitrackr.xyz/tier-list',
      EXPORT.width - EXPORT.pad, layout.height - 26);
    ctx.textAlign = 'left';
    return canvas;
  }

  function fileName(state) {
    const base = String(state.name || 'tier-list').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `${base || 'tier-list'}.png`;
  }

  // ---- Page ---------------------------------------------------------------

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function init() {
    const tool = document.getElementById('tierTool');
    if (!tool) return;
    const board = document.getElementById('tierBoard');
    const poolNode = tool.querySelector('[data-tier-pool]');
    const poolCount = tool.querySelector('[data-tier-pool-count]');
    const nameInput = tool.querySelector('[data-tier-name]');
    const status = tool.querySelector('[data-tier-status]');
    const moveBar = tool.querySelector('[data-tier-move]');
    const moveTitle = tool.querySelector('[data-tier-move-title]');
    const preview = tool.querySelector('[data-tier-preview]');
    const shareButton = tool.querySelector('[data-tier-share]');
    const cta = tool.querySelector('[data-tier-cta]');
    const compareNode = tool.querySelector('[data-tier-compare]');
    const linkButton = tool.querySelector('[data-tier-link]');
    const linkReady = tool.querySelector('[data-tier-link-ready]');
    const linkUrl = tool.querySelector('[data-tier-link-url]');
    const linkOpen = tool.querySelector('[data-tier-link-open]');
    const linkShare = tool.querySelector('[data-tier-link-share]');
    const linkNote = tool.querySelector('[data-tier-link-note]');
    const signedIn = tool.dataset.signedIn === 'true';
    let state = load() || emptyState();
    let selected = null;
    let lastBlob = null;
    let syncTimer = null;
    let linkBusy = false;

    function say(text) { if (status) status.textContent = text; }

    function persist() {
      save(state);
      lastBlob = null;
      if (shareButton) shareButton.hidden = true;
      if (state.link) {
        clearTimeout(syncTimer);
        syncTimer = setTimeout(syncLink, 1200);
      }
    }

    async function api(path, options = {}) {
      const init = { method: options.method || 'GET', credentials: 'same-origin', headers: {} };
      if (options.body !== undefined) {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(options.body);
      }
      const response = await fetch(path, init);
      const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(typeof data.detail === 'string' ? data.detail
          : (response.status === 429 ? 'Slow down a little and try again in a minute.' : 'Something went wrong. Please try again.'));
        error.status = response.status;
        throw error;
      }
      return data;
    }

    function linkAddress(token) {
      return `${window.location.origin}/tier-list/s/${token}`;
    }

    function renderLinkBox() {
      if (!linkButton) return;
      const token = state.link;
      linkButton.hidden = !!token;
      linkButton.disabled = linkBusy;
      if (linkReady) linkReady.hidden = !token;
      if (!token) return;
      if (linkUrl) linkUrl.value = linkAddress(token);
      if (linkOpen) linkOpen.href = `/tier-list/s/${token}`;
      if (linkShare) linkShare.hidden = !(navigator.share);
      if (linkNote && !linkNote.dataset.busy) {
        linkNote.replaceChildren();
        if (ranked(state) < MIN_SHARED) {
          linkNote.textContent = `Your link keeps the last version with at least ${MIN_SHARED} ranked titles.`;
        } else if (signedIn) {
          linkNote.textContent = 'Anyone with the link can see this board. Changes you make here update it, and your links are listed below.';
        } else {
          linkNote.appendChild(document.createTextNode('Anyone with the link can see this board, and changes you make here update it. '
            + 'Links made without an account stay up for 30 days. '));
          const join = element('a', '', 'Create a free account');
          join.href = '/?next=%2Ftier-list#signup';
          join.dataset.tierSignup = '';
          linkNote.appendChild(join);
          linkNote.appendChild(document.createTextNode(' to keep it for good.'));
        }
      }
    }

    function linkNoteSay(text) {
      if (!linkNote) return;
      linkNote.dataset.busy = '1';
      linkNote.textContent = text;
      setTimeout(() => { delete linkNote.dataset.busy; renderLinkBox(); }, 2600);
    }

    async function makeLink() {
      if (ranked(state) < MIN_SHARED) { say(`Put at least ${MIN_SHARED} titles in tiers, then make your link.`); return; }
      if (linkBusy) return;
      linkBusy = true;
      renderLinkBox();
      say('Making your link…');
      try {
        const made = await api('/api/tier-list/shares', { method: 'POST', body: sharePayload(state) });
        rememberLink({ token: made.token, key: made.key, name: state.name, claimed: made.member });
        state.link = made.token;
        save(state);
        say('Your link is ready. Copy it, or open it to see what friends will see.');
        renderLinkBox();
        if (linkUrl) { linkUrl.focus(); linkUrl.select(); }
        refreshMine();
      } catch (error) {
        say(error.message);
      } finally {
        linkBusy = false;
        renderLinkBox();
      }
    }

    async function syncLink() {
      const token = state.link;
      if (!token || ranked(state) < MIN_SHARED) { renderLinkBox(); return; }
      const key = linkKey(token);
      try {
        await api(`/api/tier-list/shares/${token}`, { method: 'PUT', body: Object.assign(sharePayload(state), { key }) });
        linkNoteSay('Link updated.');
      } catch (error) {
        if (error.status === 404 || error.status === 403) {
          // Deleted, expired or not ours to change: this board needs a new link.
          if (error.status === 404) forgetLink(token);
          state.link = null;
          save(state);
          renderLinkBox();
          say(error.status === 404 ? 'That link has ended. Make a new one to share this board.' : error.message);
        } else {
          linkNoteSay('Could not update the link just now. It will try again after your next change.');
        }
      }
    }

    async function copyLink() {
      if (!state.link) return;
      const address = linkAddress(state.link);
      try {
        await navigator.clipboard.writeText(address);
        linkNoteSay('Copied. Paste it anywhere.');
      } catch (error) {
        if (linkUrl) { linkUrl.focus(); linkUrl.select(); }
        linkNoteSay('Press Ctrl+C (or ⌘C) to copy the selected link.');
      }
    }

    async function shareLink() {
      if (!state.link || !navigator.share) return;
      try {
        await navigator.share({ title: state.name, text: `My ${state.name} tier list. Rank them yourself and see if we agree:`, url: linkAddress(state.link) });
        report('share_clicked');
      } catch (error) { /* share sheet closed */ }
    }

    function renderCompare() {
      if (!compareNode) return;
      const source = state.source;
      const result = agreement(state);
      compareNode.hidden = !source;
      if (!source) return;
      compareNode.replaceChildren();
      const who = source.by && !/^(someone|an OmniTrackr member)/.test(source.by) ? source.by : 'the person who made it';
      const head = element('p', 'tl-compare__head');
      const original = element('a', '', source.name);
      original.href = `/tier-list/s/${source.token}`;
      if (result.compared < MIN_SHARED) {
        head.append('You are ranking the titles from ', original, `. Place ${MIN_SHARED} or more and you will see how closely you agree with ${who}.`);
        compareNode.appendChild(head);
        return;
      }
      const score = element('strong', 'tl-compare__score', `${result.score}%`);
      head.append(score, ` agreement with ${who} on `, original, '.');
      compareNode.appendChild(head);
      const detail = `${result.same} of ${result.compared} in the same tier, ${result.close} one tier apart.`;
      compareNode.appendChild(element('p', 'tl-compare__detail', detail));
      if (result.apart.length) {
        const split = result.apart.map(entry => `${entry.title} (you ${state.labels[entry.mine] || entry.mine}, them ${entry.theirs})`).join('; ');
        compareNode.appendChild(element('p', 'tl-compare__detail', `Biggest split: ${split}.`));
      }
      if (!state.pool.length && !state.link) {
        compareNode.appendChild(element('p', 'tl-compare__detail', 'All ranked. Get a share link below and send yours back.'));
      }
    }

    function tile(id) {
      const item = state.items[id];
      const button = element('button', 'tl-tile');
      button.type = 'button';
      button.dataset.tierItem = id;
      button.setAttribute('aria-pressed', selected === id ? 'true' : 'false');
      const meta = [item.kind ? KIND_LABELS[item.kind] : '', item.year || ''].filter(Boolean).join(' · ');
      button.setAttribute('aria-label', `${item.title}${meta ? `, ${meta}` : ''}`);
      button.title = item.title;
      if (item.image) {
        const image = element('img');
        image.src = item.image;
        image.alt = '';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.referrerPolicy = 'no-referrer';
        image.draggable = false;
        image.width = 72;
        image.height = 108;
        image.addEventListener('error', () => { image.remove(); button.classList.add('tl-tile--text'); });
        button.appendChild(image);
      } else {
        button.classList.add('tl-tile--text');
      }
      button.appendChild(element('span', 'tl-tile__title', item.title));
      return button;
    }

    function render() {
      TIERS.forEach(tier => {
        const row = board.querySelector(`[data-tier-row="${tier}"]`);
        const label = row.querySelector('.tl-tier__label');
        label.replaceChildren();
        const labelButton = element('button', 'tl-tier__rename', state.labels[tier] || tier);
        labelButton.type = 'button';
        labelButton.dataset.tierRename = tier;
        labelButton.setAttribute('aria-label', `Tier ${state.labels[tier] || tier}. Rename`);
        label.appendChild(labelButton);
        const items = row.querySelector('.tl-tier__items');
        items.dataset.tierZone = tier;
        items.replaceChildren(...state.tiers[tier].map(tile));
      });
      poolNode.dataset.tierZone = 'pool';
      poolNode.replaceChildren(...state.pool.map(tile));
      if (!count(state)) poolNode.appendChild(element('p', 'tl-empty', 'Choose a set above or search for titles to begin.'));
      if (poolCount) poolCount.textContent = state.pool.length ? `(${state.pool.length})` : '';
      if (nameInput && document.activeElement !== nameInput) nameInput.value = state.name;
      if (cta) cta.hidden = !ranked(state);
      renderMoveBar();
      renderCompare();
      renderLinkBox();
    }

    function renderMoveBar() {
      if (!moveBar) return;
      const item = selected && state.items[selected];
      moveBar.hidden = !item;
      if (!item) return;
      moveTitle.textContent = `Move “${item.title}” to`;
      const buttons = moveBar.querySelector('.tl-move__buttons');
      const where = locate(state, selected);
      const options = TIERS.map(tier => [tier, state.labels[tier] || tier]).concat([['pool', 'Not ranked'], ['remove', 'Remove']]);
      buttons.replaceChildren(...options.map(([zone, label]) => {
        const button = element('button', `tl-move__button tl-move__button--${zone.toLowerCase()}`, label);
        button.type = 'button';
        button.dataset.tierMoveTo = zone;
        if (where && where.zone === zone) button.setAttribute('aria-current', 'true');
        return button;
      }));
    }

    function select(id) {
      selected = selected === id ? null : id;
      render();
      if (selected) {
        const first = moveBar && moveBar.querySelector('button');
        if (first && window.matchMedia && window.matchMedia('(pointer: coarse)').matches) moveBar.scrollIntoView({ block: 'nearest' });
      }
    }

    function placed(zone) {
      if (zone !== 'pool') report('tier_list_started');
    }

    function refocus(id) {
      const node = tool.querySelector(`[data-tier-item="${id}"]`);
      if (node) node.focus();
    }

    // Tap or keyboard: select a tile, then pick a tier in the move bar.
    tool.addEventListener('click', event => {
      const target = event.target.closest ? event.target.closest('button, a') : null;
      if (!target) return;
      if (target.dataset.tierItem) {
        if (drag.suppressClick) { drag.suppressClick = false; return; }
        select(target.dataset.tierItem);
      } else if (target.dataset.tierMoveTo && selected) {
        const id = selected;
        const zone = target.dataset.tierMoveTo;
        if (zone === 'remove') { removeItem(state, id); selected = null; say('Removed.'); }
        else { moveItem(state, id, zone); placed(zone); selected = null; }
        persist();
        render();
        if (zone !== 'remove') refocus(id);
      } else if (target.dataset.tierRename) {
        const tier = target.dataset.tierRename;
        const value = window.prompt('Name this tier', state.labels[tier] || tier);
        if (value !== null) {
          state.labels[tier] = value.trim().slice(0, MAX_LABEL) || tier;
          persist();
          render();
        }
      } else if (target.dataset.tierTemplate) {
        event.preventDefault();
        startTemplate(target.dataset.tierTemplate);
      } else if (target.hasAttribute('data-tier-export')) {
        exportImage();
      } else if (target.hasAttribute('data-tier-share')) {
        shareImage();
      } else if (target.hasAttribute('data-tier-clear')) {
        if (count(state) && !window.confirm(state.link ? 'Clear this board and start over? Your link keeps the board as it is now.'
          : 'Clear this tier list and start over?')) return;
        clearTimeout(syncTimer);
        state = emptyState();
        selected = null;
        persist();
        render();
        if (preview) preview.hidden = true;
        say('Cleared.');
      } else if (target.hasAttribute('data-tier-save-guest')) {
        saveToGuestList();
      } else if (target.hasAttribute('data-tier-link')) {
        makeLink();
      } else if (target.hasAttribute('data-tier-link-copy')) {
        copyLink();
      } else if (target.hasAttribute('data-tier-link-share')) {
        shareLink();
      } else if (target.dataset.tierAdd !== undefined) {
        const result = searchResults[Number(target.dataset.tierAdd)];
        if (result) addAndAnnounce(result);
      }
    });

    tool.addEventListener('keydown', event => {
      if (event.key === 'Escape' && selected) {
        const id = selected;
        selected = null;
        render();
        refocus(id);
      }
    });

    function addAndAnnounce(raw) {
      if (count(state) >= MAX_ITEMS) { say(`A tier list holds up to ${MAX_ITEMS} titles.`); return; }
      const id = addItem(state, raw);
      say(id ? `Added “${raw.title}”. It is waiting below the board.` : `“${raw.title}” is already on the board.`);
      if (id) { persist(); render(); }
    }

    // ---- Drag with a mouse or pen (touch uses tap and the move bar, so scrolling still works) ----
    const drag = { id: null, ghost: null, startX: 0, startY: 0, active: false, suppressClick: false };

    function zoneAt(x, y) {
      if (drag.ghost) drag.ghost.style.display = 'none';
      const node = document.elementFromPoint(x, y);
      if (drag.ghost) drag.ghost.style.display = '';
      if (!node || !node.closest) return null;
      const row = node.closest('[data-tier-row]');
      const zoneNode = row ? row.querySelector('[data-tier-zone]') : node.closest('[data-tier-zone]');
      if (!zoneNode) return null;
      const before = node.closest('[data-tier-item]');
      let beforeId = before && zoneNode.contains(before) ? before.dataset.tierItem : null;
      if (before && beforeId) {
        const rect = before.getBoundingClientRect();
        if (x > rect.left + rect.width / 2) {
          const next = before.nextElementSibling;
          beforeId = next && next.dataset.tierItem ? next.dataset.tierItem : null;
        }
      }
      return { zone: zoneNode.dataset.tierZone, node: zoneNode, beforeId };
    }

    tool.addEventListener('pointerdown', event => {
      if (event.pointerType === 'touch' || event.button !== 0) return;
      const target = event.target.closest ? event.target.closest('[data-tier-item]') : null;
      if (!target) return;
      drag.id = target.dataset.tierItem;
      drag.startX = event.clientX;
      drag.startY = event.clientY;
      drag.active = false;
    });

    document.addEventListener('pointermove', event => {
      if (!drag.id) return;
      if (!drag.active) {
        if (Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY) < 6) return;
        const source = tool.querySelector(`[data-tier-item="${drag.id}"]`);
        if (!source) { drag.id = null; return; }
        drag.active = true;
        drag.ghost = source.cloneNode(true);
        drag.ghost.classList.add('tl-tile--ghost');
        drag.ghost.removeAttribute('data-tier-item');
        document.body.appendChild(drag.ghost);
        source.classList.add('tl-tile--dragging');
        document.body.classList.add('tl-dragging');
      }
      drag.ghost.style.transform = `translate(${event.clientX - 36}px, ${event.clientY - 54}px)`;
      // Scroll while dragging near the top or bottom edge, so the pool can reach the S tier on short screens.
      const edge = 70;
      if (event.clientY < edge) window.scrollBy(0, -14);
      else if (event.clientY > window.innerHeight - edge) window.scrollBy(0, 14);
      tool.querySelectorAll('.tl-zone--over').forEach(node => node.classList.remove('tl-zone--over'));
      const over = zoneAt(event.clientX, event.clientY);
      if (over) over.node.classList.add('tl-zone--over');
    });

    function endDrag(event, cancelled) {
      if (!drag.id) return;
      const id = drag.id;
      drag.id = null;
      if (!drag.active) return;
      drag.active = false;
      drag.suppressClick = true;
      setTimeout(() => { drag.suppressClick = false; }, 0);
      const over = cancelled ? null : zoneAt(event.clientX, event.clientY);
      if (drag.ghost) drag.ghost.remove();
      drag.ghost = null;
      document.body.classList.remove('tl-dragging');
      if (over && moveItem(state, id, over.zone, over.beforeId)) {
        placed(over.zone);
        selected = null;
        persist();
      }
      render();
    }
    document.addEventListener('pointerup', event => endDrag(event, false));
    document.addEventListener('pointercancel', event => endDrag(event, true));

    // ---- Sources ----
    async function getTemplate(key) {
      const data = await api(`/api/tier-list/templates?key=${encodeURIComponent(key)}`);
      return (Array.isArray(data.templates) ? data.templates : []).find(entry => entry.key === key) || null;
    }

    function replaceBoard(next) {
      clearTimeout(syncTimer);
      state = next;
      selected = null;
      save(state);
      lastBlob = null;
      if (shareButton) shareButton.hidden = true;
      if (preview) preview.hidden = true;
      render();
    }

    function scrollToBoard() {
      const wrap = tool.querySelector('.tl-board-wrap');
      if (wrap && wrap.scrollIntoView) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function startTemplate(key) {
      try {
        const template = await getTemplate(key);
        if (!template) { say('That set is not available right now.'); return; }
        if (count(state) && !window.confirm(`Start “${template.name}”? This replaces your current board.`)) return;
        replaceBoard(fromTemplate(template));
        report('tier_list_template_started');
        say(`${count(state)} titles are waiting below the board. Drag or tap each one into a tier.`);
        scrollToBoard();
      } catch (error) {
        say('Could not load that set. Check your connection and try again.');
      }
    }

    // /tier-list?remix=<token>: the same titles as someone's shared list, unranked.
    async function startRemix(token) {
      try {
        const data = await api(`/api/tier-list/shares/${token}`);
        if (state.source && state.source.token === token && count(state)) {
          say('Your take on this list is below. Keep ranking.');
          return;
        }
        if (count(state) && !window.confirm(`Rank the titles from “${data.name}”? This replaces your current board.`)) return;
        const next = emptyState();
        next.name = `My take: ${data.name}`.slice(0, 80);
        next.template = typeof data.template === 'string' ? data.template : null;
        TIERS.forEach(tier => (data.tiers[tier] || []).forEach(item => addItem(next, item)));
        next.source = sourceFromShare(data);
        next.labels = Object.assign({}, next.labels, data.labels || {});
        replaceBoard(next);
        report('tier_list_remix_started');
        say(`${count(state)} titles from “${data.name}” are waiting below the board. Rank them your way.`);
        scrollToBoard();
      } catch (error) {
        say(error.status === 404 ? 'That tier list link has ended, so its titles could not be loaded.' : error.message);
      }
    }

    // /tier-list?edit=<token>: put a shared list back on the board to change it.
    async function startEdit(token) {
      if (state.link === token) { say('This is the board behind your link. Changes you make update it.'); return; }
      try {
        const data = await api(`/api/tier-list/shares/${token}`);
        if (!signedIn && !linkKey(token)) { say('Only the browser or account that made this link can change it.'); return; }
        if (count(state) && !window.confirm(`Load “${data.name}” to edit it? This replaces your current board.`)) return;
        const next = emptyState();
        next.name = data.name;
        next.template = typeof data.template === 'string' ? data.template : null;
        next.labels = Object.assign({}, next.labels, data.labels || {});
        TIERS.forEach(tier => (data.tiers[tier] || []).forEach(item => addItem(next, item, tier)));
        next.link = token;
        replaceBoard(next);
        say('Your shared board is loaded. Changes you make update the link.');
        scrollToBoard();
      } catch (error) {
        say(error.status === 404 ? 'That tier list link has ended.' : error.message);
      }
    }

    // Starting-set filter inside "Browse all".
    const setFilter = tool.querySelector('[data-tier-set-filter]');
    if (setFilter) {
      setFilter.addEventListener('input', () => {
        const query = setFilter.value.trim().toLowerCase();
        let shown = 0;
        tool.querySelectorAll('[data-tier-set-group]').forEach(group => {
          let inGroup = 0;
          group.querySelectorAll('[data-tier-set-name]').forEach(link => {
            const match = !query || link.dataset.tierSetName.includes(query);
            link.parentElement.hidden = !match;
            if (match) inGroup += 1;
          });
          group.hidden = !inGroup;
          shown += inGroup;
        });
        const none = tool.querySelector('[data-tier-set-none]');
        if (none) none.hidden = shown > 0;
      });
    }

    // Members: links made here before signing up move into the account, then the list of links.
    const mineNode = document.querySelector('[data-tier-mine]');
    const mineList = mineNode && mineNode.querySelector('[data-tier-mine-list]');
    async function claimLinks() {
      const waiting = readLinks().filter(link => link.key && !link.claimed);
      if (!signedIn || !waiting.length) return;
      try {
        const result = await api('/api/tier-list/shares/claim', { method: 'POST', body: { links: waiting.map(link => ({ token: link.token, key: link.key })) } });
        writeLinks(readLinks().map(link => (waiting.some(entry => entry.token === link.token) ? Object.assign({}, link, { claimed: true }) : link)));
        if (result.claimed) say(`${result.claimed} tier list link${result.claimed === 1 ? '' : 's'} you made before signing up ${result.claimed === 1 ? 'is' : 'are'} now in your account, with no expiry.`);
      } catch (error) { /* tried again next visit */ }
    }

    async function refreshMine() {
      if (!signedIn || !mineList) return;
      try {
        const data = await api('/api/tier-list/shares/mine');
        const links = Array.isArray(data.links) ? data.links : [];
        mineNode.hidden = !links.length;
        mineList.replaceChildren(...links.map(link => {
          const row = element('li', 'tl-mine__item');
          const name = element('a', 'tl-mine__name', link.name);
          name.href = link.path;
          const facts = [`${link.count} titles`];
          if (link.views) facts.push(`opened ${link.views} time${link.views === 1 ? '' : 's'}`);
          if (link.remixes) facts.push(`${link.remixes} ranked it themselves`);
          const meta = element('span', 'tl-mine__meta', facts.join(' · '));
          const edit = element('a', 'tl-mine__action', 'Edit');
          edit.href = `/tier-list?edit=${link.token}`;
          const remove = element('button', 'tl-mine__action', 'Delete');
          remove.type = 'button';
          remove.addEventListener('click', async () => {
            if (!window.confirm(`Delete the link for “${link.name}”? Anyone who has it will see that it has ended.`)) return;
            try {
              await api(`/api/tier-list/shares/${link.token}`, { method: 'DELETE', body: { key: linkKey(link.token) } });
              forgetLink(link.token);
              if (state.link === link.token) { state.link = null; save(state); renderLinkBox(); }
              refreshMine();
            } catch (error) { say(error.message); }
          });
          row.append(name, meta, edit, remove);
          return row;
        }));
      } catch (error) { /* the list is a convenience */ }
    }

    const searchForm = tool.querySelector('[data-tier-search]');
    const searchInput = searchForm && searchForm.querySelector('input');
    const resultsNode = searchForm && searchForm.querySelector('[data-tier-results]');
    let searchResults = [];
    let searchTimer = null;
    let searchGeneration = 0;
    async function runSearch() {
      const query = searchInput.value.trim();
      const current = ++searchGeneration;
      if (query.replace(/[^\p{L}\p{N}]/gu, '').length < 2) { resultsNode.hidden = true; resultsNode.replaceChildren(); return; }
      try {
        const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query.slice(0, 80))}`, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const data = await response.json();
        if (current !== searchGeneration) return;
        searchResults = Array.isArray(data.results) ? data.results : [];
        if (!searchResults.length) {
          resultsNode.replaceChildren(element('p', 'tl-empty', `No match for “${query}”. Use “Add any title by name” below instead.`));
        } else {
          const list = element('ul', 'tl-results');
          searchResults.forEach((result, index) => {
            const button = element('button', 'tl-result');
            button.type = 'button';
            button.dataset.tierAdd = String(index);
            button.appendChild(element('strong', '', result.title));
            button.appendChild(element('span', '', [result.label, result.year].filter(Boolean).join(' · ')));
            const row = element('li');
            row.appendChild(button);
            list.appendChild(row);
          });
          resultsNode.replaceChildren(list);
        }
        resultsNode.hidden = false;
      } catch (error) {
        if (current === searchGeneration) {
          resultsNode.replaceChildren(element('p', 'tl-empty', 'Search is not available right now.'));
          resultsNode.hidden = false;
        }
      }
    }
    if (searchForm) {
      searchForm.addEventListener('submit', event => { event.preventDefault(); runSearch(); });
      searchInput.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 220); });
    }

    const customForm = tool.querySelector('[data-tier-custom]');
    if (customForm) {
      customForm.addEventListener('submit', event => {
        event.preventDefault();
        const input = customForm.querySelector('input');
        const title = input.value.trim();
        if (!title) return;
        addAndAnnounce({ title });
        input.value = '';
      });
    }

    const libraryForm = tool.querySelector('[data-tier-library]');
    if (libraryForm && libraryForm.tagName === 'FORM') {
      libraryForm.addEventListener('submit', async event => {
        event.preventDefault();
        const select = libraryForm.querySelector('select');
        const kind = select.value;
        const label = select.options[select.selectedIndex].textContent;
        try {
          const response = await fetch(`/api/tier-list/library?kind=${encodeURIComponent(kind)}`, { credentials: 'same-origin' });
          if (response.status === 401) { say('Log in again to use your library.'); return; }
          if (!response.ok) throw new Error(String(response.status));
          const data = await response.json();
          const items = Array.isArray(data.items) ? data.items : [];
          if (!items.length) { say(`No ${label.toLowerCase()} in your library yet.`); return; }
          if (count(state) && !window.confirm(`Rank your ${label.toLowerCase()}? This replaces your current board.`)) return;
          state = fromTemplate({ items }, `My ${label.toLowerCase()}, ranked`);
          selected = null;
          persist();
          render();
          const unrated = state.pool.length;
          say(`${ranked(state)} titles placed by your ratings${unrated ? `, ${unrated} unrated below the board` : ''}. Move anything that feels wrong.`);
          report('tier_list_started');
        } catch (error) {
          say('Could not load your library right now.');
        }
      });
    }

    if (nameInput) {
      nameInput.addEventListener('input', () => { state.name = nameInput.value.slice(0, 80); persist(); });
    }

    // ---- Export and share ----
    async function exportImage() {
      if (!ranked(state)) { say('Put at least one title in a tier first.'); return; }
      say('Drawing your image…');
      try {
        const canvas = await renderImage(state, document);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        if (!blob) throw new Error('empty');
        lastBlob = blob;
        const url = URL.createObjectURL(blob);
        const link = element('a');
        link.href = url;
        link.download = fileName(state);
        document.body.appendChild(link);
        link.click();
        link.remove();
        // The page's image policy allows data: URLs but not blob: ones.
        if (preview) { preview.src = canvas.toDataURL('image/png'); preview.hidden = false; }
        setTimeout(() => URL.revokeObjectURL(url), 10000);
        const file = typeof File === 'function' ? new File([blob], fileName(state), { type: 'image/png' }) : null;
        if (shareButton) shareButton.hidden = !(file && navigator.canShare && navigator.canShare({ files: [file] }));
        report('tier_list_exported');
        say('Saved. Post it anywhere, or share it straight from here.');
      } catch (error) {
        say('Could not draw the image in this browser. A screenshot of the board works too.');
      }
    }

    async function shareImage() {
      if (!lastBlob) { await exportImage(); if (!lastBlob) return; }
      try {
        const file = new File([lastBlob], fileName(state), { type: 'image/png' });
        await navigator.share({ files: [file], title: state.name, text: 'My tier list, made on OmniTrackr: https://omnitrackr.xyz/tier-list' });
        report('tier_list_exported');
      } catch (error) { /* share sheet closed */ }
    }

    function saveToGuestList() {
      const list = window.OmniGuestList;
      if (!list) return;
      let added = 0;
      let full = false;
      TIERS.flatMap(tier => state.tiers[tier]).forEach(id => {
        const item = state.items[id];
        if (!item || !item.slug || !item.kind || full) return;
        const result = list.add(item.kind, item.slug, item.title);
        if (result.added) added += 1;
        if (result.full) full = true;
      });
      if (typeof list.refreshTiles === 'function') list.refreshTiles();
      const total = list.read().length;
      say(added ? `Saved ${added} title${added === 1 ? '' : 's'}. ${total} on your list; create a free library to keep them.`
        : (full ? `Your list is full (${list.MAX}). Create a free library to keep going.`
          : 'Those titles are already on your list, or were added by name only.'));
    }

    render();
    const key = tool.dataset.template;
    const remix = tool.dataset.remix;
    const edit = tool.dataset.edit;
    if (edit && TOKEN.test(edit)) startEdit(edit);
    else if (remix && TOKEN.test(remix)) startRemix(remix);
    else if (key && (!count(state))) startTemplate(key);
    else if (key) say('Your saved board is below. Choose the set again to start it fresh.');
    if (signedIn) claimLinks().then(refreshMine);
  }

  // The page a shared link opens (/tier-list/s/<token>).
  function initShared() {
    const page = document.getElementById('tierShare');
    if (!page) return;
    const token = page.dataset.token;
    const status = page.querySelector('[data-tier-status]');
    const say = text => { if (status) status.textContent = text; };
    const address = `${window.location.origin}/tier-list/s/${token}`;
    const owner = page.querySelector('[data-tier-owner]');
    const key = linkKey(token);
    if (owner && page.dataset.owner !== 'true' && key) owner.hidden = false;
    const shareButton = page.querySelector('[data-tier-shared-share]');
    if (shareButton) shareButton.hidden = !navigator.share;
    page.addEventListener('click', async event => {
      const target = event.target.closest ? event.target.closest('button, a') : null;
      if (!target) return;
      if (target.hasAttribute('data-tier-shared-copy')) {
        try { await navigator.clipboard.writeText(address); say('Link copied.'); } catch (error) { say(address); }
      } else if (target.hasAttribute('data-tier-shared-share')) {
        try {
          await navigator.share({ title: document.title, text: 'Rank these yourself and see if we agree:', url: address });
          report('share_clicked');
        } catch (error) { /* share sheet closed */ }
      } else if (target.hasAttribute('data-tier-shared-delete')) {
        if (!window.confirm('Delete this link? Anyone who has it will see that it has ended.')) return;
        try {
          const response = await fetch(`/api/tier-list/shares/${token}`, {
            method: 'DELETE', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }),
          });
          if (!response.ok && response.status !== 404) throw new Error(String(response.status));
          forgetLink(token);
          window.location.href = '/tier-list';
        } catch (error) {
          say('Could not delete the link. Try again in a moment.');
        }
      }
    });
  }

  function trackSignup() {
    document.addEventListener('click', event => {
      const target = event.target.closest ? event.target.closest('[data-tier-signup]') : null;
      if (target) report('tier_list_signup_clicked');
    });
  }

  const exported = {
    emptyState, normalizeState, addItem, moveItem, removeItem, fromTemplate, cleanItem, exportLayout, fileName,
    agreement, sourceFromShare, sharePayload, titleKey, TIERS, MAX_ITEMS,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  if (typeof document !== 'undefined' && document.addEventListener) {
    const start = () => { init(); initShared(); trackSignup(); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }
})();
