/* Episode tracking for TV shows and anime: progress bars, a one-tap "next episode"
   button and a season-by-season episode guide. Every write goes through the
   existing private progress checkpoint, so a member's place is still one record. */
(() => {
  'use strict';
  const supported = new Set(['tv-shows', 'anime']);
  let config = null;
  let dialog = null;
  let guide = null;
  let opener = null;
  let busy = false;
  let toastTimer = null;
  const pending = new Set();

  const itemId = item => Number(item?.item_id ?? item?.id);
  const validId = id => Number.isSafeInteger(id) && id > 0 && id <= 2147483647;
  function label(season, episode) {
    if (season === 0) return `Special ${episode}`;
    return Number.isInteger(season) ? `S${season} E${episode}` : `Episode ${episode}`;
  }
  function shortLabel(season, episode) {
    if (season === 0) return `Sp ${episode}`;
    return Number.isInteger(season) ? `S${season} E${episode}` : `E${episode}`;
  }
  function describe(progress, compact = false) {
    if (!progress) return '';
    if (compact && progress.current && !progress.caught_up && Number.isInteger(progress.total) && Number.isInteger(progress.watched)) {
      return `${progress.watched} of ${progress.total} episodes`;
    }
    const total = Number.isInteger(progress.total) ? progress.total : null;
    const current = progress.current;
    if (progress.caught_up) return total ? `All caught up · ${total} of ${total} episodes` : 'All caught up';
    if (!current) return total ? `Not started · ${total} episode${total === 1 ? '' : 's'}` : 'Not started';
    const where = `Watched ${shortLabel(current.season, current.episode)}`;
    return total && Number.isInteger(progress.watched) ? `${where} · ${progress.watched} of ${total}` : where;
  }
  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function bar(percent, name) {
    const track = make('span', 'episode-bar');
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-label', `Episodes watched${name ? ` in ${name}` : ''}`);
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', '100');
    track.setAttribute('aria-valuenow', String(percent));
    const fill = make('span', 'episode-bar__fill');
    fill.style.width = `${percent}%`;
    track.appendChild(fill);
    return track;
  }

  /* ---------------------------------------------------------------- list views */

  function fillBar(node, item) {
    const progress = item.episode_progress;
    node.replaceChildren();
    node.hidden = !progress;
    if (!progress) return;
    if (Number.isInteger(progress.percent) && progress.current) node.appendChild(bar(progress.percent, item.title));
    node.appendChild(make('span', 'episode-progress__label', describe(progress, node.dataset.episodeCompact === 'true')));
  }
  function fillActions(node, item) {
    const progress = item.episode_progress;
    node.replaceChildren();
    node.hidden = !progress;
    if (!progress) return;
    if (progress.next) {
      const next = make('button', 'episode-next');
      next.type = 'button';
      next.dataset.episodeNext = 'true';
      next.dataset.episodeSeason = progress.next.season === null ? '' : String(progress.next.season);
      next.dataset.episodeNumber = String(progress.next.episode);
      next.dataset.episodeRevision = String(progress.revision || 0);
      next.textContent = `+ ${shortLabel(progress.next.season, progress.next.episode)}`;
      next.setAttribute('aria-label', `Mark ${label(progress.next.season, progress.next.episode)} of ${item.title} watched`);
      next.disabled = pending.has(`${item.category}:${itemId(item)}`);
      node.appendChild(next);
    }
    const open = make('button', 'episode-guide-open', 'Episodes');
    open.type = 'button';
    open.dataset.episodeGuide = 'true';
    open.setAttribute('aria-label', `Open the episode guide for ${item.title}`);
    node.appendChild(open);
  }
  function tag(node, item, part) {
    node.dataset.episodeCategory = item.category;
    node.dataset.episodeItemId = String(itemId(item));
    node.dataset.episodeTitle = item.title || '';
    node.dataset.episodePart = part;
  }
  /** compact: the card already shows "Last watched", so the label only counts episodes. */
  function appendBar(container, item, { compact = false } = {}) {
    if (!container || !supported.has(item?.category) || !validId(itemId(item)) || !item.episode_progress) return;
    const node = make('span', 'episode-progress');
    tag(node, item, 'bar');
    if (compact) node.dataset.episodeCompact = 'true';
    fillBar(node, item);
    container.appendChild(node);
  }
  function appendActions(container, item) {
    if (!container || !supported.has(item?.category) || !validId(itemId(item)) || !item.episode_progress) return;
    const node = make('span', 'episode-actions');
    tag(node, item, 'actions');
    fillActions(node, item);
    container.appendChild(node);
  }
  /** Library rows: bar and buttons together under the title. */
  function appendRow(container, item) {
    if (!container || !supported.has(item?.category) || !item?.episode_progress) return;
    // A finished title only shows a bar when there's a place to show.
    if (item.watched && !item.episode_progress.current) return;
    const wrap = make('div', 'episode-row');
    appendBar(wrap, item);
    appendActions(wrap, item);
    container.appendChild(wrap);
  }
  function refreshNodes(category, id, title, progress) {
    document.querySelectorAll('[data-episode-part]').forEach(node => {
      if (node.dataset.episodeCategory !== category || Number(node.dataset.episodeItemId) !== id) return;
      const item = { category, id, title: node.dataset.episodeTitle || title, episode_progress: progress };
      if (node.dataset.episodePart === 'bar') fillBar(node, item); else fillActions(node, item);
    });
  }

  /* ---------------------------------------------------------------- requests */

  function sessionKey() { try { return config?.sessionKey?.() || null; } catch (_) { return null; } }
  async function send(category, id, method, path, body) {
    const response = await config.request(`${config.base || ''}/progress/${category}/${id}${path}`, {
      method, ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
    });
    const payload = response.ok ? await response.json() : null;
    if (payload && (payload.category !== category || payload.item_id !== id)) throw new Error('response');
    return { status: response.status, ok: response.ok, payload };
  }
  function afterSave(payload) {
    const session = sessionKey();
    const stillCurrent = () => sessionKey() === session;
    try { Promise.resolve(config.onSaved?.(payload, stillCurrent)).catch(() => {}); } catch (_) { /* optional refresh */ }
  }
  async function setEpisode(category, id, title, revision, season, episode) {
    const result = await send(category, id, 'PUT', '/episode', { expected_revision: revision, season, episode });
    if (result.ok && result.payload) {
      refreshNodes(category, id, title, result.payload.episodes);
      afterSave(result.payload);
    }
    return result;
  }

  function toast(text, undo) {
    let node = document.getElementById('episodeToast');
    if (!node) {
      node = make('div', 'episode-toast');
      node.id = 'episodeToast';
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      document.body.appendChild(node);
    }
    node.replaceChildren(make('span', '', text));
    if (undo) {
      const button = make('button', 'episode-toast__undo', 'Undo');
      button.type = 'button';
      button.addEventListener('click', () => { node.hidden = true; undo(); });
      node.appendChild(button);
    }
    node.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { node.hidden = true; }, undo ? 7000 : 4000);
  }

  async function quickNext(button) {
    const holder = button.closest('[data-episode-part]');
    const category = holder?.dataset.episodeCategory;
    const id = Number(holder?.dataset.episodeItemId);
    const title = holder?.dataset.episodeTitle || 'this title';
    if (!config || !supported.has(category) || !validId(id)) return;
    const key = `${category}:${id}`;
    if (pending.has(key)) return;
    const season = button.dataset.episodeSeason === '' ? null : Number(button.dataset.episodeSeason);
    const episode = Number(button.dataset.episodeNumber);
    const revision = Number(button.dataset.episodeRevision) || 0;
    pending.add(key);
    button.disabled = true;
    try {
      const result = await setEpisode(category, id, title, revision, season, episode);
      if (result.ok) {
        const before = result.payload.revision;
        toast(`Marked ${label(season, episode)} of ${title} watched.`, async () => {
          // Undo restores the previous episode, or clears a checkpoint this tap created.
          try {
            const previous = await send(category, id, 'GET', '/episodes');
            if (!previous.ok || previous.payload.revision !== before) { toast('Your progress changed since then, so nothing was undone.'); return; }
            const back = previousEpisode(previous.payload.layout.seasons, season, episode);
            const undone = back
              ? await setEpisode(category, id, title, before, back[0], back[1])
              : await send(category, id, 'DELETE', '', { expected_revision: before });
            if (!back && undone.ok) {
              afterSave(undone.payload);
              const fresh = await send(category, id, 'GET', '/episodes');
              if (fresh.ok) refreshNodes(category, id, title, fresh.payload.episodes);
            }
            toast(undone.ok ? 'Undone.' : 'That could not be undone. Reload to see your saved progress.');
          } catch (_) { toast('That could not be undone. Reload to see your saved progress.'); }
        });
      } else if (result.status === 409) {
        toast('Your progress changed in another tab or device. Refreshing it now.');
        afterSave({ category, item_id: id });
      } else if (result.status === 404) {
        toast('This title is no longer in your library. Refresh to update the list.');
      } else {
        toast('That episode could not be saved. Try again in a moment.');
      }
    } catch (_) {
      toast('That episode could not be saved. Check your connection and try again.');
    } finally {
      pending.delete(key);
      if (button.isConnected !== false) button.disabled = false;
    }
  }

  /* ---------------------------------------------------------------- arithmetic */

  const continuous = seasons => seasons.length === 1 && seasons[0].number === null;
  function absolute(seasons, season, episode) {
    if (!Number.isInteger(episode)) return 0;
    if (season === null || season === undefined) return episode;
    if (season === 0) return null;
    if (!seasons.length || continuous(seasons)) return season === 1 ? episode : null;
    let offset = 0;
    for (const entry of seasons) {
      if (entry.number >= season) break;
      offset += entry.episodes;
    }
    return offset + episode;
  }
  function locate(seasons, index) {
    for (const entry of seasons) {
      if (index <= entry.episodes) return [entry.number, index];
      index -= entry.episodes;
    }
    return null;
  }
  function previousEpisode(seasons, season, episode) {
    if (episode > 1) return [season, episode - 1];
    if (!Number.isInteger(season) || season <= 1 || !seasons.length || continuous(seasons)) return null;
    const earlier = seasons.filter(entry => entry.number < season);
    const last = earlier[earlier.length - 1];
    return last ? [last.number, last.episodes] : null;
  }

  /* ---------------------------------------------------------------- guide dialog */

  function buildDialog() {
    if (dialog) return dialog;
    dialog = make('dialog', 'progress-dialog episode-dialog');
    dialog.id = 'episodeDialog';
    dialog.setAttribute('aria-labelledby', 'episodeDialogTitle');
    const header = make('div', 'progress-dialog__header');
    const heading = make('div');
    heading.append(make('p', 'progress-dialog__eyebrow', 'Episode guide'));
    const h2 = make('h2', '', 'Episodes');
    h2.id = 'episodeDialogTitle';
    heading.appendChild(h2);
    const close = make('button', 'progress-dialog__close', '×');
    close.type = 'button';
    close.id = 'episodeDialogClose';
    close.setAttribute('aria-label', 'Close episode guide');
    close.addEventListener('click', closeGuide);
    header.append(heading, close);
    const body = make('div', 'episode-dialog__body');
    body.id = 'episodeDialogBody';
    const status = make('p', 'progress-dialog__status episode-dialog__status');
    status.id = 'episodeDialogStatus';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    dialog.append(header, body, status);
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeGuide(); });
    dialog.addEventListener('click', event => {
      const cell = event.target.closest?.('[data-guide-season]');
      if (cell && !cell.disabled) chooseEpisode(cell);
      const next = event.target.closest?.('[data-guide-next]');
      if (next && !next.disabled) chooseEpisode(next);
      if (event.target.closest?.('[data-guide-checkpoint]')) openCheckpoint();
      const offer = event.target.closest?.('[data-guide-push]');
      if (offer && !offer.disabled) offerPush(offer);
    });
    document.body.appendChild(dialog);
    return dialog;
  }
  function setStatus(text) { const node = document.getElementById('episodeDialogStatus'); if (node) node.textContent = text; }
  function closeGuide() {
    if (dialog?.open) dialog.close();
    guide = null;
    if (opener?.isConnected !== false) opener?.focus?.();
    opener = null;
  }
  function openCheckpoint() {
    if (!guide) return;
    const { category, id, title } = guide;
    const trigger = opener;
    closeGuide();
    window.OmniProgress?.open(category, id, title, trigger);
  }
  function renderGuide() {
    const body = document.getElementById('episodeDialogBody');
    if (!body || !guide) return;
    document.getElementById('episodeDialogTitle').textContent = guide.title;
    body.replaceChildren();
    if (!guide.data) {
      body.appendChild(make('p', 'progress-dialog__privacy', 'Loading the episode list…'));
      return;
    }
    const { layout, episodes: progress, checkpoint } = guide.data;
    const seasons = Array.isArray(layout?.seasons) ? layout.seasons : [];
    const current = progress?.current;
    const watched = current ? absolute(seasons, current.season, current.episode) : 0;

    const summary = make('div', 'episode-dialog__summary');
    if (Number.isInteger(progress?.percent)) summary.appendChild(bar(progress.percent, guide.title));
    summary.appendChild(make('p', 'episode-dialog__count', describe(progress)));
    if (checkpoint?.note) summary.appendChild(make('p', 'episode-dialog__note', `Your reminder: ${checkpoint.note}`));
    body.appendChild(summary);

    const actions = make('div', 'episode-dialog__actions');
    if (progress?.next) {
      const next = make('button', 'progress-dialog__save', `Mark ${label(progress.next.season, progress.next.episode)} watched`);
      next.type = 'button';
      next.dataset.guideNext = 'true';
      next.dataset.guideSeasonValue = progress.next.season === null ? '' : String(progress.next.season);
      next.dataset.guideEpisode = String(progress.next.episode);
      next.disabled = busy;
      actions.appendChild(next);
    }
    const edit = make('button', '', 'Reminder and specials');
    edit.type = 'button';
    edit.dataset.guideCheckpoint = 'true';
    actions.appendChild(edit);
    body.appendChild(actions);
    appendPushOffer(body, progress);

    if (!seasons.length) {
      body.appendChild(make('p', 'progress-dialog__privacy', 'We couldn\'t find an episode list for this title yet. Add its number of episodes when you edit it, and a grid will appear here. The button above still moves you one episode at a time.'));
    } else {
      body.appendChild(make('p', 'progress-dialog__hint', 'Tap an episode to mark it and everything before it watched. Tap your latest episode again to step back one.'));
      let offset = 0;
      const currentSeasonIndex = (() => {
        let running = 0;
        for (let i = 0; i < seasons.length; i++) {
          running += seasons[i].episodes;
          if (watched !== null && watched < running) return i;
        }
        return seasons.length - 1;
      })();
      seasons.forEach((entry, index) => {
        const block = make('details', 'episode-season');
        block.open = index === currentSeasonIndex || seasons.length === 1;
        const seen = watched === null ? 0 : Math.max(0, Math.min(entry.episodes, watched - offset));
        const name = entry.number === null ? 'All episodes' : `Season ${entry.number}`;
        const head = make('summary', 'episode-season__head');
        head.append(make('span', 'episode-season__name', name), make('span', 'episode-season__count', `${seen} of ${entry.episodes}`));
        block.appendChild(head);
        const grid = make('div', 'episode-grid');
        grid.setAttribute('role', 'group');
        grid.setAttribute('aria-label', name);
        for (let n = 1; n <= entry.episodes; n++) {
          const position = offset + n;
          const cell = make('button', 'episode-cell', String(n));
          cell.type = 'button';
          cell.dataset.guideSeason = entry.number === null ? '' : String(entry.number);
          cell.dataset.guideEpisode = String(n);
          const isWatched = watched !== null && position <= watched;
          cell.setAttribute('aria-pressed', String(isWatched));
          if (watched !== null && position === watched) cell.classList.add('episode-cell--latest');
          cell.setAttribute('aria-label', `${entry.number === null ? 'Episode' : `Season ${entry.number}, episode`} ${n}${isWatched ? ', watched' : ''}`);
          cell.disabled = busy;
          grid.appendChild(cell);
        }
        block.appendChild(grid);
        body.appendChild(block);
        offset += entry.episodes;
      });
    }
    const source = make('p', 'progress-dialog__hint episode-dialog__source');
    if (layout?.source && typeof layout.source_url === 'string' && layout.source_url.startsWith('https://')) {
      source.append('Episode list from ');
      const link = make('a', '', layout.source);
      link.href = layout.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      source.append(link, layout.source === 'TVmaze' ? ' (CC BY-SA). ' : '. ');
    } else if (seasons.length) {
      source.append('Based on the episode count saved with this title. ');
    }
    source.append('Your place in a show is private and never changes its rating, review or finished status.');
    body.appendChild(source);
  }
  // Offer phone/desktop notifications for new episodes while the show is unfinished and this device is off.
  function pushState() {
    try { return window.omniPush && typeof window.omniPush.state === 'function' ? window.omniPush.state() : undefined; } catch (_) { return undefined; }
  }
  function appendPushOffer(body, progress) {
    if (!progress || progress.percent === 100 || !progress.next) return;
    const state = pushState();
    if (state === undefined) return;
    if (state === null) {
      // Not checked yet on this page: ask, then draw the offer once if this device turns out to be off.
      const current = guide;
      Promise.resolve(window.omniPush.refresh()).then(() => { if (guide === current && pushState() === 'off') renderGuide(); }).catch(() => {});
      return;
    }
    if (state !== 'off') return;
    const offer = make('p', 'progress-dialog__hint episode-dialog__push');
    offer.dataset.episodePush = 'true';
    const button = make('button', 'episode-dialog__push-btn', 'Get a notification when a new episode is out');
    button.type = 'button';
    button.dataset.guidePush = 'true';
    offer.append(button, make('span', '', ' On this device, even when OmniTrackr is closed. Turn it off any time from the bell.'));
    body.appendChild(offer);
  }
  async function offerPush(button) {
    const offer = button.closest?.('[data-episode-push]') || button;
    button.disabled = true;
    let state;
    try { state = await window.omniPush.turnOn(); } catch (_) { state = 'off'; }
    const says = {
      on: 'Done. New episodes of your shows will show up on this device.',
      blocked: 'Notifications are blocked for OmniTrackr in this browser’s settings.',
    }[state];
    if (says) offer.replaceChildren(make('span', '', says));
    else if (state === 'install') { /* the Add to Home Screen steps are open */ }
    else button.disabled = false;
  }
  async function load(statusText) {
    if (!guide) return;
    const current = guide;
    busy = true;
    try {
      const result = await send(current.category, current.id, 'GET', '/episodes');
      if (guide !== current) return;
      if (result.ok) {
        current.data = result.payload;
        current.title = result.payload.title || current.title;
        busy = false;
        renderGuide();
        setStatus(statusText || '');
        refreshNodes(current.category, current.id, current.title, result.payload.episodes);
      } else {
        busy = false;
        setStatus(result.status === 404 ? 'This title is no longer in your library.' : 'The episode guide could not be loaded. Close it and try again.');
      }
    } catch (_) {
      busy = false;
      if (guide === current) setStatus('The episode guide could not be loaded. Check your connection and try again.');
    }
  }
  async function chooseEpisode(cell) {
    if (!guide?.data || busy) return;
    const current = guide;
    const seasons = current.data.layout?.seasons || [];
    const season = (cell.dataset.guideSeason ?? cell.dataset.guideSeasonValue) === '' ? null : Number(cell.dataset.guideSeason ?? cell.dataset.guideSeasonValue);
    const episode = Number(cell.dataset.guideEpisode);
    const at = current.data.episodes?.current;
    const target = absolute(seasons, season, episode);
    const watched = at ? absolute(seasons, at.season, at.episode) : 0;
    let move = [season, episode];
    let clear = false;
    if (!cell.dataset.guideNext && watched !== null && target === watched) {
      const back = target > 1 ? locate(seasons, target - 1) : null;
      if (back) move = back;
      else if (current.data.checkpoint?.note) { setStatus('This is your first episode. Use "Reminder and specials" to clear your place and your reminder together.'); return; }
      else clear = true;
    }
    busy = true;
    renderGuide();
    setStatus('Saving…');
    try {
      const result = clear
        ? await send(current.category, current.id, 'DELETE', '', { expected_revision: current.data.revision })
        : await setEpisode(current.category, current.id, current.title, current.data.revision, move[0], move[1]);
      if (guide !== current) return;
      busy = false;
      if (result.ok) {
        if (clear) afterSave(result.payload);
        const backwards = !clear && watched !== null && absolute(seasons, move[0], move[1]) < watched;
        await load(clear ? 'Cleared your place in this show.'
          : backwards ? `Moved your place back to ${label(move[0], move[1])}. Tap a later episode to undo.`
            : `Watched through ${label(move[0], move[1])}.`);
      } else if (result.status === 409) {
        await load('Your progress changed in another tab or device. This is the latest saved version.');
      } else {
        renderGuide();
        setStatus('That episode could not be saved. Try again in a moment.');
      }
    } catch (_) {
      if (guide !== current) return;
      busy = false;
      renderGuide();
      setStatus('That episode could not be saved. Check your connection and try again.');
    }
  }
  function openGuide(category, id, title, trigger) {
    if (!config || !supported.has(category) || !validId(id) || !sessionKey()) return;
    if (config.canOpen && !config.canOpen()) return;
    buildDialog();
    guide = { category, id, title, data: null };
    opener = trigger || document.activeElement;
    busy = false;
    renderGuide();
    setStatus('');
    if (!dialog.open) dialog.showModal();
    document.getElementById('episodeDialogClose')?.focus();
    load();
  }

  document.addEventListener('click', event => {
    const next = event.target.closest?.('[data-episode-next]');
    if (next && !next.disabled) { event.preventDefault(); quickNext(next); return; }
    const open = event.target.closest?.('[data-episode-guide]');
    if (open) {
      const holder = open.closest('[data-episode-part]');
      openGuide(holder?.dataset.episodeCategory, Number(holder?.dataset.episodeItemId), holder?.dataset.episodeTitle, open);
    }
  });
  window.addEventListener('pagehide', () => { if (dialog?.open) dialog.close(); guide = null; });

  window.OmniEpisodes = {
    configure: options => { config = options; }, appendBar, appendActions, appendRow, open: openGuide,
    describe, label, absolute, locate, previousEpisode, refresh: refreshNodes,
  };
})();
