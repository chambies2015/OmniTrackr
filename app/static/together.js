// Watch together (/together, /together/<id>, /together/join/<token>): one title, a weekly pace,
// everyone's place on one track, and notes that stay folded until you reach them.
// Everything a member typed is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  const KIND_TO_CATEGORY = { tv: 'tv-shows', anime: 'anime', book: 'books', manga: 'manga', podcast: 'podcasts',
    audiobook: 'audiobooks' };
  const CATEGORY_UNIT = { 'tv-shows': 'episode', anime: 'episode', podcasts: 'episode', books: 'chapter',
    manga: 'chapter', audiobooks: 'chapter' };
  const CATEGORY_LABEL = { 'tv-shows': 'TV show', anime: 'Anime', books: 'Book', manga: 'Manga', podcasts: 'Podcast',
    audiobooks: 'Audiobook' };
  const PACES = { episode: [1, 2, 3, 4, 7], chapter: [2, 3, 5, 7, 10] };
  const CELLS_MAX = 60;
  const DAY = 86400000;

  // ------------------------------------------------------------------ pure helpers (also used by tests)

  function plural(n, one, many) { return `${n} ${n === 1 ? one : many || `${one}s`}`; }

  function weeksFor(total, pace) {
    if (!(total > 0) || !(pace > 0)) return 0;
    return Math.ceil(total / pace);
  }

  function parseDay(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    if (!match) return null;
    const when = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return Number.isNaN(when.getTime()) ? null : when;
  }

  function isoDay(when) {
    const pad = n => String(n).padStart(2, '0');
    return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`;
  }

  function shortDay(when) {
    return when ? when.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }) : '';
  }

  function nextMonday(today) {
    const when = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const add = ((8 - when.getDay()) % 7) || 7;
    when.setDate(when.getDate() + add);
    return when;
  }

  // "10 episodes, 2 a week: 5 weeks, last week starts Mon, Dec 15."
  function planSummary(total, pace, unit, startIso) {
    const weeks = weeksFor(total, pace);
    if (!weeks) return '';
    const start = parseDay(startIso);
    let tail = '';
    if (start) {
      const end = new Date(start.getTime());
      end.setDate(end.getDate() + weeks * 7 - 1);
      tail = `, ending ${shortDay(end)}`;
    }
    return `${plural(total, unit)}, ${pace} a week: ${plural(weeks, 'week')}${tail}.`;
  }

  // Seasons to offer for a show: [{value, label, episodes}] from the episode guide's layout.
  function seasonChoices(layout) {
    const seasons = layout && Array.isArray(layout.seasons) ? layout.seasons : [];
    return seasons.filter(entry => Number.isInteger(entry.episodes) && entry.episodes > 0).map(entry => ({
      value: Number.isInteger(entry.number) ? entry.number : null,
      label: Number.isInteger(entry.number) ? `Season ${entry.number} (${plural(entry.episodes, 'episode')})`
        : `All of it (${plural(entry.episodes, 'episode')})`,
      episodes: entry.episodes,
    }));
  }

  // Where a library checkpoint puts the member in a season (mirrors together.placed on the server).
  function placeFor(at, season, total, unit) {
    if (!at || at.unit !== unit || !Number.isInteger(at.position)) return 0;
    if (unit === 'episode' && season) {
      if (Number.isInteger(at.season) && at.season !== 0) {
        if (at.season > season) return total;
        if (at.season < season) return 0;
      }
    } else if (unit === 'episode' && ![null, undefined, 0, 1].includes(at.season)) {
      return 0;
    }
    return Math.max(0, Math.min(total, at.position));
  }

  // Cells for the track: one per part, grouped by week, with who is where and which notes wait.
  function trackWeeks(plan) {
    const pins = new Map();
    (plan.notes || []).forEach(note => { if (note.part > 0) pins.set(note.part, 'open'); });
    (plan.locked || []).forEach(group => { if (group.part > 0 && !pins.has(group.part)) pins.set(group.part, 'locked'); });
    const here = new Map();
    (plan.people || []).forEach(person => {
      const list = here.get(person.position) || [];
      list.push(person);
      here.set(person.position, list);
    });
    return (plan.weeks || []).map(week => {
      const cells = [];
      for (let part = week.first; part <= week.last; part += 1) {
        cells.push({ part, pin: pins.get(part) || null, people: here.get(part) || [],
          done: part <= ((plan.you && plan.you.position) || 0) });
      }
      return { number: week.number, state: week.state, label: week.label, cells };
    });
  }

  function shareLinks(url, text) {
    const line = `${text} ${url}`;
    return [
      ['WhatsApp', `https://wa.me/?text=${encodeURIComponent(line)}`],
      ['Text message', `sms:?&body=${encodeURIComponent(line)}`],
      ['Email', `mailto:?subject=${encodeURIComponent(text)}&body=${encodeURIComponent(line)}`],
    ];
  }

  const helpers = { weeksFor, planSummary, seasonChoices, placeFor, trackWeeks, nextMonday, isoDay, shareLinks };
  if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ page helpers

  const root = document.getElementById('togetherApp');
  const reported = new Set();
  function report(event) {
    if (reported.has(event)) return;
    reported.add(event);
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  }
  document.addEventListener('click', event => {
    if (event.target.closest && event.target.closest('[data-together-signup]')) report('together_signup_clicked');
  });
  if (!root) return;

  const tz = () => -new Date().getTimezoneOffset();

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(text, className, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  async function api(path, options = {}) {
    const joiner = path.includes('?') ? '&' : '?';
    const init = { method: options.method || 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(`${path}${joiner}tz=${tz()}`, init);
    if (response.status === 401) {
      window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#login`;
      throw new Error('Please log in again.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0] && data.detail[0].msg : data.detail;
      if (response.status === 429 && !detail) throw new Error('Slow down a little and try again in a minute.');
      throw new Error(String(detail || 'Something went wrong. Please try again.').replace(/^Value error, /, ''));
    }
    return data;
  }

  function art(item, className) {
    const frame = el('span', className || 'tg-art');
    const fallback = () => frame.replaceChildren(el('span', 'tg-art__empty', (item.title || '?').slice(0, 1).toUpperCase()));
    if (typeof item.image === 'string' && /^https:\/\//.test(item.image)) {
      const image = el('img');
      image.src = item.image;
      image.alt = '';
      image.loading = 'lazy';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', fallback);
      frame.appendChild(image);
    } else {
      fallback();
    }
    return frame;
  }

  function avatar(person, extra) {
    const node = el('span', `tg-avatar${person.you ? ' tg-avatar--you' : ''}${extra ? ` ${extra}` : ''}`, person.initials);
    node.title = person.you ? 'You' : person.username;
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  function status(node, text, tone) {
    if (!node) return;
    node.textContent = text || '';
    node.dataset.tone = tone || '';
  }

  async function copyLink(url, buttonNode, statusNode) {
    try {
      await navigator.clipboard.writeText(url);
      const label = buttonNode.textContent;
      buttonNode.textContent = 'Link copied ✓';
      setTimeout(() => { buttonNode.textContent = label; }, 2200);
    } catch (error) {
      status(statusNode, `Copy this link: ${url}`);
    }
  }

  function shareRow(url, text, statusNode) {
    const row = el('div', 'tg-share');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', 'Send the invite link');
    if (navigator.share) {
      const native = button('Send the link', 'button tg-share__main', async () => {
        report('together_shared');
        try {
          await navigator.share({ title: text, text, url });
        } catch (error) {
          if (!error || error.name !== 'AbortError') copyLink(url, native, statusNode);
        }
      });
      row.appendChild(native);
    }
    const copy = button('Copy link', navigator.share ? 'tg-pill' : 'button tg-share__main', () => {
      report('together_shared');
      copyLink(url, copy, statusNode);
    });
    row.appendChild(copy);
    shareLinks(url, text).forEach(([label, href]) => {
      const link = el('a', 'tg-pill', label);
      link.href = href;
      if (href.startsWith('https://')) {
        link.target = '_blank';
        link.rel = 'noopener';
      }
      link.addEventListener('click', () => report('together_shared'));
      row.appendChild(link);
    });
    return row;
  }

  function miniTrack(card) {
    const track = el('div', 'tg-mini');
    track.setAttribute('aria-hidden', 'true');
    const total = Math.max(1, card.total || 1);
    if (card.week_last) {
      const mark = el('span', 'tg-mini__week');
      mark.style.setProperty('--tg-at', `${Math.round(100 * card.week_last / total)}%`);
      track.appendChild(mark);
    }
    (card.people || []).forEach((person, index) => {
      const dot = avatar(person, 'tg-mini__dot');
      dot.style.setProperty('--tg-at', `${Math.round(100 * person.position / total)}%`);
      dot.style.setProperty('--tg-lift', `${(index % 3) * 4}px`);
      track.appendChild(dot);
    });
    return track;
  }

  // ------------------------------------------------------------------ hub: your plans and starting one

  function planCard(card) {
    const item = el('li', 'tg-card');
    const link = el('a', 'tg-card__link');
    link.href = card.path;
    link.appendChild(art(card, 'tg-art tg-art--card'));
    const text = el('span', 'tg-card__text');
    text.appendChild(el('strong', 'tg-card__title', card.title));
    text.appendChild(el('small', 'tg-card__meta', [card.scope, card.pace_label, card.with].filter(Boolean).join(' · ')));
    const week = card.started ? (card.this_week ? `Week ${card.week} of ${card.weeks_total} · ${card.this_week}` : 'Past the last week')
      : 'Not started yet';
    text.appendChild(el('small', 'tg-card__week', week));
    text.appendChild(el('span', 'tg-card__headline', card.headline));
    link.appendChild(text);
    item.appendChild(link);
    item.appendChild(miniTrack(card));
    const badges = el('p', 'tg-card__badges');
    if (card.unread) badges.appendChild(el('span', 'tg-badge tg-badge--new', `${plural(card.unread, 'new note')}`));
    if (card.waiting) badges.appendChild(el('span', 'tg-badge', `${plural(card.waiting, 'note')} ahead of you`));
    if (badges.childNodes.length) item.appendChild(badges);
    return item;
  }

  async function hubView() {
    const mineNode = root.querySelector('[data-together-mine]');
    const startNode = root.querySelector('[data-together-start]');
    try {
      const data = await api('/api/together');
      mineNode.replaceChildren();
      if (!data.running.length) {
        mineNode.appendChild(el('p', 'tg-muted', 'Nothing running yet. Start one below, then send the link to whoever '
          + 'you\'re watching or reading with.'));
      } else {
        const list = el('ul', 'tg-cards');
        data.running.forEach(card => list.appendChild(planCard(card)));
        mineNode.appendChild(list);
      }
      if (data.ended.length) {
        const done = el('details', 'tg-ended');
        done.appendChild(el('summary', null, `Finished (${data.ended.length})`));
        const list = el('ul', 'tg-ended__list');
        data.ended.forEach(entry => {
          const row = el('li');
          const link = el('a', null, entry.title);
          link.href = entry.path;
          row.appendChild(link);
          row.appendChild(el('small', null, [entry.label, entry.scope].filter(Boolean).join(' · ')));
          list.appendChild(row);
        });
        done.appendChild(list);
        mineNode.appendChild(done);
      }
    } catch (error) {
      status(mineNode, error.message, 'error');
    }
    startForm(startNode);
  }

  async function startForm(node) {
    let data;
    try {
      data = await api('/api/together/titles');
    } catch (error) {
      status(node, error.message, 'error');
      return;
    }
    if (data.active >= data.active_max) {
      node.replaceChildren(el('p', 'tg-muted', `You're in ${data.active_max} plans, which is the most at once. `
        + 'Finish or leave one to start another.'));
      return;
    }
    const chosen = { item: null };
    const form = el('form', 'tg-form');
    form.noValidate = true;
    const pickStep = el('fieldset', 'tg-step');
    pickStep.appendChild(el('legend', null, '1. Pick a title'));
    const grid = el('ul', 'tg-picks');
    const pickButtons = [];
    function choose(item, node) {
      chosen.item = item;
      pickButtons.forEach(other => other.setAttribute('aria-pressed', String(other === node)));
      details.hidden = false;
      fillDetails(item);
    }
    data.titles.slice(0, 18).forEach(item => {
      const row = el('li');
      const pick = button('', 'tg-pick');
      pick.setAttribute('aria-pressed', 'false');
      pick.appendChild(art(item, 'tg-art tg-art--small'));
      const text = el('span', 'tg-pick__text');
      text.appendChild(el('strong', null, item.title));
      const where = item.at && item.at.position ? ` · on ${item.at.unit} ${item.at.position}` : '';
      text.appendChild(el('small', null, `${item.label}${where}`));
      pick.appendChild(text);
      pick.addEventListener('click', () => choose(item, pick));
      pickButtons.push(pick);
      row.appendChild(pick);
      grid.appendChild(row);
    });
    if (data.titles.length) {
      pickStep.appendChild(el('p', 'tg-hint', 'From your library, the ones you\'re in the middle of first.'));
      pickStep.appendChild(grid);
    } else {
      pickStep.appendChild(el('p', 'tg-hint', 'Your library has no shows, anime, books, manga, podcasts or audiobooks '
        + 'on the go yet. Search for one instead.'));
    }
    // Search, or type a title in.
    const searchLabel = el('label', null, 'Or search for anything');
    searchLabel.htmlFor = 'tgSearch';
    const search = el('input');
    search.id = 'tgSearch';
    search.type = 'search';
    search.maxLength = 80;
    search.autocomplete = 'off';
    search.placeholder = 'A show, anime, book, manga, podcast or audiobook';
    const results = el('ul', 'tg-picks tg-picks--results');
    results.hidden = true;
    let searchTimer = null;
    search.addEventListener('input', () => {
      clearTimeout(searchTimer);
      const query = search.value.trim();
      if (query.length < 2) {
        results.hidden = true;
        return;
      }
      searchTimer = setTimeout(async () => {
        try {
          const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query.slice(0, 80))}`, { credentials: 'same-origin' });
          const found = (await response.json()).results || [];
          results.replaceChildren();
          found.filter(result => KIND_TO_CATEGORY[result.kind]).slice(0, 8).forEach(result => {
            const item = { kind: result.kind, category: KIND_TO_CATEGORY[result.kind], title: result.title,
              year: result.year, image: result.image, label: result.label, unit: CATEGORY_UNIT[KIND_TO_CATEGORY[result.kind]],
              total: null, at: null, slug: result.slug };
            const row = el('li');
            const pick = button('', 'tg-pick');
            pick.setAttribute('aria-pressed', 'false');
            pick.appendChild(art(item, 'tg-art tg-art--small'));
            const text = el('span', 'tg-pick__text');
            text.appendChild(el('strong', null, item.title));
            text.appendChild(el('small', null, [item.label, item.year].filter(Boolean).join(' · ')));
            pick.appendChild(text);
            pick.addEventListener('click', () => choose(item, pick));
            pickButtons.push(pick);
            row.appendChild(pick);
            results.appendChild(row);
          });
          if (!results.childNodes.length) {
            results.appendChild(el('li', 'tg-hint', 'Nothing found. Type it in below instead.'));
          }
          results.hidden = false;
        } catch (error) {
          results.hidden = true;
        }
      }, 250);
    });
    pickStep.appendChild(searchLabel);
    pickStep.appendChild(search);
    pickStep.appendChild(results);
    const typed = el('details', 'tg-typed');
    typed.appendChild(el('summary', null, 'Not there? Type it in'));
    const typedRow = el('div', 'tg-row');
    const kindSelect = el('select');
    kindSelect.setAttribute('aria-label', 'What it is');
    Object.entries(KIND_TO_CATEGORY).forEach(([kind, category]) => {
      const option = el('option', null, CATEGORY_LABEL[category]);
      option.value = kind;
      kindSelect.appendChild(option);
    });
    const typedTitle = el('input');
    typedTitle.type = 'text';
    typedTitle.maxLength = 200;
    typedTitle.placeholder = 'Title';
    typedTitle.setAttribute('aria-label', 'Title');
    const typedGo = button('Use this', 'tg-pill', () => {
      const title = typedTitle.value.replace(/\s+/g, ' ').trim();
      if (!title) return;
      const category = KIND_TO_CATEGORY[kindSelect.value];
      choose({ kind: kindSelect.value, category, title, year: null, image: null, label: CATEGORY_LABEL[category],
        unit: CATEGORY_UNIT[category], total: null, at: null }, typedGo);
    });
    typedRow.append(kindSelect, typedTitle, typedGo);
    typed.appendChild(typedRow);
    pickStep.appendChild(typed);
    form.appendChild(pickStep);

    // Step two: length, pace, start, friends.
    const details = el('fieldset', 'tg-step');
    details.hidden = true;
    details.appendChild(el('legend', null, '2. Set the pace'));
    const chosenLine = el('p', 'tg-chosen');
    details.appendChild(chosenLine);
    const seasonWrap = el('div', 'tg-field');
    const seasonLabel = el('label', null, 'Which season');
    seasonLabel.htmlFor = 'tgSeason';
    const seasonSelect = el('select');
    seasonSelect.id = 'tgSeason';
    seasonWrap.append(seasonLabel, seasonSelect);
    const seasonNumberWrap = el('div', 'tg-field');
    const seasonNumberLabel = el('label', null, 'Season (leave empty for the whole thing)');
    seasonNumberLabel.htmlFor = 'tgSeasonNumber';
    const seasonNumber = el('input');
    seasonNumber.id = 'tgSeasonNumber';
    seasonNumber.type = 'number';
    seasonNumber.min = '1';
    seasonNumber.max = '200';
    seasonNumber.inputMode = 'numeric';
    seasonNumberWrap.append(seasonNumberLabel, seasonNumber);
    const totalWrap = el('div', 'tg-field');
    const totalLabel = el('label', null, 'How many episodes');
    totalLabel.htmlFor = 'tgTotal';
    const totalInput = el('input');
    totalInput.id = 'tgTotal';
    totalInput.type = 'number';
    totalInput.min = '1';
    totalInput.max = String(data.total_max || 1000);
    totalInput.inputMode = 'numeric';
    totalInput.required = true;
    totalWrap.append(totalLabel, totalInput);
    const paceWrap = el('div', 'tg-field');
    const paceLabel = el('p', 'tg-label', 'How many a week');
    const paceRow = el('div', 'tg-chips');
    paceRow.setAttribute('role', 'group');
    paceRow.setAttribute('aria-label', 'How many a week');
    const paceInput = el('input');
    paceInput.type = 'number';
    paceInput.min = '1';
    paceInput.inputMode = 'numeric';
    paceInput.value = '2';
    paceInput.setAttribute('aria-label', 'Or type a number');
    paceInput.className = 'tg-chips__input';
    paceWrap.append(paceLabel, paceRow);
    const startWrap = el('div', 'tg-field');
    const startLabel = el('p', 'tg-label', 'Start');
    const startRow = el('div', 'tg-chips');
    startRow.setAttribute('role', 'group');
    startRow.setAttribute('aria-label', 'When to start');
    const today = new Date();
    const monday = nextMonday(today);
    const startDate = el('input');
    startDate.type = 'date';
    startDate.min = isoDay(today);
    startDate.max = isoDay(new Date(today.getTime() + (data.start_within_days || 60) * DAY));
    startDate.value = isoDay(today);
    startDate.setAttribute('aria-label', 'Start date');
    startDate.className = 'tg-chips__input';
    const startChoices = [['Today', isoDay(today)], [`Next Monday (${monday.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })})`, isoDay(monday)]];
    startChoices.forEach(([label, value]) => {
      const chip = button(label, 'tg-chip', () => {
        startDate.value = value;
        syncChips();
        summarize();
      });
      chip.dataset.value = value;
      startRow.appendChild(chip);
    });
    startRow.appendChild(startDate);
    startWrap.append(startLabel, startRow);
    const atWrap = el('div', 'tg-field');
    const atLabel = el('label', null, 'Where are you now');
    atLabel.htmlFor = 'tgAt';
    const atInput = el('input');
    atInput.id = 'tgAt';
    atInput.type = 'number';
    atInput.min = '0';
    atInput.value = '0';
    atInput.inputMode = 'numeric';
    const atHint = el('p', 'tg-hint', '0 means you haven\'t started.');
    atWrap.append(atLabel, atInput, atHint);
    const summary = el('p', 'tg-summary');
    summary.setAttribute('aria-live', 'polite');
    details.append(seasonWrap, seasonNumberWrap, totalWrap, paceWrap, startWrap, atWrap, summary);

    const extra = el('fieldset', 'tg-step');
    extra.hidden = true;
    extra.appendChild(el('legend', null, '3. Who\'s in'));
    extra.appendChild(el('p', 'tg-hint', 'You get an invite link to send once it\'s made. Friends on OmniTrackr can be '
      + 'asked in right away.'));
    const friendBoxes = [];
    if (data.friends.length) {
      const list = el('div', 'tg-friends');
      data.friends.forEach(friend => {
        const label = el('label', 'tg-check');
        const box = el('input');
        box.type = 'checkbox';
        box.value = String(friend.id);
        friendBoxes.push(box);
        label.append(box, document.createTextNode(` ${friend.username}`));
        list.appendChild(label);
      });
      extra.appendChild(list);
    }
    const emailLabel = el('label', 'tg-check');
    const emailBox = el('input');
    emailBox.type = 'checkbox';
    emailBox.checked = true;
    emailLabel.append(emailBox, document.createTextNode(' Email me once a week if I fall behind while I\'m away'));
    extra.appendChild(emailLabel);
    const submit = el('button', 'button tg-form__go', 'Start the plan');
    submit.type = 'submit';
    const formStatus = el('p', 'tg-status');
    formStatus.setAttribute('role', 'status');
    extra.append(submit, formStatus);
    form.append(details, extra);
    node.replaceChildren(form);

    let seasonLayout = [];
    function unit() { return chosen.item ? chosen.item.unit : 'episode'; }

    function drawPaces() {
      paceRow.replaceChildren();
      (PACES[unit()] || PACES.episode).forEach(value => {
        const chip = button(String(value), 'tg-chip', () => {
          paceInput.value = String(value);
          syncChips();
          summarize();
        });
        chip.dataset.pace = String(value);
        paceRow.appendChild(chip);
      });
      paceRow.appendChild(paceInput);
    }

    function syncChips() {
      paceRow.querySelectorAll('[data-pace]').forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.pace === paceInput.value)));
      startRow.querySelectorAll('[data-value]').forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.value === startDate.value)));
    }

    function currentSeason() {
      if (!seasonWrap.hidden) {
        const value = seasonSelect.value;
        return value ? Number(value) : null;
      }
      if (!seasonNumberWrap.hidden && seasonNumber.value) return Number(seasonNumber.value);
      return null;
    }

    function syncAt() {
      const item = chosen.item;
      const total = Number(totalInput.value) || 0;
      atInput.max = String(total || 1000);
      const at = placeFor(item && item.at, currentSeason(), total, unit());
      atInput.value = String(at);
      atHint.textContent = at ? `From your library: ${unit()} ${at}. 0 means you haven't started.`
        : '0 means you haven\'t started.';
    }

    function summarize() {
      const total = Number(totalInput.value);
      const pace = Number(paceInput.value);
      paceInput.max = String(total || 1000);
      summary.textContent = total > 0 && pace > 0 && pace <= total ? planSummary(total, pace, unit(), startDate.value) : '';
    }

    async function fillDetails(item) {
      chosenLine.replaceChildren(art(item, 'tg-art tg-art--small'));
      const words = el('span');
      words.appendChild(el('strong', null, item.title));
      words.appendChild(el('small', null, [item.label, item.year].filter(Boolean).join(' · ')));
      chosenLine.appendChild(words);
      extra.hidden = false;
      totalLabel.textContent = `How many ${unit()}s`;
      atLabel.textContent = 'Where are you now';
      drawPaces();
      paceInput.value = unit() === 'chapter' ? '3' : '2';
      seasonWrap.hidden = true;
      seasonNumberWrap.hidden = !(item.category === 'tv-shows' || item.category === 'anime');
      seasonNumber.value = item.category === 'tv-shows' ? '1' : '';
      totalInput.value = item.total ? String(item.total) : '';
      seasonLayout = [];
      if ((item.category === 'tv-shows' || item.category === 'anime') && item.item_id) {
        try {
          const guide = await api(`/progress/${item.category}/${item.item_id}/episodes`);
          if (chosen.item !== item) return;
          seasonLayout = seasonChoices(guide.layout);
        } catch (error) { seasonLayout = []; }
      }
      if (seasonLayout.length) {
        seasonSelect.replaceChildren();
        seasonLayout.forEach(choice => {
          const option = el('option', null, choice.label);
          option.value = choice.value === null ? '' : String(choice.value);
          option.dataset.episodes = String(choice.episodes);
          seasonSelect.appendChild(option);
        });
        const at = item.at && item.at.unit === 'episode' && Number.isInteger(item.at.season) ? String(item.at.season) : null;
        if (at && seasonLayout.some(choice => String(choice.value) === at)) seasonSelect.value = at;
        seasonWrap.hidden = false;
        seasonNumberWrap.hidden = true;
        totalInput.value = seasonSelect.selectedOptions[0] ? seasonSelect.selectedOptions[0].dataset.episodes : '';
      }
      syncAt();
      syncChips();
      summarize();
      totalInput.focus();
    }

    seasonSelect.addEventListener('change', () => {
      const option = seasonSelect.selectedOptions[0];
      if (option) totalInput.value = option.dataset.episodes;
      syncAt();
      summarize();
    });
    seasonNumber.addEventListener('input', () => { syncAt(); });
    totalInput.addEventListener('input', () => { syncAt(); summarize(); });
    paceInput.addEventListener('input', () => { syncChips(); summarize(); });
    startDate.addEventListener('change', () => { syncChips(); summarize(); });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const item = chosen.item;
      if (!item) {
        status(formStatus, 'Pick a title first.', 'error');
        return;
      }
      const total = Number(totalInput.value);
      const pace = Number(paceInput.value);
      if (!(total >= 1)) {
        status(formStatus, `Say how many ${unit()}s it has.`, 'error');
        totalInput.focus();
        return;
      }
      if (!(pace >= 1) || pace > total) {
        status(formStatus, 'Pick how many to do each week, no more than the whole thing.', 'error');
        return;
      }
      const body = { total, pace, starts_on: startDate.value, position: Math.max(0, Math.min(total, Number(atInput.value) || 0)),
        remind_email: emailBox.checked, friend_ids: friendBoxes.filter(box => box.checked).map(box => Number(box.value)) };
      const season = currentSeason();
      if (season) body.season = season;
      if (item.item_id) {
        body.category = item.category;
        body.item_id = item.item_id;
      } else {
        Object.assign(body, { kind: item.kind, title: item.title, year: item.year || null, image: item.image || null });
      }
      submit.disabled = true;
      status(formStatus, 'Starting it…');
      try {
        const made = await api('/api/together', { method: 'POST', body });
        window.location.href = `${made.path}?new=1`;
      } catch (error) {
        submit.disabled = false;
        status(formStatus, error.message, 'error');
      }
    });
  }

  // ------------------------------------------------------------------ one plan

  function planView() {
    const id = root.dataset.planId;
    const holder = root.querySelector('[data-together-plan]');
    const headlineNode = root.querySelector('[data-together-headline]');
    const fresh = new URLSearchParams(window.location.search).get('new') === '1';
    let plan = null;
    let busy = false;
    let friendsLoaded = false;
    const view = { noteOpen: false, inviteOpen: fresh };

    async function load() {
      try {
        plan = await api(`/api/together/${id}`);
        draw();
      } catch (error) {
        status(holder, error.message, 'error');
      }
    }

    async function act(path, options, statusNode, after) {
      if (busy) return null;
      busy = true;
      try {
        const data = await api(path, options);
        if (data && data.id) plan = data;
        draw();
        if (after) after(data);
        return data;
      } catch (error) {
        status(statusNode || holder.querySelector('[data-together-status]'), error.message, 'error');
        return null;
      } finally {
        busy = false;
      }
    }

    function unitWord(n) { return n === 1 ? plan.unit : plan.unit_plural; }

    function partLabel(part) { return part <= 0 ? 'Before you start' : `${plan.unit[0].toUpperCase()}${plan.unit.slice(1)} ${part}`; }

    function drawTrack() {
      const section = el('section', 'tg-track');
      section.setAttribute('aria-labelledby', 'tgTrackTitle');
      const head = el('div', 'tg-track__head');
      const title = el('h2', null, plan.started ? (plan.this_week ? `Week ${plan.this_week.number} of ${plan.weeks_total}` : 'The last week is over')
        : `Starts ${plan.starts_label}`);
      title.id = 'tgTrackTitle';
      head.appendChild(title);
      head.appendChild(el('p', 'tg-track__sub', plan.this_week && plan.started
        ? `This week: ${plan.this_week.label}. Ends ${plan.ends_label}.`
        : `${plan.pace_label}, ${plural(plan.weeks_total, 'week')}. Ends ${plan.ends_label}.`));
      section.appendChild(head);
      if (plan.total <= CELLS_MAX) {
        const weeks = el('ol', 'tg-weeks');
        weeks.setAttribute('aria-label', 'The plan, week by week');
        trackWeeks(plan).forEach(week => {
          const item = el('li', `tg-week tg-week--${week.state}`);
          item.appendChild(el('span', 'tg-week__label', `Week ${week.number}`));
          const cells = el('ol', 'tg-cells');
          week.cells.forEach(cell => {
            const node = el('li', `tg-cell${cell.done ? ' tg-cell--done' : ''}`);
            node.appendChild(el('span', 'tg-cell__n', cell.part));
            if (cell.pin) {
              const pin = el('span', `tg-pin${cell.pin === 'locked' ? ' tg-pin--locked' : ''}`);
              pin.setAttribute('aria-hidden', 'true');
              node.appendChild(pin);
            }
            if (cell.people.length) {
              const who = el('span', 'tg-cell__who');
              cell.people.slice(0, 3).forEach(person => who.appendChild(avatar(person)));
              node.appendChild(who);
            }
            const words = [`${partLabel(cell.part)}`];
            if (cell.people.length) words.push(cell.people.map(person => (person.you ? 'you' : person.username)).join(', ') + ' here');
            if (cell.pin === 'locked') words.push('a note waits here');
            if (cell.pin === 'open') words.push('notes here');
            node.setAttribute('aria-label', words.join(', '));
            cells.appendChild(node);
          });
          item.appendChild(cells);
          weeks.appendChild(item);
        });
        section.appendChild(weeks);
      }
      const people = el('ul', 'tg-people');
      plan.people.forEach(person => {
        const row = el('li', `tg-person tg-person--${person.status}`);
        row.appendChild(avatar(person));
        const text = el('span', 'tg-person__text');
        text.appendChild(el('strong', null, person.you ? 'You' : person.username));
        const where = person.position >= plan.total ? 'Finished' : person.position === 0 ? 'Not started'
          : partLabel(person.position);
        const words = { finished: 'finished', waiting: '', ahead: 'ahead', done: 'done for the week', on: '',
          behind: 'catching up' }[person.status];
        text.appendChild(el('small', null, [where, person.position < plan.total ? words : '', person.owner ? 'runs it' : '']
          .filter(Boolean).join(' · ')));
        row.appendChild(text);
        const bar = el('span', 'tg-bar');
        bar.setAttribute('aria-hidden', 'true');
        const fill = el('span');
        fill.style.setProperty('--tg-share', `${Math.round(100 * person.position / Math.max(1, plan.total))}%`);
        bar.appendChild(fill);
        row.appendChild(bar);
        if (plan.you.owner && !person.you) {
          const remove = button('Take out', 'tg-link-button tg-link-button--quiet', () => {
            if (remove.dataset.armed !== '1') {
              remove.dataset.armed = '1';
              remove.textContent = `Take ${person.username} out?`;
              return;
            }
            act(`/api/together/${id}/members/${person.member_id}`, { method: 'DELETE' });
          });
          row.appendChild(remove);
        }
        people.appendChild(row);
      });
      section.appendChild(people);
      return section;
    }

    function drawMove() {
      const you = plan.you;
      const section = el('section', 'tg-move');
      section.setAttribute('aria-labelledby', 'tgMoveTitle');
      const heading = el('h2', null, 'Where are you?');
      heading.id = 'tgMoveTitle';
      section.appendChild(heading);
      const moveStatus = el('p', 'tg-status');
      moveStatus.setAttribute('role', 'status');
      moveStatus.dataset.togetherStatus = '';
      if (plan.ended) {
        section.appendChild(el('p', 'tg-muted', 'This plan has wrapped up, so places stay where they are.'));
      } else if (you.position < plan.total) {
        const next = you.position + 1;
        const verbs = { 'tv-shows': 'Watched', anime: 'Watched', podcasts: 'Listened to' };
        const go = button(`${verbs[plan.category] || 'Finished'} ${plan.unit} ${next}`, 'button tg-move__next', () => {
          move(next, moveStatus);
        });
        section.appendChild(go);
      } else {
        section.appendChild(el('p', 'tg-move__done', 'You reached the end.'));
      }
      const stepper = el('div', 'tg-stepper');
      const label = el('label', null, `Or set your ${plan.unit}`);
      label.htmlFor = 'tgPosition';
      const input = el('input');
      input.id = 'tgPosition';
      input.type = 'number';
      input.min = '0';
      input.max = String(plan.total);
      input.value = String(you.position);
      input.inputMode = 'numeric';
      input.disabled = plan.ended;
      const save = button('Save', 'tg-pill', () => move(Math.max(0, Math.min(plan.total, Number(input.value) || 0)), moveStatus));
      save.disabled = plan.ended;
      stepper.append(label, input, el('span', 'tg-muted', `of ${plan.total}`), save);
      section.appendChild(stepper);
      if (you.linked) {
        const follow = el('label', 'tg-check');
        const box = el('input');
        box.type = 'checkbox';
        box.checked = you.follow_library;
        box.addEventListener('change', () => act(`/api/together/${id}/me`, { method: 'PATCH', body: { follow_library: box.checked } }, moveStatus));
        follow.append(box, document.createTextNode(' Keep this in step with my library'));
        section.appendChild(follow);
        section.appendChild(el('p', 'tg-hint', you.follow_library
          ? 'Episodes and chapters you log in your library move you here, and moving forward here moves your library forward. It never moves your library back.'
          : 'Your library and this plan move separately.'));
      }
      if (you.position >= plan.total && you.linked && !you.library_done) {
        const finish = el('div', 'tg-finish');
        finish.appendChild(el('p', null, 'Tick it off in your library?'));
        const score = el('select');
        score.setAttribute('aria-label', 'Your score, optional');
        const none = el('option', null, 'No score');
        none.value = '';
        score.appendChild(none);
        for (let value = 10; value >= 1; value -= 1) {
          const option = el('option', null, `${value}/10`);
          option.value = String(value);
          score.appendChild(option);
        }
        const done = button('Mark it finished', 'tg-pill', () => act(`/api/together/${id}/finish`, {
          method: 'POST', body: { rating: score.value ? Number(score.value) : null } }, moveStatus, () => {
          status(moveStatus, 'Ticked off in your library.', 'ok');
        }));
        finish.append(score, done);
        section.appendChild(finish);
      }
      section.appendChild(moveStatus);
      return section;
    }

    async function move(position, statusNode) {
      const before = plan.you.position;
      const data = await act(`/api/together/${id}/position`, { method: 'PUT', body: { position, library: true } }, statusNode);
      if (!data) return;
      const words = [];
      if (data.opened) words.push(`${plural(data.opened, 'note')} opened.`);
      if (data.library_saved) words.push('Your library moved too.');
      if (!words.length && position > before) words.push('Saved.');
      status(root.querySelector('.tg-move [data-together-status]'), words.join(' '), 'ok');
      if (data.opened) {
        const notes = root.querySelector('#notes');
        if (notes) notes.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function drawNotes() {
      const section = el('section', 'tg-notes');
      section.id = 'notes';
      section.setAttribute('aria-labelledby', 'tgNotesTitle');
      const heading = el('h2', null, 'Notes');
      heading.id = 'tgNotesTitle';
      section.appendChild(heading);
      section.appendChild(el('p', 'tg-hint', `A note sits at an ${plan.unit}. Everyone who has reached that ${plan.unit} can read it. Nobody behind you sees yours until they get there.`));
      const groups = new Map();
      plan.notes.forEach(note => {
        const list = groups.get(note.part) || [];
        list.push(note);
        groups.set(note.part, list);
      });
      const locked = new Map(plan.locked.map(group => [group.part, group]));
      const parts = [...new Set([...groups.keys(), ...locked.keys()])].sort((a, b) => a - b);
      if (!parts.length) {
        section.appendChild(el('p', 'tg-muted', 'No notes yet. Leave the first one where you are.'));
      }
      const list = el('ol', 'tg-note-groups');
      parts.forEach(part => {
        const item = el('li', 'tg-note-group');
        item.appendChild(el('h3', 'tg-note-group__part', partLabel(part)));
        (groups.get(part) || []).forEach(note => {
          const card = el('article', `tg-note${note.you ? ' tg-note--you' : ''}${note.new ? ' tg-note--new' : ''}`);
          const top = el('p', 'tg-note__top');
          top.appendChild(avatar({ initials: note.initials, you: note.you, username: note.author }));
          top.appendChild(el('strong', null, note.you ? 'You' : note.author));
          if (note.new) top.appendChild(el('span', 'tg-badge tg-badge--new', 'New'));
          card.appendChild(top);
          card.appendChild(el('p', 'tg-note__body', note.body));
          if (note.can_delete) {
            const remove = button('Delete', 'tg-link-button tg-link-button--quiet', () => {
              if (remove.dataset.armed !== '1') {
                remove.dataset.armed = '1';
                remove.textContent = 'Delete this note?';
                return;
              }
              act(`/api/together/${id}/notes/${note.id}`, { method: 'DELETE' });
            });
            card.appendChild(remove);
          }
          item.appendChild(card);
        });
        const waiting = locked.get(part);
        if (waiting) {
          const card = el('p', 'tg-note tg-note--locked');
          const pin = el('span', 'tg-pin tg-pin--locked');
          pin.setAttribute('aria-hidden', 'true');
          card.appendChild(pin);
          card.appendChild(document.createTextNode(` ${waiting.authors.join(' and ')} left ${waiting.count === 1 ? 'a note' : `${waiting.count} notes`} here. `
            + `It opens when you reach ${plan.unit} ${part}.`));
          item.appendChild(card);
        }
        list.appendChild(item);
      });
      section.appendChild(list);
      // Writing one.
      const form = el('form', 'tg-note-form');
      const label = el('label', null, 'Leave a note');
      label.htmlFor = 'tgNoteBody';
      const where = el('select');
      where.setAttribute('aria-label', `Which ${plan.unit}`);
      for (let part = plan.you.position; part >= 0; part -= 1) {
        const option = el('option', null, part === 0 ? 'Before we start' : `At ${plan.unit} ${part}`);
        option.value = String(part);
        where.appendChild(option);
        if (plan.you.position - part >= 40 && part > 0) {
          const first = el('option', null, 'Before we start');
          first.value = '0';
          where.appendChild(first);
          break;
        }
      }
      const body = el('textarea');
      body.id = 'tgNoteBody';
      body.maxLength = plan.note_max;
      body.rows = 3;
      body.placeholder = plan.you.position ? `What did you think of ${plan.unit} ${plan.you.position}?` : 'Can\'t wait to start this.';
      const counter = el('span', 'tg-counter', `0/${plan.note_max}`);
      body.addEventListener('input', () => { counter.textContent = `${body.value.length}/${plan.note_max}`; });
      const send = el('button', 'tg-pill tg-pill--primary', 'Post note');
      send.type = 'submit';
      const noteStatus = el('p', 'tg-status');
      noteStatus.setAttribute('role', 'status');
      const row = el('div', 'tg-row');
      row.append(where, counter, send);
      form.append(label, body, row, noteStatus);
      form.addEventListener('submit', async event => {
        event.preventDefault();
        if (!body.value.trim()) {
          status(noteStatus, 'Write something first.', 'error');
          return;
        }
        const data = await act(`/api/together/${id}/notes`, { method: 'POST', body: { part: Number(where.value), body: body.value } }, noteStatus);
        if (data) {
          const again = root.querySelector('#tgNoteBody');
          if (again) again.focus();
        }
      });
      section.appendChild(form);
      return section;
    }

    function drawInvite() {
      const section = el('details', 'tg-invite-box');
      section.open = view.inviteOpen || plan.people.length < 2;
      section.addEventListener('toggle', () => { view.inviteOpen = section.open; });
      section.appendChild(el('summary', null, plan.people.length < 2 ? 'Ask someone in' : 'Invite more people'));
      const inviteStatus = el('p', 'tg-status');
      inviteStatus.setAttribute('role', 'status');
      if (plan.ended) {
        section.appendChild(el('p', 'tg-muted', 'This plan has finished, so nobody new can join.'));
        return section;
      }
      if (plan.people.length >= plan.members_max) {
        section.appendChild(el('p', 'tg-muted', `It's full: ${plan.members_max} people is the most.`));
        return section;
      }
      section.appendChild(el('p', 'tg-hint', 'Anyone with the link can join, with or without an account. They see the '
        + 'title and the pace, never your notes, until they\'re in.'));
      const field = el('input', 'tg-invite-box__url');
      field.type = 'text';
      field.readOnly = true;
      field.value = plan.invite_url;
      field.setAttribute('aria-label', 'Invite link');
      field.addEventListener('focus', () => field.select());
      section.appendChild(field);
      section.appendChild(shareRow(plan.invite_url, `${plan.verb} ${plan.title} with me, ${plan.pace_label}?`, inviteStatus));
      const friends = el('div', 'tg-friends');
      section.appendChild(friends);
      const ask = button('Ask friends on OmniTrackr', 'tg-link-button', async () => {
        ask.disabled = true;
        try {
          const data = await api(`/api/together/${id}/friends`);
          friends.replaceChildren();
          if (!data.friends.length) {
            friends.appendChild(el('p', 'tg-muted', 'All your friends are in already, or you haven\'t added any yet.'));
            return;
          }
          const boxes = [];
          data.friends.forEach(friend => {
            const label = el('label', 'tg-check');
            const box = el('input');
            box.type = 'checkbox';
            box.value = String(friend.id);
            boxes.push(box);
            label.append(box, document.createTextNode(` ${friend.username}`));
            friends.appendChild(label);
          });
          const send = button('Send', 'tg-pill tg-pill--primary', async () => {
            const ids = boxes.filter(box => box.checked).map(box => Number(box.value));
            if (!ids.length) return;
            try {
              const result = await api(`/api/together/${id}/invite`, { method: 'POST', body: { friend_ids: ids } });
              status(inviteStatus, result.asked ? `Asked ${plural(result.asked, 'friend')}.` : 'They\'ve been asked already.', 'ok');
              friends.replaceChildren();
            } catch (error) {
              status(inviteStatus, error.message, 'error');
            }
          });
          friends.appendChild(send);
        } catch (error) {
          status(inviteStatus, error.message, 'error');
        } finally {
          ask.disabled = false;
        }
      });
      if (!friendsLoaded) section.appendChild(ask);
      section.appendChild(inviteStatus);
      return section;
    }

    function drawSettings() {
      const section = el('details', 'tg-settings');
      section.appendChild(el('summary', null, 'Plan settings'));
      const settingsStatus = el('p', 'tg-status');
      settingsStatus.setAttribute('role', 'status');
      const email = el('label', 'tg-check');
      const box = el('input');
      box.type = 'checkbox';
      box.checked = plan.you.remind_email;
      box.addEventListener('change', () => act(`/api/together/${id}/me`, { method: 'PATCH', body: { remind_email: box.checked } },
        settingsStatus, () => status(settingsStatus, box.checked ? 'Weekly email on.' : 'Weekly email off.', 'ok')));
      email.append(box, document.createTextNode(' Email me once a week if I fall behind while I\'m away'));
      section.appendChild(email);
      if (plan.you.owner && !plan.ended) {
        const pace = el('div', 'tg-row');
        const label = el('label', null, `${plan.unit_plural[0].toUpperCase()}${plan.unit_plural.slice(1)} a week`);
        label.htmlFor = 'tgPace';
        const input = el('input');
        input.id = 'tgPace';
        input.type = 'number';
        input.min = '1';
        input.max = String(plan.total);
        input.value = String(plan.pace);
        const save = button('Change the pace', 'tg-pill', () => act(`/api/together/${id}`, {
          method: 'PATCH', body: { pace: Number(input.value) } }, settingsStatus, () => status(settingsStatus, 'Pace changed for everyone.', 'ok')));
        pace.append(label, input, save);
        section.appendChild(pace);
        const relink = button('Make a new invite link', 'tg-link-button', async () => {
          if (relink.dataset.armed !== '1') {
            relink.dataset.armed = '1';
            relink.textContent = 'The old link stops working. Make a new one?';
            return;
          }
          try {
            const data = await api(`/api/together/${id}/link`, { method: 'POST' });
            plan.invite_url = data.invite_url;
            draw();
          } catch (error) {
            status(settingsStatus, error.message, 'error');
          }
        });
        section.appendChild(relink);
        const end = button('Wrap it up for everyone', 'tg-link-button tg-link-button--danger', () => {
          if (end.dataset.armed !== '1') {
            end.dataset.armed = '1';
            end.textContent = 'Places stop moving and it moves to Finished. Wrap it up?';
            return;
          }
          act(`/api/together/${id}/end`, { method: 'POST' }, settingsStatus);
        });
        section.appendChild(end);
      }
      const leave = button('Leave this plan', 'tg-link-button tg-link-button--danger', async () => {
        if (leave.dataset.armed !== '1') {
          leave.dataset.armed = '1';
          leave.textContent = plan.people.length > 1 ? 'Your notes go with you. Leave?' : 'You\'re the only one, so the plan goes too. Leave?';
          return;
        }
        try {
          await api(`/api/together/${id}/leave`, { method: 'POST' });
          window.location.href = '/together';
        } catch (error) {
          status(settingsStatus, error.message, 'error');
        }
      });
      section.appendChild(leave);
      section.appendChild(settingsStatus);
      return section;
    }

    function draw() {
      if (!plan) return;
      if (headlineNode) headlineNode.textContent = [plan.with, plan.headline].filter(Boolean).join('. ').replace(/^with/, 'With');
      const active = document.activeElement;
      const typing = active && active.id === 'tgNoteBody' ? active.value : null;
      const layout = el('div', 'tg-plan__grid');
      const main = el('div', 'tg-plan__main');
      main.append(drawTrack(), drawMove(), drawNotes());
      const side = el('div', 'tg-plan__side');
      side.append(drawInvite(), drawSettings());
      layout.append(main, side);
      holder.replaceChildren(layout);
      if (typing) {
        const body = root.querySelector('#tgNoteBody');
        if (body) {
          body.value = typing;
          body.focus();
        }
      }
      if (window.location.hash === '#notes' && !view.scrolled) {
        view.scrolled = true;
        const notes = root.querySelector('#notes');
        if (notes) notes.scrollIntoView({ block: 'start' });
      }
    }

    load();
    // Places and notes change while the page is open: check now and then while it's on screen.
    setInterval(() => {
      if (busy || document.hidden || !plan) return;
      const active = document.activeElement;
      if (active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT' || active.tagName === 'SELECT')) return;
      load();
    }, 45000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden && plan) load(); });
  }

  // ------------------------------------------------------------------ joining

  async function joinView() {
    const box = root.querySelector('[data-together-join]');
    const statusNode = root.querySelector('[data-together-status]');
    if (!box) return;
    let info;
    try {
      info = await api(`/api/together/join/${encodeURIComponent(box.dataset.token)}`);
    } catch (error) {
      status(box, error.message, 'error');
      return;
    }
    if (info.member && info.path) {
      window.location.href = info.path;
      return;
    }
    const form = el('form', 'tg-join__form');
    const label = el('label', null, `Where are you now? (${info.unit} 0 to ${info.total})`);
    label.htmlFor = 'tgJoinAt';
    const input = el('input');
    input.id = 'tgJoinAt';
    input.type = 'number';
    input.min = '0';
    input.max = String(info.total);
    input.value = String(info.library_at || 0);
    input.inputMode = 'numeric';
    form.append(label, input);
    form.appendChild(el('p', 'tg-hint', info.library_at ? `Your library says ${info.unit} ${info.library_at}.`
      : '0 means you haven\'t started.'));
    let addBox = null;
    if (!info.in_library) {
      const add = el('label', 'tg-check');
      addBox = el('input');
      addBox.type = 'checkbox';
      addBox.checked = true;
      add.append(addBox, document.createTextNode(' Add it to my library too'));
      form.appendChild(add);
    }
    const email = el('label', 'tg-check');
    const emailBox = el('input');
    emailBox.type = 'checkbox';
    emailBox.checked = true;
    email.append(emailBox, document.createTextNode(' Email me once a week if I fall behind while I\'m away'));
    form.appendChild(email);
    const go = el('button', 'button', `Join ${info.title}`);
    go.type = 'submit';
    form.appendChild(go);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      go.disabled = true;
      status(statusNode, 'Joining…');
      try {
        const result = await api(`/api/together/join/${encodeURIComponent(box.dataset.token)}`, { method: 'POST', body: {
          position: Math.max(0, Math.min(info.total, Number(input.value) || 0)),
          add_to_library: addBox ? addBox.checked : true, remind_email: emailBox.checked } });
        window.location.href = result.path;
      } catch (error) {
        go.disabled = false;
        status(statusNode, error.message, 'error');
      }
    });
    box.replaceChildren(form);
  }

  if (root.dataset.view === 'hub') hubView();
  else if (root.dataset.view === 'plan') planView();
  else if (root.dataset.view === 'join') joinView();
}());
