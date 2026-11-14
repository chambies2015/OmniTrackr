/* Episode tracking for TV shows and anime: progress bars, a one-tap "next episode"
   button and a season-by-season episode guide. Every write goes through the
   existing private progress checkpoint, so a member's place is still one record.
   Ratings and notes on single episodes (Nov 2026) are their own private rows,
   saved through /progress/<kind>/<id>/episode-notes. */
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
  const MODE_KEY = 'omnitrackr.episodeGuideMode';
  const NOTE_MAX = 1000;

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

  function toast(text, undo, extra) {
    let node = document.getElementById('episodeToast');
    if (!node) {
      node = make('div', 'episode-toast');
      node.id = 'episodeToast';
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      document.body.appendChild(node);
    }
    node.replaceChildren(make('span', '', text));
    if (extra) {
      const button = make('button', 'episode-toast__undo episode-toast__extra', extra.label);
      button.type = 'button';
      button.addEventListener('click', () => { node.hidden = true; extra.action(); });
      node.appendChild(button);
    }
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
        const rateIt = { label: 'Rate it', action: () => openGuide(category, id, title, button, { edit: { season, episode } }) };
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
        }, rateIt);
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

  const noteKey = (season, episode) => (season === null || season === undefined ? `e${episode}` : `s${season}e${episode}`);
  const parseSeason = value => (value === '' || value === undefined || value === null ? null : Number(value));
  function readMode() {
    try { return window.localStorage?.getItem(MODE_KEY) === 'rate' ? 'rate' : 'watch'; } catch (_) { return 'watch'; }
  }
  function saveMode(mode) {
    try { window.localStorage?.setItem(MODE_KEY, mode); } catch (_) { /* a remembered tab is only a convenience */ }
  }
  function notesMap(data) {
    const map = new Map();
    (Array.isArray(data?.episode_notes) ? data.episode_notes : []).forEach(entry => {
      if (entry && Number.isInteger(entry.episode)) map.set(noteKey(entry.season, entry.episode), entry);
    });
    return map;
  }
  const average = values => (values.length ? Math.round(10 * values.reduce((a, b) => a + b, 0) / values.length) / 10 : null);
  const formatAverage = value => (Number.isInteger(value) ? String(value) : value.toFixed(1));
  function ratingText(rating) { return `${rating}/10`; }

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
      const target = event.target;
      const cell = target.closest?.('[data-guide-season]');
      if (cell && !cell.disabled) {
        if (guide?.mode === 'rate') openEditor(parseSeason(cell.dataset.guideSeason), Number(cell.dataset.guideEpisode));
        else chooseEpisode(cell);
        return;
      }
      const next = target.closest?.('[data-guide-next]');
      if (next && !next.disabled) { chooseEpisode(next); return; }
      if (target.closest?.('[data-guide-checkpoint]')) { openCheckpoint(); return; }
      const offer = target.closest?.('[data-guide-push]');
      if (offer && !offer.disabled) { offerPush(offer); return; }
      const mode = target.closest?.('[data-guide-mode]');
      if (mode) { setMode(mode.dataset.guideMode); return; }
      const edit = target.closest?.('[data-guide-edit]');
      if (edit && !edit.disabled) { openEditor(parseSeason(edit.dataset.guideEditSeason), Number(edit.dataset.guideEdit)); return; }
      const reveal = target.closest?.('[data-guide-reveal]');
      if (reveal) { guide?.revealed.add(reveal.dataset.guideReveal); guide.focus = `[data-guide-revealed="${reveal.dataset.guideReveal}"]`; renderGuide(); return; }
      if (target.closest?.('[data-guide-back]')) { leaveEditor(); return; }
      const rate = target.closest?.('[data-guide-rate]');
      if (rate && !rate.disabled) { pickRating(rate.dataset.guideRate === '' ? null : Number(rate.dataset.guideRate)); return; }
      const step = target.closest?.('[data-guide-step]');
      if (step && !step.disabled) { stepEditor(Number(step.dataset.guideStep)); return; }
      if (target.closest?.('[data-guide-save]')) { saveDraft('save'); return; }
      if (target.closest?.('[data-guide-remove]')) { removeEntry(); return; }
      const pick = target.closest?.('[data-guide-pick]');
      if (pick) pickFromForm(pick);
    });
    document.body.appendChild(dialog);
    return dialog;
  }
  function setStatus(text) { const node = document.getElementById('episodeDialogStatus'); if (node) node.textContent = text; }
  function closeGuide() {
    flushDraft();
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
  function setMode(mode) {
    if (!guide || (mode !== 'watch' && mode !== 'rate') || guide.mode === mode) return;
    guide.mode = mode;
    saveMode(mode);
    guide.focus = `[data-guide-mode="${mode}"]`;
    renderGuide();
    setStatus(mode === 'rate' ? 'Tap an episode to rate it or write a note.' : 'Tap an episode to mark it and everything before it watched.');
  }
  function applyFocus() {
    if (!guide?.focus || !dialog?.querySelector) return;
    const node = dialog.querySelector(guide.focus);
    guide.focus = null;
    node?.focus?.();
  }

  /* Ratings and notes shown on the guide itself. */
  function entryButton(entry, text) {
    const button = make('button', 'episode-notes__open', text);
    button.type = 'button';
    button.dataset.guideEdit = String(entry.episode);
    button.dataset.guideEditSeason = entry.season === null || entry.season === undefined ? '' : String(entry.season);
    button.setAttribute('aria-label', `Edit your rating and note for ${label(entry.season, entry.episode)}`);
    return button;
  }
  function noteList(entries, heading) {
    const wrap = make('div', 'episode-notes');
    if (heading) wrap.appendChild(make('p', 'episode-notes__heading', heading));
    const list = make('ul', 'episode-notes__list');
    entries.forEach(entry => {
      const item = make('li', 'episode-notes__item');
      const head = make('div', 'episode-notes__head');
      head.appendChild(entryButton(entry, shortLabel(entry.season, entry.episode)));
      if (Number.isInteger(entry.rating)) head.appendChild(make('span', 'episode-notes__score', ratingText(entry.rating)));
      item.appendChild(head);
      if (entry.note) {
        const key = noteKey(entry.season, entry.episode);
        if (entry.spoiler && !guide.revealed.has(key)) {
          const reveal = make('button', 'episode-notes__reveal', 'Spoiler note · show it');
          reveal.type = 'button';
          reveal.dataset.guideReveal = key;
          reveal.setAttribute('aria-label', `Show your spoiler note for ${label(entry.season, entry.episode)}`);
          item.appendChild(reveal);
        } else {
          const text = make('p', 'episode-notes__text', entry.note);
          text.dataset.guideRevealed = key;
          text.tabIndex = -1;
          item.appendChild(text);
        }
      }
      list.appendChild(item);
    });
    wrap.appendChild(list);
    return wrap;
  }
  function favourites(entries) {
    const rated = entries.filter(entry => Number.isInteger(entry.rating));
    if (rated.length < 3) return null;
    const top = rated.slice().sort((a, b) => b.rating - a.rating).slice(0, 3);
    const wrap = make('div', 'episode-favourites');
    wrap.appendChild(make('p', 'episode-notes__heading', 'Your top episodes'));
    const row = make('div', 'episode-favourites__row');
    top.forEach(entry => row.appendChild(entryButton(entry, `${shortLabel(entry.season, entry.episode)} · ${ratingText(entry.rating)}`)));
    wrap.appendChild(row);
    return wrap;
  }
  function modeSwitch() {
    const group = make('div', 'episode-mode');
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', 'What tapping an episode does');
    [['watch', 'Mark watched'], ['rate', 'Rate and note']].forEach(([mode, text]) => {
      const button = make('button', 'episode-mode__option', text);
      button.type = 'button';
      button.dataset.guideMode = mode;
      button.setAttribute('aria-pressed', String(guide.mode === mode));
      group.appendChild(button);
    });
    return group;
  }
  function pickerForm() {
    // Without an episode list there is no grid to tap, so pick by number.
    const form = make('div', 'episode-pick');
    const seasonLabel = make('label', 'episode-pick__field', 'Season');
    const season = make('input');
    season.type = 'number'; season.min = '0'; season.max = '10000'; season.inputMode = 'numeric';
    season.id = 'episodePickSeason';
    season.placeholder = 'Optional';
    seasonLabel.appendChild(season);
    const episodeLabel = make('label', 'episode-pick__field', 'Episode');
    const episode = make('input');
    episode.type = 'number'; episode.min = '1'; episode.max = '1000000'; episode.inputMode = 'numeric';
    episode.id = 'episodePickEpisode';
    episodeLabel.appendChild(episode);
    const go = make('button', '', 'Rate this episode');
    go.type = 'button';
    go.dataset.guidePick = 'true';
    form.append(seasonLabel, episodeLabel, go);
    return form;
  }
  function pickFromForm() {
    const seasonValue = document.getElementById('episodePickSeason')?.value?.trim() ?? '';
    const episodeValue = document.getElementById('episodePickEpisode')?.value?.trim() ?? '';
    const season = seasonValue === '' ? null : Number(seasonValue);
    const episode = Number(episodeValue);
    if ((season !== null && (!Number.isInteger(season) || season < 0 || season > 10000)) || !Number.isInteger(episode) || episode < 1 || episode > 1000000) {
      setStatus('Enter an episode number, and a season number if the show has seasons.');
      return;
    }
    openEditor(season, episode);
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
    if (guide.editing) { renderEditor(body); applyFocus(); return; }
    const { layout, episodes: progress, checkpoint } = guide.data;
    const seasons = Array.isArray(layout?.seasons) ? layout.seasons : [];
    const current = progress?.current;
    const watched = current ? absolute(seasons, current.season, current.episode) : 0;
    const notes = notesMap(guide.data);
    const allEntries = [...notes.values()];
    const placed = new Set();

    const summary = make('div', 'episode-dialog__summary');
    if (Number.isInteger(progress?.percent)) summary.appendChild(bar(progress.percent, guide.title));
    summary.appendChild(make('p', 'episode-dialog__count', describe(progress)));
    const counts = guide.data.episode_note_summary;
    if (counts && (counts.rated || counts.noted)) {
      const parts = [];
      if (counts.rated) parts.push(`You've rated ${counts.rated} episode${counts.rated === 1 ? '' : 's'}${Number.isFinite(counts.average) ? `, ${formatAverage(counts.average)}/10 on average` : ''}`);
      if (counts.noted) parts.push(`${counts.rated ? '' : 'You have '}${counts.noted} note${counts.noted === 1 ? '' : 's'}`);
      summary.appendChild(make('p', 'episode-dialog__ratings', `${parts.join(' · ')}.`));
    }
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
    if (guide.ratePrompt) {
      const { season, episode } = guide.ratePrompt;
      const rated = notes.get(noteKey(season, episode));
      const prompt = make('button', 'episode-dialog__rate-prompt', rated ? `Edit your note on ${shortLabel(season, episode)}` : `Rate ${shortLabel(season, episode)}`);
      prompt.type = 'button';
      prompt.dataset.guideEdit = String(episode);
      prompt.dataset.guideEditSeason = season === null ? '' : String(season);
      actions.appendChild(prompt);
    }
    const edit = make('button', '', 'Reminder and specials');
    edit.type = 'button';
    edit.dataset.guideCheckpoint = 'true';
    actions.appendChild(edit);
    body.appendChild(actions);
    appendPushOffer(body, progress);

    const top = favourites(allEntries);
    if (top) body.appendChild(top);
    body.appendChild(modeSwitch());

    if (!seasons.length) {
      if (guide.mode === 'rate') {
        body.appendChild(make('p', 'progress-dialog__hint', 'There\'s no episode list for this title yet, so pick the episode by number.'));
        body.appendChild(pickerForm());
      } else {
        body.appendChild(make('p', 'progress-dialog__privacy', 'We couldn\'t find an episode list for this title yet. Add its number of episodes when you edit it, and a grid will appear here. The button above still moves you one episode at a time.'));
      }
    } else {
      body.appendChild(make('p', 'progress-dialog__hint', guide.mode === 'rate'
        ? 'Tap an episode to give it a score out of 10 or write a note. Only you can see them.'
        : 'Tap an episode to mark it and everything before it watched. Tap your latest episode again to step back one.'));
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
        const openSeason = guide.openSeasons.has(index);
        block.open = openSeason || (guide.openSeasons.size === 0 && index === currentSeasonIndex) || seasons.length === 1;
        block.dataset.seasonIndex = String(index);
        block.addEventListener?.('toggle', () => { if (block.open) guide?.openSeasons.add(index); else guide?.openSeasons.delete(index); });
        const seen = watched === null ? 0 : Math.max(0, Math.min(entry.episodes, watched - offset));
        const name = entry.number === null ? 'All episodes' : `Season ${entry.number}`;
        const seasonEntries = [];
        for (let n = 1; n <= entry.episodes; n++) {
          const found = notes.get(noteKey(entry.number, n));
          if (found) { seasonEntries.push(found); placed.add(noteKey(entry.number, n)); }
        }
        const scores = seasonEntries.filter(item => Number.isInteger(item.rating)).map(item => item.rating);
        const head = make('summary', 'episode-season__head');
        head.appendChild(make('span', 'episode-season__name', name));
        if (scores.length) {
          const avg = make('span', 'episode-season__avg', `${formatAverage(average(scores))} avg`);
          avg.setAttribute('aria-label', `Your average for ${name}: ${formatAverage(average(scores))} out of 10`);
          head.appendChild(avg);
        }
        head.appendChild(make('span', 'episode-season__count', `${seen} of ${entry.episodes}`));
        block.appendChild(head);
        const grid = make('div', `episode-grid${guide.mode === 'rate' ? ' episode-grid--rate' : ''}`);
        grid.setAttribute('role', 'group');
        grid.setAttribute('aria-label', name);
        for (let n = 1; n <= entry.episodes; n++) {
          const position = offset + n;
          const cell = make('button', 'episode-cell', String(n));
          cell.type = 'button';
          cell.dataset.guideSeason = entry.number === null ? '' : String(entry.number);
          cell.dataset.guideEpisode = String(n);
          const isWatched = watched !== null && position <= watched;
          const saved = notes.get(noteKey(entry.number, n));
          if (guide.mode === 'watch') cell.setAttribute('aria-pressed', String(isWatched));
          else if (isWatched) cell.classList.add('episode-cell--seen');
          if (watched !== null && position === watched) cell.classList.add('episode-cell--latest');
          if (saved && Number.isInteger(saved.rating)) {
            cell.classList.add('episode-cell--rated');
            cell.appendChild(make('span', 'episode-cell__score', String(saved.rating)));
          }
          if (saved?.note) cell.classList.add('episode-cell--noted');
          const what = `${entry.number === null ? 'Episode' : `Season ${entry.number}, episode`} ${n}`;
          const extras = [isWatched ? 'watched' : '', saved && Number.isInteger(saved.rating) ? `you rated it ${saved.rating} out of 10` : '', saved?.note ? 'has a note' : ''].filter(Boolean);
          cell.setAttribute('aria-label', `${guide.mode === 'rate' ? 'Rate ' : ''}${what}${extras.length ? `, ${extras.join(', ')}` : ''}`);
          cell.disabled = busy;
          grid.appendChild(cell);
        }
        block.appendChild(grid);
        const withNotes = seasonEntries.filter(item => item.note);
        if (withNotes.length) block.appendChild(noteList(withNotes, 'Your notes'));
        body.appendChild(block);
        offset += entry.episodes;
      });
    }
    const others = allEntries.filter(entry => !placed.has(noteKey(entry.season, entry.episode)));
    if (others.length) body.appendChild(noteList(others, seasons.length ? 'Specials and other episodes you rated' : 'Episodes you rated'));
    const source = make('p', 'progress-dialog__hint episode-dialog__source');
    if (layout?.source && typeof layout.source_url === 'string' && layout.source_url.startsWith('https://')) {
      source.append('Episode list from ');
      const link = make('a', '', layout.source);
      link.href = layout.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      source.append(link, layout.source === 'TVmaze' ? ' (CC BY-SA). ' : '. ');
    } else if (seasons.length) {
      source.append('Based on the episode count saved with this title. ');
    }
    source.append('Your place in a show and your episode ratings are private. They never change the show\'s own rating, review or finished status.');
    body.appendChild(source);
    applyFocus();
  }

  /* ---------------------------------------------------------------- one episode */

  function draftFor(season, episode) {
    const saved = notesMap(guide.data).get(noteKey(season, episode));
    return { rating: saved?.rating ?? null, note: saved?.note || '', spoiler: Boolean(saved?.spoiler), dirty: false, exists: Boolean(saved) };
  }
  function openEditor(season, episode) {
    if (!guide?.data || busy || !Number.isInteger(episode) || episode < 1) return;
    if (season !== null && (!Number.isInteger(season) || season < 0)) return;
    guide.editing = { season, episode };
    guide.draft = draftFor(season, episode);
    guide.focus = '[data-guide-rate]';
    renderGuide();
    setStatus('');
  }
  async function leaveEditor() {
    if (!guide?.editing) return;
    if (guide.draft?.dirty && !(await saveDraft('leave'))) return;
    const { season, episode } = guide.editing;
    guide.editing = null;
    guide.draft = null;
    guide.focus = `[data-guide-season="${season === null ? '' : season}"][data-guide-episode="${episode}"]`;
    renderGuide();
  }
  function neighbour(step) {
    const { season, episode } = guide.editing;
    const seasons = Array.isArray(guide.data?.layout?.seasons) ? guide.data.layout.seasons : [];
    if (!seasons.length) {
      const target = episode + step;
      return target >= 1 ? [season, target] : null;
    }
    if (continuous(seasons)) {
      if (season !== null && season !== 1) return null;
      const target = episode + step;
      return target >= 1 && target <= seasons[0].episodes ? [season, target] : null;
    }
    if (season === null || season === 0 || !seasons.some(entry => entry.number === season)) return null;
    const index = absolute(seasons, season, episode);
    if (!Number.isInteger(index)) return null;
    return index + step >= 1 ? locate(seasons, index + step) : null;
  }
  async function stepEditor(step) {
    if (!guide?.editing || busy) return;
    const target = neighbour(step);
    if (!target) return;
    if (guide.draft?.dirty && !(await saveDraft('leave'))) return;
    if (!guide?.editing) return;
    guide.editing = { season: target[0], episode: target[1] };
    guide.draft = draftFor(target[0], target[1]);
    guide.focus = `[data-guide-step="${step}"]`;
    renderGuide();
    setStatus(`${label(target[0], target[1])}.`);
  }
  function pickRating(rating) {
    if (!guide?.draft || busy) return;
    guide.draft.rating = guide.draft.rating === rating ? null : rating;
    guide.draft.dirty = true;
    guide.focus = rating === null ? '[data-guide-rate="1"]' : `[data-guide-rate="${rating}"]`;
    saveDraft('rate');
  }
  function payloadFor(editing, draft) {
    const note = draft.note.trim();
    return { season: editing.season, episode: editing.episode, rating: draft.rating, note: note || null, spoiler: Boolean(note) && draft.spoiler };
  }
  async function writeEntry(current, method, body) {
    return send(current.category, current.id, method, '/episode-notes', body);
  }
  /** Save the open episode. Returns true when it was saved (or had nothing to save). */
  async function saveDraft(reason) {
    if (!guide?.editing || !guide.draft || busy) return false;
    const current = guide;
    const editing = { ...current.editing };
    const body = payloadFor(editing, current.draft);
    const removing = body.rating === null && body.note === null;
    if (removing && !current.draft.exists) {
      current.draft.dirty = false;
      if (reason === 'save') setStatus('Pick a score or write a note first.');
      renderGuide();
      return true;
    }
    busy = true;
    setStatus('Saving…');
    try {
      const result = await writeEntry(current, 'PUT', body);
      if (guide !== current) return false;
      busy = false;
      if (!result.ok) {
        renderGuide();
        setStatus(result.status === 404 ? 'This title is no longer in your library.'
          : result.status === 422 ? 'That note could not be saved. Check its length and try again.'
            : 'That could not be saved. Try again in a moment.');
        return false;
      }
      current.data = result.payload;
      current.title = result.payload.title || current.title;
      const still = current.editing && noteKey(current.editing.season, current.editing.episode) === noteKey(editing.season, editing.episode);
      if (still) {
        const keepNote = current.draft.note;
        const typedSince = current.draft.note.trim() !== (body.note || '');
        current.draft = draftFor(editing.season, editing.episode);
        if (typedSince) { current.draft.note = keepNote; current.draft.dirty = true; }
      }
      renderGuide();
      const where = label(editing.season, editing.episode);
      if (removing) setStatus(`Cleared your rating and note for ${where}.`);
      else if (reason === 'rate') setStatus(body.rating === null ? `Took the score off ${where}.` : `Gave ${where} ${ratingText(body.rating)}.`);
      else setStatus(`Saved ${where}.`);
      return true;
    } catch (_) {
      if (guide !== current) return false;
      busy = false;
      renderGuide();
      setStatus('That could not be saved. Check your connection and try again.');
      return false;
    }
  }
  async function removeEntry() {
    if (!guide?.editing || busy) return;
    const current = guide;
    const editing = { ...current.editing };
    busy = true;
    setStatus('Removing…');
    try {
      const result = await writeEntry(current, 'DELETE', { season: editing.season, episode: editing.episode });
      if (guide !== current) return;
      busy = false;
      if (!result.ok) { renderGuide(); setStatus('That could not be removed. Try again in a moment.'); return; }
      current.data = result.payload;
      current.draft = draftFor(editing.season, editing.episode);
      guide.focus = '[data-guide-rate]';
      renderGuide();
      setStatus(`Removed your rating and note for ${label(editing.season, editing.episode)}.`);
    } catch (_) {
      if (guide !== current) return;
      busy = false;
      renderGuide();
      setStatus('That could not be removed. Check your connection and try again.');
    }
  }
  function flushDraft() {
    // Closing the dialog keeps a note the member typed but didn't save.
    if (!guide?.editing || !guide.draft?.dirty || !config) return;
    const current = guide;
    const body = payloadFor(current.editing, current.draft);
    if (body.rating === null && body.note === null && !current.draft.exists) return;
    current.draft.dirty = false;
    const where = label(body.season, body.episode);
    writeEntry(current, 'PUT', body)
      .then(result => toast(result.ok ? `Saved your note on ${where} of ${current.title}.` : `Your note on ${where} could not be saved.`))
      .catch(() => toast(`Your note on ${where} could not be saved. Check your connection.`));
  }

  function renderEditor(body) {
    const { season, episode } = guide.editing;
    const draft = guide.draft;
    const seasons = Array.isArray(guide.data?.layout?.seasons) ? guide.data.layout.seasons : [];
    const current = guide.data.episodes?.current;
    const here = absolute(seasons, season, episode);
    const watchedUpTo = current ? absolute(seasons, current.season, current.episode) : 0;

    const top = make('div', 'episode-editor__top');
    const back = make('button', 'episode-editor__back', '‹ All episodes');
    back.type = 'button';
    back.dataset.guideBack = 'true';
    back.disabled = busy;
    top.appendChild(back);
    const nav = make('div', 'episode-editor__nav');
    [[-1, '‹', 'Previous episode'], [1, '›', 'Next episode']].forEach(([step, glyph, name]) => {
      const target = neighbour(step);
      const button = make('button', 'episode-editor__step', target ? (step < 0 ? `${glyph} ${shortLabel(target[0], target[1])}` : `${shortLabel(target[0], target[1])} ${glyph}`) : glyph);
      button.type = 'button';
      button.dataset.guideStep = String(step);
      button.disabled = busy || !target;
      button.setAttribute('aria-label', target ? `${name}: ${label(target[0], target[1])}` : `No ${name.toLowerCase()}`);
      nav.appendChild(button);
    });
    top.appendChild(nav);
    body.appendChild(top);

    const heading = make('h3', 'episode-editor__title', label(season, episode));
    heading.id = 'episodeEditorTitle';
    body.appendChild(heading);
    if (Number.isInteger(here) && Number.isInteger(watchedUpTo)) {
      body.appendChild(make('p', 'progress-dialog__hint episode-editor__seen', here <= watchedUpTo ? 'You\'ve watched this one.' : 'You haven\'t marked this one watched yet.'));
    }

    const scoreLabel = make('p', 'episode-editor__label', 'Your score');
    scoreLabel.id = 'episodeEditorScoreLabel';
    body.appendChild(scoreLabel);
    const scores = make('div', 'episode-rate');
    scores.setAttribute('role', 'group');
    scores.setAttribute('aria-labelledby', 'episodeEditorScoreLabel');
    for (let n = 1; n <= 10; n++) {
      const chip = make('button', 'episode-rate__chip', String(n));
      chip.type = 'button';
      chip.dataset.guideRate = String(n);
      chip.setAttribute('aria-pressed', String(draft.rating === n));
      chip.setAttribute('aria-label', `${n} out of 10`);
      chip.disabled = busy;
      scores.appendChild(chip);
    }
    body.appendChild(scores);
    const scoreHint = make('p', 'progress-dialog__hint episode-rate__hint', draft.rating === null
      ? 'Tap a number to score it. It saves right away.'
      : `You gave it ${ratingText(draft.rating)}. Tap the same number again to take the score off.`);
    body.appendChild(scoreHint);

    const noteLabel = make('label', 'episode-editor__note');
    noteLabel.append('Your note');
    const area = make('textarea');
    area.id = 'episodeEditorNote';
    area.maxLength = NOTE_MAX;
    area.rows = 4;
    area.placeholder = 'A line you loved, a theory, who you watched it with…';
    area.value = draft.note;
    area.disabled = busy;
    const counter = make('span', 'episode-editor__counter', `${draft.note.length}/${NOTE_MAX}`);
    counter.setAttribute('aria-live', 'off');
    area.addEventListener?.('input', () => {
      if (!guide?.draft) return;
      guide.draft.note = area.value.slice(0, NOTE_MAX);
      guide.draft.dirty = true;
      counter.textContent = `${guide.draft.note.length}/${NOTE_MAX}`;
    });
    noteLabel.append(area, counter);
    body.appendChild(noteLabel);

    const spoilerLabel = make('label', 'episode-editor__spoiler');
    const box = make('input');
    box.type = 'checkbox';
    box.id = 'episodeEditorSpoiler';
    box.checked = draft.spoiler;
    box.disabled = busy;
    box.addEventListener?.('change', () => { if (guide?.draft) { guide.draft.spoiler = box.checked; guide.draft.dirty = true; } });
    spoilerLabel.append(box, make('span', '', 'It has spoilers. Keep it hidden in the list until I tap it.'));
    body.appendChild(spoilerLabel);

    const actions = make('div', 'episode-dialog__actions episode-editor__actions');
    const save = make('button', 'progress-dialog__save', 'Save note');
    save.type = 'button';
    save.dataset.guideSave = 'true';
    save.disabled = busy;
    actions.appendChild(save);
    if (draft.exists) {
      const remove = make('button', 'episode-editor__remove', 'Remove score and note');
      remove.type = 'button';
      remove.dataset.guideRemove = 'true';
      remove.disabled = busy;
      actions.appendChild(remove);
    }
    body.appendChild(actions);
    body.appendChild(make('p', 'progress-dialog__hint episode-dialog__source', 'Only you can see your episode scores and notes. They\'re kept with your backup when you export your library.'));
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
        if (current.pendingEdit) {
          const { season, episode } = current.pendingEdit;
          current.pendingEdit = null;
          openEditor(season, episode);
        } else {
          renderGuide();
        }
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
        // After moving forward, offer to score the episode just watched.
        current.ratePrompt = !clear && !backwards ? { season: move[0], episode: move[1] } : null;
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
  /** options.edit = { season, episode } opens straight onto that episode's score and note. */
  function openGuide(category, id, title, trigger, options = {}) {
    if (!config || !supported.has(category) || !validId(id) || !sessionKey()) return;
    if (config.canOpen && !config.canOpen()) return;
    if (guide) flushDraft();
    buildDialog();
    const edit = options?.edit && Number.isInteger(options.edit.episode) ? { season: options.edit.season ?? null, episode: options.edit.episode } : null;
    guide = { category, id, title, data: null, mode: readMode(), editing: null, draft: null, pendingEdit: edit,
      ratePrompt: null, revealed: new Set(), openSeasons: new Set(), focus: null };
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
  window.addEventListener('pagehide', () => { flushDraft(); if (dialog?.open) dialog.close(); guide = null; });

  window.OmniEpisodes = {
    configure: options => { config = options; }, appendBar, appendActions, appendRow, open: openGuide,
    rate: (category, id, title, season, episode, trigger) => openGuide(category, id, title, trigger, { edit: { season, episode } }),
    describe, label, absolute, locate, previousEpisode, refresh: refreshNodes, noteKey,
  };
})();
