// Year in Review owner page: create, refresh, copy and stop a shared recap link.
(function () {
  'use strict';

  const box = document.querySelector('[data-recap-year]');
  if (!box) return;
  const year = box.dataset.recapYear;
  const status = box.querySelector('[data-recap-status]');
  const linkRow = box.querySelector('[data-recap-link]');
  const shareButton = box.querySelector('[data-recap-share]');
  const copyButton = box.querySelector('[data-recap-copy]');
  const unshareButton = box.querySelector('[data-recap-unshare]');

  function say(text) { if (status) status.textContent = text; }

  function render(state) {
    const shared = Boolean(state && state.shared);
    box.dataset.shared = shared ? 'true' : 'false';
    linkRow.hidden = !shared;
    copyButton.hidden = !shared;
    unshareButton.hidden = !shared;
    shareButton.textContent = shared ? 'Update shared recap' : 'Create share link';
    const anchor = linkRow.querySelector('a');
    if (anchor) { anchor.href = shared ? state.url : ''; anchor.textContent = shared ? state.url : ''; }
  }

  async function call(method) {
    const response = await fetch(`/api/year-in-review/${encodeURIComponent(year)}/share`, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: '{}',
    });
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  }

  async function copy(url) {
    if (navigator.share) {
      try { await navigator.share({ title: `My ${year} in review`, url }); return 'Shared.'; }
      catch (error) { if (error && error.name === 'AbortError') return ''; }
    }
    try { await navigator.clipboard.writeText(url); return 'Link copied.'; }
    catch (error) { window.prompt('Copy this link:', url); return ''; }
  }

  shareButton.addEventListener('click', async () => {
    const wasShared = box.dataset.shared === 'true';
    shareButton.disabled = true;
    say(wasShared ? 'Updating…' : 'Creating your link…');
    try {
      const state = await call('PUT');
      render(state);
      say(wasShared ? 'Updated. The link now shows this page as it is today.' : 'Your link is ready.');
      if (!wasShared) say(await copy(state.url) || 'Your link is ready.');
    } catch (error) {
      say('That did not work. Please try again.');
    } finally {
      shareButton.disabled = false;
    }
  });

  copyButton.addEventListener('click', async () => {
    const anchor = linkRow.querySelector('a');
    if (anchor && anchor.href) say(await copy(anchor.href));
  });

  unshareButton.addEventListener('click', async () => {
    unshareButton.disabled = true;
    try {
      render(await call('DELETE'));
      say('Sharing stopped. The old link no longer works.');
    } catch (error) {
      say('That did not work. Please try again.');
    } finally {
      unshareButton.disabled = false;
    }
  });
}());
