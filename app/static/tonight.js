// Group polls (/tonight, /tonight/<token>): make a "what should we watch tonight?" poll and vote on it.
// Everything a member or visitor typed is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  document.addEventListener('click', event => {
    if (!event.target.closest || !event.target.closest('[data-tonight-signup]')) return;
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event: 'tonight_poll_signup_clicked' })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  });

  const root = document.getElementById('tonightApp');
  if (!root) return;

  const KINDS = [['movie', 'Movie'], ['tv', 'TV show'], ['anime', 'Anime'], ['game', 'Game'], ['book', 'Book'],
    ['album', 'Album'], ['manga', 'Manga'], ['podcast', 'Podcast']];
  const NAME_KEY = 'omnitrackr_poll_name';

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

  async function share(url, text, buttonNode, statusNode) {
    if (navigator.share) {
      try {
        await navigator.share({ title: text, text, url });
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      const label = buttonNode.textContent;
      buttonNode.textContent = 'Link copied ✓';
      setTimeout(() => { buttonNode.textContent = label; }, 2200);
    } catch (error) {
      if (statusNode) statusNode.textContent = `Copy this link: ${url}`;
    }
  }

  // ------------------------------------------------------------------ making a poll

  function makeView() {
    const form = root.querySelector('[data-tonight-make]');
    const pickedNode = root.querySelector('[data-tonight-picked]');
    const countNode = root.querySelector('[data-tonight-count]');
    const suggestNode = root.querySelector('[data-tonight-suggest]');
    const friendsNode = root.querySelector('[data-tonight-friends]');
    const search = root.querySelector('#tnSearch');
    const results = root.querySelector('[data-tonight-results]');
    const wildcard = root.querySelector('[data-tonight-wildcard]');
    const submit = form.querySelector('.tn-make__go');
    const status = form.querySelector('[data-tonight-status]');
    const mineNode = root.querySelector('[data-tonight-mine]');
    let max = 8;
    const picked = [];
    const suggestButtons = new Map();

    function keyOf(item) {
      return `${item.kind}|${String(item.title).trim().toLowerCase()}|${item.year || ''}`;
    }

    function has(item) {
      return picked.some(entry => entry.key === keyOf(item));
    }

    function syncSuggestions() {
      suggestButtons.forEach((node, key) => node.setAttribute('aria-pressed', String(picked.some(entry => entry.key === key))));
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
      syncSuggestions();
    }

    function add(item) {
      if (has(item)) {
        status.textContent = `${item.title} is already on the poll.`;
        return false;
      }
      if (picked.length >= max) {
        status.textContent = `A poll holds up to ${max} titles.`;
        return false;
      }
      picked.push(Object.assign({}, item, { key: keyOf(item) }));
      status.textContent = '';
      draw();
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

    api('/api/tonight/suggestions', { member: true }).then(data => {
      max = data.options_max || max;
      suggestNode.replaceChildren();
      const queue = data.titles.filter(item => item.source === 'Next Up');
      const library = data.titles.filter(item => item.source !== 'Next Up');
      if (queue.length) suggestNode.appendChild(suggestionGroup('From your Next Up', queue));
      if (library.length) suggestNode.appendChild(suggestionGroup(queue.length ? 'Also in your library' : 'From your library', library));
      if (!data.titles.length) {
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
      draw();
    }).catch(error => {
      suggestNode.replaceChildren(el('p', 'tn-muted', error.message));
    });

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
        const label = KINDS.find(([value]) => value === kind.value)[1];
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

    // A wildcard from Pick for me's editorial pool.
    let pool = null;
    wildcard.addEventListener('click', async () => {
      wildcard.disabled = true;
      try {
        if (!pool) pool = (await api('/api/pick/pool')).picks || [];
        const fresh = pool.filter(entry => !has({ kind: entry.kind, title: entry.title, year: entry.year }));
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
        ready(data);
        picked.length = 0;
        form.reset();
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
      const heading = el('h2', null, 'Your poll is ready');
      heading.id = 'tnReadyTitle';
      heading.tabIndex = -1;
      panel.appendChild(heading);
      panel.appendChild(el('p', null, data.asked
        ? `We let ${data.asked === 1 ? 'your friend' : `${data.asked} friends`} know. Send the link to everyone else.`
        : 'Send the link to whoever you\'re watching with. They can vote without an account.'));
      const link = el('input', 'tn-ready__link');
      link.type = 'text';
      link.readOnly = true;
      link.value = data.url;
      link.setAttribute('aria-label', 'Poll link');
      link.addEventListener('focus', () => link.select());
      panel.appendChild(link);
      const row = el('div', 'tn-row');
      const shareButton = button('Share the link', 'button', () => share(data.url, data.question, shareButton, status));
      row.appendChild(shareButton);
      const open = el('a', 'button button--ghost', 'Open the poll');
      open.href = data.path;
      row.appendChild(open);
      panel.appendChild(row);
      root.querySelector('.tn-ready')?.remove();
      form.before(panel);
      status.textContent = '';
      heading.focus();
    }

    async function loadMine() {
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

    draw();
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
    let state = null;
    let busy = false;
    let deleteArmed = false;

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

    function winnerPanel(option) {
      const panel = el('div', 'tn-winner');
      panel.appendChild(art(option, 'tn-art tn-art--winner'));
      const text = el('div', 'tn-winner__text');
      text.appendChild(el('p', 'eyebrow', 'THE GROUP PICKED'));
      text.appendChild(el('h2', null, option.title));
      text.appendChild(el('p', 'tn-muted', `${meta(option)} · ${option.votes} of ${state.total} vote${state.total === 1 ? '' : 's'}`));
      const row = el('div', 'tn-row');
      if (signedIn && option.url) {
        const save = button('Add to my library', 'button', async () => {
          save.disabled = true;
          try {
            const slug = option.url.split('/').pop();
            const result = await api(`/api/titles/${option.kind}/${slug}/add`, { method: 'POST', member: true });
            save.textContent = result.state === 'created' ? 'Added ✓' : 'Already in your library';
          } catch (error) {
            status.textContent = error.message;
            save.disabled = false;
          }
        });
        row.appendChild(save);
      }
      if (option.url) {
        const page = el('a', 'button button--ghost', 'Reviews and where to watch');
        page.href = option.url;
        row.appendChild(page);
      }
      if (row.children.length) text.appendChild(row);
      panel.appendChild(text);
      return panel;
    }

    function draw() {
      const closed = state.closed;
      eyebrow.textContent = `GROUP POLL · ${state.closes_label.toUpperCase()}`;
      lead.textContent = `${state.owner.you ? 'You asked.' : `${state.owner.name} asked.`} ${closed
        ? (state.winner ? 'Voting is over. Here\'s what won.' : 'Voting closed before anyone voted.')
        : 'Tap the one you\'d pick. You can change your mind until voting closes.'}`;
      board.replaceChildren();
      const winner = closed ? state.options.find(option => option.id === state.winner) : null;
      if (winner) board.appendChild(winnerPanel(winner));

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

    // Results update while the poll is open and the page is on screen.
    setInterval(() => {
      if (busy || !state || state.closed || document.hidden) return;
      const typing = document.activeElement && document.activeElement.matches && document.activeElement.matches('[data-tonight-name]');
      if (!typing) load();
    }, 20000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden && state && !state.closed) load(); });
    load();
  }

  if (root.dataset.view === 'make') makeView();
  else if (root.dataset.view === 'poll') pollView();
}());
