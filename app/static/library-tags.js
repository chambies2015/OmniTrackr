/* Private tags on library titles and saved shelf views (Oct 2026).
   The dashboard bundle calls remember(), decorate() and renderFilters(); everything
   else stays in here. Tags and views are only ever visible to their owner. */
(() => {
  'use strict';
  // The dashboard's corner notice (dashboard/notices.js), or a plain alert without it.
  const notice = message => (typeof window.showNotice === 'function' ? window.showNotice(message) : window.alert(message));
  const TABLES = {
    movieTable: 'movies', tvShowTable: 'tv-shows', animeTable: 'anime', videoGameTable: 'video-games',
    musicTable: 'music', bookTable: 'books', mangaTable: 'manga', podcastTable: 'podcasts',
  };
  const MAX_TAGS = 10;
  const MAX_LENGTH = 32;
  const itemTags = new Map();
  const shelfTags = new Map();
  const shelfRequests = new Map();
  const views = new Map();
  const viewRequests = new Map();
  let allTags = [];
  let editor = null;
  let epoch = 0;

  const api = path => `${typeof API_BASE === 'string' ? API_BASE : ''}/library${path}`;
  const key = (category, id) => `${category}:${id}`;
  const fold = label => label.toLocaleLowerCase();
  function clean(raw) {
    return String(raw).split(/\s+/).filter(Boolean).join(' ').replace(/^#+/, '').trim();
  }
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

  // ---------- Tag counts per shelf ----------
  function loadShelfTags(category) {
    if (shelfRequests.has(category)) return shelfRequests.get(category);
    const started = epoch;
    const pending = request(`/tags?category=${encodeURIComponent(category)}`).then(tags => {
      if (started !== epoch) return;
      shelfTags.set(category, Array.isArray(tags) ? tags : []);
      const host = document.getElementById(`${libraryPageConfig(category)[0]}Filters`);
      if (host) renderFilters(category, host);
    }).catch(() => {}).finally(() => shelfRequests.delete(category));
    shelfRequests.set(category, pending);
    return pending;
  }
  async function loadAllTags() {
    try { allTags = await request('/tags'); } catch (_) { /* suggestions are optional */ }
    return allTags;
  }

  function remember(category, items) {
    if (!Array.isArray(items)) return;
    for (const item of items) {
      if (item && Number.isInteger(item.id)) itemTags.set(key(category, item.id), Array.isArray(item.tags) ? item.tags : []);
    }
    loadShelfTags(category);
    loadViews(category);
  }

  // ---------- Rows ----------
  function decorate(row, tableId) {
    const category = TABLES[tableId];
    const anchor = row?.querySelector?.('[data-next-up-item-id]');
    if (!category || !anchor) return; // Edit mode rows have no actions to hang this on.
    const id = Number(anchor.dataset.nextUpItemId);
    const tags = itemTags.get(key(category, id)) || [];
    const titleCell = row.cells[1];
    titleCell.querySelector('.library-tags')?.remove();
    if (tags.length) {
      const list = document.createElement('span');
      list.className = 'library-tags';
      for (const label of tags) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'library-tag';
        chip.textContent = label;
        chip.setAttribute('aria-label', `Show titles tagged ${label}`);
        chip.addEventListener('click', () => applyLibraryFilters(category, { tag: label }));
        list.appendChild(chip);
      }
      titleCell.appendChild(list);
    }
    const actions = row.cells[row.cells.length - 1];
    if (actions.querySelector('[data-action="edit-library-tags"]')) return;
    const title = row.querySelector('[data-collection-item-title]')?.dataset.collectionItemTitle
      || titleCell.firstChild?.textContent?.trim() || 'this title';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'action-btn';
    button.dataset.action = 'edit-library-tags';
    button.textContent = tags.length ? 'Edit tags' : 'Add tags';
    button.addEventListener('click', () => openEditor(category, id, title, button));
    const remove = actions.querySelector('[class*="delete-"]');
    actions.insertBefore(button, remove && remove.parentNode === actions ? remove : null);
  }

  // ---------- Tag editor ----------
  function buildEditor() {
    const dialog = document.createElement('dialog');
    dialog.className = 'progress-dialog library-tags-dialog';
    dialog.setAttribute('aria-labelledby', 'libraryTagsTitle');
    dialog.setAttribute('aria-describedby', 'libraryTagsPrivacy');
    dialog.innerHTML = `
      <div class="progress-dialog__header">
        <div><p class="progress-dialog__eyebrow">Your tags</p><h2 id="libraryTagsTitle"></h2></div>
        <button type="button" class="progress-dialog__close" data-tags-close aria-label="Close tag editor">×</button>
      </div>
      <p id="libraryTagsPrivacy" class="progress-dialog__privacy">Tags are private. Group titles your own way, like "comfort watch", "with Sam" or "on Netflix", then filter any shelf by them.</p>
      <form novalidate>
        <div class="library-tags-current" aria-live="polite"></div>
        <label for="libraryTagInput">Add a tag</label>
        <div class="library-tags-entry">
          <input id="libraryTagInput" type="text" maxlength="${MAX_LENGTH}" autocomplete="off" list="libraryTagSuggestions" enterkeyhint="done" placeholder="Type a tag and press Enter">
          <button type="button" data-tags-add>Add</button>
        </div>
        <datalist id="libraryTagSuggestions"></datalist>
        <div class="library-tags-suggest" hidden><p class="progress-dialog__hint">Used before</p><div></div></div>
        <p class="progress-dialog__status" role="status" aria-live="polite"></p>
        <div class="progress-dialog__actions">
          <button type="submit" class="progress-dialog__save">Save tags</button>
          <button type="button" data-tags-close>Cancel</button>
        </div>
      </form>`;
    document.body.appendChild(dialog);
    const state = {
      dialog, category: '', id: 0, tags: [], trigger: null, saving: false,
      form: dialog.querySelector('form'), input: dialog.querySelector('#libraryTagInput'),
      current: dialog.querySelector('.library-tags-current'), status: dialog.querySelector('[role="status"]'),
      suggest: dialog.querySelector('.library-tags-suggest'), list: dialog.querySelector('datalist'),
    };
    dialog.querySelectorAll('[data-tags-close]').forEach(button => button.addEventListener('click', () => dialog.close()));
    dialog.querySelector('[data-tags-add]').addEventListener('click', () => addTyped(state));
    state.input.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ',') { event.preventDefault(); addTyped(state); }
      if (event.key === 'Backspace' && !state.input.value && state.tags.length) {
        state.tags.pop(); paint(state);
      }
    });
    state.form.addEventListener('submit', event => { event.preventDefault(); save(state); });
    dialog.addEventListener('close', () => { state.trigger?.isConnected && state.trigger.focus(); });
    return state;
  }
  function addTag(state, raw) {
    const label = clean(raw);
    if (!label) return true;
    if (label.length > MAX_LENGTH) { state.status.textContent = `Keep each tag to ${MAX_LENGTH} characters.`; return false; }
    if (state.tags.some(tag => fold(tag) === fold(label))) return true;
    if (state.tags.length >= MAX_TAGS) { state.status.textContent = `A title can have up to ${MAX_TAGS} tags.`; return false; }
    const known = allTags.find(tag => fold(tag.label) === fold(label));
    state.tags.push(known ? known.label : label);
    state.status.textContent = '';
    return true;
  }
  function addTyped(state) {
    const parts = state.input.value.split(',');
    if (parts.every(part => addTag(state, part))) state.input.value = '';
    paint(state);
    state.input.focus();
  }
  function paint(state) {
    state.current.replaceChildren();
    if (!state.tags.length) {
      const empty = document.createElement('p');
      empty.className = 'progress-dialog__hint';
      empty.textContent = 'No tags yet.';
      state.current.appendChild(empty);
    }
    state.tags.forEach((label, index) => {
      const chip = document.createElement('span');
      chip.className = 'library-tag library-tag--edit';
      chip.textContent = label;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `Remove tag ${label}`);
      remove.addEventListener('click', () => { state.tags.splice(index, 1); paint(state); state.input.focus(); });
      chip.appendChild(remove);
      state.current.appendChild(chip);
    });
    const unused = allTags.filter(tag => !state.tags.some(label => fold(label) === fold(tag.label)));
    state.list.replaceChildren(...unused.map(tag => Object.assign(document.createElement('option'), { value: tag.label })));
    const quick = state.suggest.querySelector('div');
    quick.replaceChildren(...unused.slice(0, 8).map(tag => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-tag library-tag--suggest';
      button.textContent = `+ ${tag.label}`;
      button.setAttribute('aria-label', `Add tag ${tag.label}`);
      button.addEventListener('click', () => { addTag(state, tag.label); paint(state); state.input.focus(); });
      return button;
    }));
    state.suggest.hidden = !quick.childElementCount;
  }
  async function openEditor(category, id, title, trigger) {
    if (typeof editingRowId !== 'undefined' && editingRowId !== null) {
      notice('Save or cancel your current edit before changing tags.');
      return;
    }
    editor = editor || buildEditor();
    Object.assign(editor, { category, id, trigger, tags: [...(itemTags.get(key(category, id)) || [])] });
    editor.dialog.querySelector('h2').textContent = title;
    editor.input.value = '';
    editor.status.textContent = '';
    paint(editor);
    editor.dialog.showModal();
    editor.input.focus();
    await loadAllTags();
    if (editor.dialog.open && editor.id === id) paint(editor);
  }
  async function save(state) {
    if (state.saving) return;
    if (state.input.value.trim()) {
      const parts = state.input.value.split(',');
      if (!parts.every(part => addTag(state, part))) { paint(state); return; }
      state.input.value = '';
      paint(state);
    }
    state.saving = true;
    const submit = state.form.querySelector('[type="submit"]');
    submit.disabled = true;
    state.status.textContent = 'Saving…';
    const { category, id } = state;
    try {
      const body = await request(`/tags/${encodeURIComponent(category)}/${id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tags: state.tags }),
      });
      itemTags.set(key(category, id), body.tags);
      shelfTags.delete(category);
      allTags = [];
      state.dialog.close();
      // Reload the shelf: the chips change, and a title can leave a tag-filtered view.
      reload(category);
    } catch (error) {
      state.status.textContent = error.message;
    } finally {
      state.saving = false;
      submit.disabled = false;
    }
  }

  // ---------- Saved views ----------
  function loadViews(category) {
    if (views.has(category) || viewRequests.has(category)) return viewRequests.get(category);
    const started = epoch;
    const pending = request(`/views/${encodeURIComponent(category)}`).then(list => {
      if (started !== epoch) return;
      views.set(category, Array.isArray(list) ? list : []);
      const host = document.getElementById(`${libraryPageConfig(category)[0]}Filters`);
      if (host) renderFilters(category, host);
    }).catch(() => {}).finally(() => viewRequests.delete(category));
    viewRequests.set(category, pending);
    return pending;
  }
  function currentView(category) {
    const [, sortId] = libraryPageConfig(category);
    const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
    const filters = getLibraryFilters(category);
    return {
      search: document.getElementById(source.input).value.trim(),
      sort: document.getElementById(sortId).value,
      completion: filters.completion, unrated: !!filters.unrated,
      has_progress: !!filters.hasProgress, tag: filters.tag || '', recommended_by: filters.recommendedBy || '',
    };
  }
  const sameView = (a, b) => ['search', 'sort', 'completion', 'unrated', 'has_progress', 'tag', 'recommended_by']
    .every(name => (['tag', 'recommended_by'].includes(name) ? fold(a[name] || '') === fold(b[name] || '') : a[name] === b[name]));
  const isDefault = view => sameView(view, { search: '', sort: '', completion: 'all', unrated: false, has_progress: false, tag: '', recommended_by: '' });
  function applyView(category, view) {
    if (typeof editingRowId !== 'undefined' && editingRowId !== null) {
      notice('Save or cancel your current edit before changing filters.');
      return;
    }
    const [, sortId] = libraryPageConfig(category);
    const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
    const sort = document.getElementById(sortId);
    const known = Array.from(sort.options || [], option => option.value);
    sort.value = !known.length || known.includes(view.filters.sort) ? view.filters.sort : '';
    document.getElementById(source.input).value = view.filters.search;
    applyLibraryFilters(category, {
      completion: view.filters.completion, unrated: view.filters.unrated,
      hasProgress: view.filters.has_progress, tag: view.filters.tag, recommendedBy: view.filters.recommended_by || '',
    });
  }
  async function saveView(category, name, status) {
    try {
      const saved = await request(`/views/${encodeURIComponent(category)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, filters: currentView(category) }),
      });
      const list = (views.get(category) || []).filter(view => view.id !== saved.id);
      list.push(saved);
      list.sort((a, b) => fold(a.name).localeCompare(fold(b.name)));
      views.set(category, list);
      return true;
    } catch (error) {
      status.textContent = error.message;
      return false;
    }
  }
  async function deleteView(category, view) {
    if (!confirm(`Delete the saved view "${view.name}"? Your titles and tags stay as they are.`)) return;
    try {
      await request(`/views/${encodeURIComponent(category)}/${view.id}`, { method: 'DELETE' });
    } catch (error) {
      if (error.message !== 'Saved view not found') { notice(error.message); return; }
    }
    views.set(category, (views.get(category) || []).filter(item => item.id !== view.id));
    renderFilters(category, document.getElementById(`${libraryPageConfig(category)[0]}Filters`));
  }

  // ---------- Filter bar ----------
  function renderFilters(category, host) {
    if (!host) return;
    const reset = host.querySelector('.library-filter-reset');
    const filters = getLibraryFilters(category);
    const tags = shelfTags.get(category) || [];
    if (!shelfTags.has(category)) loadShelfTags(category);

    let tagField = host.querySelector('.library-filter-tag');
    if (!tagField) {
      tagField = document.createElement('label');
      tagField.className = 'library-filter-option library-filter-tag';
      const text = document.createElement('span');
      text.textContent = 'Tag';
      const select = document.createElement('select');
      select.setAttribute('aria-label', 'Show titles with this tag');
      select.addEventListener('change', () => {
        if (!applyLibraryFilters(category, { tag: select.value })) select.value = getLibraryFilters(category).tag || '';
      });
      tagField.append(text, select);
      host.insertBefore(tagField, reset || null);
    }
    const select = tagField.querySelector('select');
    const active = filters.tag || '';
    const options = [['', 'Any']].concat(tags.map(tag => [tag.label, `${tag.label} (${tag.count})`]));
    if (active && !tags.some(tag => fold(tag.label) === fold(active))) options.push([active, `${active} (0)`]);
    select.replaceChildren(...options.map(([value, label]) => Object.assign(document.createElement('option'), { value, textContent: label })));
    const match = options.find(([value]) => fold(value) === fold(active));
    select.value = match ? match[0] : '';
    tagField.hidden = !tags.length && !active;

    let bar = host.querySelector('.library-views');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'library-views';
      bar.setAttribute('role', 'group');
      bar.setAttribute('aria-label', 'Saved views');
      host.insertBefore(bar, host.firstChild);
    }
    renderViewBar(category, host, bar);
  }

  function renderViewBar(category, host, bar) {
    if (bar.querySelector('form')) return; // Leave a half-typed name alone.
    const list = views.get(category) || [];
    const now = currentView(category);
    bar.replaceChildren();
    for (const view of list) {
      const pill = document.createElement('span');
      pill.className = 'library-view';
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'library-view__open';
      open.textContent = view.name;
      open.setAttribute('aria-pressed', String(sameView(view.filters, now)));
      open.addEventListener('click', () => applyView(category, view));
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'library-view__delete';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `Delete saved view ${view.name}`);
      remove.addEventListener('click', () => deleteView(category, view));
      pill.append(open, remove);
      bar.appendChild(pill);
    }
    const unsaved = !isDefault(now) && !list.some(view => sameView(view.filters, now));
    if (unsaved) {
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'library-view__save';
      save.textContent = 'Save this view';
      save.addEventListener('click', () => openNameForm(category, host, bar));
      bar.appendChild(save);
    }
    bar.hidden = !bar.childElementCount;
  }

  function openNameForm(category, host, bar) {
    const form = document.createElement('form');
    form.className = 'library-view__form';
    form.noValidate = true;
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 40;
    input.placeholder = 'Name this view';
    input.setAttribute('aria-label', 'Name for this saved view');
    const status = document.createElement('span');
    status.className = 'library-view__status';
    status.setAttribute('role', 'status');
    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'library-view__save';
    submit.textContent = 'Save';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'library-view__cancel';
    cancel.textContent = 'Cancel';
    const close = () => { form.remove(); renderViewBar(category, host, bar); };
    cancel.addEventListener('click', close);
    input.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); close(); } });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const name = input.value.split(/\s+/).filter(Boolean).join(' ');
      if (!name) { status.textContent = 'Give the view a name.'; input.focus(); return; }
      submit.disabled = true;
      if (await saveView(category, name, status)) close();
      else submit.disabled = false;
    });
    form.append(input, submit, cancel, status);
    bar.querySelector('.library-view__save')?.remove();
    bar.appendChild(form);
    bar.hidden = false;
    input.focus();
  }

  function reset() {
    epoch++;
    itemTags.clear(); shelfTags.clear(); views.clear(); allTags = [];
    if (editor?.dialog.open) editor.dialog.close();
  }
  window.addEventListener('pagehide', () => { if (editor?.dialog.open) editor.dialog.close(); });

  window.OmniLibraryTags = { remember, decorate, renderFilters, reset };
})();
