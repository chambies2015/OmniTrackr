// Profile widgets page: dark/light previews and copy buttons for the embed code.
(function () {
  'use strict';

  function setTheme(theme) {
    document.querySelectorAll('[data-widget-theme]').forEach(button => {
      const active = button.dataset.widgetTheme === theme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.body.classList.toggle('is-light', theme === 'light');
    document.querySelectorAll('.widget-preview img[data-dark]').forEach(img => {
      const src = img.dataset[theme];
      if (src && img.getAttribute('src') !== src) img.setAttribute('src', src);
    });
    document.querySelectorAll('textarea[data-dark]').forEach(field => {
      field.value = field.dataset[theme] || field.value;
    });
  }

  async function copy(button) {
    const field = document.getElementById(button.dataset.widgetCopy);
    if (!field) return;
    const original = button.dataset.label || button.textContent;
    button.dataset.label = original;
    try {
      await navigator.clipboard.writeText(field.value);
      button.textContent = 'Copied';
    } catch (error) {
      field.focus();
      field.select();
      button.textContent = 'Press Ctrl+C';
    }
    setTimeout(() => { button.textContent = original; }, 2000);
  }

  function init() {
    document.querySelectorAll('[data-widget-theme]').forEach(button => {
      button.addEventListener('click', () => setTheme(button.dataset.widgetTheme));
    });
    document.querySelectorAll('[data-widget-copy]').forEach(button => {
      button.addEventListener('click', () => copy(button));
    });
    document.querySelectorAll('.widget-code__row textarea, .widget-code__row input').forEach(field => {
      field.addEventListener('focus', () => field.select());
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
