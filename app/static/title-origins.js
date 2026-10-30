/* Why I added it: who recommended a title, or where you heard of it (Oct 2026).
   The dashboard bundle calls remember(), decorate(), renderFilters(), reset() and
   loadRecommenders(); everything else stays in here. Only the owner ever sees it. */
(() => {
  'use strict';
  const TABLES = {
    movieTable: 'movies', tvShowTable: 'tv-shows', animeTable: 'anime', videoGameTable: 'video-games',
    musicTable: 'music', bookTable: 'books', mangaTable: 'manga', podcastTable: 'podcasts',
    audiobookTable: 'audiobooks',
  };
  const SOURCES = [
    ['friend', 'A friend on OmniTrackr'],
    ['person', 'Someone I know'],
    ['article', 'An article or website'],
    ['video', 'A video, podcast or stream'],
    ['browsing', 'I came across it'],
    ['other', 'Something else'],
  ];
  const WHO_PROMPT = {
    person: ['Who recommended it?', 'Mum, Alex from work…'],
    article: ['Which site? (optional)', 'Polygon, a Reddit thread…'],
    video: ['Which one? (optional)', 'A YouTube channel, a podcast episode…'],
    browsing: ['Where? (optional)', 'A bookshop table, a trailer…'],
    other: ['Where from? (optional)', ''],
  };
  const SHELF_NAMES = {
    movies: 'movies', 'tv-shows': 'TV shows', anime: 'anime', 'video-games': 'games',
    music: 'music', books: 'books', manga: 'manga', podcasts: 'podcasts', audiobooks: 'audiobooks',
  };
  const WHO_MAX = 60;
  const NOTE_MAX = 280;
  const itemOrigins = new Map();
  const shelfPeople = new Map();
  const shelfRequests = new Map();
  let friends = null;
  let editor = null;
  let epoch = 0;

  const api = path => `${typeof API_BASE === 'string' ? API_BASE : ''}${path}`;
  const key = (category, id) => `${category}:${id}`;
  const fold = text => String(text || '').toLocaleLowerCase();
  async function request(path, options = {}) {
    const response = await authenticatedFetch(api(path), options);
    if (response.ok) return response.status === 204 ? null : response.json();
    let message = 'Something went wrong. Try again.';
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch (_) { /* keep the general message */ }
    throw new Error(message);
  }
  function reload(category) {
    const config = typeof libraryPageConfig === 'function' ? libraryPageConfig(category) : null;
    if (config) config[2]();
  }
  function summary(origin) {
    if (!origin) return '';
    if (origin.source === 'friend' || origin.source === 'person') return `From ${origin.who}`;
    return origin.who ? `Via ${origin.who}` : origin.source_label;
  }

  // ---------- Rows ----------
  function remember(category, items) {
    if (!Array.isArray(items)) return;
    for (const item of items) {
      if (item && Number.isInteger(item.id)) itemOrigins.set(key(category, item.id), item.origin || null);
    }
    loadShelfPeople(category);
  }

  function decorate(row, tableId) {
    const category = TABLES[tableId];
    const anchor = row?.querySelector?.('[data-next-up-item-id]');
    if (!category || !anchor) return; // Edit mode rows have no actions to hang this on.
    const id = Number(anchor.dataset.nextUpItemId);
    const origin = itemOrigins.get(key(category, id)) || null;
    const titleCell = row.cells[1];
    titleCell.querySelector('.title-origin')?.remove();
    if (origin) {
      const line = document.createElement('span');
      line.className = 'title-origin';
      const text = summary(origin);
      if (origin.who_key && (origin.source === 'friend' || origin.source === 'person')) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'title-origin__who';
        chip.textContent = text;
        chip.setAttribute('aria-label', `Show titles recommended by ${origin.who}`);
        chip.addEventListener('click', () => applyLibraryFilters(category, { recommendedBy: origin.who_key }));
        line.appendChild(chip);
      } else {
        line.appendChild(document.createTextNode(text));
      }
      if (origin.note) {
        const note = document.createElement('span');
        note.className = 'title-origin__note';
        note.textContent = origin.note;
        line.appendChild(note);
      }
      titleCell.appendChild(line);
    }
    const actions = row.cells[row.cells.length - 1];
    const existing = actions.querySelector('[data-action="edit-title-origin"]');
    if (existing) { existing.textContent = origin ? 'Edit why I added it' : 'Why I added it'; return; }
    const title = row.querySelector('[data-collection-item-title]')?.dataset.collectionItemTitle
      || titleCell.firstChild?.textContent?.trim() || 'this title';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'action-btn';
    button.dataset.action = 'edit-title-origin';
    button.textContent = origin ? 'Edit why I added it' : 'Why I added it';
    button.addEventListener('click', () => openEditor(category, id, title, button));
    const remove = actions.querySelector('[class*="delete-"]');
    actions.insertBefore(button, remove && remove.parentNode === actions ? remove : null);
  }

  // ---------- Editor ----------
  function buildEditor() {
    const dialog = document.createElement('dialog');
    dialog.className = 'progress-dialog title-origin-dialog';
    dialog.setAttribute('aria-labelledby', 'titleOriginTitle');
    dialog.setAttribute('aria-describedby', 'titleOriginPrivacy');
    dialog.innerHTML = `
      <div class="progress-dialog__header">
        <div><p class="progress-dialog__eyebrow">Why I added it</p><h2 id="titleOriginTitle"></h2></div>
        <button type="button" class="progress-dialog__close" data-origin-close aria-label="Close">×</button>
      </div>
      <p id="titleOriginPrivacy" class="progress-dialog__privacy">Only you see this. Months from now you'll know who to thank, or who to blame.</p>
      <form novalidate>
        <fieldset class="title-origin-sources">
          <legend>Where did it come from?</legend>
          <div class="title-origin-sources__list"></div>
        </fieldset>
        <div class="title-origin-friend" hidden>
          <label for="titleOriginFriend">Which friend?</label>
          <select id="titleOriginFriend"></select>
          <p class="progress-dialog__hint" data-origin-no-friends hidden>You haven't added any friends yet. Choose "Someone I know" and type their name instead.</p>
        </div>
        <div class="title-origin-who" hidden>
          <label for="titleOriginWho"></label>
          <input id="titleOriginWho" type="text" maxlength="${WHO_MAX}" autocomplete="off" list="titleOriginPeople">
          <datalist id="titleOriginPeople"></datalist>
        </div>
        <label for="titleOriginNote">Note (optional)</label>
        <textarea id="titleOriginNote" rows="3" maxlength="${NOTE_MAX}" placeholder="What made you want it? &quot;Said the ending wrecked them&quot;"></textarea>
        <p class="title-origin-count" aria-live="polite"></p>
        <p class="progress-dialog__status" role="status" aria-live="polite"></p>
        <div class="progress-dialog__actions">
          <button type="submit" class="progress-dialog__save">Save</button>
          <button type="button" data-origin-clear hidden>Remove</button>
          <button type="button" data-origin-close>Cancel</button>
        </div>
      </form>`;
    document.body.appendChild(dialog);
    const state = {
      dialog, category: '', id: 0, trigger: null, saving: false,
      form: dialog.querySelector('form'), list: dialog.querySelector('.title-origin-sources__list'),
      friendBox: dialog.querySelector('.title-origin-friend'), friend: dialog.querySelector('#titleOriginFriend'),
      noFriends: dialog.querySelector('[data-origin-no-friends]'),
      whoBox: dialog.querySelector('.title-origin-who'), who: dialog.querySelector('#titleOriginWho'),
      whoLabel: dialog.querySelector('label[for="titleOriginWho"]'), people: dialog.querySelector('#titleOriginPeople'),
      note: dialog.querySelector('#titleOriginNote'), count: dialog.querySelector('.title-origin-count'),
      status: dialog.querySelector('[role="status"]'), clear: dialog.querySelector('[data-origin-clear]'),
    };
    for (const [value, label] of SOURCES) {
      const option = document.createElement('label');
      option.className = 'title-origin-source';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'titleOriginSource';
      input.value = value;
      input.addEventListener('change', () => paint(state));
      const text = document.createElement('span');
      text.textContent = label;
      option.append(input, text);
      state.list.appendChild(option);
    }
    dialog.querySelectorAll('[data-origin-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
    state.note.addEventListener('input', () => count(state));
    state.clear.addEventListener('click', () => clear(state));
    state.form.addEventListener('submit', event => { event.preventDefault(); save(state); });
    dialog.addEventListener('close', () => { state.trigger?.isConnected && state.trigger.focus(); });
    return state;
  }
  const chosen = state => state.form.querySelector('input[name="titleOriginSource"]:checked')?.value || '';
  function count(state) {
    const left = NOTE_MAX - state.note.value.length;
    state.count.textContent = left < 60 ? `${left} characters left` : '';
  }
  function paint(state) {
    const source = chosen(state);
    const isFriend = source === 'friend';
    state.friendBox.hidden = !isFriend;
    const list = friends || [];
    state.noFriends.hidden = !isFriend || list.length > 0;
    state.friend.hidden = !list.length;
    const prompt = WHO_PROMPT[source];
    state.whoBox.hidden = !prompt;
    if (prompt) {
      state.whoLabel.textContent = prompt[0];
      state.who.placeholder = prompt[1];
    }
    state.status.textContent = '';
  }
  async function loadFriends() {
    if (friends) return friends;
    try {
      const data = await request('/friends');
      friends = (Array.isArray(data) ? data : []).map(entry => entry.friend).filter(Boolean)
        .sort((a, b) => a.username.localeCompare(b.username));
    } catch (_) {
      friends = [];
    }
    return friends;
  }
  function fillFriends(state, selected) {
    const options = [['', 'Choose a friend']].concat((friends || []).map(friend => [String(friend.id), friend.username]));
    state.friend.replaceChildren(...options.map(([value, label]) => Object.assign(document.createElement('option'), { value, textContent: label })));
    state.friend.value = selected ? String(selected) : '';
  }
  async function openEditor(category, id, title, trigger) {
    if (typeof editingRowId !== 'undefined' && editingRowId !== null) {
      alert('Save or cancel your current edit first.');
      return;
    }
    editor = editor || buildEditor();
    const origin = itemOrigins.get(key(category, id)) || null;
    Object.assign(editor, { category, id, trigger });
    editor.dialog.querySelector('h2').textContent = title;
    const source = origin?.source === 'friend' && !origin.friend ? 'person' : (origin?.source || 'friend');
    editor.form.querySelectorAll('input[name="titleOriginSource"]').forEach(input => { input.checked = input.value === source; });
    editor.who.value = origin && !origin.friend ? origin.who : '';
    editor.note.value = origin?.note || '';
    editor.clear.hidden = !origin;
    count(editor);
    fillFriends(editor, origin?.friend?.id);
    paint(editor);
    editor.status.textContent = '';
    editor.dialog.showModal();
    editor.form.querySelector('input[name="titleOriginSource"]:checked')?.focus();
    await loadFriends();
    if (!editor.dialog.open || editor.id !== id) return;
    fillFriends(editor, origin?.friend?.id);
    const names = (shelfPeople.get(category) || []).map(person => person.name);
    editor.people.replaceChildren(...names.map(name => Object.assign(document.createElement('option'), { value: name })));
    paint(editor);
  }
  async function save(state) {
    if (state.saving) return;
    const source = chosen(state);
    const body = { source, who: '', note: state.note.value.trim() };
    if (source === 'friend') {
      body.friend_id = Number(state.friend.value) || null;
      if (!body.friend_id) { state.status.textContent = 'Pick a friend, or choose "Someone I know".'; return; }
    } else {
      body.who = state.who.value.trim();
      if (source === 'person' && !body.who) { state.status.textContent = 'Add the name of who recommended it.'; state.who.focus(); return; }
    }
    await commit(state, `/library/origins/${encodeURIComponent(state.category)}/${state.id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
  }
  async function clear(state) {
    if (state.saving) return;
    await commit(state, `/library/origins/${encodeURIComponent(state.category)}/${state.id}`, { method: 'DELETE' });
  }
  async function commit(state, path, options) {
    state.saving = true;
    const buttons = state.form.querySelectorAll('button');
    buttons.forEach(button => { button.disabled = true; });
    state.status.textContent = 'Saving…';
    const { category, id } = state;
    try {
      const result = await request(path, options);
      itemOrigins.set(key(category, id), result ? result.origin : null);
      shelfPeople.delete(category);
      recommenders.stale = true;
      state.dialog.close();
      // Reload the shelf: the line under the title changes, and a title can leave a filtered view.
      reload(category);
    } catch (error) {
      state.status.textContent = error.message;
    } finally {
      state.saving = false;
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  // ---------- "Recommended by" filter ----------
  function loadShelfPeople(category) {
    if (shelfPeople.has(category) || shelfRequests.has(category)) return shelfRequests.get(category);
    const started = epoch;
    const pending = request(`/library/recommenders?category=${encodeURIComponent(category)}`).then(list => {
      if (started !== epoch) return;
      shelfPeople.set(category, Array.isArray(list) ? list : []);
      const host = document.getElementById(`${libraryPageConfig(category)[0]}Filters`);
      if (host) renderFilters(category, host);
    }).catch(() => {}).finally(() => shelfRequests.delete(category));
    shelfRequests.set(category, pending);
    return pending;
  }
  function renderFilters(category, host) {
    if (!host) return;
    const reset = host.querySelector('.library-filter-reset');
    const active = getLibraryFilters(category).recommendedBy || '';
    const people = shelfPeople.get(category) || [];
    if (!shelfPeople.has(category)) loadShelfPeople(category);
    let field = host.querySelector('.library-filter-origin');
    if (!field) {
      field = document.createElement('label');
      field.className = 'library-filter-option library-filter-origin';
      const text = document.createElement('span');
      text.textContent = 'Recommended by';
      const select = document.createElement('select');
      select.setAttribute('aria-label', 'Show titles recommended by');
      select.addEventListener('change', () => {
        if (!applyLibraryFilters(category, { recommendedBy: select.value })) select.value = getLibraryFilters(category).recommendedBy || '';
      });
      field.append(text, select);
      host.insertBefore(field, reset || null);
    }
    const select = field.querySelector('select');
    const options = [['', 'Anyone']].concat(people.map(person => [person.key, `${person.name} (${person.count})`]));
    if (active && !people.some(person => person.key === fold(active))) options.push([active, `${active} (0)`]);
    select.replaceChildren(...options.map(([value, label]) => Object.assign(document.createElement('option'), { value, textContent: label })));
    const match = options.find(([value]) => value === fold(active) || value === active);
    select.value = match ? match[0] : '';
    field.hidden = !people.length && !active;
  }

  // ---------- Best recommenders card (friends feed tab) ----------
  const recommenders = { stale: true, request: 0 };
  async function loadRecommenders() {
    const host = document.getElementById('bestRecommenders');
    if (!host || !recommenders.stale) return;
    const started = ++recommenders.request;
    try {
      const data = await request('/library/recommenders');
      if (started !== recommenders.request) return;
      recommenders.stale = false;
      renderRecommenders(host, data);
    } catch (_) {
      host.hidden = true; // Optional; the feed works without it.
    }
  }
  function renderRecommenders(host, data) {
    const list = host.querySelector('#bestRecommendersList');
    const summaryLine = host.querySelector('#bestRecommendersSummary');
    const people = Array.isArray(data?.people) ? data.people : [];
    host.hidden = false;
    list.replaceChildren();
    if (!people.length) {
      summaryLine.textContent = 'When you add a title, open its More menu and choose "Why I added it". Titles you save from a friend\'s recommendation or the feed are filled in for you.';
      return;
    }
    summaryLine.textContent = `${data.total_titles} ${data.total_titles === 1 ? 'title' : 'titles'} from ${data.total_people} ${data.total_people === 1 ? 'person' : 'people'}. Ranked by how you rated the ones you finished.`;
    people.forEach((person, index) => {
      const item = document.createElement('li');
      item.className = 'best-recs__person';
      const rank = document.createElement('span');
      rank.className = 'best-recs__rank';
      rank.textContent = String(index + 1);
      rank.setAttribute('aria-hidden', 'true');
      const body = document.createElement('div');
      body.className = 'best-recs__body';
      const name = document.createElement('p');
      name.className = 'best-recs__name';
      name.textContent = person.name;
      const facts = document.createElement('p');
      facts.className = 'best-recs__facts';
      const parts = [`${person.titles} ${person.titles === 1 ? 'pick' : 'picks'}`, `${person.finished} finished`];
      if (person.best) parts.push(`best: ${person.best.title}`);
      facts.textContent = parts.join(' · ');
      body.append(name, facts);
      const score = document.createElement('span');
      score.className = 'best-recs__score';
      score.textContent = person.average_rating === null ? 'Not rated yet' : `${person.average_rating.toFixed(1)}/10`;
      if (person.average_rating !== null) score.setAttribute('aria-label', `Average rating ${person.average_rating.toFixed(1)} out of 10`);
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'best-recs__open';
      open.textContent = `See their ${SHELF_NAMES[person.top_shelf] || 'picks'}`;
      open.setAttribute('aria-label', `Show ${SHELF_NAMES[person.top_shelf] || 'titles'} recommended by ${person.name}`);
      open.addEventListener('click', () => showPicks(person.top_shelf, person.key));
      item.append(rank, body, score, open);
      list.appendChild(item);
    });
  }
  async function showPicks(category, whoKey) {
    // A hidden tab or an unsaved edit keeps the member where they are.
    if (typeof navigateLibraryTab !== 'function' || !(await navigateLibraryTab(category))) return;
    applyLibraryFilters(category, { recommendedBy: whoKey });
  }

  function reset() {
    epoch++;
    itemOrigins.clear(); shelfPeople.clear();
    friends = null;
    recommenders.stale = true;
    recommenders.request++;
    const host = document.getElementById('bestRecommenders');
    if (host) host.hidden = true;
    if (editor?.dialog.open) editor.dialog.close();
  }
  window.addEventListener('pagehide', () => { if (editor?.dialog.open) editor.dialog.close(); });

  window.OmniTitleOrigins = { remember, decorate, renderFilters, reset, loadRecommenders };
})();
