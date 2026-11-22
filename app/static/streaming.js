// "On your services": a home card that asks once which streaming services the member has, then lists the
// films, shows and anime on their list that stream on them, newest arrivals first. It also adds the
// "On my services" filter to those three libraries. The server decides what shows and what's new
// (app/streaming_services.py). Server text is only ever set as textContent.
(function () {
  'use strict';

  const REFRESH_GAP_MS = 60 * 1000;
  const FIRST_SHOWN = 6;
  const VIDEO = ['movies', 'tv-shows', 'anime'];
  const HASH = '#on-your-services';
  const KIND_WORDS = { movies: ['film', 'films'], 'tv-shows': ['show', 'shows'], anime: ['anime', 'anime'] };
  // Each pending recheck waits longer: the server looks titles up a dozen at a time after a save.
  const RETRY_DELAYS = [15000, 45000, 120000];
  // About what the lookups right after a save and the next half-hourly run get through.
  const PENDING_SOON = 24;
  const state = {
    epoch: 0, card: null, chosen: [], request: null, loadedAt: 0, filter: '', expanded: false, editing: false,
    busy: false, retries: 0, retryTimer: 0, seen: new Set(), observer: null, filterCounted: false, hashDone: false,
  };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);
  const localPath = url => typeof url === 'string' && /^\/titles\/(movie|tv|anime)\/[a-z0-9-]{1,140}$/.test(url);

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  async function send(method, path, body) {
    const response = await fetch(`${apiBase()}${path}`, fetchOptions({
      method,
      headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      throw new Error(typeof detail === 'string' ? detail : 'That didn’t work. Please try again.');
    }
    return data;
  }

  function event(name) {
    send('POST', '/api/streaming/event', { event: name }).catch(() => { /* a counter only */ });
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(className, text, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    node.addEventListener('click', clickEvent => onClick(clickEvent.currentTarget));
    return node;
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text || '';
  }

  function show(id, visible) {
    const node = $(id);
    if (node) node.hidden = !visible;
  }

  function setStatus(text) { setText('onYourServicesStatus', text); }

  function andList(parts) {
    if (parts.length <= 1) return parts.join('');
    return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
  }

  function plural(count, one, many) { return `${count} ${count === 1 ? one : many}`; }

  function serviceNames(chosen) {
    const names = chosen.map(service => service.name);
    return names.length > 3 ? `${names.slice(0, 2).join(', ')} and ${names.length - 2} more` : andList(names);
  }

  function kindWords(kinds) {
    const words = (kinds || []).filter(kind => KIND_WORDS[kind]).map(kind => KIND_WORDS[kind][1]);
    return words.length ? andList(words) : 'films and shows';
  }

  // ------------------------------------------------ the picker

  function picked() {
    return Array.from(document.querySelectorAll('#onYourServicesPicker input[name="streamingService"]:checked'))
      .map(input => input.value);
  }

  function renderPicker(card) {
    const form = $('onYourServicesPicker');
    if (!form) return;
    const chosen = new Set((card.chosen || []).map(service => service.id));
    const current = form.dataset.built === '1' ? new Set(picked()) : chosen;
    form.querySelectorAll('[data-services]').forEach(holder => {
      const free = holder.dataset.services === 'free';
      holder.replaceChildren(...(card.catalog || []).filter(service => Boolean(service.free) === free).map(service => {
        const label = el('label', 'on-services__chip');
        const input = el('input');
        input.type = 'checkbox';
        input.name = 'streamingService';
        input.value = service.id;
        input.checked = current.has(service.id);
        label.append(input, el('span', '', service.name));
        return label;
      }));
    });
    form.dataset.built = '1';
    const alerts = $('onYourServicesAlerts');
    if (alerts && form.dataset.alertsSet !== '1') alerts.checked = card.alerts !== false;
    form.dataset.alertsSet = '1';
    const save = $('onYourServicesSave');
    if (save) save.textContent = card.state === 'choose' ? 'Show what I can watch' : 'Save my services';
    show('onYourServicesCancel', card.state !== 'choose');
  }

  function closePicker() {
    const form = $('onYourServicesPicker');
    if (form) { form.dataset.built = ''; form.dataset.alertsSet = ''; }
    state.editing = false;
  }

  async function save(submitEvent) {
    submitEvent.preventDefault();
    if (state.busy) return;
    const services = picked();
    const first = state.card && state.card.state === 'choose';
    if (first && !services.length) {
      setStatus('Tick at least one service, or press No thanks if you don’t stream.');
      return;
    }
    state.busy = true;
    const saveButton = $('onYourServicesSave');
    if (saveButton) saveButton.disabled = true;
    setStatus('Saving…');
    const epoch = state.epoch;
    try {
      const data = await send('PUT', '/api/streaming', { services, alerts: Boolean($('onYourServicesAlerts')?.checked) });
      if (epoch !== state.epoch) return;
      closePicker();
      state.chosen = Array.isArray(data.chosen) ? data.chosen : [];
      state.filter = '';
      state.expanded = false;
      state.retries = 0;
      state.loadedAt = Date.now();
      render(data.card);
      syncLibraryFilters();
      setStatus(services.length ? 'Saved. Only you can see these.' : 'Your services are cleared.');
      $('onYourServicesTitle')?.focus?.({ preventScroll: true });
    } catch (error) {
      setStatus(error.message);
    } finally {
      state.busy = false;
      if (saveButton) saveButton.disabled = false;
    }
  }

  async function answer(what) {
    if (state.busy) return;
    state.busy = true;
    const epoch = state.epoch;
    try {
      const data = await send('POST', '/api/streaming/answer', { answer: what });
      if (epoch !== state.epoch) return;
      if (what === 'show') {
        render(data.card);
        return;
      }
      // A share link keeps working while the card is hidden, and its page is where it can be turned off.
      const linked = Boolean(state.card && state.card.share && SHARE_PATH.test(state.card.share.path || ''));
      render(null);
      if (typeof showNotice === 'function') {
        showNotice({
          later: 'We’ll ask about streaming services another time.',
          stop: 'Okay, we won’t ask about streaming services again.',
          hide: linked
            ? 'Hidden for three weeks. Your share link still works, and you can turn it off from its page.'
            : 'Hidden for three weeks. The “On my services” filter in your library still works.',
        }[what] || 'Done.', 'success');
      }
    } catch (error) {
      setStatus(error.message);
    } finally {
      state.busy = false;
    }
  }

  // ------------------------------------------------ the list

  function cover(item) {
    const holder = el('span', 'on-services__cover');
    holder.setAttribute('aria-hidden', 'true');
    // prepend, so a "New" badge already on the poster stays when the image fails
    const letter = () => {
      holder.classList.add('on-services__cover--letter');
      holder.prepend((String(item.title || '').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase());
    };
    const image = typeof item.poster === 'string' && /^https:\/\//.test(item.poster) ? item.poster : '';
    if (!image) { letter(); return holder; }
    const img = el('img');
    img.src = image;
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.referrerPolicy = 'no-referrer';
    img.width = 120;
    img.height = 180;
    img.addEventListener('error', () => { img.remove(); letter(); }, { once: true });
    holder.appendChild(img);
    return holder;
  }

  async function queue(item, control) {
    if (control.disabled || typeof authenticatedFetch !== 'function') return;
    control.disabled = true;
    let ok = false;
    try {
      const response = await authenticatedFetch(`${apiBase()}/next-up/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: item.category, item_id: item.id }),
      });
      ok = Boolean(response && (response.ok || response.status === 409));
    } catch (error) {
      ok = false;
    }
    if (!ok) {
      control.disabled = false;
      setStatus('That didn’t save. Try again in a moment.');
      return;
    }
    item.queued = true;
    control.textContent = '✓';
    control.setAttribute('aria-label', queueLabel(item));
    control.title = queueLabel(item);
    setStatus(`${item.title} is in your Up next queue.`);
    event('queued');
    if (typeof refreshNextUpQueue === 'function') refreshNextUpQueue();
  }

  function queueLabel(item) {
    return item.queued ? `${item.title} is in Up next` : `Add ${item.title} to Up next`;
  }

  function tile(item) {
    const node = el('li', 'on-services__item');
    node.dataset.format = item.category;
    if (item.new) node.classList.add('is-new');
    const art = el('div', 'on-services__art');
    const poster = cover(item);
    if (item.new) poster.appendChild(el('span', 'on-services__new', 'New'));
    // Up next sits on the poster's corner, the way the library shelf puts its actions.
    const queueButton = button('on-services__queue', item.queued ? '✓' : '+', control => queue(item, control));
    queueButton.disabled = Boolean(item.queued);
    queueButton.setAttribute('aria-label', queueLabel(item));
    queueButton.title = queueLabel(item);
    art.append(poster, queueButton);
    const copy = el('div', 'on-services__copy');
    const name = el('h3', 'on-services__name');
    if (localPath(item.path)) {
      const link = el('a', '', item.title);
      link.href = item.path;
      link.addEventListener('click', () => event('opened'));
      name.appendChild(link);
    } else {
      const open = el('button', 'on-services__open', item.title);
      open.type = 'button';
      open.dataset.action = 'pulse-open-item';
      open.dataset.pulseTab = item.category;
      open.dataset.pulseItemId = String(item.id);
      open.dataset.pulseTitle = item.title || '';
      open.setAttribute('aria-label', `Open ${item.title} in your library`);
      open.addEventListener('click', () => event('opened'));
      name.appendChild(open);
    }
    copy.appendChild(name);
    copy.appendChild(el('p', 'on-services__meta', [item.label, item.year].filter(Boolean).join(' · ')));
    const where = el('p', 'on-services__where');
    (item.services || []).forEach(service => {
      const tag = el('span', service.new ? 'on-services__svc on-services__svc--new' : 'on-services__svc', service.name);
      tag.dataset.service = service.id;
      where.appendChild(tag);
    });
    const services = (item.services || []).map(service => service.name);
    where.prepend(el('span', 'sr-only', item.new ? `New on ${andList(services)}: ` : `On ${andList(services)}: `));
    copy.appendChild(where);
    const kind = { movies: 'movie', 'tv-shows': 'tv', anime: 'anime' }[item.category];
    if (window.OmniTitleLinks && typeof window.OmniTitleLinks.openWhere === 'function') {
      const whereButton = button('on-services__act', 'Where to watch', () => {
        event('where');
        window.OmniTitleLinks.openWhere(kind, item.title, item.year);
      });
      whereButton.setAttribute('aria-label', `Where to watch ${item.title}`);
      copy.appendChild(whereButton);
    }
    node.append(art, copy);
    return node;
  }

  function filtered(card) {
    const items = Array.isArray(card.items) ? card.items : [];
    if (!state.filter) return items;
    return items.filter(item => (item.services || []).some(service => service.id === state.filter));
  }

  function renderFilters(card) {
    const holder = $('onYourServicesFilters');
    if (!holder) return;
    const withTitles = (card.chosen || []).filter(service => service.count > 0);
    if (withTitles.length < 2) {
      state.filter = '';
      holder.hidden = true;
      holder.replaceChildren();
      return;
    }
    if (state.filter && !withTitles.some(service => service.id === state.filter)) state.filter = '';
    const chips = [{ id: '', name: 'All', count: card.total }].concat(withTitles).map(service => {
      const chip = button('on-services__filter', '', () => {
        state.filter = service.id;
        state.expanded = false;
        renderList(state.card);
      });
      chip.append(el('span', '', service.name), el('span', 'on-services__count', Number(service.count || 0).toLocaleString()));
      chip.setAttribute('aria-pressed', String(state.filter === service.id));
      return chip;
    });
    holder.replaceChildren(...chips);
    holder.hidden = false;
  }

  // Folded, the card shows one row of posters however wide the column is, or four rows on a phone.
  const TILE_MIN = 112;
  const TILE_GAP = 14;
  const PHONE = '(max-width: 640px)';
  function firstShown(list) {
    if (window.matchMedia && window.matchMedia(PHONE).matches) return 4;
    const width = list.clientWidth || list.parentElement?.clientWidth || 0;
    if (!width) return FIRST_SHOWN;
    const columns = Math.max(1, Math.floor((width + TILE_GAP) / (TILE_MIN + TILE_GAP)));
    return columns <= 2 ? 4 : columns;
  }

  function renderList(card) {
    const list = $('onYourServicesList');
    const more = $('onYourServicesMore');
    if (!list || !card) return;
    renderFilters(card);
    const items = filtered(card);
    const fold = firstShown(list);
    state.fold = fold;
    const shown = state.expanded ? items : items.slice(0, fold);
    list.replaceChildren(...shown.map(tile));
    list.hidden = !shown.length;
    if (more) {
      const extra = items.length - fold;
      more.hidden = extra <= 0;
      more.textContent = state.expanded ? 'Show fewer' : `Show all ${items.length.toLocaleString()}`;
      more.setAttribute('aria-expanded', String(state.expanded));
    }
  }

  function summaryFor(card) {
    const names = serviceNames(card.chosen || []);
    const parts = [];
    if (card.total) {
      parts.push(`${plural(card.total, 'title', 'titles')} on your list ${card.total === 1 ? 'is' : 'are'} streaming on ${names}.`);
      if (card.new) parts.push(`${card.new === 1 ? 'One' : card.new} arrived in the last two weeks.`);
    } else {
      parts.push(`Nothing on your list is streaming on ${names} right now.`);
      if (card.alerts) parts.push('We’ll tell you when something arrives.');
    }
    if (card.pending && card.pending <= PENDING_SOON) {
      parts.push(`Still checking ${plural(card.pending, 'title', 'titles')}, so more may turn up within the hour.`);
    } else if (card.pending) {
      // The server looks titles up a few dozen an hour, shared between members, so a big list takes a while.
      parts.push(`Still checking ${plural(card.pending, 'title', 'titles')}. We look them up a few dozen an hour, so more will turn up through the day.`);
    }
    return parts.join(' ');
  }

  // ------------------------------------------------ the share link

  const SHARE_PATH = /^\/on-my-services\/[A-Za-z0-9_-]{16,32}$/;

  function funnel(name) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event: name })], { type: 'application/json' }));
      }
    } catch (error) { /* counting only */ }
  }

  async function shareLink(path) {
    if (!SHARE_PATH.test(path || '')) return;
    const url = `${window.location.origin}${path}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: 'What I can stream tonight', url });
        funnel('svc_link_shared');
      } catch (error) { /* closed the share sheet */ }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      setStatus('Link copied. Anyone with it sees the titles on this card and the services they’re on.');
      funnel('svc_link_shared');
    } catch (error) {
      setStatus(`Copy this link: ${url}`);
    }
  }

  async function saveStory(path, control) {
    if (!SHARE_PATH.test(path || '')) return;
    control.disabled = true;
    setStatus('Getting your image ready…');
    try {
      const response = await fetch(`${path}/story.png`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error(String(response.status));
      const blob = await response.blob();
      const file = typeof File === 'function' ? new File([blob], 'omnitrackr-on-my-services.png', { type: 'image/png' }) : null;
      funnel('svc_link_shared');
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        try { await navigator.share({ files: [file] }); setStatus(''); } catch (error) {
          setStatus(error && error.name === 'AbortError' ? '' : 'Sharing didn’t open, so try again or long-press the image.');
        }
      } else {
        const link = el('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'omnitrackr-on-my-services.png';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(link.href), 4000);
        setStatus('Image saved. Add it to a story and put the link on it.');
      }
    } catch (error) {
      setStatus('The image didn’t load. Try again in a minute.');
    } finally {
      control.disabled = false;
    }
  }

  async function shareCall(path, control) {
    if (state.busy) return null;
    state.busy = true;
    if (control) control.disabled = true;
    const epoch = state.epoch;
    try {
      const data = await send('POST', path);
      if (epoch !== state.epoch || !state.card) return null;
      state.card.share = data.share || null;
      renderShare(state.card);
      return data.share || null;
    } catch (error) {
      setStatus(error.message);
      return null;
    } finally {
      state.busy = false;
      if (control && control.isConnected) control.disabled = false;
    }
  }

  // "Your anime stays off it, because that shelf is private or hidden." when the link leaves a format out.
  function leftOut(share) {
    const kinds = Array.isArray(share.left_out) ? share.left_out.filter(kind => KIND_WORDS[kind]) : [];
    if (!kinds.length) return '';
    const words = kinds.map(kind => KIND_WORDS[kind][1]);
    const stay = kinds.length === 1 && kinds[0] === 'anime' ? 'stays' : 'stay';
    return ` Your ${andList(words)} ${stay} off it, because ${kinds.length === 1 ? 'that shelf is' : 'those shelves are'} private or hidden.`;
  }

  function renderShare(card) {
    const box = $('onYourServicesShare');
    const privacy = $('onYourServicesPrivacy');
    // In the asking state the server only sends a link that's already out (services were cleared).
    const share = card ? card.share || null : null;
    const linked = Boolean(share && SHARE_PATH.test(share.path || ''));
    if (privacy) {
      privacy.textContent = linked
        ? 'Only you can see which services you pick. Your share link shows the ones your titles are on.'
        : 'Only you can see which services you pick.';
    }
    if (!box) return;
    // Nothing to offer until there are a few titles to show, unless a link is already out there.
    if (!share || (!linked && !share.allowed)) {
      box.hidden = true;
      box.replaceChildren();
      return;
    }
    const copy = el('div', 'on-services__share-copy');
    const row = el('div', 'on-services__share-actions');
    if (linked && !share.allowed) {
      copy.append(el('p', 'on-services__share-title', 'Your share link is paused'),
        el('p', 'on-services__share-text', share.reason === 'services'
          ? 'You have no services picked, so anyone who opens the link sees that it isn’t shared anymore. Pick them again and the same link works.'
          : 'Fewer than three titles from your list are on your services right now, so anyone who opens the link sees that it isn’t shared anymore. It comes back by itself when there are three again.'));
    } else if (linked) {
      const opened = Number(share.opened) || 0;
      copy.append(el('p', 'on-services__share-title', 'This list is shared by link'),
        el('p', 'on-services__share-text', `Friends see the titles here and which services they’re on, never your scores or the rest of your library.${leftOut(share)} They can tick their own services to see what they can watch too.${opened ? ` Opened ${plural(opened, 'time', 'times')} so far.` : ''}`));
      row.append(
        button('on-services__btn on-services__btn--primary', navigator.share ? 'Share link' : 'Copy link', () => shareLink(share.path)),
        button('on-services__btn', 'Save image for stories', control => saveStory(share.path, control)));
      const open = el('a', 'on-services__quiet', 'Open the page');
      open.href = share.path;
      row.appendChild(open);
    } else {
      copy.append(el('p', 'on-services__share-title', 'Show friends what you can stream tonight'),
        el('p', 'on-services__share-text', `Get a link to this list. Friends see the titles and which services they’re on, never your scores or the rest of your library, and can check which ones they can watch too.${leftOut(share)}`));
      row.appendChild(button('on-services__btn on-services__btn--primary', 'Get a share link', async control => {
        const made = await shareCall('/api/streaming/share', control);
        if (!made) return;
        setStatus('Your link is ready.');
        $('onYourServicesShare')?.querySelector('.on-services__share-actions button')?.focus({ preventScroll: true });
      }));
    }
    if (linked) {
      row.appendChild(button('on-services__quiet', 'Turn off', async control => {
        const ended = await shareCall('/api/streaming/share/off', control);
        if (ended) setStatus('The link is off. Anyone who opens it now sees that it isn’t shared anymore.');
      }));
    }
    box.replaceChildren(copy, row);
    box.hidden = false;
  }

  // ------------------------------------------------ the card

  function render(card) {
    const section = $('onYourServices');
    if (!section) return;
    state.card = card || null;
    window.clearTimeout(state.retryTimer);
    if (!card) {
      section.hidden = true;
      section.dataset.status = '';
      renderShare(null);
      return;
    }
    const choosing = card.state === 'choose';
    section.dataset.status = choosing ? 'choose' : (card.new ? 'new' : 'list');
    setText('onYourServicesEyebrow', choosing ? 'New: your streaming services'
      : (card.new ? `${plural(card.new, 'arrival', 'arrivals')} on your services` : 'Streaming tonight'));
    setText('onYourServicesTitle', choosing ? 'What can you stream tonight?' : 'On your services');
    setText('onYourServicesSummary', choosing
      ? `Pick the services you have, and we’ll show which of the ${plural(card.tracked, 'title', 'titles')} you haven’t finished (${kindWords(card.kinds)}) you can watch on them right now. When another one arrives, we’ll tell you.`
      : summaryFor(card));
    section.hidden = false;
    const editing = choosing || state.editing;
    show('onYourServicesPicker', editing);
    if (editing) renderPicker(card); else closePicker();
    const edit = $('onYourServicesEdit');
    if (edit) {
      edit.hidden = choosing;
      edit.setAttribute('aria-expanded', String(state.editing));
      edit.textContent = state.editing ? 'Close' : 'Edit services';
    }
    show('onYourServicesLater', choosing);
    show('onYourServicesStop', choosing);
    show('onYourServicesHide', !choosing);
    renderShare(card);
    if (choosing) {
      show('onYourServicesFilters', false);
      show('onYourServicesList', false);
      show('onYourServicesMore', false);
      show('onYourServicesEmpty', false);
    } else {
      renderList(card);
      setText('onYourServicesEmpty', card.total ? '' : 'Films, shows and anime you save show up here once they stream on one of these. Rentals and purchases don’t count.');
      show('onYourServicesEmpty', !card.total && !card.pending);
      if (card.pending && state.retries < RETRY_DELAYS.length) {
        const epoch = state.epoch;
        state.retryTimer = window.setTimeout(() => {
          if (epoch !== state.epoch || state.editing) return;
          state.retries += 1;
          refresh(true);
        }, RETRY_DELAYS[state.retries]);
      }
    }
    const notice = card.tmdb_notice ? ' This product uses the TMDB API but is not endorsed or certified by TMDB.' : '';
    setText('onYourServicesCredit', `${card.credit || ''}${notice}`);
    section.hidden = false;
    watchSeen(section, choosing ? 'seen_choose' : 'seen_list');
    arrivedFromLink(section);
  }

  // Counted once a visit, the first time the card is actually on screen.
  function watchSeen(section, name) {
    if (state.seen.has(name)) return;
    if (typeof IntersectionObserver !== 'function') { state.seen.add(name); event(name); return; }
    if (state.observer) state.observer.disconnect();
    state.observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting) || state.seen.has(name)) return;
      state.seen.add(name);
      event(name);
      state.observer.disconnect();
    }, { threshold: 0.4 });
    state.observer.observe(section);
  }

  // /#on-your-services from the bell, a push or the weekly email: bring the card into view.
  function arrivedFromLink(section) {
    if (state.hashDone || window.location.hash !== HASH) return;
    state.hashDone = true;
    event('from_alert');
    window.OmniHomeLayout?.reveal?.(section);
    window.requestAnimationFrame?.(() => section.scrollIntoView?.({ block: 'start' }));
  }

  function refresh(force = false) {
    if (!signedIn()) return Promise.resolve();
    if (state.editing || state.busy) return state.request || Promise.resolve();
    if (!force && state.request && Date.now() - state.loadedAt < REFRESH_GAP_MS) return state.request;
    const epoch = state.epoch;
    state.loadedAt = Date.now();
    const request = fetch(`${apiBase()}/api/streaming`, fetchOptions({ headers: { Accept: 'application/json' } }))
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (!data || epoch !== state.epoch || !signedIn() || state.editing) return;
        state.chosen = Array.isArray(data.chosen) ? data.chosen : [];
        render(data.card);
        syncLibraryFilters();
      })
      .catch(() => { /* Optional card; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function reset() {
    state.epoch += 1;
    state.card = null;
    state.chosen = [];
    state.request = null;
    state.loadedAt = 0;
    state.filter = '';
    state.expanded = false;
    state.busy = false;
    state.retries = 0;
    state.seen.clear();
    state.filterCounted = false;
    closePicker();
    window.clearTimeout(state.retryTimer);
    if (state.observer) state.observer.disconnect();
    const section = $('onYourServices');
    if (section) { section.hidden = true; section.dataset.status = ''; }
    ['onYourServicesList', 'onYourServicesFilters', 'onYourServicesShare'].forEach(id => $(id)?.replaceChildren());
    show('onYourServicesShare', false);
    setStatus('');
    syncLibraryFilters();
  }

  // ------------------------------------------------ the library filter

  function renderLibraryFilter(category, host) {
    if (!host || !VIDEO.includes(category)) return;
    const reset = host.querySelector('.library-filter-reset');
    let field = host.querySelector('.library-filter-streaming');
    const active = typeof getLibraryFilters === 'function' && Boolean(getLibraryFilters(category).onServices);
    if (!state.chosen.length && !active) {
      if (field) field.hidden = true;
      return;
    }
    if (!field) {
      field = el('label', 'library-filter-option library-filter-streaming');
      const input = el('input');
      input.type = 'checkbox';
      input.dataset.streamingFilter = category;
      input.addEventListener('change', () => {
        if (typeof applyLibraryFilters !== 'function' || !applyLibraryFilters(category, { onServices: input.checked })) {
          input.checked = typeof getLibraryFilters === 'function' && Boolean(getLibraryFilters(category).onServices);
          return;
        }
        if (input.checked && !state.filterCounted) { state.filterCounted = true; event('filter'); }
      });
      field.append(input, el('span', '', 'On my services'));
      host.insertBefore(field, reset || null);
    }
    field.hidden = false;
    field.title = state.chosen.length ? `Streaming on ${andList(state.chosen)}` : '';
    field.querySelector('input').checked = active;
  }

  function syncLibraryFilters() {
    if (typeof libraryPageConfig !== 'function') return;
    VIDEO.forEach(category => {
      const config = libraryPageConfig(category);
      const host = config && $(`${config[0]}Filters`);
      if (host && host.childElementCount) renderLibraryFilter(category, host);
    });
  }

  // ------------------------------------------------ wiring

  function start() {
    $('onYourServicesPicker')?.addEventListener('submit', save);
    $('onYourServicesEdit')?.addEventListener('click', () => {
      state.editing = !state.editing;
      if (!state.editing) closePicker();
      render(state.card);
      if (state.editing) $('onYourServicesPicker')?.querySelector('input')?.focus();
    });
    $('onYourServicesCancel')?.addEventListener('click', () => {
      closePicker();
      render(state.card);
      $('onYourServicesEdit')?.focus();
    });
    $('onYourServicesMore')?.addEventListener('click', () => {
      state.expanded = !state.expanded;
      renderList(state.card);
    });
    // The home column can change width after the first render (the side rail fills in, fonts
    // load, the window is resized), so the one-row fold is worked out again when it does.
    let resizeTimer = 0;
    const refold = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        const list = $('onYourServicesList');
        if (!state.card || state.card.state !== 'list' || state.expanded || !list || list.hidden) return;
        if (list.contains(document.activeElement)) return;
        if (firstShown(list) !== state.fold) renderList(state.card);
      }, 120);
    };
    const section = $('onYourServices');
    if (section && 'ResizeObserver' in window) new ResizeObserver(refold).observe(section);
    else window.addEventListener('resize', refold);
    $('onYourServicesLater')?.addEventListener('click', () => answer('later'));
    $('onYourServicesStop')?.addEventListener('click', () => answer('stop'));
    $('onYourServicesHide')?.addEventListener('click', () => answer('hide'));
    window.addEventListener('hashchange', () => {
      if (window.location.hash !== HASH) return;
      state.hashDone = false;
      // A hidden card comes back when a note or email links to it.
      if (!state.card) answer('show'); else arrivedFromLink($('onYourServices'));
    });
    if (window.location.hash === HASH && signedIn()) {
      send('POST', '/api/streaming/answer', { answer: 'show' }).catch(() => {}).finally(() => refresh(true));
    } else {
      refresh();
    }
  }

  window.OmniStreaming = { refresh, reset, renderFilters: renderLibraryFilter, get chosen() { return state.chosen.slice(); } };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { render, summaryFor, serviceNames, kindWords, filtered, state, renderLibraryFilter, renderShare, leftOut };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
