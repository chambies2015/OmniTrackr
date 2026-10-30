/* Header extras for public pages, kept apart from site.js so sandboxed pages
   (the demo) can leave them out: the member button swap and title search. */
/* Signed-in visitors see "My library" instead of "Log in" and "Start tracking".
   The session itself is an HttpOnly cookie, so this reads the same stored hint
   the dashboard uses; a stale hint only means the button leads to the homepage. */
(function () {
  let member = false;
  try {
    member = Boolean(window.localStorage.getItem('omnitrackr_user') || window.localStorage.getItem('omnitrackr_token'));
  } catch (_) { return; }
  if (!member) return;
  document.querySelectorAll('.site-header').forEach(function (header) {
    header.classList.add('is-member');
    header.querySelectorAll('.site-nav__library, .site-menu__library').forEach(function (link) { link.hidden = false; });
  });
})();

/* Title search from the header: a dialog that looks up titles members track
   (GET /api/titles/search) and links to their pages. Results are drawn with
   textContent only. Press "/" anywhere outside a text field to open it. Other
   links marked data-site-search-open (the not-found page) open it too, filled in
   with their data-search-hint. */
(function () {
  const trigger = document.querySelector('.site-search[data-site-search]');
  if (!trigger || typeof window.HTMLDialogElement !== 'function') return;

  const STARTERS = [
    ['Best of 2026', '/best-of', 'The year so far, picked and explained'],
    ['Franchises in order', '/in-order', 'Watch and play the big series the right way'],
    ['If you liked…', '/if-you-liked', 'What to try after a favorite'],
    ['Popular titles', '/titles', 'Everything members are tracking'],
  ];
  let dialog = null;
  let input = null;
  let body = null;
  let timer = null;
  let request = 0;
  let selected = -1;
  let opener = trigger;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function links() {
    return Array.from(body.querySelectorAll('.site-finder__list a'));
  }

  function select(index) {
    const all = links();
    if (!all.length) { selected = -1; return; }
    selected = (index + all.length) % all.length;
    all.forEach(function (link, i) { link.setAttribute('aria-selected', i === selected ? 'true' : 'false'); });
    all[selected].scrollIntoView({ block: 'nearest' });
    input.setAttribute('aria-activedescendant', all[selected].id);
  }

  function list(label, rows) {
    const heading = el('p', 'site-finder__label', label);
    const ul = el('ul', 'site-finder__list');
    ul.setAttribute('role', 'listbox');
    ul.setAttribute('aria-label', label);
    rows.forEach(function (row, i) {
      const li = el('li');
      const link = el('a');
      link.href = row.url;
      link.id = 'site-finder-option-' + i;
      link.setAttribute('role', 'option');
      link.setAttribute('aria-selected', 'false');
      const art = el('span', 'site-finder__art');
      if (row.image && /^https?:\/\//.test(row.image)) {
        const img = el('img');
        img.src = row.image;
        img.alt = '';
        img.loading = 'lazy';
        img.addEventListener('error', function () { img.remove(); });
        art.appendChild(img);
      }
      const text = el('span', 'site-finder__text');
      text.append(el('strong', '', row.title), el('span', '', row.meta));
      link.append(art, text);
      li.appendChild(link);
      ul.appendChild(li);
    });
    body.replaceChildren(heading, ul);
    selected = -1;
    input.removeAttribute('aria-activedescendant');
  }

  function note(message, withLink) {
    const p = el('p', 'site-finder__note', message);
    if (withLink) {
      p.append(' ');
      const link = el('a', '', 'Browse popular titles');
      link.href = '/titles';
      p.appendChild(link);
    }
    body.replaceChildren(p);
    selected = -1;
  }

  function starters() {
    list('Good places to start', STARTERS.map(function (row) {
      return { title: row[0], url: row[1], meta: row[2] };
    }));
    body.querySelectorAll('.site-finder__art').forEach(function (art) { art.remove(); });
  }

  function search(text) {
    const id = ++request;
    fetch('/api/titles/search?q=' + encodeURIComponent(text), { headers: { Accept: 'application/json' } })
      .then(function (response) { return response.ok ? response.json() : Promise.reject(response.status); })
      .then(function (data) {
        if (id !== request) return;
        const rows = (data && data.results) || [];
        if (!rows.length) { note('No tracked titles match "' + text + '" yet.', true); return; }
        list('Titles', rows.map(function (item) {
          return { title: item.title, url: item.url, image: item.image,
                   meta: [item.label, item.year].filter(Boolean).join(' · ') };
        }));
      })
      .catch(function () { if (id === request) note('Search is not available right now.', true); });
  }

  function build() {
    dialog = el('dialog', 'site-finder');
    dialog.setAttribute('aria-label', 'Search titles');
    const box = el('div', 'site-finder__box');
    const field = el('div', 'site-finder__field');
    const icon = trigger.querySelector('svg');
    if (icon) field.appendChild(icon.cloneNode(true));
    input = el('input');
    input.type = 'search';
    input.placeholder = 'Search movies, shows, anime, games, books…';
    input.maxLength = 200;
    input.autocomplete = 'off';
    input.setAttribute('aria-label', 'Search titles');
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-controls', 'site-finder-body');
    const close = el('button', 'site-finder__close', 'Esc');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close search');
    close.addEventListener('click', function () { dialog.close(); });
    field.append(input, close);
    body = el('div', 'site-finder__body');
    body.id = 'site-finder-body';
    box.append(field, body);
    dialog.appendChild(box);
    document.body.appendChild(dialog);

    input.addEventListener('input', function () {
      clearTimeout(timer);
      const text = input.value.trim();
      if (text.length < 2) { request++; starters(); return; }
      timer = setTimeout(function () { search(text); }, 200);
    });
    input.addEventListener('keydown', function (event) {
      // A search field clears itself on Escape; close the dialog in one press instead.
      if (event.key === 'Escape') { event.preventDefault(); dialog.close(); }
      else if (event.key === 'ArrowDown') { event.preventDefault(); select(selected + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); select(selected - 1); }
      else if (event.key === 'Enter') {
        const all = links();
        const target = all[selected] || (input.value.trim().length >= 2 ? all[0] : null);
        if (target) { event.preventDefault(); window.location.assign(target.href); }
      }
    });
    dialog.addEventListener('click', function (event) { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () { opener.focus(); });
  }

  function open(from, hint) {
    if (!dialog) build();
    if (dialog.open) return;
    opener = from || trigger;
    const text = (hint || '').trim();
    input.value = text;
    if (text.length >= 2) search(text); else starters();
    dialog.showModal();
    input.focus();
  }

  function bindOpener(link) {
    link.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button === 1) return;
      event.preventDefault();
      open(link, link.dataset.searchHint);
    });
  }

  bindOpener(trigger);
  document.querySelectorAll('[data-site-search-open]').forEach(bindOpener);
  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return;
    const active = document.activeElement;
    if (active && (active.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName))) return;
    event.preventDefault();
    open();
  });
})();
