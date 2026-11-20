// Profile widgets page: colors (dark, light, auto) and file (PNG, SVG) for every preview and
// embed code, plus the copy buttons. The codes for each pairing come from the page itself
// (#widgetCodes); nothing here builds an address.
(function () {
  'use strict';

  const HINTS = {
    png: 'PNG works on every forum and chat app. SVG stays sharp at any size and suits GitHub and websites.',
    svg: 'SVG stays sharp at any size. Some forums and chat apps only show PNG, so switch back if yours shows a broken image.',
    auto: 'Auto follows each reader\'s light or dark mode. Only SVG can do that, so the codes below use SVG.',
  };
  const state = { theme: 'dark', format: 'png' };
  let codes = {};

  function readCodes() {
    const node = document.getElementById('widgetCodes');
    try {
      codes = node ? JSON.parse(node.textContent) : {};
    } catch (error) {
      codes = {};
    }
    return codes;
  }

  function count(key) {
    if (!key || typeof fetch !== 'function') return;
    try {
      fetch('/api/widgets/event', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
        keepalive: true,
      }).catch(() => {});
    } catch (error) { /* counting never gets in the way */ }
  }

  function press(group, value) {
    document.querySelectorAll(`[data-widget-${group}]`).forEach(button => {
      const active = button.getAttribute(`data-widget-${group}`) === value;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function apply() {
    if (state.theme === 'auto') state.format = 'svg';
    press('theme', state.theme);
    press('format', state.format);
    document.body.classList.toggle('is-light', state.theme === 'light');
    document.body.classList.toggle('is-auto', state.theme === 'auto');
    const key = `${state.theme}-${state.format}`;
    document.querySelectorAll('[data-widget-kind]').forEach(card => {
      const set = (codes[card.getAttribute('data-widget-kind')] || {})[key];
      if (!set) return;
      const img = card.querySelector('.widget-preview img');
      if (img && typeof set.preview === 'string' && set.preview.startsWith('/u/') && img.getAttribute('src') !== set.preview) {
        img.setAttribute('src', set.preview);
      }
      card.querySelectorAll('textarea[data-widget-field]').forEach(field => {
        const value = set[field.getAttribute('data-widget-field')];
        if (typeof value === 'string') field.value = value;
      });
    });
    const hint = document.getElementById('widgetHint');
    if (hint) hint.textContent = state.theme === 'auto' ? HINTS.auto : HINTS[state.format];
    return key;
  }

  function pickTheme(value) {
    if (!['dark', 'light', 'auto'].includes(value)) return;
    state.theme = value;
    if (value === 'auto') count('pick_auto');
    apply();
  }

  function pickFormat(value) {
    if (!['png', 'svg'].includes(value)) return;
    state.format = value;
    // PNG can't follow the reader's mode, so auto falls back to dark.
    if (value === 'png' && state.theme === 'auto') state.theme = 'dark';
    if (value === 'svg') count('pick_svg');
    apply();
  }

  async function copy(button) {
    const field = document.getElementById(button.getAttribute('data-widget-copy'));
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
    count(button.getAttribute('data-widget-count'));
    setTimeout(() => { button.textContent = original; }, 2000);
  }

  function init() {
    readCodes();
    document.querySelectorAll('[data-widget-theme]').forEach(button => {
      button.addEventListener('click', () => pickTheme(button.getAttribute('data-widget-theme')));
    });
    document.querySelectorAll('[data-widget-format]').forEach(button => {
      button.addEventListener('click', () => pickFormat(button.getAttribute('data-widget-format')));
    });
    document.querySelectorAll('[data-widget-copy]').forEach(button => {
      button.addEventListener('click', () => copy(button));
    });
    document.querySelectorAll('.widget-code__row textarea, .widget-code__row input').forEach(field => {
      field.addEventListener('focus', () => field.select());
    });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { state, apply, pickTheme, pickFormat, readCodes, copy };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
