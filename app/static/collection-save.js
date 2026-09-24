/* Public selections are previews. Only explicit confirmation creates a private copy. */
(() => {
  'use strict';
  const panel = document.getElementById('collectionSavePanel');
  if (!panel) return;
  const id = panel.dataset.collectionId;
  const get = name => document.getElementById(`collectionSave${name}`);
  const title = get('Title');
  const summary = get('Summary');
  const status = get('Status');
  const confirm = get('Confirm');
  const signin = get('Signin');
  const retry = get('Retry');
  const open = get('Open');
  const choices = get('Choices');
  const list = get('Items');
  const all = get('All');
  const none = get('None');
  const categories = new Set(['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books']);
  const validId = value => Number.isInteger(value) && value > 0 && value <= 2147483647;
  let version = null;
  let items = [];
  let inputs = [];
  let selected = new Set();
  let pendingSave = null;
  let busy = false;
  let completed = false;
  let leftPage = false;
  let generation = 0;
  let controller;

  function updateControls() {
    const locked = busy || Boolean(pendingSave) || completed || !version;
    inputs.forEach(input => { input.disabled = locked; });
    all.disabled = locked;
    none.disabled = locked;
    confirm.disabled = busy || completed || !version || selected.size === 0;
    retry.disabled = busy;
    panel.setAttribute('aria-busy', String(busy));
  }

  function updateSelection() {
    const existing = items.filter(item => selected.has(item.id) && item.existing).length;
    const added = selected.size - existing;
    summary.textContent = selected.size
      ? `${selected.size} selected · ${added} new to your library · ${existing} already in your library. Existing titles keep your ratings, reviews and progress.`
      : 'Choose at least one title to save your private collection.';
    updateControls();
  }

  function renderItems() {
    list.replaceChildren();
    inputs = items.map(item => {
      const label = document.createElement('label');
      label.className = 'collection-save-item';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = selected.has(item.id);
      const content = document.createElement('span');
      content.className = 'collection-save-item__content';
      const name = document.createElement('span');
      name.className = 'collection-save-item__title';
      name.textContent = item.title;
      const metadata = document.createElement('span');
      metadata.className = 'collection-save-item__meta';
      const category = document.createElement('span');
      category.textContent = item.category_label;
      const badge = document.createElement('span');
      badge.className = `collection-save-item__badge${item.existing ? ' collection-save-item__badge--existing' : ''}`;
      badge.textContent = item.existing ? 'Already in your library' : 'New to your library';
      metadata.append(category, badge);
      content.append(name, metadata);
      label.append(input, content);
      list.append(label);
      input.addEventListener('change', () => {
        if (busy || pendingSave || completed || !version) return;
        if (input.checked) selected.add(item.id); else selected.delete(item.id);
        updateSelection();
      });
      return input;
    });
    choices.hidden = false;
  }

  async function request(action, options = {}) {
    const activeController = new AbortController();
    controller = activeController;
    const headers = {'Content-Type': 'application/json'};
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (_) {}
    let timer;
    let onAbort;
    try {
      return await Promise.race([
        (async () => {
          const response = await fetch(`/collections/public/${id}/${action}`, {
            ...options, headers, credentials: 'same-origin', cache: 'no-store', signal: activeController.signal,
          });
          if (!response.ok) {
            const error = new Error('Request failed');
            error.status = response.status;
            throw error;
          }
          return response.json();
        })(),
        new Promise((_, reject) => {
          onAbort = () => reject(new Error('Request cancelled'));
          activeController.signal.addEventListener('abort', onAbort, {once: true});
          timer = setTimeout(() => { reject(new Error('Request timed out')); activeController.abort(); }, 15000);
        }),
      ]);
    } finally {
      clearTimeout(timer);
      activeController.signal.removeEventListener('abort', onAbort);
    }
  }

  function showError(error, saving) {
    open.hidden = true;
    signin.hidden = true;
    retry.hidden = true;
    // An uncertain write may already have committed. Retry the identical selection.
    if (saving && (!error.status || error.status >= 500)) {
      confirm.hidden = false;
      confirm.textContent = 'Retry save safely';
      status.textContent = 'We couldn’t confirm the save. Your selection is held in place. Retry safely to find or finish the same private copy.';
      return;
    }
    version = null;
    pendingSave = null;
    confirm.hidden = true;
    if (error.status === 401) {
      signin.hidden = false;
      status.textContent = 'Sign in to check your library. You’ll return to this collection to choose your titles before saving.';
    } else if (error.status === 404) {
      choices.hidden = true;
      status.textContent = 'This shared collection is no longer available. Explore other collections to find your next titles.';
    } else {
      retry.hidden = false;
      status.textContent = error.status === 409
        ? 'This collection changed since your preview. Check your library again, then confirm the latest selection.'
        : 'Your collection preview couldn’t load. Please check your library again.';
    }
  }

  async function preview() {
    if (busy || leftPage || pendingSave) return;
    const current = ++generation;
    const previousVersion = version;
    const previousSelection = new Set(selected);
    version = null;
    confirm.hidden = true; signin.hidden = true; retry.hidden = true; open.hidden = true;
    choices.hidden = true;
    busy = true;
    updateControls();
    status.textContent = 'Checking these titles against your library…';
    try {
      const data = await request('save-preview');
      if (leftPage || current !== generation) return;
      if (!data || typeof data.collection_name !== 'string' || typeof data.version !== 'string'
        || !/^[a-f0-9]{64}$/.test(data.version) || !Array.isArray(data.items) || !data.items.length
        || data.items.some(item => !item || !validId(item.id) || typeof item.title !== 'string'
          || !categories.has(item.category) || typeof item.category_label !== 'string' || typeof item.existing !== 'boolean')
        || new Set(data.items.map(item => item.id)).size !== data.items.length) throw new Error('Invalid preview');
      version = data.version;
      items = data.items;
      selected = previousVersion === version ? previousSelection : new Set(items.map(item => item.id));
      title.textContent = data.collection_name;
      renderItems();
      updateSelection();
      confirm.textContent = 'Save my private collection';
      confirm.hidden = false;
      status.textContent = 'Review your selection, then save. Nothing is added until you confirm.';
    } catch (error) {
      if (!leftPage && current === generation) showError(error, false);
    } finally {
      if (!leftPage && current === generation) { busy = false; updateControls(); }
    }
  }

  confirm.addEventListener('click', async () => {
    if (busy || !version || !selected.size || completed || leftPage) return;
    const current = ++generation;
    if (!pendingSave) pendingSave = {version, item_ids: items.filter(item => selected.has(item.id)).map(item => item.id)};
    busy = true;
    updateControls();
    status.textContent = 'Saving your private collection…';
    try {
      const result = await request('save', {method: 'POST', body: JSON.stringify(pendingSave)});
      if (leftPage || current !== generation) return;
      if (!result || !validId(result.collection_id) || typeof result.already_saved !== 'boolean'
        || !Number.isInteger(result.created) || result.created < 0 || !Number.isInteger(result.reused) || result.reused < 0) throw new Error('Invalid save response');
      completed = true;
      pendingSave = null;
      version = null;
      confirm.hidden = true;
      choices.hidden = true;
      summary.textContent = result.already_saved
        ? 'You already saved this selection. Your existing private copy is ready to open, with your edits preserved.'
        : `Your private collection is ready. ${result.created} new to your library · ${result.reused} already in your library. Your existing ratings, reviews and progress are preserved.`;
      status.textContent = 'Open your collection to make it your own.';
      open.href = `/?collection=${result.collection_id}`;
      open.hidden = false;
      open.focus();
    } catch (error) {
      if (!leftPage && current === generation) showError(error, true);
    } finally {
      if (!leftPage && current === generation) { busy = false; updateControls(); }
    }
  });

  function selectItems(value) {
    if (busy || pendingSave || completed || !version) return;
    selected = new Set(value ? items.map(item => item.id) : []);
    inputs.forEach(input => { input.checked = value; });
    updateSelection();
  }
  all.addEventListener('click', () => selectItems(true));
  none.addEventListener('click', () => selectItems(false));
  retry.addEventListener('click', preview);
  window.addEventListener('pagehide', () => { leftPage = true; ++generation; controller?.abort(); });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    leftPage = false;
    busy = false;
    if (pendingSave) showError(new Error('Save interrupted'), true);
    else if (!completed) preview();
    updateControls();
  });
  if (!/^[1-9]\d{0,9}$/.test(id) || !validId(Number(id))) {
    status.textContent = 'This collection link is unavailable. Return to Collections to choose another.';
    return;
  }
  preview();
})();
