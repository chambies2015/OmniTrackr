// Tier list maker (/tier-list). The board lives only in this browser (localStorage);
// titles come from ready-made sets (GET /api/tier-list/templates), the members'
// title search (GET /api/titles/search), free text, or a member's own ratings
// (GET /api/tier-list/library). Everything is drawn with textContent only. The
// exported picture is drawn on a canvas, with posters fetched through the
// same-origin /api/tier-list/image proxy so the canvas can be saved.
(function () {
  'use strict';

  const KEY = 'omnitrackr_tier_list';
  const TIERS = ['S', 'A', 'B', 'C', 'D'];
  const TIER_COLORS = { S: '#f472b6', A: '#fb923c', B: '#facc15', C: '#4ade80', D: '#60a5fa' };
  const KINDS = new Set(['movie', 'tv', 'anime', 'game', 'album', 'book']);
  const KIND_LABELS = { movie: 'Movie', tv: 'TV show', anime: 'Anime', game: 'Video game', album: 'Album', book: 'Book' };
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
    return { name: 'My tier list', labels: Object.assign({}, ...TIERS.map(t => ({ [t]: t }))), tiers, pool: [], items: {}, next: 1 };
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
    state.name = (name || template.name || 'My tier list').slice(0, 80);
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
    ctx.fillText('omnitrackr.xyz/tier-list', EXPORT.width - EXPORT.pad, layout.height - 26);
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
    let state = load() || emptyState();
    let selected = null;
    let templates = null;
    let lastBlob = null;

    function say(text) { if (status) status.textContent = text; }

    function persist() {
      save(state);
      lastBlob = null;
      if (shareButton) shareButton.hidden = true;
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
        if (count(state) && !window.confirm('Clear this tier list and start over?')) return;
        state = emptyState();
        selected = null;
        persist();
        render();
        if (preview) preview.hidden = true;
        say('Cleared.');
      } else if (target.hasAttribute('data-tier-save-guest')) {
        saveToGuestList();
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
    async function getTemplates() {
      if (templates) return templates;
      const response = await fetch('/api/tier-list/templates', { credentials: 'same-origin' });
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      templates = Array.isArray(data.templates) ? data.templates : [];
      return templates;
    }

    async function startTemplate(key) {
      try {
        const template = (await getTemplates()).find(entry => entry.key === key);
        if (!template) { say('That set is not available right now.'); return; }
        if (count(state) && !window.confirm(`Start “${template.name}”? This replaces your current board.`)) return;
        state = fromTemplate(template);
        selected = null;
        persist();
        render();
        say(`${count(state)} titles are waiting below the board. Drag or tap each one into a tier.`);
        const wrap = tool.querySelector('.tl-board-wrap');
        if (wrap && wrap.scrollIntoView) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (error) {
        say('Could not load that set. Check your connection and try again.');
      }
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
    if (key && (!count(state))) startTemplate(key);
    else if (key) say('Your saved board is below. Choose the set again to start it fresh.');
  }

  const api = { emptyState, normalizeState, addItem, moveItem, removeItem, fromTemplate, cleanItem, exportLayout, fileName, TIERS, MAX_ITEMS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
