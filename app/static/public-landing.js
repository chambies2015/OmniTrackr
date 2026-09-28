/*
 * Small progressive-enhancement layer for the anonymous homepage.
 *
 * The private dashboard script is intentionally not loaded on public responses,
 * so this file owns only landing-page interactions. Keeping it separate reduces
 * transfer size and prevents anonymous visitors from receiving dashboard code.
 */
(function () {
  function showForm(action) {
    if (action === 'show-register-form' && typeof window.showRegisterForm === 'function') {
      window.showRegisterForm();
    }
    if (action === 'show-login-form' && typeof window.showLoginForm === 'function') {
      window.showLoginForm();
    }
  }

  function openPreview(source, alt) {
    const modal = document.getElementById('screenshotModal');
    const image = document.getElementById('screenshotModalImage');
    const caption = document.getElementById('screenshotModalCaption');
    if (!modal || !image || !caption || !source) return;

    image.src = source;
    image.alt = alt || 'OmniTrackr dashboard preview';
    caption.textContent = alt || 'OmniTrackr dashboard preview';
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closePreview() {
    const modal = document.getElementById('screenshotModal');
    if (!modal) return;
    modal.classList.remove('show');
    document.body.style.overflow = '';
  }

  document.addEventListener('click', function (event) {
    const action = event.target.closest('[data-action]');
    if (action) {
      const actionName = action.dataset.action;
      if (actionName === 'show-register-form' || actionName === 'show-login-form') {
        event.preventDefault();
        showForm(actionName);
        return;
      }
      if (actionName === 'close-screenshot-modal') {
        event.preventDefault();
        closePreview();
        return;
      }
    }

    const preview = event.target.closest('[data-screenshot-src]');
    if (preview) {
      event.preventDefault();
      openPreview(preview.dataset.screenshotSrc, preview.dataset.screenshotAlt);
      return;
    }

    const faqQuestion = event.target.closest('.faq-question');
    if (faqQuestion) {
      const item = faqQuestion.closest('.faq-item');
      if (item) {
        const expanded = item.classList.toggle('active');
        faqQuestion.setAttribute('aria-expanded', String(expanded));
      }
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closePreview();
  });
})();
