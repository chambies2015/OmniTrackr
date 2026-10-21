// Account → Public profile → Showcase: pin titles from your library to the top of your profile.
// Every change saves right away. Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const CATEGORY = /^[a-z-]{1,16}$/;
  let picks = [];
  let limit = 3;
  let supporterLimit = 6;
  let saving = false;
  let searchTimer = null;
  let searchToken = 0;

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function message(id, text) {
    const node = $(id);
    if (!node) return;
    node.textContent = text || '';
    node.style.display = text ? 'block' : 'none';
  }

  function cleanItems(items) {
    return (Array.isArray(items) ? items : []).filter(item => item && CATEGORY.test(item.category)
      && Number.isInteger(item.id) && typeof item.title === 'string');
  }

  function safeImage(url) {
    return typeof url === 'string' && /^https?:\/\//.test(url) ? url : null;
  }

  function subtitle(item) {
    const bits = [typeof item.label === 'string' ? item.label : ''];
    if (Number.isInteger(item.year)) bits.push(String(item.year));
    if (typeof item.rating === 'number') bits.push(`${item.rating}/10`);
    return bits.filter(Boolean).join(' · ');
  }

  function row(item, buttons) {
    const li = document.createElement('li');
    li.className = 'showcase-row';
    const image = safeImage(item.image);
    const art = document.createElement(image ? 'img' : 'span');
    art.className = 'showcase-row__art';
    if (image) {
      art.src = image;
      art.alt = '';
      art.loading = 'lazy';
    }
    const copy = document.createElement('span');
    copy.className = 'showcase-row__copy';
    const title = document.createElement('strong');
    title.textContent = item.title;
    const small = document.createElement('small');
    small.textContent = subtitle(item);
    copy.append(title, small);
    const actions = document.createElement('span');
    actions.className = 'showcase-row__actions';
    buttons.forEach(([text, label, onClick, disabled]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = text;
      button.setAttribute('aria-label', label);
      button.disabled = !!disabled;
      button.addEventListener('click', onClick);
      actions.appendChild(button);
    });
    li.append(art, copy, actions);
    return li;
  }

  function hint() {
    const node = $('profileShowcaseHint');
    if (!node) return;
    let text = `Pin up to ${limit} titles from your library to the top of your profile. ${picks.length} of ${limit} pinned.`;
    if (picks.length > limit) {
      text = `Pin up to ${limit} titles from your library to the top of your profile. You have ${picks.length} pinned from when you supported; your profile shows the first ${limit}.`;
    }
    if (limit < supporterLimit) text += ` Supporters can pin ${supporterLimit}.`;
    node.textContent = text;
  }

  function renderPicks() {
    const list = $('profileShowcaseList');
    if (!list) return;
    list.replaceChildren(...picks.map((item, index) => row(item, [
      ['↑', `Move ${item.title} up`, () => move(index, -1), index === 0],
      ['↓', `Move ${item.title} down`, () => move(index, 1), index === picks.length - 1],
      ['Remove', `Remove ${item.title} from your showcase`, () => remove(index)],
    ])));
    hint();
  }

  function renderResults(results, query) {
    const list = $('profileShowcaseResults');
    if (!list) return;
    const pinned = new Set(picks.map(item => `${item.category}:${item.id}`));
    const fresh = results.filter(item => !pinned.has(`${item.category}:${item.id}`));
    if (!fresh.length) {
      const empty = document.createElement('li');
      empty.className = 'showcase-results__empty';
      empty.textContent = query ? 'Nothing in your library matches that.' : 'Add titles to your library to pin them here.';
      list.replaceChildren(empty);
      return;
    }
    const full = picks.length >= limit;
    list.replaceChildren(...fresh.map(item => row(item, [
      ['Pin', `Pin ${item.title} to your showcase`, () => add(item), full],
    ])));
  }

  async function save(next) {
    if (saving) return;
    saving = true;
    message('profileShowcaseError', '');
    message('profileShowcaseSuccess', '');
    try {
      const response = await fetch(`${apiBase()}/api/profile/showcase`, fetchOptions({
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: next.map(item => ({ category: item.category, id: item.id })) }),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        message('profileShowcaseError', typeof data.detail === 'string' ? data.detail : 'Could not save your showcase.');
        return;
      }
      picks = cleanItems(data.showcase);
      if (Number.isInteger(data.showcase_limit)) limit = data.showcase_limit;
      renderPicks();
      message('profileShowcaseSuccess', 'Showcase saved.');
      search();
    } catch (error) {
      message('profileShowcaseError', 'Could not save your showcase.');
    } finally {
      saving = false;
    }
  }

  function add(item) {
    if (picks.length >= limit) return;
    save(picks.concat([item]));
  }

  function remove(index) {
    save(picks.filter((_, i) => i !== index));
  }

  function move(index, step) {
    const next = picks.slice();
    const target = index + step;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    save(next);
  }

  async function search() {
    const input = $('profileShowcaseSearch');
    if (!input) return;
    const query = input.value.trim();
    const token = ++searchToken;
    try {
      const response = await fetch(`${apiBase()}/api/profile/showcase/search?q=${encodeURIComponent(query)}`, fetchOptions());
      if (!response.ok || token !== searchToken) return;
      const data = await response.json();
      if (token === searchToken) renderResults(cleanItems(data.results), query);
    } catch (error) { /* the search list just stays as it was */ }
  }

  async function load() {
    if (!$('profileShowcase')) return;
    message('profileShowcaseError', '');
    message('profileShowcaseSuccess', '');
    try {
      const response = await fetch(`${apiBase()}/api/profile/settings`, fetchOptions());
      if (!response.ok) throw new Error('load failed');
      const data = await response.json();
      picks = cleanItems(data.showcase);
      if (Number.isInteger(data.showcase_limit)) limit = data.showcase_limit;
      if (Number.isInteger(data.showcase_supporter_limit)) supporterLimit = data.showcase_supporter_limit;
      renderPicks();
      search();
    } catch (error) {
      message('profileShowcaseError', 'Could not load your showcase.');
    }
  }

  function wrapAccountLoader() {
    const original = window.loadAccountInfo;
    if (typeof original !== 'function' || original.__showcaseWrapped) return;
    const wrapped = async function () {
      const result = await original.apply(this, arguments);
      load();
      return result;
    };
    wrapped.__showcaseWrapped = true;
    window.loadAccountInfo = wrapped;
  }

  function init() {
    const input = $('profileShowcaseSearch');
    if (!input) return;
    input.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(search, 250);
    });
    wrapAccountLoader();
  }

  window.ProfileShowcase = { load };
  if (typeof module !== 'undefined' && module.exports) module.exports = { load, cleanItems, subtitle };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
