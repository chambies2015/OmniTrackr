(() => {
  'use strict';

  const actions = document.querySelector('.collection-actions[data-collection-id]');
  if (!actions) return;
  const collectionId = Number(actions.dataset.collectionId);
  const status = document.getElementById('collectionActionStatus');
  const reportForm = document.getElementById('collectionReportForm');

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

  actions.addEventListener('click', async (event) => {
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
        const response = await post(`/collections/public/${collectionId}/helpful`);
        if (!response.ok) throw new Error('helpful');
        const result = await response.json();
        document.getElementById('collectionHelpfulCount').textContent = `${result.count} found this helpful`;
        button.textContent = 'Marked helpful';
        setStatus('Thanks—your feedback helps thoughtful collections stand out.');
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
      const response = await post(`/collections/public/${collectionId}/report`, {
        reason: document.getElementById('collectionReportReason').value,
      });
      if (!response.ok) throw new Error('report');
      reportForm.hidden = true;
      setStatus('Report received. Thank you for helping keep public collections useful.');
    } catch (error) {
      submit.disabled = false;
      setStatus('The report could not be sent. Please try again.');
    }
  });
})();
