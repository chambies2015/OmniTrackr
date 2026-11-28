(() => {
  'use strict';

  const actions = document.querySelector('.collection-actions[data-collection-id]');
  const status = document.getElementById('collectionActionStatus');
  const reportForm = document.getElementById('collectionReportForm');
  const list = document.querySelector('ol[data-entry-path]');

  function setStatus(message) {
    if (status) status.textContent = message;
  }

  async function post(path, body) {
    return fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  function report(event) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  // Older pages (cached HTML) have no data paths; fall back to the public address.
  const collectionId = actions ? Number(actions.dataset.collectionId) : 0;
  const reportPath = actions?.dataset.reportPath || `/collections/public/${collectionId}/report`;
  const helpfulPath = actions?.dataset.helpfulPath || `/collections/public/${collectionId}/helpful`;

  actions?.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-collection-action]');
    if (!button || button.disabled) return;
    const action = button.dataset.collectionAction;
    if (action === 'show-report') {
      reportForm.hidden = !reportForm.hidden;
      if (!reportForm.hidden) document.getElementById('collectionReportReason')?.focus();
      return;
    }
    button.disabled = true;
    try {
      if (action === 'helpful') {
        const response = await post(helpfulPath);
        if (!response.ok) throw new Error('helpful');
        const result = await response.json();
        const count = document.getElementById('collectionHelpfulCount');
        if (count) count.textContent = `${result.count} found this helpful`;
        button.textContent = 'Marked helpful';
        setStatus('Thanks for the feedback.');
      }
    } catch (error) {
      button.disabled = false;
      setStatus('That action could not be completed. Please try again.');
    }
  });

  reportForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = reportForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const response = await post(reportPath, {
        reason: document.getElementById('collectionReportReason').value,
      });
      if (!response.ok) throw new Error('report');
      reportForm.hidden = true;
      setStatus('Report received. Thank you.');
    } catch (error) {
      submit.disabled = false;
      setStatus('The report could not be sent. Please try again.');
    }
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-entry-signup]')) report('collection_signup_clicked');
  });

  list?.addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-entry-save]');
    if (!button || button.disabled) return;
    const entryId = Number(button.dataset.entrySave);
    if (!Number.isInteger(entryId) || entryId < 1) return;
    button.disabled = true;
    const label = button.textContent;
    button.textContent = 'Adding…';
    try {
      const response = await post(`${list.dataset.entryPath}/${entryId}/library`);
      if (response.status === 401) {
        // Signed out since the page loaded: offer the sign-in link instead of the button.
        const signin = document.createElement('a');
        signin.className = 'collection-entry__add';
        signin.rel = 'nofollow';
        signin.dataset.entrySignup = '';
        signin.href = `/?next=${encodeURIComponent(document.location.pathname)}#landing-auth`;
        signin.textContent = 'Sign in to add';
        button.replaceWith(signin);
        return;
      }
      if (!response.ok) throw new Error('save');
      const result = await response.json();
      const done = document.createElement('span');
      done.className = 'collection-entry__have';
      done.textContent = result.added ? '✓ Added to your library' : '✓ In your library';
      button.replaceWith(done);
      setStatus(result.added
        ? `${result.title} is in your library now, marked as not started.`
        : `${result.title} was already in your library, so nothing changed.`);
    } catch (error) {
      button.disabled = false;
      button.textContent = label;
      setStatus('That title could not be added. Please try again.');
    }
  });
})();
