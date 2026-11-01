/*
 * Small progressive-enhancement layer for the anonymous homepage.
 *
 * The private dashboard script is intentionally not loaded on public responses,
 * so this file owns only landing-page interactions. Keeping it separate reduces
 * transfer size and prevents anonymous visitors from receiving dashboard code.
 */
(function () {
  // Sign-up and log-in buttons open the form card in a pop-up instead of scrolling
  // past the whole page to it. The card is moved (not copied) so auth.js keeps
  // working on the same elements, and goes back to its section when the pop-up closes.
  var authHome = null;

  function authDialog() {
    var dialog = document.getElementById('authDialog');
    return dialog && typeof dialog.showModal === 'function' ? dialog : null;
  }

  function openAuthDialog() {
    var dialog = authDialog();
    var slot = dialog && dialog.querySelector('[data-auth-dialog-slot]');
    var card = document.querySelector('.lp-auth__card');
    if (!dialog || !slot || !card) return false;
    if (dialog.open) return true;
    if (!authHome) authHome = {parent: card.parentNode, next: card.nextSibling};
    slot.appendChild(card);
    try {
      dialog.showModal();
    } catch (error) {
      returnAuthCard();
      return false;
    }
    document.body.style.overflow = 'hidden';
    return true;
  }

  function returnAuthCard() {
    var card = document.querySelector('.lp-auth__card');
    if (authHome && card && card.parentNode !== authHome.parent) authHome.parent.insertBefore(card, authHome.next);
    document.body.style.overflow = '';
  }

  function closeAuthDialog() {
    var dialog = authDialog();
    if (dialog && dialog.open) dialog.close();
  }

  var dialogElement = authDialog();
  if (dialogElement) {
    dialogElement.addEventListener('close', returnAuthCard);
    // A click on the dimmed backdrop lands on the dialog itself.
    dialogElement.addEventListener('click', function (event) {
      if (event.target === dialogElement) closeAuthDialog();
    });
  }
  window.OmniAuthDialog = {open: openAuthDialog, close: closeAuthDialog};

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') window.reportFunnelEvent(event);
  }

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
        if (action.hasAttribute && action.hasAttribute('data-hero-signup')) report('hero_signup_clicked');
        showForm(actionName);
        return;
      }
      if (actionName === 'close-auth-dialog') {
        event.preventDefault();
        closeAuthDialog();
        return;
      }
      if (actionName === 'close-screenshot-modal') {
        event.preventDefault();
        closePreview();
        return;
      }
    }

    if (event.target.closest('a[data-hero-signup]')) report('hero_signup_clicked');

    // Show/Hide password buttons are handled by auth.js, which every sign-in form loads.
    if (event.target.closest('[data-password-toggle]')) return;

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
