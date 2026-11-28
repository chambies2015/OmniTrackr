// Top nine (/top-nine): pick nine titles for a 3x3 grid, then get pictures and a link.
// The maker keeps its draft in this browser; the server only stores a grid once
// "Make my pictures" is pressed (POST /api/top-nine), and later changes update it.
// A shared grid (/top-nine/<token>) lets visitors tap the squares they've seen too.
(function () {
  'use strict';

  const DRAFT_KEY = 'omnitrackr_top_nine_draft';
  const LINKS_KEY = 'omnitrackr_top_nine_links';
  const KEEP_KEY = 'omnitrackr_top_nine_keep';
  const SLOTS = 9;
  const MIN_FILLED = 3;
  const MAX_NAME = 40;
  const KINDS = {
    movie: ['Film', 'films'], tv: ['Show', 'shows'], anime: ['Anime', 'anime'], game: ['Game', 'games'],
    album: ['Album', 'albums'], book: ['Book', 'books'], manga: ['Manga', 'manga'],
    podcast: ['Podcast', 'podcasts'], audiobook: ['Audiobook', 'audiobooks'],
  };
  const SLUG = /^[a-z0-9-]{1,130}$/;
  const TOKEN = /^[A-Za-z0-9_-]{16,32}$/;
  const APP_BROWSER = /Instagram|FBAN|FBAV|FB_IAB|TikTok|musical_ly|BytedanceWebview|Snapchat|Line\/|LinkedInApp|Pinterest/i;

  function report(event) {
    report.sent = report.sent || new Set();
    if (report.sent.has(event)) return;
    report.sent.add(event);
    try {
      if (typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function readJSON(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || 'null');
      return value === null ? fallback : value;
    } catch (error) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function safeImage(url) {
    return typeof url === 'string' && /^https:\/\//i.test(url) && url.length < 1000 ? url : null;
  }

  function cleanTile(raw) {
    if (!raw || typeof raw !== 'object' || typeof raw.title !== 'string' || !KINDS[raw.kind]) return null;
    const title = raw.title.replace(/\s+/g, ' ').trim().slice(0, 200);
    if (!title) return null;
    const year = Number.isInteger(raw.year) && raw.year >= 1000 && raw.year <= 2200 ? raw.year : null;
    return {
      title, kind: raw.kind, year,
      slug: typeof raw.slug === 'string' && SLUG.test(raw.slug) ? raw.slug : null,
      creator: typeof raw.creator === 'string' && raw.creator.trim() ? raw.creator.trim().slice(0, 120) : null,
      image: safeImage(raw.image),
      thumb: safeImage(raw.thumb),
    };
  }

  function sameTitle(a, b) {
    return a && b && a.kind === b.kind && a.title.toLowerCase() === b.title.toLowerCase() && (a.year || 0) === (b.year || 0);
  }

  function meta(tile) {
    return [KINDS[tile.kind][0], tile.creator, tile.year].filter(Boolean).join(' · ');
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      return false;
    }
  }

  function links() {
    const list = readJSON(LINKS_KEY, []);
    return Array.isArray(list) ? list.filter(link => link && TOKEN.test(link.token || '') && typeof link.key === 'string').slice(-12) : [];
  }

  function rememberLink(token, key, year) {
    const list = links().filter(link => link.token !== token);
    list.push({ token, key, year, at: Date.now() });
    writeJSON(LINKS_KEY, list.slice(-12));
  }

  function keyFor(token) {
    const link = links().find(item => item.token === token);
    return link ? link.key : null;
  }

  function forgetLinks(tokens) {
    const drop = new Set(tokens);
    writeJSON(LINKS_KEY, links().filter(link => !drop.has(link.token)));
  }

  // ---- The maker ---------------------------------------------------------

  function maker(root) {
    const year = Number(root.dataset.year) || new Date().getFullYear();
    const signedIn = root.dataset.signedIn === 'true';
    const frame = root.querySelector('[data-tn-frame]');
    const gridNode = root.querySelector('[data-tn-grid]');
    const nameInput = root.querySelector('[data-tn-name]');
    const cellbar = root.querySelector('[data-tn-cellbar]');
    const cellbarLabel = root.querySelector('[data-tn-cellbar-label]');
    const pickerTitle = root.querySelector('[data-tn-picker-title]');
    const searchForm = root.querySelector('[data-tn-search]');
    const searchInput = searchForm.querySelector('input');
    const chips = Array.from(root.querySelectorAll('[data-tn-kind]'));
    const resultsHead = root.querySelector('[data-tn-results-head]');
    const resultsNode = root.querySelector('[data-tn-results]');
    const customForm = root.querySelector('[data-tn-custom]');
    const customLead = root.querySelector('[data-tn-custom-lead]');
    const customKind = root.querySelector('[data-tn-custom-kind]');
    const makeButton = root.querySelector('[data-tn-make]');
    const doneHint = root.querySelector('[data-tn-done-hint]');
    const ready = root.querySelector('[data-tn-ready]');
    const preview = root.querySelector('[data-tn-preview]');
    const saveLinks = Array.from(root.querySelectorAll('[data-tn-save]'));
    const shareImageButton = root.querySelector('[data-tn-share-image]');
    const appNote = root.querySelector('[data-tn-appnote]');
    const linkInput = root.querySelector('[data-tn-link-url]');
    const copyButton = root.querySelector('[data-tn-copy]');
    const shareButton = root.querySelector('[data-tn-share]');
    const note = root.querySelector('[data-tn-note]');
    const cta = root.querySelector('[data-tn-cta]');
    const keepBox = root.querySelector('[data-tn-keep-box]');
    const keepButton = root.querySelector('[data-tn-keep]');
    const clearButton = root.querySelector('[data-tn-clear]');
    const status = root.querySelector('[data-tn-status]');
    const mineBox = root.querySelector('[data-tn-mine]');
    const mineList = root.querySelector('[data-tn-mine-list]');
    const dock = root.querySelector('[data-tn-dock]');
    const dockText = root.querySelector('[data-tn-dock-text]');
    const dockUp = root.querySelector('[data-tn-dock-up]');
    const inApp = APP_BROWSER.test(navigator.userAgent || '');

    let state = loadDraft();
    let selected = firstEmpty();
    let kind = '';
    let results = [];
    let searchTimer = null;
    let searchGeneration = 0;
    let saveTimer = null;
    let saving = false;
    let saveAgain = false;
    let clearArmed = false;

    function blank() {
      return { v: 1, year, name: `My ${year}`, theme: 'night', tiles: new Array(SLOTS).fill(null), token: null, key: null,
               version: null, source: null };
    }

    function loadDraft() {
      const raw = readJSON(DRAFT_KEY, null);
      if (!raw || raw.v !== 1 || raw.year !== year || !Array.isArray(raw.tiles)) return blank();
      const tiles = raw.tiles.slice(0, SLOTS).map(cleanTile);
      while (tiles.length < SLOTS) tiles.push(null);
      return {
        v: 1, year, tiles,
        name: typeof raw.name === 'string' ? raw.name.slice(0, MAX_NAME) : `My ${year}`,
        theme: ['night', 'paper', 'berry'].includes(raw.theme) ? raw.theme : 'night',
        token: TOKEN.test(raw.token || '') ? raw.token : null,
        key: typeof raw.key === 'string' ? raw.key : null,
        version: typeof raw.version === 'string' ? raw.version : null,
        source: TOKEN.test(raw.source || '') ? raw.source : null,
      };
    }

    function persist() {
      writeJSON(DRAFT_KEY, { ...state, tiles: state.tiles, at: Date.now() });
    }

    function filled() {
      return state.tiles.filter(Boolean).length;
    }

    function firstEmpty(after) {
      const start = typeof after === 'number' ? after + 1 : 0;
      for (let offset = 0; offset < SLOTS; offset += 1) {
        const index = (start + offset) % SLOTS;
        if (!state.tiles[index]) return index;
      }
      return -1;
    }

    function say(text) {
      status.textContent = text || '';
    }

    // ---- drawing the grid

    function cellContent(button, tile, index) {
      button.textContent = '';
      button.appendChild(el('span', 'tn-cell__num', String(index + 1)));
      if (!tile) {
        button.className = 'tn-cell tn-cell--empty';
        button.appendChild(el('span', 'tn-cell__add', '+'));
        button.setAttribute('aria-label', `Square ${index + 1}, empty. Choose a title`);
        button.draggable = false;
        return;
      }
      const image = tile.thumb || tile.image;
      if (image) {
        button.className = 'tn-cell tn-cell--art';
        const img = el('img');
        img.src = image;
        img.alt = '';
        img.decoding = 'async';
        img.referrerPolicy = 'no-referrer';
        img.width = 300;
        img.height = 400;
        img.addEventListener('error', () => {
          // A dead cover becomes a drawn square, here and in the pictures.
          tile.thumb = null;
          tile.image = null;
          persist();
          drawGrid();
          scheduleSave();
        }, { once: true });
        button.appendChild(img);
      } else {
        button.className = `tn-cell tn-cell--text tn-kind--${tile.kind}`;
        button.appendChild(el('span', 'tn-cell__kind', KINDS[tile.kind][0]));
        button.appendChild(el('span', 'tn-cell__name', tile.title));
      }
      button.setAttribute('aria-label', `Square ${index + 1}: ${tile.title}, ${meta(tile)}. Choose to move, change or remove it`);
      button.draggable = true;
    }

    function drawGrid() {
      frame.className = `tn-frame tn-theme--${state.theme}`;
      const buttons = gridNode.querySelectorAll('[data-tn-cell]');
      buttons.forEach(button => {
        const index = Number(button.dataset.tnCell);
        cellContent(button, state.tiles[index], index);
        button.classList.toggle('is-selected', index === selected);
        button.setAttribute('aria-pressed', index === selected ? 'true' : 'false');
      });
      const count = filled();
      makeButton.disabled = count < MIN_FILLED;
      doneHint.textContent = count < MIN_FILLED
        ? `Fill at least ${MIN_FILLED} squares to make the pictures. Nine looks best.`
        : count < SLOTS ? `${count} of 9 squares filled. You can make the pictures now, or fill the rest first.`
          : 'All nine squares are filled.';
      drawPickerTitle();
      drawCellbar();
      drawDock();
    }

    function drawPickerTitle() {
      if (selected < 0) {
        pickerTitle.textContent = 'All nine squares are filled';
        return;
      }
      const tile = state.tiles[selected];
      pickerTitle.textContent = tile ? `Change square ${selected + 1}` : `Square ${selected + 1}`;
    }

    function drawCellbar() {
      const tile = selected >= 0 ? state.tiles[selected] : null;
      cellbar.hidden = !tile;
      if (!tile) return;
      cellbarLabel.textContent = `${selected + 1}. ${tile.title}`;
      cellbar.querySelector('[data-tn-move="-1"]').disabled = selected === 0;
      cellbar.querySelector('[data-tn-move="1"]').disabled = selected === SLOTS - 1;
    }

    function drawDock() {
      if (!dock) return;
      const count = filled();
      dockText.textContent = selected >= 0 ? `${count} of 9 filled · square ${selected + 1} next` : `${count} of 9 filled`;
    }

    function select(index) {
      selected = index;
      drawGrid();
    }

    // ---- changing squares

    function place(raw) {
      const tile = cleanTile(raw);
      if (!tile) return;
      const already = state.tiles.findIndex(other => sameTitle(other, tile));
      if (already >= 0 && already !== selected) {
        say(`${tile.title} is already in square ${already + 1}.`);
        return;
      }
      let index = selected >= 0 ? selected : firstEmpty();
      if (index < 0) {
        say('All nine squares are filled. Tap one to change it.');
        return;
      }
      state.tiles[index] = tile;
      if (filled() === 1) report('top_nine_started');
      selected = firstEmpty(index);
      persist();
      drawGrid();
      say(`${tile.title} is in square ${index + 1}.`);
      if (!tile.image) findArt(index, tile);
      scheduleSave();
    }

    async function findArt(index, tile) {
      const params = new URLSearchParams({ kind: tile.kind, title: tile.title });
      if (tile.year) params.set('year', String(tile.year));
      if (tile.creator) params.set('creator', tile.creator);
      try {
        const response = await fetch(`/api/top-nine/art?${params}`, { credentials: 'same-origin' });
        if (!response.ok) return;
        const data = await response.json();
        const current = state.tiles[index];
        if (!current || !sameTitle(current, tile) || current.image) return;
        current.image = safeImage(data.image);
        current.thumb = safeImage(data.thumb);
        if (current.image) {
          persist();
          drawGrid();
          scheduleSave();
        }
      } catch (error) { /* the square stays a drawn one */ }
    }

    function move(step) {
      const target = selected + step;
      if (selected < 0 || target < 0 || target >= SLOTS) return;
      [state.tiles[selected], state.tiles[target]] = [state.tiles[target], state.tiles[selected]];
      selected = target;
      persist();
      drawGrid();
      scheduleSave();
    }

    function swap(from, to) {
      if (from === to || from < 0 || to < 0) return;
      [state.tiles[from], state.tiles[to]] = [state.tiles[to], state.tiles[from]];
      selected = to;
      persist();
      drawGrid();
      scheduleSave();
    }

    function removeSelected() {
      if (selected < 0 || !state.tiles[selected]) return;
      const title = state.tiles[selected].title;
      state.tiles[selected] = null;
      persist();
      drawGrid();
      say(`${title} is out. Square ${selected + 1} is empty.`);
      scheduleSave();
    }

    gridNode.addEventListener('click', event => {
      const button = event.target.closest('[data-tn-cell]');
      if (!button) return;
      const index = Number(button.dataset.tnCell);
      select(index === selected && state.tiles[index] ? -1 : index);
      if (selected >= 0 && window.matchMedia('(max-width: 899px)').matches) {
        root.querySelector('[data-tn-picker]').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    let dragFrom = -1;
    gridNode.addEventListener('dragstart', event => {
      const button = event.target.closest('[data-tn-cell]');
      if (!button) return;
      dragFrom = Number(button.dataset.tnCell);
      try { event.dataTransfer.setData('text/plain', String(dragFrom)); } catch (error) { /* some browsers */ }
      event.dataTransfer.effectAllowed = 'move';
    });
    gridNode.addEventListener('dragover', event => {
      if (dragFrom >= 0 && event.target.closest('[data-tn-cell]')) event.preventDefault();
    });
    gridNode.addEventListener('drop', event => {
      const button = event.target.closest('[data-tn-cell]');
      if (!button || dragFrom < 0) return;
      event.preventDefault();
      swap(dragFrom, Number(button.dataset.tnCell));
      dragFrom = -1;
    });
    gridNode.addEventListener('dragend', () => { dragFrom = -1; });

    cellbar.addEventListener('click', event => {
      const moveButton = event.target.closest('[data-tn-move]');
      if (moveButton) move(Number(moveButton.dataset.tnMove));
      if (event.target.closest('[data-tn-remove]')) removeSelected();
    });

    nameInput.addEventListener('input', () => {
      state.name = nameInput.value.slice(0, MAX_NAME);
      persist();
      scheduleSave();
    });

    root.querySelectorAll('[data-tn-theme]').forEach(input => {
      input.addEventListener('change', () => {
        if (!input.checked) return;
        state.theme = input.value;
        persist();
        drawGrid();
        scheduleSave();
      });
    });

    // ---- the picker

    function resultButton(raw) {
      const tile = cleanTile(raw);
      const button = el('button', 'tn-result');
      button.type = 'button';
      const art = el('span', `tn-result__art tn-kind--${tile.kind}`);
      const thumb = tile.thumb || tile.image;
      if (thumb) {
        const img = el('img');
        img.src = thumb;
        img.alt = '';
        img.loading = 'lazy';
        img.decoding = 'async';
        img.referrerPolicy = 'no-referrer';
        img.width = 48;
        img.height = 64;
        art.appendChild(img);
      } else {
        art.textContent = tile.title.slice(0, 1).toUpperCase();
      }
      const text = el('span', 'tn-result__text');
      text.appendChild(el('strong', '', tile.title));
      text.appendChild(el('span', '', meta(tile)));
      button.appendChild(art);
      button.appendChild(text);
      const markIn = () => {
        if (button.classList.contains('is-in')) return;
        button.classList.add('is-in');
        text.appendChild(el('span', 'tn-result__in', 'In your grid'));
      };
      if (state.tiles.some(other => sameTitle(other, tile))) markIn();
      button.addEventListener('click', () => {
        place(tile);
        if (state.tiles.some(other => sameTitle(other, tile))) markIn();
      });
      return button;
    }

    function drawResults(groups) {
      resultsNode.textContent = '';
      let any = false;
      groups.forEach(group => {
        if (!group.items.length) return;
        any = true;
        if (group.label) resultsNode.appendChild(el('h3', 'tn-results__group', group.label));
        const list = el('div', 'tn-results__list');
        const shown = group.shown || group.items.length;
        group.items.slice(0, shown).forEach(item => list.appendChild(resultButton(item)));
        resultsNode.appendChild(list);
        if (group.items.length > shown) {
          // Long lists start short, so the Post it box stays near the grid.
          const more = el('button', 'tn-textbtn tn-results__more', `Show all ${group.items.length}`);
          more.type = 'button';
          more.addEventListener('click', () => {
            group.items.slice(shown).forEach(item => list.appendChild(resultButton(item)));
            more.remove();
          });
          resultsNode.appendChild(more);
        }
      });
      return any;
    }

    async function suggest() {
      resultsHead.textContent = '';
      customForm.hidden = true;
      const current = ++searchGeneration;
      try {
        const response = await fetch(`/api/top-nine/suggest?kind=${encodeURIComponent(kind)}`, { credentials: 'same-origin' });
        const data = response.ok ? await response.json() : {};
        if (current !== searchGeneration) return;
        const mine = data.mine || {};
        const groups = [
          { label: `You finished these in ${year}`, items: (mine.year || []).slice(0, 24), shown: 8 },
          { label: 'You rated these highly', items: (mine.loved || []).slice(0, 12), shown: 4 },
          { label: `${year}'s big releases`, items: (data.big || []).slice(0, 46), shown: 10 },
        ];
        if (!drawResults(groups)) {
          resultsNode.textContent = '';
          resultsNode.appendChild(el('p', 'tn-empty', 'Search for a title above.'));
        }
      } catch (error) {
        if (current === searchGeneration) {
          resultsNode.textContent = '';
          resultsNode.appendChild(el('p', 'tn-empty', 'Search for a title above.'));
        }
      }
    }

    async function runSearch() {
      const query = searchInput.value.trim();
      if (query.length < 2) {
        suggest();
        return;
      }
      const current = ++searchGeneration;
      try {
        const params = new URLSearchParams({ q: query.slice(0, 80) });
        if (kind) params.set('kind', kind);
        const response = await fetch(`/api/top-nine/search?${params}`, { credentials: 'same-origin' });
        const data = response.ok ? await response.json() : { results: [] };
        if (current !== searchGeneration) return;
        results = Array.isArray(data.results) ? data.results : [];
        resultsHead.textContent = results.length ? '' : `Nothing on the site matches "${query}" yet.`;
        drawResults([{ label: '', items: results }]);
        customForm.hidden = false;
        customLead.textContent = results.length ? `Not the one? Add "${query}" as` : `Add "${query}" as`;
        if (kind) customKind.value = kind;
      } catch (error) {
        if (current === searchGeneration) say('Search is not answering right now. Try again in a moment.');
      }
    }

    searchForm.addEventListener('submit', event => {
      event.preventDefault();
      clearTimeout(searchTimer);
      runSearch();
    });
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(runSearch, 220);
    });
    chips.forEach(chip => chip.addEventListener('click', () => {
      kind = chip.dataset.tnKind || '';
      chips.forEach(other => other.setAttribute('aria-pressed', other === chip ? 'true' : 'false'));
      runSearch();
    }));
    customForm.addEventListener('submit', event => {
      event.preventDefault();
      const title = searchInput.value.replace(/\s+/g, ' ').trim();
      if (title.length < 1) return;
      place({ title: title.slice(0, 200), kind: customKind.value });
      searchInput.value = '';
      suggest();
    });

    // ---- pictures and the link

    function payload() {
      return {
        name: (state.name || '').trim() || `My ${year}`,
        theme: state.theme,
        tiles: state.tiles.map(tile => tile ? {
          title: tile.title, kind: tile.kind, year: tile.year, slug: tile.slug, creator: tile.creator, image: tile.image,
        } : null),
      };
    }

    function pictureUrl(which, download) {
      const name = which === 'story' ? 'story.jpg' : 'post.jpg';
      return `/top-nine/${state.token}/${name}?${download ? 'download=1&' : ''}v=${encodeURIComponent(state.version || '')}`;
    }

    function drawReady() {
      const made = Boolean(state.token);
      ready.hidden = !made;
      makeButton.hidden = made;
      if (!made) {
        if (cta) cta.hidden = true;
        if (keepBox) keepBox.hidden = true;
        return;
      }
      const url = `${location.origin}/top-nine/${state.token}`;
      linkInput.value = url;
      preview.src = pictureUrl('post', false);
      preview.hidden = false;
      saveLinks.forEach(link => { link.href = pictureUrl(link.dataset.tnSave, true); });
      appNote.hidden = !inApp;
      shareButton.hidden = typeof navigator.share !== 'function';
      shareImageButton.hidden = !(typeof navigator.share === 'function' && typeof navigator.canShare === 'function');
      if (cta) cta.hidden = signedIn;
      if (keepBox) keepBox.hidden = !signedIn;
      note.textContent = signedIn
        ? 'Changes you make here update the link and the pictures.'
        : 'Changes you make in this browser update the link and the pictures.';
    }

    async function send(method) {
      const body = payload();
      if (method === 'POST' && state.source) body.source = state.source;
      if (method === 'PUT' && state.key) body.key = state.key;
      const url = method === 'POST' ? '/api/top-nine' : `/api/top-nine/${state.token}`;
      const response = await fetch(url, {
        method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      let data = {};
      try { data = await response.json(); } catch (error) { data = {}; }
      return { ok: response.ok, status: response.status, data };
    }

    async function make() {
      if (filled() < MIN_FILLED) return;
      makeButton.disabled = true;
      say('Making your pictures…');
      try {
        const reply = await send('POST');
        if (!reply.ok) {
          say(reply.data.detail || 'That did not work. Try again in a moment.');
          makeButton.disabled = false;
          return;
        }
        state.token = reply.data.token;
        state.key = reply.data.key || null;
        state.version = reply.data.version;
        state.source = null;
        if (!reply.data.member && state.key) rememberLink(state.token, state.key, year);
        persist();
        drawReady();
        say('Your pictures and link are ready.');
        ready.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        loadMine();
      } catch (error) {
        say('That did not work. Check your connection and try again.');
      }
      makeButton.disabled = filled() < MIN_FILLED;
    }

    function scheduleSave() {
      if (!state.token) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(saveChanges, 1200);
    }

    async function saveChanges() {
      if (!state.token) return;
      if (filled() < MIN_FILLED) {
        say(`Your link keeps the last version with ${MIN_FILLED} or more squares. Fill a few more to update it.`);
        return;
      }
      if (saving) {
        saveAgain = true;
        return;
      }
      saving = true;
      try {
        const reply = await send('PUT');
        if (reply.ok) {
          state.version = reply.data.version;
          persist();
          drawReady();
          say('Link and pictures updated.');
        } else if (reply.status === 404 || reply.status === 403) {
          state.token = null;
          state.key = null;
          state.version = null;
          persist();
          drawReady();
          say('That link is gone, so the next pictures get a new one.');
          drawGrid();
        } else {
          say(reply.data.detail || 'Your changes are saved here but not on the link yet.');
        }
      } catch (error) {
        say('Your changes are saved here but not on the link yet.');
      }
      saving = false;
      if (saveAgain) {
        saveAgain = false;
        saveChanges();
      }
    }

    makeButton.addEventListener('click', make);

    saveLinks.forEach(link => link.addEventListener('click', () => report('top_nine_saved')));

    shareImageButton.addEventListener('click', async () => {
      try {
        const response = await fetch(pictureUrl('post', false), { credentials: 'same-origin' });
        const blob = await response.blob();
        const file = new File([blob], `top-nine-${year}.jpg`, { type: 'image/jpeg' });
        if (!navigator.canShare({ files: [file] })) {
          say('This browser can only save the picture. Use Save picture instead.');
          return;
        }
        await navigator.share({ files: [file], title: state.name || `My ${year}` });
        report('top_nine_saved');
      } catch (error) {
        if (error && error.name === 'AbortError') return;
        say('Sharing did not work here. Use Save picture instead.');
      }
    });

    copyButton.addEventListener('click', async () => {
      if (await copyText(linkInput.value)) {
        say('Link copied.');
        report('top_nine_shared');
      } else {
        linkInput.select();
        say('Press and hold the link to copy it.');
      }
    });

    shareButton.addEventListener('click', async () => {
      try {
        await navigator.share({ title: `${state.name || `My ${year}`}: my top nine`, url: linkInput.value });
        report('top_nine_shared');
      } catch (error) { /* closed the sheet */ }
    });

    if (cta) {
      cta.querySelector('[data-tn-signup]').addEventListener('click', () => {
        if (state.token) writeJSON(KEEP_KEY, { token: state.token, at: Date.now() });
        report('top_nine_signup_clicked');
      });
    }

    async function keep(token) {
      const response = await fetch(`/api/top-nine/${token}/keep`, { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) return null;
      return response.json();
    }

    function keptText(data) {
      const added = (data.added || []).length;
      const had = (data.existing || []).length;
      if (!added && had) return 'You already had all of them, so nothing changed.';
      const first = added === 1 ? '1 title went into your library, marked finished.'
        : `${added} titles went into your library, marked finished.`;
      return had ? `${first} ${had} you already had stayed as they were.` : first;
    }

    if (keepButton) {
      keepButton.addEventListener('click', async () => {
        if (!state.token) return;
        keepButton.disabled = true;
        try {
          const data = await keep(state.token);
          say(data ? keptText(data) : 'That did not work. Try again in a moment.');
        } catch (error) {
          say('That did not work. Try again in a moment.');
        }
        keepButton.disabled = false;
      });
    }

    clearButton.addEventListener('click', () => {
      if (!clearArmed) {
        clearArmed = true;
        clearButton.textContent = 'Tap again to start over (your link stays up)';
        setTimeout(() => { clearArmed = false; clearButton.textContent = 'Start a new top nine'; }, 4000);
        return;
      }
      clearArmed = false;
      clearButton.textContent = 'Start a new top nine';
      state = blank();
      selected = 0;
      nameInput.value = state.name;
      root.querySelector('[data-tn-theme][value="night"]').checked = true;
      persist();
      drawGrid();
      drawReady();
      say('New grid. Your earlier link still works.');
    });

    // ---- a member's grids, and grids made before signing up

    async function loadMine() {
      if (!signedIn || !mineBox) return;
      try {
        const response = await fetch('/api/top-nine/mine', { credentials: 'same-origin' });
        if (!response.ok) return;
        const data = await response.json();
        const grids = Array.isArray(data.grids) ? data.grids : [];
        mineList.textContent = '';
        grids.forEach(grid => {
          const item = el('li', 'tn-mine__item');
          const link = el('a', 'tn-mine__link');
          link.href = grid.path;
          const art = el('span', 'tn-mine__art');
          (grid.images || []).forEach(src => {
            const img = el('img');
            img.src = src;
            img.alt = '';
            img.loading = 'lazy';
            img.referrerPolicy = 'no-referrer';
            img.width = 36;
            img.height = 48;
            art.appendChild(img);
          });
          link.appendChild(art);
          const text = el('span', 'tn-mine__text');
          text.appendChild(el('strong', '', grid.name));
          const bits = [`${grid.count} titles`];
          if (grid.views) bits.push(`opened ${grid.views} ${grid.views === 1 ? 'time' : 'times'}`);
          if (grid.answers) bits.push(`${grid.answers} said how many they've seen`);
          if (grid.remixes) bits.push(`${grid.remixes} made their own`);
          text.appendChild(el('span', '', bits.join(' · ')));
          link.appendChild(text);
          item.appendChild(link);
          if (grid.token !== state.token) {
            const edit = el('a', 'tn-mine__edit', 'Change it');
            edit.href = `/top-nine?edit=${grid.token}`;
            item.appendChild(edit);
          }
          mineList.appendChild(item);
        });
        mineBox.hidden = !grids.length;
      } catch (error) { /* the list is a convenience */ }
    }

    async function claimAndKeep() {
      if (!signedIn) return;
      const made = links();
      if (made.length) {
        try {
          const response = await fetch('/api/top-nine/claim', {
            method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ links: made.map(link => ({ token: link.token, key: link.key })) }),
          });
          if (response.ok) {
            const data = await response.json();
            const claimed = Array.isArray(data.claimed) ? data.claimed : [];
            forgetLinks(made.map(link => link.token));
            if (state.token && claimed.includes(state.token)) {
              state.key = null;
              persist();
            }
          }
        } catch (error) { /* tried again next visit */ }
      }
      const pending = readJSON(KEEP_KEY, null);
      if (pending && TOKEN.test(pending.token || '') && Date.now() - (pending.at || 0) < 3 * 86400000) {
        try {
          const data = await keep(pending.token);
          if (data) {
            writeJSON(KEEP_KEY, null);
            say(`Your top nine is in your account now. ${keptText(data)}`);
          }
        } catch (error) { /* left for the next visit */ }
      } else if (pending) {
        writeJSON(KEEP_KEY, null);
      }
    }

    // ---- starting from someone's grid, or changing one

    async function fetchGrid(token) {
      const response = await fetch(`/api/top-nine/${token}`, { credentials: 'same-origin' });
      return response.ok ? response.json() : null;
    }

    async function start() {
      const edit = root.dataset.edit;
      const source = root.dataset.from;
      if (edit) {
        const grid = await fetchGrid(edit).catch(() => null);
        const key = keyFor(edit);
        if (grid && (signedIn || key)) {
          state = {
            v: 1, year: grid.year, name: grid.name, theme: grid.theme,
            tiles: (grid.tiles || []).slice(0, SLOTS).map(cleanTile), token: grid.token, key, version: grid.version,
            source: null,
          };
          while (state.tiles.length < SLOTS) state.tiles.push(null);
          if (grid.year !== year) say(`This is your ${grid.year} top nine.`);
          persist();
        } else {
          say('That top nine can only be changed in the browser that made it.');
        }
        history.replaceState(null, '', '/top-nine');
      } else if (source) {
        const grid = await fetchGrid(source).catch(() => null);
        if (grid) {
          const have = (root.dataset.have || '').split(',').filter(Boolean).map(Number)
            .filter(index => Number.isInteger(index) && index >= 0 && index < SLOTS);
          const picked = have.map(index => cleanTile((grid.tiles || [])[index])).filter(Boolean);
          if (state.token || filled()) {
            // A grid already in progress keeps its squares; the new titles go into empty ones.
            if (state.token) state = blank();
          }
          picked.forEach(tile => {
            if (state.tiles.some(other => sameTitle(other, tile))) return;
            const index = firstEmpty();
            if (index >= 0) state.tiles[index] = tile;
          });
          state.source = source;
          persist();
          say(picked.length ? `${picked.length} from ${grid.name} are in. Add your own for the rest.`
            : `Make yours, then send it back to whoever sent you ${grid.name}.`);
        }
        history.replaceState(null, '', '/top-nine');
      }
      nameInput.value = state.name;
      const theme = root.querySelector(`[data-tn-theme][value="${state.theme}"]`);
      if (theme) theme.checked = true;
      selected = firstEmpty();
      drawGrid();
      drawReady();
      suggest();
      await claimAndKeep();
      loadMine();
      // A grid made before a cover arrived gets its cover now.
      state.tiles.forEach((tile, index) => { if (tile && !tile.image) findArt(index, tile); });
    }

    if (dock && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        const narrow = window.matchMedia('(max-width: 899px)').matches;
        dock.hidden = !narrow || entries[0].isIntersecting;
      }, { threshold: 0.15 });
      observer.observe(frame);
      dockUp.addEventListener('click', () => frame.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }

    start();
  }

  // ---- A shared grid -----------------------------------------------------

  function shared(root) {
    const token = root.dataset.token;
    const total = Number(root.dataset.filled) || 0;
    const score = root.querySelector('[data-tn-score]');
    const startLink = root.querySelector('[data-tn-start]');
    const hint = root.querySelector('[data-tn-start-hint]');
    const status = root.querySelector('[data-tn-status]');
    const copyButton = root.querySelector('[data-tn-copy]');
    const shareButton = root.querySelector('[data-tn-share]');
    const owner = root.querySelector('[data-tn-owner]');
    const deleteButton = root.querySelector('[data-tn-delete]');
    const seen = new Set();
    let answered = false;
    let answerTimer = null;
    const key = keyFor(token);
    if (owner && key) owner.hidden = false;

    function say(text) {
      if (status) status.textContent = text || '';
    }

    function drawScore() {
      const count = seen.size;
      score.textContent = `${count} of ${total}`;
      const have = Array.from(seen).sort((a, b) => a - b).join(',');
      startLink.href = `/top-nine?from=${encodeURIComponent(token)}${have ? `&have=${have}` : ''}`;
      hint.textContent = count
        ? `The ${count === 1 ? 'one' : count} you tapped ${count === 1 ? 'goes' : 'go'} in first. Add your own for the rest.`
        : 'Your grid starts empty, so the year is yours to fill.';
    }

    function sendAnswer() {
      if (answered || (owner && !owner.hidden)) return;
      answered = true;
      fetch(`/api/top-nine/${token}/answer`, {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seen: seen.size }),
      }).catch(() => {});
    }

    root.querySelectorAll('[data-tn-seen]').forEach(button => {
      button.addEventListener('click', () => {
        const index = Number(button.dataset.tnSeen);
        if (seen.has(index)) seen.delete(index);
        else seen.add(index);
        button.setAttribute('aria-pressed', seen.has(index) ? 'true' : 'false');
        button.classList.toggle('is-seen', seen.has(index));
        drawScore();
        clearTimeout(answerTimer);
        answerTimer = setTimeout(sendAnswer, 2500);
      });
    });

    startLink.addEventListener('click', () => {
      report('top_nine_start_clicked');
      sendAnswer();
    });

    copyButton.addEventListener('click', async () => {
      if (await copyText(location.href.split('#')[0])) {
        say('Link copied.');
        report('top_nine_shared');
      } else {
        say('Copy the address from your browser bar.');
      }
    });
    if (typeof navigator.share === 'function') {
      shareButton.hidden = false;
      shareButton.addEventListener('click', async () => {
        try {
          await navigator.share({ title: document.title, url: location.href.split('#')[0] });
          report('top_nine_shared');
        } catch (error) { /* closed the sheet */ }
      });
    }

    root.querySelectorAll('[data-tn-signup]').forEach(link => link.addEventListener('click', () => report('top_nine_signup_clicked')));
    root.querySelectorAll('[data-tn-owner-save]').forEach(link => link.addEventListener('click', () => report('top_nine_saved')));

    if (deleteButton) {
      let armed = false;
      deleteButton.addEventListener('click', async () => {
        if (!armed) {
          armed = true;
          deleteButton.textContent = 'Tap again to delete it';
          setTimeout(() => { armed = false; deleteButton.textContent = 'Delete this top nine'; }, 4000);
          return;
        }
        try {
          const response = await fetch(`/api/top-nine/${token}`, {
            method: 'DELETE', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key }),
          });
          if (response.status === 204) {
            forgetLinks([token]);
            const draft = readJSON(DRAFT_KEY, null);
            if (draft && draft.token === token) writeJSON(DRAFT_KEY, { ...draft, token: null, key: null, version: null });
            location.href = '/top-nine';
            return;
          }
          say('Only the browser or account that made it can delete it.');
        } catch (error) {
          say('That did not work. Try again in a moment.');
        }
      });
    }
    drawScore();
  }

  function init() {
    const makerRoot = document.getElementById('topNine');
    if (makerRoot) maker(makerRoot);
    const sharedRoot = document.getElementById('topNineShare');
    if (sharedRoot) shared(sharedRoot);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
