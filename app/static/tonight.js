// Group polls (/tonight, /tonight/<token>): make a "what should we watch tonight?" poll and vote on it.
// Everything a member or visitor typed is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  const KINDS = [['movie', 'Movie'], ['tv', 'TV show'], ['anime', 'Anime'], ['game', 'Game'], ['book', 'Book'],
    ['album', 'Album'], ['manga', 'Manga'], ['podcast', 'Podcast'],
    ['audiobook', 'Audiobook']];
  const KIND_LABELS = new Map(KINDS);
  const NAME_KEY = 'omnitrackr_poll_name';
  // A shortlist that isn't a poll yet. It lives in this browser only: a visitor builds one before
  // signing up, and other pages (a shared list) can hand one over the same way.
  const DRAFT_KEY = 'omnitrackr_poll_draft';
  const DRAFT_DAYS = 7;
  const DRAFT_MAX = 8;
  const HOURS = [1, 3, 6, 24, 72];
  const FILL_TO = 4;
  const SLUG = /^[a-z0-9-]{1,130}$/;

  // ------------------------------------------------------------------ pure helpers (also used by tests)

  function keyOf(item) {
    return `${item.kind}|${String(item.title).trim().toLowerCase()}|${item.year || ''}`;
  }

  function cleanOption(item) {
    if (!item || !KIND_LABELS.has(item.kind) || typeof item.title !== 'string') return null;
    const title = item.title.replace(/\s+/g, ' ').trim().slice(0, 200);
    if (!title) return null;
    const year = Number.isInteger(item.year) && item.year >= 1800 && item.year <= 2100 ? item.year : null;
    const image = typeof item.image === 'string' && /^https:\/\//.test(item.image) && item.image.length <= 500 ? item.image : null;
    return { kind: item.kind, label: KIND_LABELS.get(item.kind), title, year,
      slug: typeof item.slug === 'string' && SLUG.test(item.slug) ? item.slug : null, image };
  }

  // A stored draft, checked field by field, or null when there is nothing usable.
  function parseDraft(text, now) {
    let data;
    try { data = JSON.parse(text); } catch (error) { return null; }
    if (!data || typeof data !== 'object' || !Array.isArray(data.options)) return null;
    if (!Number.isFinite(data.at) || data.at > now || now - data.at > DRAFT_DAYS * 86400000) return null;
    const options = [];
    const seen = new Set();
    data.options.forEach(item => {
      const option = cleanOption(item);
      if (!option || seen.has(keyOf(option)) || options.length >= DRAFT_MAX) return;
      seen.add(keyOf(option));
      options.push(option);
    });
    const question = typeof data.question === 'string' ? data.question.slice(0, 120) : '';
    if (!options.length && !question.trim()) return null;
    return { at: data.at, question, hours: HOURS.includes(data.hours) ? data.hours : 3, options,
      waiting: data.waiting === true, from: typeof data.from === 'string' ? data.from.slice(0, 80) : '' };
  }

  // Titles to add so a shortlist reaches four: one kind only, so a film isn't up against a ten-hour series.
  function fillChoice(pool, picked, max) {
    const room = Math.min(max, Math.max(FILL_TO, picked.length + 1)) - picked.length;
    if (room <= 0) return [];
    const taken = new Set(picked.map(keyOf));
    const open = pool.filter(item => !taken.has(keyOf(item)));
    if (!open.length) return [];
    const counts = new Map();
    (picked.length ? picked : open).forEach(item => counts.set(item.kind, (counts.get(item.kind) || 0) + 1));
    let kind = null;
    counts.forEach((count, name) => { if (kind === null || count > counts.get(kind)) kind = name; });
    const same = open.filter(item => item.kind === kind);
    return (same.length ? same : open).slice(0, room);
  }

  function shareLinks(url, question) {
    const line = `${question} Vote here: ${url}`;
    return [
      ['WhatsApp', `https://wa.me/?text=${encodeURIComponent(line)}`],
      ['Text message', `sms:?&body=${encodeURIComponent(line)}`],
      ['Email', `mailto:?subject=${encodeURIComponent(question)}&body=${encodeURIComponent(line)}`],
    ];
  }

  function shuffled(list) {
    const copy = list.slice();
    for (let index = copy.length - 1; index > 0; index -= 1) {
      const other = Math.floor(Math.random() * (index + 1));
      [copy[index], copy[other]] = [copy[other], copy[index]];
    }
    return copy;
  }

  const helpers = { keyOf, cleanOption, parseDraft, fillChoice, shareLinks, DRAFT_KEY };
  if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ page helpers

  const reported = new Set();
  function report(event) {
    if (reported.has(event)) return;
    reported.add(event);
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  }

  document.addEventListener('click', event => {
    if (!event.target.closest) return;
    if (event.target.closest('[data-tonight-signup]')) report('tonight_poll_signup_clicked');
  });

  function readDraft() {
    try { return parseDraft(localStorage.getItem(DRAFT_KEY) || '', Date.now()); } catch (error) { return null; }
  }

  function writeDraft(draft) {
    try {
      if (draft) localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      else localStorage.removeItem(DRAFT_KEY);
      return true;
    } catch (error) {
      return false;
    }
  }

  const root = document.getElementById('tonightApp');
  if (!root) return;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function button(label, className, onClick) {
    const node = el('button', className, label);
    node.type = 'button';
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  function safeUrl(value) {
    return typeof value === 'string' && /^https:\/\//.test(value) ? value : null;
  }

  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', credentials: 'same-origin', headers: {} };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    if (response.status === 401 && options.member) {
      window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#login`;
      throw new Error('Please log in again.');
    }
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      if (response.status === 429 && !detail) throw new Error('Slow down a little and try again in a minute.');
      throw new Error((detail || 'Something went wrong. Please try again.').replace(/^Value error, /, ''));
    }
    return data;
  }

  function art(item, className) {
    const frame = el('span', className || 'tn-art');
    const fallback = () => frame.replaceChildren(el('span', 'tn-art__empty', (item.title || '?').slice(0, 1).toUpperCase()));
    if (item.image) {
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

  function meta(item) {
    return [item.label, item.year].filter(Boolean).join(' · ');
  }

  async function copyLink(url, buttonNode, statusNode) {
    try {
      await navigator.clipboard.writeText(url);
      const label = buttonNode.textContent;
      buttonNode.textContent = 'Link copied ✓';
      setTimeout(() => { buttonNode.textContent = label; }, 2200);
    } catch (error) {
      if (statusNode) statusNode.textContent = `Copy this link: ${url}`;
    }
  }

  async function share(url, text, buttonNode, statusNode) {
    report('tonight_poll_shared');
    if (navigator.share) {
      try {
        await navigator.share({ title: text, text, url });
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    copyLink(url, buttonNode, statusNode);
  }

  // The ways a poll link usually travels: the phone's share sheet, a copied link, or straight into a chat.
  function shareRow(url, question, statusNode, lead) {
    const row = el('div', 'tn-share');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', 'Share the poll');
    if (navigator.share) {
      const native = button(lead || 'Share the link', 'button tn-share__main', () => share(url, question, native, statusNode));
      row.appendChild(native);
    }
    const copy = button('Copy link', navigator.share ? 'tn-pill' : 'button tn-share__main', () => {
      report('tonight_poll_shared');
      copyLink(url, copy, statusNode);
    });
    row.appendChild(copy);
    shareLinks(url, question).forEach(([label, href]) => {
      const link = el('a', 'tn-pill', label);
      link.href = href;
      if (href.startsWith('https://')) {
        link.target = '_blank';
        link.rel = 'noopener';
      }
      link.addEventListener('click', () => report('tonight_poll_shared'));
      row.appendChild(link);
    });
    return row;
  }

  // ------------------------------------------------------------------ making a poll

  function makeView() {
    const guest = root.dataset.guest === '1';
    const form = root.querySelector('[data-tonight-make]');
    const pickedNode = root.querySelector('[data-tonight-picked]');
    const countNode = root.querySelector('[data-tonight-count]');
    const suggestNode = root.querySelector('[data-tonight-suggest]');
    const friendsNode = root.querySelector('[data-tonight-friends]');
    const draftNode = root.querySelector('[data-tonight-draft]');
    const previewNode = root.querySelector('[data-tonight-preview]');
    const search = root.querySelector('#tnSearch');
    const results = root.querySelector('[data-tonight-results]');
    const wildcard = root.querySelector('[data-tonight-wildcard]');
    const fill = root.querySelector('[data-tonight-fill]');
    const submit = form.querySelector('.tn-make__go');
    const status = form.querySelector('[data-tonight-status]');
    const mineNode = root.querySelector('[data-tonight-mine]');
    const sample = previewNode ? Array.from(previewNode.childNodes) : [];
    let max = 8;
    let pool = [];
    // True once the visitor pressed Get the link: the poll they make after signing up counts as one that came through.
    let waiting = false;
    let restoring = false;
    const picked = [];
    const suggestButtons = new Map();

    function has(item) {
      return picked.some(entry => entry.key === keyOf(item));
    }

    function syncSuggestions() {
      suggestButtons.forEach((node, key) => node.setAttribute('aria-pressed', String(picked.some(entry => entry.key === key))));
    }

    function saveDraft(pressed) {
      if (restoring) return;
      const question = form.question.value.trim();
      if (!picked.length && !question) {
        writeDraft(null);
        return;
      }
      if (pressed === true) waiting = true;
      // Once a member is back on this page the draft stops asking sign-in to return here.
      writeDraft({ at: Date.now(), question, hours: Number(form.hours.value), waiting: guest && waiting,
        options: picked.map(item => ({ kind: item.kind, title: item.title, year: item.year || null, slug: item.slug || null,
          image: item.image || null })) });
    }

    // What the group will see, drawn from the shortlist so far (visitors only; members see their polls there).
    function drawPreview() {
      if (!previewNode) return;
      if (!picked.length) {
        previewNode.replaceChildren(...sample);
        return;
      }
      const figure = el('figure', 'tn-sample tn-sample--live');
      figure.appendChild(el('p', 'tn-sample__q', form.question.value.trim() || defaultQuestion()));
      const list = el('ul');
      picked.forEach(item => {
        const row = el('li', 'tn-sample__row tn-sample__row--art');
        row.appendChild(art(item, 'tn-art tn-art--small'));
        const title = el('span', 'tn-sample__title');
        title.appendChild(el('strong', null, item.title));
        title.appendChild(el('small', null, meta(item)));
        row.appendChild(title);
        row.appendChild(el('span', 'tn-sample__votes', '0 votes'));
        list.appendChild(row);
      });
      figure.appendChild(list);
      figure.appendChild(el('figcaption', null, picked.length < 2
        ? 'Add one more and it\'s ready to send.'
        : 'Ready to send. Bars fill in as votes arrive.'));
      previewNode.replaceChildren(figure);
    }

    function defaultQuestion() {
      const verbs = new Set(picked.map(item => ({ movie: 'watch', tv: 'watch', anime: 'watch', game: 'play', book: 'read',
        album: 'play', manga: 'read', podcast: 'play', audiobook: 'play' })[item.kind] || 'start'));
      return verbs.size === 1 ? `What should we ${[...verbs][0]} tonight?` : 'What should we start tonight?';
    }

    function draw() {
      pickedNode.replaceChildren();
      if (picked.length) {
        const list = el('ol', 'tn-picked__list');
        picked.forEach((item, index) => {
          const row = el('li', 'tn-picked__item');
          row.appendChild(art(item, 'tn-art tn-art--small'));
          const text = el('span', 'tn-picked__text');
          text.appendChild(el('strong', null, item.title));
          text.appendChild(el('small', null, meta(item)));
          row.appendChild(text);
          const remove = button('', 'tn-remove', () => {
            picked.splice(index, 1);
            draw();
          });
          remove.setAttribute('aria-label', `Take ${item.title} off the poll`);
          remove.textContent = '✕';
          row.appendChild(remove);
          list.appendChild(row);
        });
        pickedNode.appendChild(list);
      }
      const left = max - picked.length;
      countNode.textContent = picked.length < 2
        ? `Pick ${2 - picked.length} more to start. Up to ${max} in all.`
        : (left > 0 ? `${picked.length} picked. Room for ${left} more.` : `${max} picked, the most a poll holds.`);
      submit.disabled = picked.length < 2;
      if (fill) fill.hidden = picked.length >= FILL_TO || picked.length >= max;
      syncSuggestions();
      drawPreview();
      saveDraft();
    }

    function add(item, quiet) {
      if (has(item)) {
        if (!quiet) status.textContent = `${item.title} is already on the poll.`;
        return false;
      }
      if (picked.length >= max) {
        if (!quiet) status.textContent = `A poll holds up to ${max} titles.`;
        return false;
      }
      picked.push(Object.assign({}, item, { key: keyOf(item) }));
      if (guest) report('tonight_poll_draft_started');
      if (!quiet) {
        status.textContent = '';
        draw();
      }
      return true;
    }

    function toggle(item) {
      const index = picked.findIndex(entry => entry.key === keyOf(item));
      if (index >= 0) {
        picked.splice(index, 1);
        draw();
      } else {
        add(item);
      }
    }

    function suggestionGroup(heading, titles) {
      const group = el('div', 'tn-suggest__group');
      group.appendChild(el('p', 'tn-suggest__heading', heading));
      const list = el('ul', 'tn-chips');
      titles.forEach(item => {
        const li = el('li');
        const chip = button('', 'tn-chip', () => toggle(item));
        chip.setAttribute('aria-pressed', 'false');
        chip.appendChild(art(item, 'tn-art tn-art--chip'));
        const text = el('span', 'tn-chip__text');
        text.appendChild(el('strong', null, item.title));
        text.appendChild(el('small', null, meta(item)));
        chip.appendChild(text);
        suggestButtons.set(keyOf(item), chip);
        li.appendChild(chip);
        list.appendChild(li);
      });
      group.appendChild(list);
      return group;
    }

    // A shortlist from before: built before signing up, handed over by a shared list, or left unfinished.
    function restoreDraft() {
      const draft = readDraft();
      if (!draft) return;
      restoring = true;
      draft.options.forEach(option => {
        // A title that is also in the member's library goes on as their copy, with its own cover.
        const own = pool.find(item => keyOf(item) === keyOf(option));
        add(own || option, true);
      });
      if (draft.question) form.question.value = draft.question;
      form.hours.value = String(draft.hours);
      waiting = draft.waiting;
      restoring = false;
      if (!picked.length) return;
      if (draftNode && !guest) {
        draftNode.replaceChildren(el('span', null, draft.from
          ? `${picked.length} titles from ${draft.from} are on the poll. Take off any you don't want, then make it.`
          : (picked.length >= 2 ? 'Your shortlist is back. Press Make the poll and the link is yours.'
            : 'Your shortlist is back. Add one more title and it\'s ready.')));
        draftNode.appendChild(button('Start over', 'tn-link-button', () => {
          picked.length = 0;
          form.reset();
          waiting = false;
          draftNode.hidden = true;
          draw();
        }));
        draftNode.hidden = false;
      }
      draw();
      if (waiting && !guest && picked.length >= 2) {
        submit.scrollIntoView({ block: 'center' });
        submit.focus({ preventScroll: true });
      }
    }

    const loading = guest
      ? api('/api/tonight/starters').then(data => {
        max = data.options_max || max;
        pool = data.titles || [];
        suggestNode.replaceChildren();
        if (pool.length) suggestNode.appendChild(suggestionGroup('Popular with members', pool.slice(0, 12)));
        else suggestNode.appendChild(el('p', 'tn-muted', 'Search for any movie, show, game or book below.'));
      })
      : api('/api/tonight/suggestions', { member: true }).then(data => {
        max = data.options_max || max;
        pool = data.titles || [];
        suggestNode.replaceChildren();
        const queue = pool.filter(item => item.source === 'Next Up');
        const library = pool.filter(item => item.source !== 'Next Up');
        if (queue.length) suggestNode.appendChild(suggestionGroup('From your Next Up', queue));
        if (library.length) suggestNode.appendChild(suggestionGroup(queue.length ? 'Also in your library' : 'From your library', library));
        if (!pool.length) {
          suggestNode.appendChild(el('p', 'tn-muted', 'Titles you add to your library or Next Up show up here. For now, search for anything below.'));
        }
        if (data.friends && data.friends.length) {
          friendsNode.hidden = false;
          const box = el('details', 'tn-friends__box');
          box.appendChild(el('summary', null, 'Ask friends on OmniTrackr to vote'));
          box.appendChild(el('p', 'tn-muted', 'They get a notification with the link. Anyone else can vote from the link you share.'));
          const list = el('ul', 'tn-friends__list');
          data.friends.forEach(friend => {
            const li = el('li');
            const label = el('label', 'tn-check');
            const input = el('input');
            input.type = 'checkbox';
            input.value = String(friend.id);
            input.name = 'friend';
            label.appendChild(input);
            label.appendChild(el('span', null, friend.username));
            li.appendChild(label);
            list.appendChild(li);
          });
          box.appendChild(list);
          friendsNode.replaceChildren(box);
        }
      });
    loading.catch(error => {
      suggestNode.replaceChildren(el('p', 'tn-muted', error.message));
    }).then(() => {
      restoreDraft();
      draw();
    });

    form.question.addEventListener('input', () => {
      drawPreview();
      saveDraft();
    });
    form.hours.addEventListener('change', () => saveDraft());

    // Search over titles members track, then a by-name fallback for anything else.
    let timer = null;
    let ticket = 0;
    function showManual(query) {
      const li = el('li', 'tn-manual');
      li.appendChild(el('span', 'tn-muted', `Not here? Add “${query}” as`));
      const kind = el('select');
      kind.setAttribute('aria-label', 'What kind of title it is');
      KINDS.forEach(([value, label]) => {
        const option = el('option', null, label);
        option.value = value;
        kind.appendChild(option);
      });
      li.appendChild(kind);
      li.appendChild(button('Add', 'tn-small-button', () => {
        const label = KIND_LABELS.get(kind.value);
        if (add({ kind: kind.value, label, title: query, year: null, image: null })) {
          search.value = '';
          results.hidden = true;
          search.focus();
        }
      }));
      results.appendChild(li);
    }
    search.addEventListener('input', () => {
      clearTimeout(timer);
      const query = search.value.trim();
      if (query.length < 2) {
        results.hidden = true;
        results.replaceChildren();
        return;
      }
      timer = setTimeout(async () => {
        const mine = ++ticket;
        let data;
        try {
          const response = await fetch(`/api/titles/search?q=${encodeURIComponent(query.slice(0, 80))}`, { credentials: 'same-origin' });
          data = await response.json();
        } catch (error) {
          return;
        }
        if (mine !== ticket) return;
        results.replaceChildren();
        (data.results || []).slice(0, 6).forEach(result => {
          const li = el('li');
          const pick = button('', 'tn-result', () => {
            if (add({ kind: result.kind, label: result.label, title: result.title, year: result.year, slug: result.slug, image: result.image })) {
              search.value = '';
              results.hidden = true;
              search.focus();
            }
          });
          pick.appendChild(art(result, 'tn-art tn-art--chip'));
          const text = el('span', 'tn-chip__text');
          text.appendChild(el('strong', null, result.title));
          text.appendChild(el('small', null, meta(result)));
          pick.appendChild(text);
          pick.appendChild(el('span', 'tn-result__add', 'Add'));
          li.appendChild(pick);
          results.appendChild(li);
        });
        showManual(query.slice(0, 200));
        results.hidden = false;
      }, 220);
    });
    search.addEventListener('keydown', event => {
      if (event.key === 'Enter') event.preventDefault();
    });

    // Up to four of one kind, from Next Up and the library (members) or what's popular (visitors).
    if (fill) {
      fill.addEventListener('click', () => {
        const chosen = fillChoice(guest ? shuffled(pool) : pool, picked, max);
        if (!chosen.length) {
          status.textContent = guest ? 'Nothing left to suggest. Search for a title instead.'
            : 'Nothing unfinished left to suggest. Search for a title, or add a wildcard.';
          return;
        }
        chosen.forEach(item => add(item, true));
        status.textContent = `Added ${chosen.map(item => item.title).join(', ')}. Swap out any you don't want.`;
        draw();
      });
    }

    // A wildcard from Pick for me's editorial pool.
    let wildcards = null;
    wildcard.addEventListener('click', async () => {
      wildcard.disabled = true;
      try {
        if (!wildcards) wildcards = (await api('/api/pick/pool')).picks || [];
        const fresh = wildcards.filter(entry => !has({ kind: entry.kind, title: entry.title, year: entry.year }));
        if (!fresh.length) throw new Error('No wildcards left to add.');
        const entry = fresh[Math.floor(Math.random() * fresh.length)];
        if (add({ kind: entry.kind, label: entry.label, title: entry.title, year: entry.year, slug: entry.slug, image: entry.image })) {
          status.textContent = `Added ${entry.title}. ${entry.why || ''}`.trim();
        }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        wildcard.disabled = false;
      }
    });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (picked.length < 2) return;
      if (guest) {
        // The shortlist waits in this browser; signing up comes back here with it filled in.
        saveDraft(true);
        report('tonight_poll_draft_signup');
        window.location.href = '/?next=%2Ftonight#signup';
        return;
      }
      submit.disabled = true;
      status.textContent = 'Making your poll…';
      const options = picked.map(item => (item.category && item.item_id
        ? { category: item.category, item_id: item.item_id }
        : { kind: item.kind, title: item.title, year: item.year || null, slug: item.slug || null }));
      const friendIds = Array.from(form.querySelectorAll('input[name="friend"]:checked')).map(input => Number(input.value));
      try {
        const data = await api('/api/tonight', { method: 'POST', member: true, body: {
          question: form.question.value, options, hours: Number(form.hours.value), friend_ids: friendIds,
        } });
        if (waiting) report('tonight_poll_draft_sent');
        waiting = false;
        ready(data);
        picked.length = 0;
        form.reset();
        if (draftNode) draftNode.hidden = true;
        draw();
        loadMine();
      } catch (error) {
        status.textContent = error.message;
        submit.disabled = false;
      }
    });

    function ready(data) {
      const panel = el('section', 'tn-ready');
      panel.setAttribute('aria-labelledby', 'tnReadyTitle');
      const text = el('div', 'tn-ready__text');
      const heading = el('h2', null, 'Your poll is ready');
      heading.id = 'tnReadyTitle';
      heading.tabIndex = -1;
      text.appendChild(heading);
      text.appendChild(el('p', null, data.asked
        ? `We let ${data.asked === 1 ? 'your friend' : `${data.asked} friends`} know. Send the link to everyone else.`
        : 'Send the link to whoever you\'re watching with. They can vote without an account.'));
      const link = el('input', 'tn-ready__link');
      link.type = 'text';
      link.readOnly = true;
      link.value = data.url;
      link.setAttribute('aria-label', 'Poll link');
      link.addEventListener('focus', () => link.select());
      text.appendChild(link);
      text.appendChild(shareRow(data.url, data.question, status));
      const open = el('a', 'tn-link-button tn-ready__open', 'Open the poll');
      open.href = data.path;
      text.appendChild(open);
      panel.appendChild(text);
      // The picture chat apps show under the link.
      const card = el('figure', 'tn-ready__card');
      const image = el('img');
      image.src = `${data.path}/card.png`;
      image.alt = `Preview card: ${data.question}`;
      image.width = 1200;
      image.height = 630;
      image.addEventListener('error', () => card.remove());
      card.appendChild(image);
      card.appendChild(el('figcaption', 'tn-muted', 'How the link looks in a chat.'));
      panel.appendChild(card);
      root.querySelector('.tn-ready')?.remove();
      form.before(panel);
      status.textContent = '';
      heading.focus();
    }

    async function loadMine() {
      if (!mineNode) return;
      let data;
      try {
        data = await api('/api/tonight', { member: true });
      } catch (error) {
        mineNode.replaceChildren(el('p', 'tn-muted', error.message));
        return;
      }
      mineNode.replaceChildren();
      if (!data.polls.length) {
        mineNode.appendChild(el('p', 'tn-muted', 'Polls you make show up here, with what\'s winning.'));
        return;
      }
      const list = el('ul', 'tn-cards');
      data.polls.forEach(poll => {
        const li = el('li');
        const link = el('a', 'tn-card');
        link.href = poll.url;
        if (poll.top) link.appendChild(art(poll.top, 'tn-art tn-art--card'));
        const text = el('span', 'tn-card__text');
        text.appendChild(el('strong', null, poll.question));
        let line;
        if (poll.closed) line = poll.top ? `${poll.top.title} won` : 'Closed with no votes';
        else if (poll.top) line = `${poll.top.title} is ahead`;
        else line = 'No votes yet';
        text.appendChild(el('span', 'tn-card__lead', line));
        text.appendChild(el('small', null, `${poll.total} vote${poll.total === 1 ? '' : 's'} · ${poll.options} titles · ${poll.closes_label}`));
        link.appendChild(text);
        li.appendChild(link);
        list.appendChild(li);
      });
      mineNode.appendChild(list);
    }

    loadMine();
  }

  // ------------------------------------------------------------------ voting

  function pollView() {
    const token = root.dataset.token;
    const signedIn = root.dataset.signedIn === '1';
    const board = root.querySelector('[data-tonight-board]');
    const status = root.querySelector('[data-tonight-status]');
    const eyebrow = root.querySelector('.tn-poll__head .eyebrow');
    const lead = root.querySelector('.tn-poll__lead');
    const nudge = document.querySelector('[data-tonight-nudge]');
    const ORDINALS = ['', '', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
    let state = null;
    let busy = false;
    let deleteArmed = false;
    let where = null;
    let whereAsked = false;
    let kept = null;

    function storedName() {
      try { return localStorage.getItem(NAME_KEY) || ''; } catch (error) { return ''; }
    }

    function rememberName(value) {
      try { localStorage.setItem(NAME_KEY, value); } catch (error) { /* optional */ }
    }

    async function run(work, message) {
      if (busy) return;
      busy = true;
      try {
        state = await work();
        draw();
        if (message) status.textContent = typeof message === 'function' ? message(state) : message;
      } catch (error) {
        status.textContent = error.message;
      } finally {
        busy = false;
      }
    }

    function voters(option) {
      const row = el('span', 'tn-voters');
      option.voters.forEach(person => {
        const chip = el('span', person.member ? 'tn-voter tn-voter--member' : 'tn-voter', person.you ? 'You' : person.name);
        row.appendChild(chip);
      });
      if (option.others) row.appendChild(el('span', 'tn-voter tn-voter--more', `+${option.others}`));
      return row;
    }

    // Where the winner streams, sells or lends. Service names come from our own lookups; links open in a new tab.
    function whereSection(data) {
      const groups = (Array.isArray(data.groups) ? data.groups : []).filter(group => (group.providers || []).length);
      const buy = (Array.isArray(data.buy) ? data.buy : []).filter(link => safeUrl(link.url));
      const searches = (Array.isArray(data.searches) ? data.searches : []).filter(link => safeUrl(link.url));
      const more = safeUrl(data.more);
      if (!groups.length && !buy.length && !searches.length && !more) return null;
      const section = el('div', 'tn-where');
      section.appendChild(el('h3', null, data.heading || 'Where to watch'));
      const track = () => report('tonight_poll_where_clicked');
      const chipList = (label, entries, rel) => {
        const line = el('div', 'tn-where__group');
        line.appendChild(el('span', 'tn-where__label', label));
        const list = el('ul');
        entries.slice(0, 6).forEach(entry => {
          const item = el('li');
          const url = safeUrl(entry.url);
          const chip = el(url ? 'a' : 'span', 'tn-where__chip');
          if (url) {
            chip.href = url;
            chip.target = '_blank';
            chip.rel = rel;
            chip.addEventListener('click', track);
          }
          const logo = safeUrl(entry.logo);
          if (logo) {
            const image = el('img');
            image.src = logo;
            image.alt = '';
            image.width = 22;
            image.height = 22;
            image.loading = 'lazy';
            image.referrerPolicy = 'no-referrer';
            chip.appendChild(image);
          }
          chip.appendChild(el('span', null, entry.name));
          item.appendChild(chip);
          list.appendChild(item);
        });
        line.appendChild(list);
        return line;
      };
      groups.slice(0, 3).forEach(group => section.appendChild(chipList(group.label, group.providers, 'noopener nofollow')));
      if (buy.length) section.appendChild(chipList('Buy a copy', buy, 'sponsored noopener'));
      if (!groups.length && searches.length) section.appendChild(chipList('Search', searches, 'noopener nofollow'));
      if (more) {
        const link = el('a', 'tn-where__more', groups.length ? 'Compare every service ↗' : 'Check JustWatch ↗');
        link.href = more;
        link.target = '_blank';
        link.rel = 'noopener nofollow';
        link.addEventListener('click', track);
        section.appendChild(link);
      }
      const notes = [];
      if (data.region && groups.length) notes.push(`Showing ${data.region} availability.`);
      const credits = (data.credits || []).map(credit => credit.name).filter(Boolean);
      if (credits.length) notes.push(`Data from ${credits.join(', ')}.`);
      if (data.tmdb_notice) notes.push('This product uses the TMDB API but is not endorsed or certified by TMDB.');
      if (buy.length && data.disclosure) notes.push(String(data.disclosure));
      if (notes.length) section.appendChild(el('p', 'tn-where__note', notes.join(' ')));
      return section;
    }

    function loadWhere() {
      if (whereAsked) return;
      whereAsked = true;
      api(`/api/tonight/${token}/where`).then(data => {
        where = data;
        const slot = board.querySelector('[data-tonight-where]');
        const section = whereSection(data);
        if (slot && section) slot.replaceChildren(section);
      }).catch(() => { /* the result reads fine without it */ });
    }

    function winnerPanel(option) {
      const panel = el('div', 'tn-winner');
      panel.appendChild(art(option, 'tn-art tn-art--winner'));
      const text = el('div', 'tn-winner__text');
      text.appendChild(el('p', 'eyebrow', 'THE GROUP PICKED'));
      text.appendChild(el('h2', null, option.title));
      text.appendChild(el('p', 'tn-muted', `${meta(option)} · ${option.votes} of ${state.total} vote${state.total === 1 ? '' : 's'}`));
      const row = el('div', 'tn-row');
      if (signedIn) {
        const save = button(kept || 'Add to Next Up', 'button', async () => {
          save.disabled = true;
          try {
            const result = await api(`/api/tonight/${token}/keep`, { method: 'POST', member: true, body: { queue: true } });
            kept = result.queued ? 'In your Next Up ✓' : 'Already in your Next Up';
            save.textContent = kept;
            status.textContent = result.state === 'created'
              ? `${result.title} is in your library and at the end of your Next Up.`
              : (result.queued ? `${result.title} is at the end of your Next Up.` : `${result.title} was already in your Next Up.`);
          } catch (error) {
            status.textContent = error.message;
            save.disabled = false;
          }
        });
        save.disabled = Boolean(kept);
        row.appendChild(save);
      } else if (option.url && window.OmniGuestList) {
        const slug = option.url.split('/').pop();
        const saved = () => window.OmniGuestList.read().some(item => item.kind === option.kind && item.slug === slug);
        const save = button(saved() ? 'Saved to your list ✓' : 'Save it for later', 'button', () => {
          if (!saved()) {
            const result = window.OmniGuestList.add(option.kind, slug, option.title);
            if (!result.added) {
              status.textContent = result.full ? 'Your list is full. Sign up to keep it and add more.'
                : 'Your browser didn\'t let us save that. Sign up and add it from the title page.';
              return;
            }
            report('tonight_poll_winner_saved');
          }
          save.textContent = 'Saved to your list ✓';
          save.disabled = true;
          status.textContent = `${option.title} is saved in this browser. Join free and it moves into your library.`;
          if (nudge) {
            nudge.classList.add('tn-nudge--lit');
            nudge.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        });
        save.disabled = saved();
        row.appendChild(save);
      }
      if (option.url) {
        const page = el('a', 'button button--ghost', 'Reviews and details');
        page.href = option.url;
        row.appendChild(page);
      }
      if (row.children.length) text.appendChild(row);
      const slot = el('div', 'tn-winner__where');
      slot.setAttribute('data-tonight-where', '');
      if (where) {
        const section = whereSection(where);
        if (section) slot.appendChild(section);
      }
      text.appendChild(slot);
      panel.appendChild(text);
      return panel;
    }

    // Another round: the owner starts it, everyone else is pointed at it once it exists.
    function roundPanel(winner) {
      if (state.next) {
        const panel = el('div', 'tn-round tn-round--open');
        const text = el('div');
        text.appendChild(el('strong', null, state.next.closed ? 'The next round has finished too' : 'A new round is open'));
        text.appendChild(el('span', 'tn-muted', state.next.closed ? 'See what won after this one.'
          : `Same group, fresh vote. ${state.next.closes_label}.`));
        panel.appendChild(text);
        const go = el('a', 'button', state.next.closed ? 'See the next round' : 'Vote in the new round');
        go.href = state.next.path;
        panel.appendChild(go);
        return panel;
      }
      if (!state.me.owner) return null;
      const rest = state.options.length - (winner ? 1 : 0);
      const dropWinner = Boolean(winner) && rest >= 2;
      const panel = el('div', 'tn-round');
      const text = el('div');
      text.appendChild(el('strong', null, winner ? 'Same group next time?' : 'Nobody voted in time'));
      text.appendChild(el('span', 'tn-muted', dropWinner
        ? `Start another round with the ${rest === 2 ? 'other two' : `other ${rest}`}. This link will point people to it.`
        : 'Start another round with the same titles. This link will point people to it.'));
      panel.appendChild(text);
      const go = button(dropWinner ? `Next round without ${winner.title}` : 'Vote again', 'button button--ghost', async () => {
        go.disabled = true;
        try {
          const made = await api(`/api/tonight/${token}/again`, { method: 'POST', member: true, body: { keep_winner: !dropWinner } });
          window.location.href = made.path;
        } catch (error) {
          status.textContent = error.message;
          go.disabled = false;
        }
      });
      panel.appendChild(go);
      return panel;
    }

    function draw() {
      const closed = state.closed;
      const round = state.round > 1 ? `ROUND ${(ORDINALS[state.round] || String(state.round)).toUpperCase()} · ` : '';
      eyebrow.textContent = `GROUP POLL · ${round}${state.closes_label.toUpperCase()}`;
      const before = state.previous && state.previous.winner ? ` Last time the group picked ${state.previous.winner}.` : '';
      lead.textContent = `${state.owner.you ? 'You asked.' : `${state.owner.name} asked.`} ${closed
        ? (state.winner ? 'Voting is over. Here\'s what won.' : 'Voting closed before anyone voted.')
        : 'Tap the one you\'d pick. You can change your mind until voting closes.'}${closed ? '' : before}`;
      board.replaceChildren();
      const winner = closed ? state.options.find(option => option.id === state.winner) : null;
      if (closed && state.next) board.appendChild(roundPanel(winner));
      if (winner) {
        board.appendChild(winnerPanel(winner));
        loadWhere();
      }

      // Nobody can vote until the link goes out, so the owner's first view leads with sending it.
      if (state.me.owner && !closed && state.total <= 1) {
        const send = el('div', 'tn-send');
        send.appendChild(el('strong', null, state.total ? 'Now send it to the group' : 'Send it to the group'));
        send.appendChild(el('span', 'tn-muted', 'Anyone with the link can vote. They don\'t need an account.'));
        send.appendChild(shareRow(state.url, state.question, status));
        board.appendChild(send);
      }

      if (!closed && !signedIn) {
        const label = el('label', 'tn-name');
        label.appendChild(el('span', null, 'Your name, so friends know who voted'));
        const input = el('input');
        input.type = 'text';
        input.maxLength = 30;
        input.autocomplete = 'given-name';
        input.placeholder = 'Optional';
        input.value = state.me.name || storedName();
        input.setAttribute('data-tonight-name', '');
        label.appendChild(input);
        board.appendChild(label);
      }

      const list = el('ul', 'tn-options');
      list.setAttribute('aria-label', 'Titles to vote on');
      state.options.forEach(option => {
        const li = el('li');
        const mine = state.me.option_id === option.id;
        const ahead = state.leading.includes(option.id);
        const classes = ['tn-option'];
        if (mine) classes.push('tn-option--mine');
        if (closed && option.id === state.winner) classes.push('tn-option--won');
        if (!closed && ahead && state.total) classes.push('tn-option--ahead');
        const node = closed ? el('div', classes.join(' ')) : button('', classes.join(' '), () => {
          if (mine) return;
          const name = (board.querySelector('[data-tonight-name]')?.value || '').trim();
          if (name) rememberName(name);
          run(() => api(`/api/tonight/${token}/vote`, { method: 'PUT', body: { option_id: option.id, name: name || null } }),
            next => `Voted for ${option.title}.${!signedIn && next.total === 1 ? ' You\'re the first!' : ''}`)
            .then(() => { if (nudge && !signedIn) nudge.classList.add('tn-nudge--lit'); });
        });
        if (!closed) node.setAttribute('aria-pressed', String(mine));
        node.appendChild(art(option));
        const text = el('span', 'tn-option__text');
        const title = el('strong', null, option.title);
        text.appendChild(title);
        const tags = [];
        if (mine) tags.push(['Your vote', 'tn-tag tn-tag--mine']);
        if (closed && option.id === state.winner) tags.push(['Winner', 'tn-tag tn-tag--won']);
        else if (!closed && ahead && state.total) tags.push([state.leading.length > 1 ? 'Tied' : 'Ahead', 'tn-tag']);
        tags.forEach(([word, className]) => title.appendChild(el('span', className, word)));
        text.appendChild(el('small', null, meta(option)));
        const bar = el('span', 'tn-bar');
        bar.setAttribute('aria-hidden', 'true');
        const fill = el('span');
        fill.style.setProperty('--tn-share', `${option.share}%`);
        bar.appendChild(fill);
        text.appendChild(bar);
        if (option.voters.length || option.others) text.appendChild(voters(option));
        node.appendChild(text);
        node.appendChild(el('span', 'tn-option__votes', `${option.votes} vote${option.votes === 1 ? '' : 's'}`));
        li.appendChild(node);
        list.appendChild(li);
      });
      board.appendChild(list);
      board.appendChild(el('p', 'tn-muted', state.total
        ? `${state.total} vote${state.total === 1 ? '' : 's'} so far.${closed ? '' : ' Results update as people vote.'}`
        : (closed ? '' : 'No votes yet. Be the first.')));

      if (closed && !state.next) {
        const again = roundPanel(winner);
        if (again) board.appendChild(again);
      }

      const tools = el('div', 'tn-row tn-tools');
      const shareButton = button(closed ? 'Share the result' : 'Share the poll', 'button button--ghost',
        () => share(state.url, state.question, shareButton, status));
      tools.appendChild(shareButton);
      if (!closed && state.me.option_id) {
        tools.appendChild(button('Take back my vote', 'tn-link-button', () =>
          run(() => api(`/api/tonight/${token}/vote`, { method: 'DELETE' }), 'Your vote is gone.')));
      }
      if (state.me.owner && !closed && state.total) {
        tools.appendChild(button('Close voting now', 'tn-link-button', () =>
          run(() => api(`/api/tonight/${token}/close`, { method: 'POST', member: true }), next => {
            const won = next.options.find(option => option.id === next.winner);
            return won ? `Voting closed. ${won.title} won.` : 'Voting closed.';
          })));
      }
      if (state.previous) {
        const earlier = el('a', 'tn-link-button', 'See the last round');
        earlier.href = state.previous.path;
        tools.appendChild(earlier);
      }
      if (state.me.owner) {
        const remove = button('Delete poll', 'tn-link-button tn-link-button--danger', async () => {
          if (!deleteArmed) {
            deleteArmed = true;
            remove.textContent = 'Tap again to delete';
            setTimeout(() => { deleteArmed = false; remove.textContent = 'Delete poll'; }, 4000);
            return;
          }
          try {
            await api(`/api/tonight/${token}`, { method: 'DELETE', member: true });
            window.location.href = '/tonight';
          } catch (error) {
            status.textContent = error.message;
          }
        });
        tools.appendChild(remove);
      }
      if (signedIn && !state.me.owner) {
        const own = el('a', 'tn-link-button', 'Make your own poll');
        own.href = '/tonight';
        tools.appendChild(own);
      }
      board.appendChild(tools);
    }

    async function load() {
      try {
        state = await api(`/api/tonight/${token}`);
        draw();
      } catch (error) {
        status.textContent = error.message;
      }
    }

    // Results update while the poll is open and the page is on screen. A closed poll is checked
    // less often, only to notice a new round.
    let ticks = 0;
    setInterval(() => {
      ticks += 1;
      if (busy || !state || document.hidden) return;
      if (state.closed && (state.next || ticks % 6)) return;
      const active = document.activeElement;
      const typing = active && active.matches && active.matches('[data-tonight-name]');
      if (!typing) load();
    }, 20000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden && state && !state.closed) load(); });
    load();
  }

  if (root.dataset.view === 'make') makeView();
  else if (root.dataset.view === 'poll') pollView();
}());
