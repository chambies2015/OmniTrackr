// Homepage hero search: find titles members track and put them on the guest list
// (guest-list.js) before signing up. Results come from GET /api/titles/search and
// are drawn with textContent only. Clicks on a result are handled by guest-list.js.
(function () {
  'use strict';

  const MIN_CHARS = 2;
  const DELAY_MS = 220;

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') window.reportFunnelEvent(event);
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function resultButton(item) {
    const button = element('button', 'lp-search__result');
    button.type = 'button';
    button.dataset.guestKind = item.kind;
    button.dataset.guestSlug = item.slug;
    button.dataset.guestTitle = item.title;
    button.setAttribute('aria-pressed', 'false');
    const art = element('span', 'lp-search__art');
    if (item.image && /^https?:\/\//.test(item.image)) {
      const image = element('img');
      image.src = item.image;
      image.alt = '';
      image.loading = 'lazy';
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      image.width = 40;
      image.height = 60;
      art.appendChild(image);
    } else {
      art.textContent = (item.title || '?').charAt(0).toUpperCase();
    }
    const copy = element('span', 'lp-search__copy');
    copy.appendChild(element('span', 'lp-search__title', item.title));
    copy.appendChild(element('span', 'lp-search__meta', item.year ? `${item.label} · ${item.year}` : item.label));
    const state = element('span', 'lp-search__state');
    state.setAttribute('aria-hidden', 'true');
    button.append(art, copy, state);
    button.setAttribute('aria-label', `${item.title}, ${item.label}${item.year ? ` ${item.year}` : ''}`);
    return button;
  }

  function render(container, results, query) {
    container.replaceChildren();
    if (!results.length) {
      const empty = element('div', 'lp-search__empty');
      empty.appendChild(element('p', '', `No match for “${query}” among titles members track yet.`));
      const more = element('p', '', 'Your free library searches millions of movies, shows, anime, games, albums and books. ');
      const cta = element('button', 'lp-search__link', 'Create it and add this title');
      cta.type = 'button';
      cta.dataset.action = 'show-register-form';
      more.appendChild(cta);
      empty.appendChild(more);
      container.appendChild(empty);
    } else {
      container.appendChild(element('p', 'sr-only', `${results.length} match${results.length === 1 ? '' : 'es'}. Choose one to add it to your list.`));
      const list = element('ul', 'lp-search__list');
      results.forEach(item => {
        const row = element('li');
        row.appendChild(resultButton(item));
        list.appendChild(row);
      });
      container.appendChild(list);
    }
    container.hidden = false;
    if (window.OmniGuestList && typeof window.OmniGuestList.refreshTiles === 'function') window.OmniGuestList.refreshTiles();
  }

  function setup(form) {
    const input = form.querySelector('input[type="search"]');
    const container = form.querySelector('.lp-search__results');
    if (!input || !container) return null;
    let timer = null;
    let controller = null;
    let generation = 0;

    async function run() {
      const query = input.value.trim();
      const current = ++generation;
      if (controller) controller.abort();
      if (query.replace(/[^\p{L}\p{N}]/gu, '').length < MIN_CHARS) {
        container.hidden = true;
        container.replaceChildren();
        return;
      }
      report('title_search_used');
      controller = typeof AbortController === 'function' ? new AbortController() : null;
      try {
        const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query.slice(0, 80))}`,
          { credentials: 'same-origin', signal: controller ? controller.signal : undefined });
        if (!response.ok) throw new Error(String(response.status));
        const data = await response.json();
        if (current !== generation) return;
        render(container, Array.isArray(data.results) ? data.results : [], query);
      } catch (error) {
        if (current !== generation || (error && error.name === 'AbortError')) return;
        container.replaceChildren(element('p', 'lp-search__empty', 'Search is not available right now. Try the popular picks below.'));
        container.hidden = false;
      }
    }

    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(run, DELAY_MS);
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        input.value = '';
        run();
      }
    });
    form.addEventListener('submit', event => {
      event.preventDefault();
      clearTimeout(timer);
      run();
    });
    return { run, render };
  }

  function init() {
    document.querySelectorAll('[data-title-search]').forEach(setup);
  }

  const api = { setup, render, resultButton };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})();
