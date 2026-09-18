(function () {
  function createReviewReportControls(category, reviewId) {
    const details = document.createElement('details');
    details.className = 'review-report';

    const summary = document.createElement('summary');
    summary.textContent = 'Report this review';

    const form = document.createElement('form');
    form.dataset.reviewReport = 'true';
    form.dataset.category = category;
    form.dataset.reviewId = String(reviewId);

    const label = document.createElement('label');
    label.textContent = 'What is the issue?';
    const select = document.createElement('select');
    select.name = 'reason';
    select.required = true;
    [
      ['', 'Choose a reason'],
      ['spam', 'Spam or promotion'],
      ['harassment', 'Harassment'],
      ['personal_information', 'Personal information'],
      ['copied_content', 'Copied content'],
      ['other', 'Other safety issue'],
    ].forEach(([value, text]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });
    label.appendChild(select);

    const button = document.createElement('button');
    button.type = 'submit';
    button.textContent = 'Send report';
    const status = document.createElement('p');
    status.className = 'review-report__status';
    status.setAttribute('aria-live', 'polite');
    form.append(label, button, status);
    details.append(summary, form);
    return details;
  }

  async function submitReport(form) {
    const button = form.querySelector('button[type="submit"]');
    const status = form.querySelector('.review-report__status');
    const reason = new FormData(form).get('reason');
    if (!reason || !button || !status) return;
    button.disabled = true;
    status.textContent = 'Sending…';
    try {
      const response = await fetch(
        `/api/public/reviews/${encodeURIComponent(form.dataset.category)}/${encodeURIComponent(form.dataset.reviewId)}/report`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason }),
        },
      );
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'The report could not be sent.');
      if (result.visibility === 'unlisted') {
        status.textContent = 'Thank you. This review has been temporarily unlisted for revision.';
      } else if (result.duplicate) {
        status.textContent = 'A report from this browser is already recorded.';
      } else {
        status.textContent = 'Thank you. Your report was recorded.';
      }
      form.querySelector('select').disabled = true;
    } catch (error) {
      status.textContent = error.message || 'The report could not be sent.';
      button.disabled = false;
    }
  }

  document.addEventListener('submit', (event) => {
    const form = event.target.closest('[data-review-report]');
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();
    submitReport(form);
  });
  document.addEventListener('click', (event) => {
    if (event.target.closest('.review-report')) event.stopPropagation();
  });

  window.createReviewReportControls = createReviewReportControls;
}());
