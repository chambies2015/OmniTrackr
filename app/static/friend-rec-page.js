// /r/<token>: a friend's recommendation. Visitors keep the link in this browser so the title is
// waiting in their inbox once they sign up; signed-in members save it with one click.
(function () {
  'use strict';

  const KEY = 'omnitrackr_pending_recs';
  const token = document.body.dataset.recToken || '';
  const status = document.querySelector('[data-friend-rec-status]');
  if (!/^[A-Za-z0-9_-]{16,48}$/.test(token)) return;

  function remember() {
    try {
      const list = JSON.parse(localStorage.getItem(KEY) || '[]');
      const tokens = (Array.isArray(list) ? list : []).filter(item => item !== token);
      tokens.push(token);
      localStorage.setItem(KEY, JSON.stringify(tokens.slice(-5)));
    } catch (error) { /* storage off: the signed-in button still works */ }
  }

  if (document.body.dataset.signedIn !== '1') {
    remember();
    return;
  }

  const save = document.querySelector('[data-friend-rec-claim]');
  if (!save) return;
  save.addEventListener('click', async () => {
    save.disabled = true;
    const headers = { Accept: 'application/json' };
    try {
      const stored = localStorage.getItem('omnitrackr_token');
      if (stored) headers.Authorization = `Bearer ${stored}`;
    } catch (error) { /* cookie session */ }
    try {
      const response = await fetch(`/api/friend-recs/claim/${encodeURIComponent(token)}`, {
        method: 'POST', credentials: 'same-origin', headers,
      });
      if (response.status === 401) {
        remember();
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#login`;
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not save it. Please try again.');
      if (data.own) {
        status.textContent = 'This is your own recommendation. Send the link to a friend.';
      } else {
        status.textContent = data.claimed ? 'Saved. It\'s waiting on your dashboard.' : 'It\'s already on your dashboard.';
        const go = document.createElement('a');
        go.className = 'site-btn site-btn--primary';
        go.href = '/#friend-recs';
        go.textContent = 'Open my dashboard';
        save.replaceWith(go);
        return;
      }
      save.disabled = false;
    } catch (error) {
      status.textContent = error.message;
      save.disabled = false;
    }
  });
}());
