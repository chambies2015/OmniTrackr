// Title pages: click-to-play trailers (nothing loads from YouTube until asked)
// and "Add to my library" for signed-in members.
(function () {
  'use strict';

  function playTrailer(button) {
    const id = button.dataset.youtubeId || '';
    if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
    const frame = document.createElement('iframe');
    frame.className = 'title-trailer-frame';
    frame.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
    frame.title = button.getAttribute('aria-label') || 'Trailer';
    frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    button.replaceWith(frame);
  }

  function authHeaders() {
    const headers = { Accept: 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  async function addToLibrary(button) {
    const status = document.querySelector('.title-hero__status');
    button.disabled = true;
    const original = button.textContent;
    button.textContent = 'Adding…';
    try {
      const response = await fetch(`/api/titles/${encodeURIComponent(button.dataset.titleKind)}/${encodeURIComponent(button.dataset.titleSlug)}/add`, {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(),
      });
      if (response.status === 401) {
        window.location.href = '/#landing-auth';
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not add it');
      button.textContent = '✓ In your library';
      if (status) status.textContent = data.state === 'existing' ? 'Already in your library.' : 'Added to your library. Rate it or write a review from your dashboard.';
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      if (status) status.textContent = 'Could not add it right now. Please try again.';
    }
  }

  document.addEventListener('click', event => {
    const trailer = event.target.closest && event.target.closest('.title-trailer');
    if (trailer) {
      playTrailer(trailer);
      return;
    }
    const add = event.target.closest && event.target.closest('[data-title-add]');
    if (add) addToLibrary(add);
  });
})();
