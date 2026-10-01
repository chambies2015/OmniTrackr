/* Private checkpoints. Drafts stay in memory; only explicit Save/Clear sends a write. */
(() => {
  'use strict';
  const supported = new Set(['tv-shows', 'anime', 'books']);
  const drafts = new Map();
  let config = null;
  let active = null;
  let session = null;
  let sequence = 0;
  let lifecycle = 0;
  let requestController = null;
  let trigger = null;
  let focusRegion = null;
  let initialized = false;
  const el = id => document.getElementById(id);
  const fields = ['progressUnit', 'progressPosition', 'progressSeason', 'progressNote'];

  function sessionKey() {
    try { return config?.sessionKey() || null; } catch (_) { return null; }
  }
  function contextKey() { return config?.contextKey?.() ?? ''; }
  function summary(checkpoint) {
    if (!checkpoint || !Number.isInteger(checkpoint.position) || checkpoint.position < 1) return '';
    if (checkpoint.unit === 'episode') {
      const season = checkpoint.season === 0 ? 'Specials, ' : Number.isInteger(checkpoint.season) ? `Season ${checkpoint.season}, ` : '';
      return `Last watched · ${season}${season ? 'episode' : 'Episode'} ${checkpoint.position}`;
    }
    if (checkpoint.unit === 'page' || checkpoint.unit === 'chapter') {
      return `Last read · ${checkpoint.unit === 'page' ? 'Page' : 'Chapter'} ${checkpoint.position}`;
    }
    return '';
  }
  function appendSummary(container, item) {
    if (!supported.has(item?.category)) return;
    const span = document.createElement('span');
    span.className = 'progress-checkpoint';
    span.dataset.progressSummaryCategory = item.category;
    span.dataset.progressSummaryItemId = String(item.item_id ?? item.id);
    span.textContent = summary(item.progress);
    span.hidden = !span.textContent;
    container.appendChild(span);
  }
  function appendAction(container, item) {
    const id = Number(item?.item_id ?? item?.id);
    if (!supported.has(item?.category) || !Number.isSafeInteger(id) || id < 1 || id > 2147483647) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'progress-update';
    button.dataset.progressCategory = item.category;
    button.dataset.progressItemId = String(id);
    button.dataset.progressTitle = item.title;
    button.textContent = 'Update progress';
    button.setAttribute('aria-label', `Update progress for ${item.title}`);
    container.appendChild(button);
  }
  function status(text) { el('progressStatus').textContent = text; }
  function draftFromFields() {
    return { unit: el('progressUnit').value, position: el('progressPosition').value,
      season: el('progressSeason').value, note: el('progressNote').value };
  }
  function fieldsFromCheckpoint(checkpoint, category) {
    return { unit: checkpoint?.unit || (category === 'books' ? 'page' : 'episode'),
      position: String(checkpoint?.position ?? ''), season: String(checkpoint?.season ?? ''), note: checkpoint?.note || '' };
  }
  function stash() {
    if (!active?.loaded) return;
    active.draft = draftFromFields();
    if (dirty() || active.retry || active.conflict) drafts.set(active.key, active);
    else drafts.delete(active.key);
  }
  function cancelRequest() {
    sequence++;
    requestController?.abort();
    requestController = null;
    if (active) active.busy = false;
  }
  function close(restoreFocus = true) {
    const target = active ? { category: active.category, itemId: active.itemId } : null;
    stash();
    cancelRequest();
    el('progressDialog')?.close();
    active = null;
    if (restoreFocus) {
      if (trigger?.isConnected !== false) trigger?.focus();
      else if (target) {
        // A successful save can replace the queue/pulse button while the modal is open.
        const replacement = focusRegion?.querySelector?.(`[data-progress-category="${target.category}"][data-progress-item-id="${target.itemId}"]`);
        replacement?.focus();
      }
    }
    trigger = null;
    focusRegion = null;
  }
  function reset() {
    lifecycle++;
    close(false);
    drafts.clear();
    session = null;
    fields.forEach(id => { if (el(id)) el(id).value = ''; });
    if (el('progressTitle')) el('progressTitle').textContent = '';
    if (el('progressStatus')) status('');
  }
  function checkSession() {
    if (session && sessionKey() !== session) { reset(); return false; }
    return true;
  }
  function dirty() {
    return active?.loaded && JSON.stringify(draftFromFields()) !== JSON.stringify(active.saved);
  }
  function syncLabels() {
    const book = active?.category === 'books';
    el('progressUnitField').hidden = !book;
    el('progressSeasonField').hidden = book;
    el('progressPositionLabel').textContent = book
      ? `Last read ${el('progressUnit').value === 'chapter' ? 'chapter' : 'page'}` : 'Last watched episode';
  }
  function render() {
    if (!active) return;
    el('progressTitle').textContent = active.title;
    const draft = active.draft;
    if (draft) {
      el('progressUnit').value = draft.unit;
      el('progressPosition').value = draft.position;
      el('progressSeason').value = draft.season;
      el('progressNote').value = draft.note;
    }
    syncLabels();
    const locked = active.busy || !active.loaded || !!active.retry || active.conflict || active.missing;
    el('progressFields').disabled = !!locked;
    el('progressSave').disabled = !!locked;
    el('progressClear').hidden = !active.checkpoint;
    el('progressClear').disabled = !!locked;
    el('progressRetry').hidden = !active.retry;
    el('progressRetry').disabled = !!active.busy;
    el('progressReload').hidden = !(active.retry || active.conflict || active.loadError);
    el('progressReload').disabled = !!active.busy;
    el('progressCurrent').textContent = active.checkpoint
      ? `Saved: ${summary(active.checkpoint)}` : 'No saved checkpoint yet.';
    el('progressCurrent').hidden = !active.loaded;
  }
  async function request(method, body) {
    const item = active;
    if (!item || !checkSession()) return;
    const requestSequence = ++sequence;
    const requestSession = session;
    const requestContext = contextKey();
    const requestLifecycle = lifecycle;
    const controller = new AbortController();
    requestController = controller;
    const current = () => active === item && requestSequence === sequence
      && sessionKey() === requestSession && contextKey() === requestContext;
    item.busy = true; item.loadError = false;
    render();
    status(method === 'GET' ? 'Loading your saved progress…' : method === 'DELETE' ? 'Clearing your checkpoint…' : 'Saving your progress…');
    let timeout;
    try {
      const expired = new Promise((_, reject) => {
        timeout = window.setTimeout(() => { controller.abort(); reject(new Error('timeout')); }, 12000);
      });
      // Race the full response, including JSON, so a stalled body also has a deadline.
      const result = await Promise.race([expired, (async () => {
        const response = await config.request(`${config.base || ''}/progress/${item.category}/${item.itemId}`, {
          method, signal: controller.signal,
          ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
        });
        return { response, payload: response.ok ? await response.json() : null };
      })()]);
      if (!current()) { checkSession(); return; }
      const { response, payload } = result;
      if (response.status === 409) {
        item.retry = null; item.conflict = true;
        status('Your saved progress changed elsewhere. Your draft is still shown. Reload saved progress and review it before making another change.');
        return;
      }
      if (response.status === 404) {
        item.retry = null; item.missing = true;
        status('This title is no longer available in your library. Close this editor and refresh your library.');
        return;
      }
      if (response.status === 422) {
        item.retry = null;
        status('That checkpoint could not be saved. Check the episode, page or chapter and try again.');
        return;
      }
      if (!response.ok) throw new Error('request');
      if (payload?.category !== item.category || payload?.item_id !== item.itemId
        || !Number.isInteger(payload.revision) || payload.revision < 0) throw new Error('response');
      item.title = payload.title || item.title;
      item.revision = payload.revision; item.checkpoint = payload.checkpoint;
      item.loaded = true; item.conflict = false; item.missing = false; item.retry = null;
      item.saved = fieldsFromCheckpoint(payload.checkpoint, item.category);
      item.draft = { ...item.saved };
      drafts.delete(item.key);
      status(method === 'GET' ? 'Only Save progress or Clear progress changes your saved checkpoint.'
        : method === 'DELETE' ? 'Checkpoint cleared. Your ratings, reviews and finished status are unchanged.' : 'Progress saved privately. Your finished status is unchanged.');
      if (method !== 'GET') {
        document.querySelectorAll('[data-progress-summary-category]').forEach(node => {
          if (node.dataset.progressSummaryCategory === item.category && Number(node.dataset.progressSummaryItemId) === item.itemId) {
            node.textContent = summary(payload.checkpoint); node.hidden = !node.textContent;
          }
        });
        const stillCurrent = () => lifecycle === requestLifecycle && sessionKey() === requestSession && contextKey() === requestContext;
        Promise.resolve(config.onSaved?.(payload, stillCurrent)).catch(() => {});
      }
    } catch (_) {
      if (!current()) { checkSession(); return; }
      if (method === 'GET') {
        item.loadError = true;
        status('Your saved progress could not be loaded. Reload to try again.');
      } else {
        status('The result could not be confirmed. Retry the same change or reload saved progress to check what was saved.');
      }
    } finally {
      window.clearTimeout(timeout);
      if (current()) { item.busy = false; requestController = null; render(); }
    }
  }
  function validPayload() {
    const draft = draftFromFields();
    const integer = value => /^\d+$/.test(value) && Number.isSafeInteger(Number(value));
    if (!integer(draft.position) || Number(draft.position) < 1 || Number(draft.position) > 1000000) {
      status('Enter an episode, page or chapter from 1 to 1,000,000.'); el('progressPosition').focus(); return null;
    }
    const book = active.category === 'books';
    if (!book && (el('progressSeason').validity?.badInput
      || (draft.season !== '' && (!integer(draft.season) || Number(draft.season) > 10000)))) {
      status('Enter a season from 0 to 10,000, or leave it blank. Season 0 is for specials.'); el('progressSeason').focus(); return null;
    }
    if (draft.note.length > 300) { status('Keep your private reminder to 300 characters.'); el('progressNote').focus(); return null; }
    if (book && !['page', 'chapter'].includes(draft.unit)) return null;
    return { expected_revision: active.revision, unit: book ? draft.unit : 'episode', position: Number(draft.position),
      season: book || draft.season === '' ? null : Number(draft.season), note: draft.note.trim() || null };
  }
  function mutate(method, payload) {
    if (!active || !checkSession() || active.busy || active.conflict || active.missing || !active.loaded) return;
    stash();
    active.retry = { method, payload };
    request(method, payload);
  }
  function initialize() {
    if (initialized) return true;
    const dialog = el('progressDialog');
    if (!dialog) return false;
    initialized = true;
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    el('progressClose').addEventListener('click', () => close());
    el('progressCancel').addEventListener('click', () => close());
    el('progressUnit').addEventListener('change', syncLabels);
    el('progressForm').addEventListener('submit', event => {
      event.preventDefault();
      if (!active || active.busy || active.retry || active.conflict) return;
      const payload = validPayload();
      if (payload) mutate('PUT', payload);
    });
    el('progressClear').addEventListener('click', () => {
      if (!active || active.busy || active.retry || active.conflict) return;
      if (window.confirm('Clear this saved checkpoint and discard any unsaved progress edits? Your rating, review and finished status will stay the same.')) {
        mutate('DELETE', { expected_revision: active.revision });
      }
    });
    el('progressRetry').addEventListener('click', () => {
      if (active?.retry && !active.busy) request(active.retry.method, active.retry.payload);
    });
    el('progressReload').addEventListener('click', () => {
      if (!active || active.busy || !checkSession()) return;
      if (dirty() && !window.confirm('Reload saved progress and discard the unsaved changes shown here?')) return;
      active.retry = null; active.conflict = false; active.loaded = false;
      request('GET');
    });
    return true;
  }
  function open(category, itemId, title, opener) {
    if (!supported.has(category) || !Number.isSafeInteger(itemId) || itemId < 1 || itemId > 2147483647 || !config || !initialize()) return;
    const currentSession = sessionKey();
    if (!currentSession) { reset(); return; }
    if (config.canOpen && !config.canOpen()) return;
    if (session !== currentSession) reset();
    else close(false);
    session = currentSession;
    const key = `${category}:${itemId}`;
    const existing = drafts.get(key)?.loaded ? drafts.get(key) : null;
    if (!existing) drafts.delete(key);
    active = existing || { key, category, itemId, title, loaded: false, busy: false, revision: 0,
      checkpoint: null, draft: fieldsFromCheckpoint(null, category) };
    trigger = opener || document.activeElement;
    focusRegion = trigger?.closest?.('[id]') || null;
    render();
    el('progressDialog').showModal();
    el('progressClose').focus();
    if (!existing) request('GET');
    else status(active.retry ? 'The previous result was not confirmed. Retry the same change or reload saved progress.'
      : active.conflict ? 'Your draft is still shown. Reload saved progress and review it before making another change.'
        : 'Your draft is restored. Changes are only saved when you choose Save progress.');
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-progress-category][data-progress-item-id]');
    if (button && !button.disabled) open(button.dataset.progressCategory, Number(button.dataset.progressItemId), button.dataset.progressTitle, button);
  });
  window.addEventListener('storage', event => {
    if (event.key === null || event.key === 'omnitrackr_user' || event.key === 'omnitrackr_token') checkSession();
  });
  document.addEventListener('visibilitychange', checkSession);
  window.addEventListener('pagehide', reset);
  window.OmniProgress = { configure: options => { config = options; }, open, close, reset,
    navigate: () => { lifecycle++; close(false); }, summary, appendSummary, appendAction };
})();
