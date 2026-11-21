/* Quick changes from the library (Nov 2026): mark a title done or rate it without
   opening Edit, a short "year · creator" line on each card, and a tidier toolbar.
   enhanceLibraryCards() calls decorate() for every row it draws. Saves go through
   the same PUT endpoints Edit uses, sending only the one field that changed. */
(() => {
  'use strict';
  // table id: [category, completion field, done word, not-done word]
  const TABLES = {
    movieTable: ['movies', 'watched', 'Watched', 'Not watched'],
    tvShowTable: ['tv-shows', 'watched', 'Finished', 'Not finished'],
    animeTable: ['anime', 'watched', 'Finished', 'Not finished'],
    videoGameTable: ['video-games', 'played', 'Played', 'Not played'],
    musicTable: ['music', 'listened', 'Listened', 'Not listened'],
    bookTable: ['books', 'read', 'Read', 'Not read'],
    mangaTable: ['manga', 'read', 'Read', 'Not read'],
    podcastTable: ['podcasts', 'listened', 'Listened', 'Not listened'],
    audiobookTable: ['audiobooks', 'listened', 'Finished', 'Not finished'],
  };
  const YEAR_LABELS = ['Year', 'Release Date', 'Started'];
  const CREATOR_LABELS = ['Director', 'Artist', 'Author', 'Mangaka', 'Host'];
  let popover = null;
  let saving = false;

  const notice = (message, tone) => { if (typeof window.showNotice === 'function') window.showNotice(message, tone); };
  const base = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const editing = () => typeof editingRowId !== 'undefined' && editingRowId !== null;

  function rowInfo(row, tableId) {
    const config = TABLES[tableId];
    const anchor = row?.querySelector?.('[data-next-up-item-id]');
    if (!config || !anchor) return null;
    const id = Number(anchor.dataset.nextUpItemId);
    if (!Number.isSafeInteger(id) || id < 1) return null;
    const title = row.querySelector('[data-collection-item-title]')?.dataset.collectionItemTitle
      || row.cells[1]?.textContent.trim() || 'this title';
    return { category: config[0], field: config[1], done: config[2], notDone: config[3], id, title, tableId };
  }

  function cellText(row, labels) {
    for (const label of labels) {
      const cell = row.querySelector(`td[data-label="${label}"]`);
      const text = cell?.textContent.trim();
      if (text) return text;
    }
    return '';
  }

  function metaLine(row) {
    const yearText = cellText(row, YEAR_LABELS);
    const year = (yearText.match(/\b(1[89]\d\d|2\d\d\d)\b/) || [''])[0];
    let second = cellText(row, CREATOR_LABELS);
    if (!second) {
      const seasons = Number(cellText(row, ['Seasons']));
      if (Number.isInteger(seasons) && seasons > 0) second = `${seasons} season${seasons === 1 ? '' : 's'}`;
    }
    if (!second) second = cellText(row, ['Genres', 'Genre']).split(',')[0].trim();
    return [year, second].filter(Boolean).join(' · ');
  }

  async function save(info, changes) {
    if (saving) return false;
    if (editing()) {
      notice('Save or cancel your current edit first.');
      return false;
    }
    saving = true;
    try {
      const response = await authenticatedFetch(`${base()}/${info.category}/${info.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(changes),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const text = typeof apiErrorText === 'function' ? apiErrorText(body, '') : '';
        notice(text || 'That change did not save. Try again in a moment.');
        return false;
      }
      // The heading's stat line and the status chip counts follow the change. Ticking off
      // several titles in a row asks for the numbers once (each read is about 20 queries,
      // limited to 60 a minute), not once a tick.
      const hero = window.OmniHomeHero;
      (hero?.refreshSoon || hero?.refresh)?.();
      return true;
    } catch (_) {
      notice('That change did not save. Check your connection and try again.');
      return false;
    } finally {
      saving = false;
    }
  }

  function reload(category) {
    const config = typeof libraryPageConfig === 'function' ? libraryPageConfig(category) : null;
    if (config) config[2]();
  }

  // ---------- Done / not done ----------
  function decorateStatus(row, info) {
    const cell = row.querySelector('td[data-card-field="status"]');
    const icon = cell?.querySelector('.watched-icon');
    if (!icon || icon.closest('.library-quick-status')) return;
    const complete = icon.classList.contains('watched');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'library-quick-status';
    button.setAttribute('aria-pressed', String(complete));
    button.setAttribute('aria-label', complete
      ? `${info.done}: ${info.title}. Press to mark it ${info.notDone.toLowerCase()}`
      : `Mark ${info.title} as ${info.done.toLowerCase()}`);
    button.title = complete ? `Mark as ${info.notDone.toLowerCase()}` : `Mark as ${info.done.toLowerCase()}`;
    icon.replaceWith(button);
    button.appendChild(icon);
    // The icon's own label is what the List pill prints; the button carries the spoken name.
    icon.setAttribute('aria-hidden', 'true');
    button.addEventListener('click', async () => {
      button.disabled = true;
      const ok = await save(info, { [info.field]: !complete });
      button.disabled = false;
      if (!ok) return;
      if (complete) {
        notice(`${info.title} is back to ${info.notDone.toLowerCase()}.`, 'info');
      } else {
        notice(`${info.title}: marked ${info.done.toLowerCase()}.`, 'success');
        if (typeof window.openCompletionMoment === 'function') window.openCompletionMoment(info.category, info.id);
      }
      reload(info.category);
    });
  }

  // ---------- Rating ----------
  function decorateRating(row, info) {
    const cell = row.querySelector('td[data-card-field="rating"]');
    if (!cell || cell.querySelector('.library-quick-rate')) return;
    const text = cell.textContent.trim();
    const value = parseFloat(text);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'library-quick-rate';
    button.dataset.rated = String(Number.isFinite(value));
    button.setAttribute('aria-haspopup', 'dialog');
    if (Number.isFinite(value)) {
      const star = document.createElement('span');
      star.className = 'library-quick-rate__star';
      star.setAttribute('aria-hidden', 'true');
      star.textContent = '★';
      const score = document.createElement('span');
      score.textContent = value.toFixed(1);
      const out = document.createElement('span');
      out.className = 'library-quick-rate__out';
      out.textContent = '/10';
      button.append(star, score, out);
      button.setAttribute('aria-label', `Your rating for ${info.title}: ${value.toFixed(1)} out of 10. Change it`);
    } else {
      button.textContent = 'Rate';
      button.setAttribute('aria-label', `Rate ${info.title}`);
    }
    cell.replaceChildren(button);
    cell.classList.add('library-cell--quick-rate');
    button.addEventListener('click', () => openRating(button, info, Number.isFinite(value) ? value : null));
  }

  function buildPopover() {
    const box = document.createElement('div');
    box.className = 'library-rate-pop';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'false');
    box.setAttribute('aria-labelledby', 'libraryRatePopTitle');
    box.hidden = true;
    box.innerHTML = '<p class="library-rate-pop__title" id="libraryRatePopTitle"></p>'
      + '<div class="library-rate-pop__scale" role="group" aria-label="Score out of 10"></div>'
      + '<div class="library-rate-pop__foot"><span class="library-rate-pop__hint">Half points? Use Edit.</span>'
      + '<button type="button" class="library-rate-pop__clear">Clear</button></div>';
    const scale = box.querySelector('.library-rate-pop__scale');
    for (let score = 1; score <= 10; score += 1) {
      const pick = document.createElement('button');
      pick.type = 'button';
      pick.dataset.score = String(score);
      pick.textContent = String(score);
      pick.setAttribute('aria-label', `${score} out of 10`);
      scale.appendChild(pick);
    }
    box.addEventListener('click', event => {
      const pick = event.target.closest('button');
      if (!pick || !box.contains(pick) || !popover.info) return;
      if (pick.dataset.score) choose(Number(pick.dataset.score));
      else if (pick.classList.contains('library-rate-pop__clear')) choose(null);
    });
    box.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.stopPropagation(); closeRating(true); return; }
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      const picks = Array.from(scale.children);
      const at = picks.indexOf(document.activeElement);
      if (at < 0) return;
      event.preventDefault();
      picks[Math.max(0, Math.min(picks.length - 1, at + (event.key === 'ArrowRight' ? 1 : -1)))].focus();
    });
    document.body.appendChild(box);
    popover = { box, scale, info: null, trigger: null };
    document.addEventListener('click', event => {
      if (box.hidden || box.contains(event.target) || event.target.closest?.('.library-quick-rate') === popover.trigger) return;
      closeRating(false);
    });
    ['scroll', 'resize'].forEach(type => window.addEventListener(type, () => { if (!box.hidden) place(); }, { passive: true, capture: true }));
  }

  function place() {
    const { box, trigger } = popover;
    if (!trigger?.isConnected) { closeRating(false); return; }
    const anchor = trigger.getBoundingClientRect();
    const width = box.offsetWidth || 300;
    const height = box.offsetHeight || 120;
    const left = Math.min(window.innerWidth - width - 8, Math.max(8, anchor.left + anchor.width / 2 - width / 2));
    const below = anchor.bottom + 8;
    const top = below + height > window.innerHeight - 8 ? Math.max(8, anchor.top - height - 8) : below;
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
  }

  function openRating(trigger, info, current) {
    if (editing()) { notice('Save or cancel your current edit first.'); return; }
    if (!popover) buildPopover();
    if (!popover.box.hidden && popover.trigger === trigger) { closeRating(true); return; }
    popover.info = info;
    popover.trigger = trigger;
    popover.box.querySelector('.library-rate-pop__title').textContent = `Rate ${info.title}`;
    const rounded = current === null ? null : Math.round(current);
    Array.from(popover.scale.children).forEach(pick => {
      pick.setAttribute('aria-pressed', String(Number(pick.dataset.score) === rounded && current === rounded));
    });
    popover.box.querySelector('.library-rate-pop__clear').hidden = current === null;
    popover.box.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    place();
    const focus = popover.scale.querySelector('[aria-pressed="true"]') || popover.scale.children[Math.max(0, (rounded || 7) - 1)];
    focus?.focus({ preventScroll: true });
  }

  function closeRating(returnFocus) {
    if (!popover || popover.box.hidden) return;
    popover.box.hidden = true;
    popover.trigger?.setAttribute('aria-expanded', 'false');
    if (returnFocus && popover.trigger?.isConnected) popover.trigger.focus({ preventScroll: true });
    popover.info = null;
  }

  async function choose(score) {
    const info = popover.info;
    popover.box.querySelectorAll('button').forEach(button => { button.disabled = true; });
    const ok = await save(info, { rating: score });
    popover.box.querySelectorAll('button').forEach(button => { button.disabled = false; });
    if (!ok) return;
    closeRating(false);
    notice(score === null ? `Cleared your rating for ${info.title}.` : `Rated ${info.title} ${score}/10.`, 'success');
    reload(info.category);
  }

  // ---------- Card line ----------
  function decorateMeta(row) {
    const cell = row.querySelector('td[data-card-field="rating"]');
    if (!cell || cell.querySelector('.library-card-meta')) return;
    const text = metaLine(row);
    if (!text) return;
    const meta = document.createElement('span');
    meta.className = 'library-card-meta';
    meta.textContent = text;
    cell.appendChild(meta);
  }

  // Shelf cards have no room for a "More details" link, so the row menu gets a
  // Details entry that opens the same panel. CSS shows each one in its own layout.
  function decorateDetails(row) {
    const actions = row.cells[row.cells.length - 1];
    const original = actions?.querySelector('.library-card-details');
    if (!original || actions.querySelector('.library-card-details-shortcut')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'action-btn library-card-details-shortcut';
    button.textContent = 'Details';
    button.addEventListener('click', () => original.click());
    actions.insertBefore(button, original);
  }

  function decorate(row, tableId) {
    const info = rowInfo(row, tableId);
    if (!info) return; // Edit mode rows keep their inputs untouched.
    decorateStatus(row, info);
    decorateRating(row, info);
    decorateMeta(row);
    decorateDetails(row);
  }

  // ---------- Toolbar ----------
  // Refresh, Export and Import are rarely used, so they move into a small menu at the
  // end of the toolbar. The buttons keep their ids, so every handler still finds them.
  function tidyToolbar() {
    document.querySelectorAll('.library-panel .library-utilities').forEach(group => {
      if (group.closest('.library-tools-menu')) return;
      const menu = document.createElement('details');
      menu.className = 'library-tools-menu';
      const summary = document.createElement('summary');
      summary.setAttribute('aria-label', 'Refresh, export or import this library');
      summary.title = 'Refresh, export or import';
      summary.innerHTML = '<span aria-hidden="true">•••</span>';
      group.replaceWith(menu);
      menu.append(summary, group);
    });
  }
  document.addEventListener('click', event => {
    document.querySelectorAll('details.library-tools-menu[open]').forEach(menu => {
      const chosen = event.target.closest?.('.library-utilities button');
      if (!menu.contains(event.target) || (chosen && menu.contains(chosen))) menu.removeAttribute('open');
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = document.querySelector('details.library-tools-menu[open]');
    if (!open) return;
    open.removeAttribute('open');
    open.querySelector('summary')?.focus();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tidyToolbar);
  else tidyToolbar();

  window.OmniLibraryQuick = { decorate, metaLine, closeRating };
})();
