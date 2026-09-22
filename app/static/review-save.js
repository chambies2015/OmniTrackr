/* Public identifiers select a preview; only the confirmation button writes. */
(() => {
  'use strict';
  const panel = document.getElementById('reviewSavePanel');
  if (!panel) return;
  const categories = {movie: 'movies', tv_show: 'tv-shows', anime: 'anime', video_game: 'video-games', music: 'music', book: 'books'};
  const category = panel.dataset.category;
  const id = panel.dataset.reviewId;
  const title = document.getElementById('reviewSaveTitle');
  const summary = document.getElementById('reviewSaveSummary');
  const status = document.getElementById('reviewSaveStatus');
  const confirm = document.getElementById('reviewSaveConfirm');
  const signin = document.getElementById('reviewSaveSignin');
  const retry = document.getElementById('reviewSaveRetry');
  const open = document.getElementById('reviewSaveOpen');
  let version = null;
  let busy = false;
  let generation = 0;
  let controller;
  let leftPage = false;
  const validId = value => Number.isInteger(value) && value > 0 && value <= 2147483647;

  function setBusy(value) {
    busy = value;
    confirm.disabled = value;
    retry.disabled = value;
    panel.setAttribute('aria-busy', String(value));
  }

  function showLibraryLink(itemId, libraryCategory) {
    if (!validId(itemId) || libraryCategory !== categories[category]) throw new Error('Invalid library response');
    open.href = `/?library_category=${encodeURIComponent(libraryCategory)}&library_item=${itemId}`;
    open.hidden = false;
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
          const response = await fetch(`/api/public/reviews/${id}/${action}?category=${encodeURIComponent(category)}`, {
            ...options, headers, credentials: 'same-origin', signal: activeController.signal,
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
    version = null;
    confirm.hidden = true;
    open.hidden = true;
    if (error.status === 401) {
      signin.hidden = false;
      status.textContent = 'Sign in to check your library. You’ll return here to review this title before adding it.';
    } else if (error.status === 404) {
      retry.hidden = true;
      status.textContent = 'This public review is no longer available. Explore other reviews to find your next title.';
    } else {
      retry.hidden = false;
      status.textContent = error.status === 409
        ? 'This title changed since your preview. Check your library again to review the latest details.'
        : saving
          ? 'We couldn’t confirm the save. Check your library again before trying to add this title.'
          : 'Your library preview couldn’t load. Please try again.';
    }
  }

  async function preview() {
    if (busy || leftPage) return;
    const current = ++generation;
    version = null;
    confirm.hidden = true; signin.hidden = true; retry.hidden = true; open.hidden = true;
    setBusy(true);
    status.textContent = 'Checking your library…';
    try {
      const data = await request('save-preview');
      if (leftPage || current !== generation) return;
      if (data.category !== category || data.library_category !== categories[category]
        || typeof data.title !== 'string' || typeof data.existing !== 'boolean'
        || typeof data.version !== 'string' || !data.version) throw new Error('Invalid preview');
      title.textContent = data.title;
      if (data.existing) {
        showLibraryLink(data.item_id, data.library_category);
        summary.textContent = 'A title with this name is already in your library. Your notes, rating and progress are preserved.';
        status.textContent = 'Open it to check the edition and your notes.';
      } else {
        version = data.version;
        summary.textContent = 'Add this title as unfinished and unrated. You can add your own impressions later.';
        status.textContent = 'Ready for your confirmation.';
        confirm.hidden = false;
      }
    } catch (error) {
      if (!leftPage && current === generation) showError(error, false);
    } finally {
      if (!leftPage && current === generation) setBusy(false);
    }
  }

  confirm.addEventListener('click', async () => {
    if (busy || !version || leftPage) return;
    const current = ++generation;
    setBusy(true);
    status.textContent = 'Adding this title…';
    try {
      const result = await request('save', {method: 'POST', body: JSON.stringify({version})});
      if (leftPage || current !== generation) return;
      if (typeof result.created !== 'boolean' || typeof result.reused !== 'boolean'
        || result.created === result.reused) throw new Error('Invalid save response');
      showLibraryLink(result.item_id, result.category);
      version = null;
      confirm.hidden = true;
      summary.textContent = result.created ? 'Added to your library, ready for your own notes and rating.' : 'A title with this name is already in your library. Your notes, rating and progress are preserved.';
      status.textContent = 'Your title is ready.';
      open.focus();
    } catch (error) {
      if (!leftPage && current === generation) showError(error, true);
    } finally {
      if (!leftPage && current === generation) setBusy(false);
    }
  });
  retry.addEventListener('click', preview);
  window.addEventListener('pagehide', () => { leftPage = true; ++generation; controller?.abort(); });
  window.addEventListener('pageshow', event => {
    if (event.persisted) { leftPage = false; setBusy(false); preview(); }
  });
  if (!Object.hasOwn(categories, category) || !/^[1-9]\d{0,9}$/.test(id) || !validId(Number(id))) {
    status.textContent = 'This review link is unavailable. Return to Public Reviews to choose a title.';
    return;
  }
  preview();
})();
