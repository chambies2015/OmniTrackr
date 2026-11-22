// Pick swap (/swap, /swap/<id>, /swap/join/<token>): Secret Santa where everyone gives one recommendation.
// Draw names, pick one title for the person you drew with a note on why, and open everything on unwrap day.
// Everything a member typed is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  const KINDS = ['movie', 'tv', 'anime', 'game', 'album', 'book', 'manga', 'podcast', 'audiobook'];
  const KIND_LABEL = { movie: 'Film', tv: 'TV show', anime: 'Anime', game: 'Game', album: 'Album', book: 'Book',
    manga: 'Manga', podcast: 'Podcast', audiobook: 'Audiobook' };
  const KIND_PLURAL = { movie: 'films', tv: 'shows', anime: 'anime', game: 'games', album: 'albums', book: 'books',
    manga: 'manga', podcast: 'podcasts', audiobook: 'audiobooks' };
  const DAY = 86400000;

  // ------------------------------------------------------------------ pure helpers (also used by tests)

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

  function addDays(iso, days) {
    const when = parseDay(iso);
    if (!when) return '';
    when.setDate(when.getDate() + days);
    return isoDay(when);
  }

  // "Films, shows or anime" for a list of kinds; anything for none or all nine.
  function kindsLabel(kinds) {
    const chosen = KINDS.filter(kind => (kinds || []).includes(kind));
    if (!chosen.length || chosen.length === KINDS.length) return 'Anything: films, shows, books, games, music and more';
    const words = chosen.map(kind => KIND_PLURAL[kind]);
    const text = words.length === 1 ? words[0] : `${words.slice(0, -1).join(', ')} or ${words[words.length - 1]}`;
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function daysWords(days) {
    const n = Number(days);
    if (!Number.isFinite(n)) return '';
    if (n <= 0) return 'Unwrap day is today';
    if (n === 1) return '1 day to unwrap day';
    return `${n} days to unwrap day`;
  }

  // Only same-site paths a swap can point at.
  function safePath(path) {
    return typeof path === 'string' && /^\/(?:swap(?:\/\d{1,10})?|titles\/[a-z]+\/[a-z0-9-]{1,140})$/.test(path) ? path : '/swap';
  }

  function safeImage(url) {
    return typeof url === 'string' && /^https:\/\//.test(url) && url.length <= 500 ? url : '';
  }

  // Search results this swap can take: allowed kinds only, at most eight.
  function allowedResults(results, kinds) {
    const allowed = Array.isArray(kinds) && kinds.length ? new Set(kinds) : null;
    return (Array.isArray(results) ? results : [])
      .filter(result => result && KIND_LABEL[result.kind] && (!allowed || allowed.has(result.kind)))
      .slice(0, 8);
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = { parseDay, isoDay, addDays, kindsLabel, daysWords, safePath, safeImage, allowedResults };
    return;
  }

  const root = document.getElementById('swapApp');
  const reported = new Set();
  function report(event) {
    if (reported.has(event) || !navigator.sendBeacon) return;
    reported.add(event);
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  }
  document.addEventListener('click', event => {
    if (event.target.closest && event.target.closest('[data-swap-signup]')) report('swap_signup_clicked');
  });
  if (!root) return;

  const tz = () => -new Date().getTimezoneOffset();
  const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

  function field(labelText, input, hint) {
    const wrap = el('div', 'ps-field');
    const label = el('label', null, labelText);
    if (!input.id) input.id = `ps${Math.random().toString(36).slice(2, 9)}`;
    label.htmlFor = input.id;
    wrap.appendChild(label);
    if (hint) wrap.appendChild(el('p', 'ps-hint', hint));
    wrap.appendChild(input);
    return wrap;
  }

  function input(type, options = {}) {
    const node = el(type === 'textarea' ? 'textarea' : 'input');
    if (type !== 'textarea') node.type = type;
    Object.entries(options).forEach(([key, value]) => {
      if (value !== undefined && value !== null) node[key] = value;
    });
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
    const frame = el('span', className || 'ps-art');
    const fallback = () => frame.replaceChildren(el('span', 'ps-art__empty', (item.title || '?').slice(0, 1).toUpperCase()));
    const src = safeImage(item.image);
    if (src) {
      const image = el('img');
      image.src = src;
      image.alt = '';
      image.loading = 'lazy';
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', fallback, { once: true });
      frame.appendChild(image);
    } else {
      fallback();
    }
    return frame;
  }

  function avatar(person) {
    const node = el('span', `ps-avatar${person.you ? ' ps-avatar--you' : ''}`, String(person.initials || '?').slice(0, 2));
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  function statusLine() {
    let node = root.querySelector('[data-swap-status]');
    if (!node) {
      node = el('p', 'ps-status');
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      node.dataset.swapStatus = '';
      root.appendChild(node);
    }
    return node;
  }

  function say(text, tone) {
    const node = statusLine();
    node.textContent = text || '';
    if (tone) node.dataset.tone = tone; else delete node.dataset.tone;
  }

  // Two taps for anything that can't be undone: the first asks, the second does it.
  function confirmButton(text, question, yes, className, action) {
    const wrap = el('div', 'ps-confirm');
    const first = button(text, className || 'ps-link-button');
    first.addEventListener('click', () => {
      wrap.replaceChildren();
      wrap.appendChild(el('p', 'ps-confirm__ask', question));
      const row = el('div', 'ps-row');
      const go = button(yes, 'ps-pill ps-pill--primary', async () => {
        go.disabled = true;
        try { await action(); } catch (error) { say(error.message, 'error'); go.disabled = false; }
      });
      row.appendChild(go);
      row.appendChild(button('Not now', 'ps-pill', () => { wrap.replaceChildren(first); first.focus(); }));
      wrap.appendChild(row);
      go.focus();
    });
    wrap.appendChild(first);
    return wrap;
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      return false;
    }
  }

  // ------------------------------------------------------------------ the invite box

  function inviteBox(swap, fresh) {
    const box = el('section', `ps-card ps-share${fresh ? ' ps-share--fresh' : ''}`);
    box.id = 'invite';
    box.setAttribute('aria-labelledby', 'psShareTitle');
    const heading = el('h2', null, fresh ? 'Your swap is ready. Send the link.' : 'Send the link');
    heading.id = 'psShareTitle';
    box.appendChild(heading);
    box.appendChild(el('p', 'ps-hint', 'Post it in the group chat or send it one by one. Anyone with the link can join '
      + 'until names are drawn. New people make a free account and come straight back here.'));
    const row = el('div', 'ps-share__row');
    const link = input('text', { value: swap.invite_url || '', readOnly: true, id: 'psInviteLink' });
    link.setAttribute('aria-label', 'Invite link');
    link.addEventListener('focus', () => link.select());
    row.appendChild(link);
    const copy = button('Copy link', 'ps-pill ps-pill--primary', async () => {
      const ok = await copyText(swap.invite_url);
      if (!ok) { link.focus(); link.select(); }
      say(ok ? 'Link copied. Paste it wherever your people are.' : 'Select the link and copy it.');
      report('swap_shared');
    });
    row.appendChild(copy);
    if (navigator.share) {
      row.appendChild(button('Share…', 'ps-pill', async () => {
        try {
          await navigator.share({ title: swap.name, text: `Join ${swap.name}, a pick swap. Unwrap day is ${swap.reveal_label}.`,
            url: swap.invite_url });
          report('swap_shared');
        } catch (error) { /* closed the share sheet */ }
      }));
    }
    box.appendChild(row);
    const friends = el('details', 'ps-friends');
    friends.appendChild(el('summary', null, 'Ask friends on OmniTrackr'));
    const list = el('div', 'ps-friends__list');
    list.appendChild(el('p', 'ps-muted', 'Loading your friends…'));
    friends.appendChild(list);
    let loaded = false;
    friends.addEventListener('toggle', async () => {
      if (!friends.open || loaded) return;
      loaded = true;
      try {
        const data = await api(`/api/swaps/${swap.id}/friends`);
        list.replaceChildren();
        if (!data.friends.length) {
          list.appendChild(el('p', 'ps-muted', 'Everyone on your friends list is in already, or you haven\'t added friends yet.'));
          return;
        }
        const chosen = new Set();
        data.friends.forEach(friend => {
          const label = el('label', 'ps-check');
          const box2 = input('checkbox');
          box2.addEventListener('change', () => { if (box2.checked) chosen.add(friend.id); else chosen.delete(friend.id); });
          label.appendChild(box2);
          label.appendChild(document.createTextNode(friend.username));
          list.appendChild(label);
        });
        const send = button('Ask them', 'ps-pill', async () => {
          if (!chosen.size) { say('Tick at least one friend.'); return; }
          send.disabled = true;
          try {
            const result = await api(`/api/swaps/${swap.id}/invite`, { method: 'POST', body: { friend_ids: [...chosen] } });
            say(result.asked ? `Asked ${result.asked === 1 ? '1 friend' : `${result.asked} friends`}. They'll see it in their notifications.`
              : 'They were asked recently, so nobody new got a note.');
          } catch (error) { say(error.message, 'error'); }
          send.disabled = false;
        });
        list.appendChild(send);
      } catch (error) {
        list.replaceChildren(el('p', 'ps-muted', error.message));
      }
    });
    box.appendChild(friends);
    return box;
  }

  // ------------------------------------------------------------------ hub: your swaps + start form

  async function loadMine() {
    const holder = root.querySelector('[data-swap-mine]');
    if (!holder) return;
    try {
      const data = await api('/api/swaps');
      holder.replaceChildren();
      if (!data.swaps.length) {
        holder.appendChild(el('p', 'ps-muted', 'You\'re not in a swap yet. Start one below, or ask a friend for the link to theirs.'));
        return;
      }
      const list = el('ul', 'ps-list');
      data.swaps.forEach(swap => {
        const item = el('li', `ps-list__item${swap.urgent ? ' ps-list__item--urgent' : ''}`);
        const box = el('span', `ps-mini-box ps-mini-box--${swap.state}`);
        box.setAttribute('aria-hidden', 'true');
        item.appendChild(box);
        const copy = el('div', 'ps-list__copy');
        const name = el('a', 'ps-list__name', swap.name);
        name.href = safePath(swap.path);
        copy.appendChild(name);
        copy.appendChild(el('p', 'ps-list__line', swap.line));
        item.appendChild(copy);
        if (swap.action) {
          const go = el('a', `ps-pill${swap.urgent ? ' ps-pill--primary' : ''}`, swap.action.label);
          go.href = safePath(swap.action.path);
          item.appendChild(go);
        }
        list.appendChild(item);
      });
      holder.appendChild(list);
    } catch (error) {
      holder.replaceChildren(el('p', 'ps-muted', error.message));
    }
  }

  function kindChips(selected, onChange) {
    const wrap = el('div', 'ps-kinds');
    const anything = el('label', 'ps-check');
    const anyBox = input('checkbox', { checked: !selected.size });
    anything.appendChild(anyBox);
    anything.appendChild(document.createTextNode('Anything goes'));
    wrap.appendChild(anything);
    const chips = el('div', 'ps-chips');
    chips.setAttribute('role', 'group');
    chips.setAttribute('aria-label', 'Formats a pick can be');
    const buttons = KINDS.map(kind => {
      const chip = button(KIND_PLURAL[kind].charAt(0).toUpperCase() + KIND_PLURAL[kind].slice(1), 'ps-chip');
      chip.setAttribute('aria-pressed', String(selected.has(kind)));
      chip.addEventListener('click', () => {
        if (selected.has(kind)) selected.delete(kind); else selected.add(kind);
        if (selected.size === KINDS.length) selected.clear();
        sync();
        onChange();
      });
      chips.appendChild(chip);
      return [kind, chip];
    });
    function sync() {
      anyBox.checked = !selected.size;
      chips.hidden = !selected.size && anyBox.checked && !wrap.dataset.open;
      buttons.forEach(([kind, chip]) => chip.setAttribute('aria-pressed', String(selected.has(kind))));
    }
    anyBox.addEventListener('change', () => {
      if (anyBox.checked) { selected.clear(); delete wrap.dataset.open; } else { wrap.dataset.open = '1'; }
      sync();
      onChange();
    });
    wrap.appendChild(chips);
    wrap.sync = sync;
    sync();
    return wrap;
  }

  async function loadStart() {
    const holder = root.querySelector('[data-swap-start]');
    if (!holder) return;
    let options;
    try {
      options = await api('/api/swaps/start');
    } catch (error) {
      holder.replaceChildren(el('p', 'ps-muted', error.message));
      return;
    }
    holder.replaceChildren();
    if (options.active >= options.active_max) {
      holder.appendChild(el('p', 'ps-muted', `You're in ${options.active_max} swaps already. Start another once one has unwrapped.`));
      return;
    }
    const form = el('form', 'ps-form');
    form.noValidate = true;
    const themes = el('div', 'ps-themes-pick');
    themes.appendChild(el('p', 'ps-label', 'Start from a theme'));
    const themeRow = el('div', 'ps-chips');
    themeRow.setAttribute('role', 'group');
    themeRow.setAttribute('aria-label', 'Themes');
    themes.appendChild(themeRow);
    form.appendChild(themes);

    const name = input('text', { maxLength: 60, required: true, autocomplete: 'off', placeholder: 'Office swap, Family picks…', id: 'psName' });
    form.appendChild(field('Name', name));
    const selected = new Set();
    const kindsWrap = el('div', 'ps-field');
    kindsWrap.appendChild(el('p', 'ps-label', 'What counts as a pick'));
    const chips = kindChips(selected, () => {});
    kindsWrap.appendChild(chips);
    form.appendChild(kindsWrap);

    const reveal = input('date', { value: options.reveal_on, min: addDays(options.today, 1), max: options.latest, required: true, id: 'psReveal' });
    form.appendChild(field('Unwrap day', reveal, 'Everything opens at 8 a.m. your time.'));

    const drawWrap = el('fieldset', 'ps-draw');
    drawWrap.appendChild(el('legend', null, 'Drawing names'));
    const manual = input('radio', { name: 'psDrawWhen', value: 'manual', checked: true, id: 'psDrawManual' });
    const dated = input('radio', { name: 'psDrawWhen', value: 'date', id: 'psDrawDate' });
    const manualLabel = el('label', 'ps-check');
    manualLabel.appendChild(manual);
    manualLabel.appendChild(document.createTextNode('I\'ll press Draw once everyone is in'));
    const datedLabel = el('label', 'ps-check');
    datedLabel.appendChild(dated);
    datedLabel.appendChild(document.createTextNode('Draw on a set day'));
    const drawDay = input('date', { value: addDays(options.today, 7) < options.reveal_on ? addDays(options.today, 7) : options.today,
      min: options.today, id: 'psDrawDay' });
    drawDay.setAttribute('aria-label', 'Draw day');
    drawDay.hidden = true;
    [manual, dated].forEach(radio => radio.addEventListener('change', () => { drawDay.hidden = !dated.checked; }));
    drawWrap.appendChild(manualLabel);
    drawWrap.appendChild(datedLabel);
    drawWrap.appendChild(drawDay);
    form.appendChild(drawWrap);

    const note = input('textarea', { rows: 2, maxLength: 300, id: 'psNote', placeholder: 'Something under two hours. No sequels.' });
    form.appendChild(field('Rules (optional)', note, 'Shown to everyone in the swap.'));
    const wish = input('text', { maxLength: 160, autocomplete: 'off', id: 'psWish', placeholder: 'Something funny, or a book I can finish in a week' });
    form.appendChild(field('What would you like? (optional)', wish, 'Whoever draws you sees this. So does everyone else in the swap.'));

    const chosenFriends = new Set();
    if (options.friends.length) {
      const friends = el('details', 'ps-friends');
      friends.appendChild(el('summary', null, 'Ask friends on OmniTrackr now'));
      const list = el('div', 'ps-friends__list');
      options.friends.forEach(friend => {
        const label = el('label', 'ps-check');
        const box = input('checkbox');
        box.addEventListener('change', () => { if (box.checked) chosenFriends.add(friend.id); else chosenFriends.delete(friend.id); });
        label.appendChild(box);
        label.appendChild(document.createTextNode(friend.username));
        list.appendChild(label);
      });
      friends.appendChild(list);
      form.appendChild(friends);
    }

    let themeName = '';
    let themeNote = '';
    (options.themes || []).forEach(theme => {
      const chip = button(theme.name, 'ps-chip');
      chip.setAttribute('aria-pressed', 'false');
      chip.addEventListener('click', () => {
        themeRow.querySelectorAll('.ps-chip').forEach(other => other.setAttribute('aria-pressed', String(other === chip)));
        if (!name.value.trim() || name.value === themeName) name.value = theme.name;
        if (!note.value.trim() || note.value === themeNote) note.value = theme.note;
        themeName = theme.name;
        themeNote = theme.note;
        selected.clear();
        (theme.kinds || []).forEach(kind => selected.add(kind));
        if (selected.size) chips.dataset.open = '1'; else delete chips.dataset.open;
        chips.sync();
      });
      themeRow.appendChild(chip);
    });

    const submit = el('button', 'ps-pill ps-pill--primary ps-submit', 'Start the swap');
    submit.type = 'submit';
    form.appendChild(submit);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (name.value.trim().length < 2) { say('Give the swap a name first.', 'error'); name.focus(); return; }
      if (!parseDay(reveal.value)) { say('Pick an unwrap day.', 'error'); reveal.focus(); return; }
      if (dated.checked && !(drawDay.value && drawDay.value < reveal.value)) {
        say('The draw day has to come before unwrap day.', 'error');
        drawDay.focus();
        return;
      }
      submit.disabled = true;
      say('Starting your swap…');
      try {
        const made = await api('/api/swaps', { method: 'POST', body: {
          name: name.value, note: note.value || null, kinds: [...selected], reveal_on: reveal.value,
          draw_on: dated.checked ? drawDay.value : null, wish: wish.value || null, friend_ids: [...chosenFriends],
        } });
        window.location.href = `${safePath(made.path)}?new=1#invite`;
      } catch (error) {
        say(error.message, 'error');
        submit.disabled = false;
      }
    });
    holder.appendChild(form);
  }

  // ------------------------------------------------------------------ one swap

  const view = { id: null, swap: null, picking: false, fresh: false, opening: false };

  function factsLine(swap) {
    const parts = [`Unwrap day ${swap.reveal_label}`, swap.kinds_label, swap.count === 1 ? '1 person' : `${swap.count} people`];
    if (swap.state === 'open') parts.push(swap.draw_label ? `names drawn ${swap.draw_label}` : 'the host draws names');
    return parts.join(' · ');
  }

  function banner(swap) {
    const box = el('div', `ps-banner ps-banner--${swap.state}`);
    if (swap.state === 'open') {
      box.appendChild(el('strong', null, 'Waiting for the draw'));
      const need = Math.max(0, swap.min - swap.count);
      box.appendChild(el('span', null, need ? `You need ${need} more ${need === 1 ? 'person' : 'people'} before names can be drawn.`
        : (swap.draw_label ? `Names are drawn on ${swap.draw_label} at 8 a.m.` : `${swap.host ? 'Draw' : 'The host draws'} names once everyone is in.`)));
    } else if (swap.state === 'drawn') {
      box.appendChild(el('strong', null, daysWords(swap.days)));
      box.appendChild(el('span', null, `${swap.wrapped} of ${swap.givers} picks wrapped. Everything opens on ${swap.reveal_label}.`));
    } else if (swap.state === 'revealed') {
      box.appendChild(el('strong', null, 'Unwrapped'));
      box.appendChild(el('span', null, `${swap.wrapped} of ${swap.givers} picks are in.`));
    } else {
      box.appendChild(el('strong', null, 'Called off'));
      box.appendChild(el('span', null, 'This swap isn\'t running anymore.'));
    }
    return box;
  }

  function giftCard(gift, from, className) {
    const card = el('article', `ps-gift ${className || ''}`.trim());
    card.appendChild(art(gift, 'ps-art ps-art--big'));
    const copy = el('div', 'ps-gift__copy');
    if (from) copy.appendChild(el('p', 'ps-gift__from', from));
    const heading = el('h3');
    if (gift.url) {
      const link = el('a', null, gift.title);
      link.href = safePath(gift.url);
      heading.appendChild(link);
    } else {
      heading.textContent = gift.title;
    }
    copy.appendChild(heading);
    copy.appendChild(el('p', 'ps-gift__facts', [gift.label, gift.year, gift.creator].filter(Boolean).join(' · ')));
    if (gift.note) copy.appendChild(el('blockquote', 'ps-gift__note', gift.note));
    card.appendChild(copy);
    return card;
  }

  function confetti(host) {
    if (reduceMotion()) return;
    const burst = el('div', 'ps-confetti');
    burst.setAttribute('aria-hidden', 'true');
    for (let index = 0; index < 22; index += 1) {
      const bit = el('span');
      bit.style.setProperty('--x', `${Math.round((Math.random() - 0.5) * 340)}px`);
      bit.style.setProperty('--y', `${Math.round(-80 - Math.random() * 180)}px`);
      bit.style.setProperty('--r', `${Math.round(Math.random() * 540 - 270)}deg`);
      bit.style.setProperty('--d', `${(Math.random() * 0.25).toFixed(2)}s`);
      bit.className = `ps-confetti__bit ps-confetti__bit--${index % 5}`;
      burst.appendChild(bit);
    }
    host.appendChild(burst);
    setTimeout(() => burst.remove(), 1800);
  }

  function receivedSection(swap) {
    const received = swap.me.received;
    const section = el('section', 'ps-card ps-received');
    section.setAttribute('aria-labelledby', 'psReceivedTitle');
    const heading = el('h2', null, 'Your pick');
    heading.id = 'psReceivedTitle';
    section.appendChild(heading);
    if (!received) {
      section.appendChild(el('p', 'ps-muted', 'You weren\'t in the draw for this one.'));
      return section;
    }
    if (received.pending) {
      section.appendChild(el('p', 'ps-muted', `${received.from} is still wrapping yours. You'll get a notification when it lands.`));
      return section;
    }
    const stage = el('div', 'ps-stage');
    section.appendChild(stage);
    const showGift = animate => {
      stage.replaceChildren();
      const card = giftCard(received, `From ${received.from}`, animate ? 'ps-gift--pop' : '');
      stage.appendChild(card);
      const actions = el('div', 'ps-row ps-gift__actions');
      const add = button(received.added ? 'In your library' : 'Add to my library', 'ps-pill ps-pill--primary', () => addReceived(false, add, queue));
      const queue = button('Add to Up next', 'ps-pill', () => addReceived(true, add, queue));
      if (received.added) add.disabled = true;
      actions.appendChild(add);
      actions.appendChild(queue);
      stage.appendChild(actions);
      const react = el('div', 'ps-react');
      react.appendChild(el('p', 'ps-label', `Tell ${received.from}`));
      const chips = el('div', 'ps-chips');
      chips.setAttribute('role', 'group');
      chips.setAttribute('aria-label', `Your reaction for ${received.from}`);
      (swap.thanks || []).forEach(option => {
        const chip = button(option.label, 'ps-chip');
        chip.setAttribute('aria-pressed', String(received.thanks === option.key));
        chip.addEventListener('click', async () => {
          chip.disabled = true;
          try {
            const fresh = await api(`/api/swaps/${swap.id}/received/thanks`, { method: 'POST', body: { reaction: option.key } });
            say(`Sent to ${received.from}.`);
            view.swap = fresh;
            chips.querySelectorAll('.ps-chip').forEach(other => other.setAttribute('aria-pressed', String(other === chip)));
          } catch (error) { say(error.message, 'error'); }
          chip.disabled = false;
        });
        chips.appendChild(chip);
      });
      react.appendChild(chips);
      stage.appendChild(react);
      if (animate) confetti(stage);
    };
    if (received.opened) {
      showGift(false);
    } else {
      const wrapped = button('', 'ps-unwrap');
      wrapped.setAttribute('aria-label', `Unwrap your pick from ${received.from}`);
      const present = el('span', 'ps-present');
      present.setAttribute('aria-hidden', 'true');
      present.appendChild(el('span', 'ps-present__lid'));
      present.appendChild(el('span', 'ps-present__body'));
      wrapped.appendChild(present);
      wrapped.appendChild(el('span', 'ps-unwrap__label', `Unwrap your pick from ${received.from}`));
      wrapped.addEventListener('click', async () => {
        if (view.opening) return;
        view.opening = true;
        wrapped.classList.add('is-opening');
        try {
          await api(`/api/swaps/${swap.id}/received/open`, { method: 'POST' });
        } catch (error) { /* still show it */ }
        received.opened = true;
        setTimeout(() => {
          showGift(true);
          const waiting = root.querySelector('[data-swap-board]');
          if (waiting) waiting.replaceWith(boardSection(swap));
          view.opening = false;
          stage.querySelector('h3')?.setAttribute('tabindex', '-1');
          stage.querySelector('h3')?.focus();
        }, reduceMotion() ? 0 : 650);
      });
      stage.appendChild(wrapped);
    }
    return section;
  }

  async function addReceived(queue, addButton, queueButton) {
    addButton.disabled = true;
    queueButton.disabled = true;
    try {
      const result = await api(`/api/swaps/${view.id}/received/add`, { method: 'POST', body: { queue } });
      addButton.textContent = 'In your library';
      if (result.queued) queueButton.textContent = 'In Up next';
      else queueButton.disabled = false;
      say(result.queued ? 'Added to your library and put in Up next.' : (result.created ? 'Added to your library.' : 'It was in your library already.'));
    } catch (error) {
      say(error.message, 'error');
      addButton.disabled = false;
      queueButton.disabled = false;
    }
  }

  function pickForm(swap, target) {
    const form = el('form', 'ps-pick-form');
    form.noValidate = true;
    let chosen = null;
    const searchLabel = el('label', null, 'Find something');
    const search = input('search', { maxLength: 80, autocomplete: 'off', id: 'psSearch',
      placeholder: swap.kinds.length ? `Search ${swap.kinds_label.toLowerCase()}` : 'A film, show, book, game, album…' });
    searchLabel.htmlFor = search.id;
    form.appendChild(searchLabel);
    form.appendChild(search);
    const results = el('ul', 'ps-results');
    results.hidden = true;
    form.appendChild(results);
    const picked = el('div', 'ps-chosen');
    picked.hidden = true;
    form.appendChild(picked);

    const typed = el('details', 'ps-typed');
    typed.appendChild(el('summary', null, 'Not there? Type it in'));
    const kindSelect = el('select');
    kindSelect.id = 'psTypedKind';
    (swap.kinds.length ? swap.kinds : KINDS).forEach(kind => {
      const option = el('option', null, KIND_LABEL[kind]);
      option.value = kind;
      kindSelect.appendChild(option);
    });
    const typedTitle = input('text', { maxLength: 200, id: 'psTypedTitle', autocomplete: 'off' });
    const typedYear = input('number', { min: 1800, max: 2100, id: 'psTypedYear', inputMode: 'numeric' });
    const typedGrid = el('div', 'ps-typed__grid');
    typedGrid.appendChild(field('Format', kindSelect));
    typedGrid.appendChild(field('Title', typedTitle));
    typedGrid.appendChild(field('Year (optional)', typedYear));
    typed.appendChild(typedGrid);
    const useTyped = button('Use this', 'ps-pill', () => {
      const title = typedTitle.value.trim();
      if (!title) { say('Type the title first.', 'error'); typedTitle.focus(); return; }
      const year = Number(typedYear.value);
      choose({ kind: kindSelect.value, title, year: Number.isInteger(year) && year >= 1800 ? year : null, image: null, slug: null });
      typed.open = false;
    });
    typed.appendChild(useTyped);
    form.appendChild(typed);

    const note = input('textarea', { rows: 3, maxLength: 500, id: 'psGiftNote',
      placeholder: `Why this, for ${target.username}? Where to start, when it gets good, what to watch out for.` });
    form.appendChild(field('Your note', note, 'The note is half the gift. It shows next to your pick on unwrap day.'));
    const mine = swap.me.gift;
    if (mine) {
      note.value = mine.note || '';
    }
    const actions = el('div', 'ps-row');
    const submit = el('button', 'ps-pill ps-pill--primary', mine ? 'Save the change' : 'Wrap it');
    submit.type = 'submit';
    actions.appendChild(submit);
    if (mine) actions.appendChild(button('Keep the one I wrapped', 'ps-pill', () => { view.picking = false; renderSwap(); }));
    form.appendChild(actions);
    const warn = el('div', 'ps-warn');
    warn.hidden = true;
    form.appendChild(warn);

    function choose(item) {
      chosen = item;
      picked.replaceChildren();
      picked.appendChild(art(item, 'ps-art ps-art--small'));
      const text = el('div', 'ps-chosen__text');
      text.appendChild(el('strong', null, item.title));
      text.appendChild(el('small', null, [KIND_LABEL[item.kind], item.year].filter(Boolean).join(' · ')));
      picked.appendChild(text);
      picked.appendChild(button('Change', 'ps-link-button', () => { chosen = null; picked.hidden = true; search.focus(); }));
      picked.hidden = false;
      results.hidden = true;
      warn.hidden = true;
      note.focus();
    }
    if (mine) choose({ kind: mine.kind, title: mine.title, year: mine.year, image: mine.image, slug: mine.url ? mine.url.split('/').pop() : null, creator: mine.creator });

    let timer = null;
    let serial = 0;
    search.addEventListener('input', () => {
      clearTimeout(timer);
      const query = search.value.trim();
      if (query.length < 2) { results.hidden = true; return; }
      timer = setTimeout(async () => {
        const mineSerial = ++serial;
        try {
          const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query.slice(0, 80))}`, { credentials: 'same-origin' });
          const found = allowedResults((await response.json()).results, swap.kinds);
          if (mineSerial !== serial) return;
          results.replaceChildren();
          found.forEach(result => {
            const row = el('li');
            const option = button('', 'ps-result');
            option.appendChild(art(result, 'ps-art ps-art--small'));
            const text = el('span', 'ps-result__text');
            text.appendChild(el('strong', null, result.title));
            text.appendChild(el('small', null, [KIND_LABEL[result.kind], result.year].filter(Boolean).join(' · ')));
            option.appendChild(text);
            option.addEventListener('click', () => choose({ kind: result.kind, title: result.title, year: result.year,
              image: safeImage(result.image) || null, slug: result.slug || null }));
            row.appendChild(option);
            results.appendChild(row);
          });
          if (!found.length) results.appendChild(el('li', 'ps-hint', 'Nothing found. Type it in below instead.'));
          results.hidden = false;
        } catch (error) {
          results.hidden = true;
        }
      }, 250);
    });

    async function send(anyway) {
      if (!chosen) { say('Pick a title first.', 'error'); search.focus(); return; }
      submit.disabled = true;
      try {
        const result = await api(`/api/swaps/${swap.id}/gift`, { method: 'PUT', body: {
          kind: chosen.kind, title: chosen.title, year: chosen.year || null, image: chosen.image || null,
          slug: chosen.slug || null, creator: chosen.creator || null, note: note.value || null, anyway: Boolean(anyway),
        } });
        if (!result.saved && result.has_it) {
          warn.replaceChildren(el('p', null, result.message));
          const row = el('div', 'ps-row');
          row.appendChild(button('Wrap it anyway', 'ps-pill', () => send(true)));
          row.appendChild(button('Pick something else', 'ps-link-button', () => { warn.hidden = true; chosen = null; picked.hidden = true; search.focus(); }));
          warn.appendChild(row);
          warn.hidden = false;
          submit.disabled = false;
          return;
        }
        view.picking = false;
        view.swap = result.swap;
        renderSwap();
        say(swap.state === 'revealed' ? `Sent. ${target.username} can open it now.` : `Wrapped. ${target.username} sees it on unwrap day.`);
      } catch (error) {
        say(error.message, 'error');
        submit.disabled = false;
      }
    }
    form.addEventListener('submit', event => { event.preventDefault(); send(false); });
    return form;
  }

  function givingSection(swap) {
    const target = swap.me.gives_to;
    const section = el('section', 'ps-card ps-giving');
    section.setAttribute('aria-labelledby', 'psGivingTitle');
    const head = el('div', 'ps-giving__head');
    head.appendChild(avatar({ initials: target.initials }));
    const heading = el('h2', null, swap.state === 'revealed' ? `${target.username} is waiting on your pick` : `You're picking for ${target.username}`);
    heading.id = 'psGivingTitle';
    head.appendChild(heading);
    section.appendChild(head);
    if (target.wish) {
      const wish = el('p', 'ps-wish');
      wish.appendChild(el('span', 'ps-wish__label', 'They asked for'));
      wish.appendChild(el('q', null, target.wish));
      section.appendChild(wish);
    }
    section.appendChild(el('p', 'ps-hint', `What counts: ${swap.kinds_label.charAt(0).toLowerCase()}${swap.kinds_label.slice(1)}.`));
    if (Array.isArray(target.hints) && target.hints.length) {
      const hints = el('div', 'ps-hints');
      hints.appendChild(el('p', 'ps-label', `${target.username} rated these highly`));
      const row = el('ul', 'ps-hints__row');
      target.hints.forEach(hint => {
        const item = el('li', 'ps-hint-card');
        item.appendChild(art(hint, 'ps-art ps-art--hint'));
        item.appendChild(el('span', 'ps-hint-card__title', hint.title));
        item.appendChild(el('small', null, hint.label));
        row.appendChild(item);
      });
      hints.appendChild(row);
      section.appendChild(hints);
    }
    const gift = swap.me.gift;
    if (gift && !view.picking) {
      section.appendChild(giftCard(gift, swap.state === 'revealed' ? 'You gave' : 'Wrapped and waiting', 'ps-gift--mine'));
      if (swap.state === 'drawn') {
        const row = el('div', 'ps-row');
        row.appendChild(button('Change my pick', 'ps-pill', () => { view.picking = true; renderSwap(); root.querySelector('#psSearch')?.focus(); }));
        row.appendChild(confirmButton('Take it back', 'Take your pick back? You can wrap another one any time before unwrap day.',
          'Take it back', 'ps-link-button', async () => {
            view.swap = await api(`/api/swaps/${swap.id}/gift`, { method: 'DELETE' });
            renderSwap();
            say('Taken back. Wrap another one before unwrap day.');
          }));
        section.appendChild(row);
      }
    } else {
      section.appendChild(pickForm(swap, target));
    }
    return section;
  }

  function boxesRow(swap) {
    const list = el('ul', 'ps-boxes');
    list.setAttribute('aria-label', `${swap.wrapped} of ${swap.givers} picks wrapped`);
    swap.people.filter(person => person.in_draw).forEach(person => {
      const item = el('li', `ps-box${person.wrapped ? ' ps-box--wrapped' : ' ps-box--empty'}`);
      item.appendChild(el('span', 'ps-box__lid'));
      item.appendChild(el('span', 'ps-box__body'));
      item.appendChild(el('small', null, person.you ? 'You' : person.username));
      item.title = person.wrapped ? `${person.username} has wrapped a pick` : `${person.username} hasn't picked yet`;
      list.appendChild(item);
    });
    return list;
  }

  function boardSection(swap) {
    const section = el('section', 'ps-card ps-board');
    section.setAttribute('aria-labelledby', 'psBoardTitle');
    const heading = el('h2', null, 'Every pick');
    heading.id = 'psBoardTitle';
    section.appendChild(heading);
    const list = el('ul', 'ps-board__list');
    (swap.board || []).forEach(entry => {
      const item = el('li', `ps-board__item${entry.to_you ? ' ps-board__item--you' : ''}`);
      const who = el('p', 'ps-board__who');
      who.appendChild(el('strong', null, entry.from_you ? 'You' : entry.from));
      who.appendChild(document.createTextNode(' picked for '));
      who.appendChild(el('strong', null, entry.to_you ? 'you' : entry.to));
      item.appendChild(who);
      if (entry.gift) {
        const gift = el('div', 'ps-board__gift');
        gift.appendChild(art(entry.gift, 'ps-art ps-art--small'));
        const text = el('div', 'ps-board__text');
        const title = el('strong');
        if (entry.gift.url) {
          const link = el('a', null, entry.gift.title);
          link.href = safePath(entry.gift.url);
          title.appendChild(link);
        } else {
          title.textContent = entry.gift.title;
        }
        text.appendChild(title);
        text.appendChild(el('small', null, [entry.gift.label, entry.gift.year].filter(Boolean).join(' · ')));
        if (entry.gift.note) text.appendChild(el('p', 'ps-board__note', entry.gift.note));
        if (entry.thanks) text.appendChild(el('p', 'ps-board__thanks', `${entry.to_you ? 'You' : entry.to}: ${entry.thanks}`));
        gift.appendChild(text);
        item.appendChild(gift);
      } else {
        item.appendChild(el('p', 'ps-muted', 'Still wrapping.'));
      }
      list.appendChild(item);
    });
    section.appendChild(list);
    const again = el('p', 'ps-hint');
    again.appendChild(document.createTextNode('Want another round? '));
    const link = el('a', null, 'Start a new swap');
    link.href = '/swap#start';
    again.appendChild(link);
    again.appendChild(document.createTextNode(' and send the link to the same group.'));
    section.appendChild(again);
    return section;
  }

  function peopleSection(swap) {
    const section = el('section', 'ps-card ps-people');
    section.setAttribute('aria-labelledby', 'psPeopleTitle');
    const heading = el('h2', null, swap.count === 1 ? 'Just you so far' : `${swap.count} people`);
    heading.id = 'psPeopleTitle';
    section.appendChild(heading);
    const list = el('ul', 'ps-people__list');
    swap.people.forEach(person => {
      const item = el('li', 'ps-person');
      item.appendChild(avatar(person));
      const text = el('div', 'ps-person__text');
      const name = el('strong', null, person.you ? `${person.username} (you)` : person.username);
      text.appendChild(name);
      if (person.host) text.appendChild(el('span', 'ps-tag', 'Host'));
      if (person.wish) text.appendChild(el('p', 'ps-person__wish', person.wish));
      item.appendChild(text);
      if (swap.host && !person.you && (swap.state === 'open' || swap.state === 'drawn')) {
        item.appendChild(confirmButton('Take out', `Take ${person.username} out of the swap? The link won't add them back.`,
          'Take them out', 'ps-link-button', async () => {
            view.swap = await api(`/api/swaps/${swap.id}/members/${person.id}`, { method: 'DELETE' });
            renderSwap();
            say(`${person.username} is out.${swap.state === 'drawn' ? ' Whoever drew them has a new name.' : ''}`);
          }));
      }
      list.appendChild(item);
    });
    section.appendChild(list);
    if (swap.state === 'open' || swap.state === 'drawn') {
      const wishForm = el('form', 'ps-wish-form');
      const wish = input('text', { maxLength: 160, value: swap.me.wish || '', id: 'psMyWish', autocomplete: 'off',
        placeholder: 'Something funny, or a book I can finish in a week' });
      wishForm.appendChild(field('What would you like?', wish, 'Whoever draws you sees this.'));
      const save = el('button', 'ps-pill', 'Save');
      save.type = 'submit';
      wishForm.appendChild(save);
      wishForm.addEventListener('submit', async event => {
        event.preventDefault();
        save.disabled = true;
        try {
          view.swap = await api(`/api/swaps/${swap.id}/me`, { method: 'PATCH', body: { wish: wish.value || null } });
          say('Saved.');
          renderSwap();
        } catch (error) { say(error.message, 'error'); save.disabled = false; }
      });
      section.appendChild(wishForm);
    }
    return section;
  }

  function hostSection(swap) {
    const section = el('section', 'ps-card ps-host');
    section.setAttribute('aria-labelledby', 'psHostTitle');
    const heading = el('h2', null, 'You\'re the host');
    heading.id = 'psHostTitle';
    section.appendChild(heading);
    if (swap.state === 'open') {
      if (swap.can_draw) {
        section.appendChild(el('p', 'ps-hint', 'Once names are drawn nobody new can join, so wait until everyone is in.'));
        section.appendChild(confirmButton('Draw names now', `Draw names for ${swap.count} people? Nobody else can join after this.`,
          'Yes, draw names', 'ps-pill ps-pill--primary', async () => {
            view.swap = await api(`/api/swaps/${swap.id}/draw`, { method: 'POST' });
            renderSwap();
            say('Names are drawn. Everyone has been told who they\'re picking for.');
          }));
      } else {
        section.appendChild(el('p', 'ps-hint', `Names can be drawn once at least ${swap.min} people are in.`));
      }
    }
    if (swap.state === 'drawn') {
      if (swap.can_unwrap) {
        section.appendChild(el('p', 'ps-hint', 'Every pick is wrapped. Open them now if you\'re all together, or let unwrap day come.'));
        section.appendChild(confirmButton('Open everything now', 'Open every pick for everyone now?', 'Yes, open them',
          'ps-pill ps-pill--primary', async () => {
            view.swap = await api(`/api/swaps/${swap.id}/unwrap`, { method: 'POST' });
            renderSwap();
          }));
      } else {
        section.appendChild(el('p', 'ps-hint', `${swap.givers - swap.wrapped} still to wrap. Anyone who hasn't picked gets a reminder two days before unwrap day.`));
      }
    }
    const edit = el('details', 'ps-edit');
    edit.appendChild(el('summary', null, 'Change the swap'));
    const form = el('form', 'ps-form');
    const name = input('text', { maxLength: 60, value: swap.name, id: 'psEditName' });
    form.appendChild(field('Name', name));
    const note = input('textarea', { rows: 2, maxLength: 300, value: swap.note || '', id: 'psEditNote' });
    form.appendChild(field('Rules', note));
    const reveal = input('date', { value: swap.reveal_on, id: 'psEditReveal' });
    form.appendChild(field('Unwrap day', reveal));
    let drawDay = null;
    let clearDraw = null;
    if (swap.state === 'open') {
      drawDay = input('date', { value: swap.draw_on || '', id: 'psEditDraw' });
      form.appendChild(field('Draw day', drawDay, 'Leave it empty to draw by hand.'));
      clearDraw = () => !drawDay.value;
    }
    const save = el('button', 'ps-pill', 'Save changes');
    save.type = 'submit';
    form.appendChild(save);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      save.disabled = true;
      const body = { name: name.value, note: note.value };
      if (reveal.value && reveal.value !== swap.reveal_on) body.reveal_on = reveal.value;
      if (drawDay) {
        if (clearDraw()) { if (swap.draw_on) body.clear_draw = true; } else if (drawDay.value !== swap.draw_on) body.draw_on = drawDay.value;
      }
      try {
        view.swap = await api(`/api/swaps/${swap.id}`, { method: 'PATCH', body });
        renderSwap();
        say('Saved.');
      } catch (error) { say(error.message, 'error'); save.disabled = false; }
    });
    edit.appendChild(form);
    if (swap.state === 'open') {
      edit.appendChild(confirmButton('Make a new invite link', 'Make a new link? The old one stops working. People already in stay in.',
        'Make a new link', 'ps-link-button', async () => {
          await api(`/api/swaps/${swap.id}/link`, { method: 'POST' });
          await loadSwap();
          say('New link made. The old one no longer works.');
        }));
    }
    edit.appendChild(confirmButton('Call off the swap', 'Call off the swap for everyone? This can\'t be undone.',
      'Call it off', 'ps-link-button ps-link-button--danger', async () => {
        await api(`/api/swaps/${swap.id}/cancel`, { method: 'POST' });
        window.location.href = '/swap';
      }));
    section.appendChild(edit);
    return section;
  }

  function renderSwap() {
    const swap = view.swap;
    const body = root.querySelector('[data-swap-body]');
    if (!swap || !body) return;
    const facts = root.querySelector('[data-swap-facts]');
    if (facts) facts.textContent = factsLine(swap);
    const heading = root.querySelector('.ps-swap__head h1');
    if (heading && heading.textContent !== swap.name) heading.textContent = swap.name;
    body.replaceChildren();
    body.appendChild(banner(swap));
    if (swap.note) {
      const rules = el('p', 'ps-rules');
      rules.appendChild(el('strong', null, 'The rules: '));
      rules.appendChild(document.createTextNode(swap.note));
      body.appendChild(rules);
    }
    if (swap.state === 'cancelled') return;
    if (swap.state === 'revealed') {
      body.appendChild(receivedSection(swap));
      if (swap.me.gives_to && !swap.me.gift) body.appendChild(givingSection(swap));
      const received = swap.me.received;
      if (received && !received.pending && !received.opened) {
        // The list of every pick names yours, so it waits until you've opened it.
        const waiting = el('section', 'ps-card ps-board ps-board--waiting');
        waiting.dataset.swapBoard = '';
        waiting.appendChild(el('h2', null, 'Every pick'));
        waiting.appendChild(el('p', 'ps-muted', 'Open yours first. Then you\'ll see what everyone else got, and who picked it.'));
        body.appendChild(waiting);
      } else {
        body.appendChild(boardSection(swap));
      }
    } else if (swap.state === 'drawn') {
      if (swap.me.gives_to) body.appendChild(givingSection(swap));
      else body.appendChild(el('p', 'ps-card ps-muted', 'Names were drawn before you were in this swap, so you don\'t have anyone to pick for.'));
      const boxes = el('section', 'ps-card ps-wrapped');
      boxes.setAttribute('aria-labelledby', 'psWrappedTitle');
      const title = el('h2', null, `${swap.wrapped} of ${swap.givers} wrapped`);
      title.id = 'psWrappedTitle';
      boxes.appendChild(title);
      boxes.appendChild(boxesRow(swap));
      boxes.appendChild(el('p', 'ps-hint', 'Nobody can see what anyone picked, or who drew whom, until unwrap day.'));
      body.appendChild(boxes);
    } else if (swap.invite_url) {
      body.appendChild(inviteBox(swap, view.fresh));
    }
    if (swap.host && swap.state !== 'revealed') body.appendChild(hostSection(swap));
    body.appendChild(peopleSection(swap));
    if (swap.state !== 'revealed') {
      body.appendChild(confirmButton('Leave this swap', swap.state === 'drawn'
        ? 'Leave the swap? Whoever drew you will pick for someone else.' : 'Leave the swap?', 'Leave', 'ps-link-button ps-leave',
      async () => {
        await api(`/api/swaps/${swap.id}/leave`, { method: 'POST' });
        window.location.href = '/swap';
      }));
    }
  }

  async function loadSwap() {
    try {
      view.swap = await api(`/api/swaps/${view.id}`);
      renderSwap();
    } catch (error) {
      const body = root.querySelector('[data-swap-body]');
      if (body) body.replaceChildren(el('p', 'ps-muted', error.message));
    }
  }

  // ------------------------------------------------------------------ joining

  async function loadJoin() {
    const box = root.querySelector('[data-swap-join]');
    if (!box) return;
    let info;
    try {
      info = await api(`/api/swaps/join/${encodeURIComponent(box.dataset.token)}`);
    } catch (error) {
      box.replaceChildren(el('p', 'ps-muted', error.message));
      return;
    }
    box.replaceChildren();
    if (info.member) {
      const open = el('a', 'button', 'Open the swap');
      open.href = safePath(info.path);
      box.appendChild(open);
      return;
    }
    const form = el('form', 'ps-join__form');
    const wish = input('text', { maxLength: 160, autocomplete: 'off', id: 'psJoinWish',
      placeholder: 'Something funny, or a book I can finish in a week' });
    form.appendChild(field('What would you like? (optional)', wish, 'Whoever draws you sees this.'));
    const go = el('button', 'button', 'Join the swap');
    go.type = 'submit';
    form.appendChild(go);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      go.disabled = true;
      try {
        const result = await api(`/api/swaps/join/${encodeURIComponent(box.dataset.token)}`, { method: 'POST', body: { wish: wish.value || null } });
        window.location.href = safePath(result.path);
      } catch (error) {
        say(error.message, 'error');
        go.disabled = false;
      }
    });
    box.appendChild(form);
  }

  // ------------------------------------------------------------------ start

  const kind = root.dataset.view;
  if (kind === 'hub') {
    loadMine();
    loadStart();
  } else if (kind === 'swap') {
    view.id = Number(root.dataset.swapId);
    view.fresh = new URLSearchParams(window.location.search).get('new') === '1';
    loadSwap().then(() => {
      if (view.fresh) {
        const link = root.querySelector('#psInviteLink');
        root.querySelector('#invite')?.scrollIntoView({ block: 'center' });
        if (link) link.focus({ preventScroll: true });
        history.replaceState(null, '', window.location.pathname);
      }
    });
  } else if (kind === 'join') {
    loadJoin();
  }
}());
