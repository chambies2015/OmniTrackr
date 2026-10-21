// Shared lists (/lists, /lists/<id>, /lists/join/<token>): build one list together with friends.
// Everything a member typed is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  const root = document.getElementById('sharedLists');
  if (!root) return;

  const KINDS = [
    ['movie', 'Movie', 'Movies'], ['tv', 'TV show', 'Shows'], ['anime', 'Anime', 'Anime'],
    ['game', 'Game', 'Games'], ['book', 'Book', 'Books'], ['album', 'Album', 'Music'],
  ];
  const DONE_WORD = { movie: 'Watched', tv: 'Watched', anime: 'Watched', game: 'Played', book: 'Read', album: 'Heard' };

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

  function signIn() {
    window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
  }

  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', credentials: 'same-origin', headers: {} };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    if (response.status === 401) {
      signIn();
      throw new Error('Please log in again.');
    }
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
      throw new Error((detail || 'Something went wrong. Please try again.').replace(/^Value error, /, ''));
    }
    return data;
  }

  function hue(text) {
    let total = 0;
    for (const char of String(text || '')) total = (total * 31 + char.charCodeAt(0)) % 360;
    return total;
  }

  function avatar(person, small) {
    const node = el('span', small ? 'sl-avatar sl-avatar--small' : 'sl-avatar', person.initials);
    node.style.setProperty('--sl-hue', String(hue(person.username)));
    node.title = person.you ? `${person.username} (you)` : person.username;
    return node;
  }

  function avatars(people, small) {
    const row = el('span', 'sl-avatars');
    people.slice(0, 6).forEach(person => row.appendChild(avatar(person, small)));
    if (people.length > 6) row.appendChild(el('span', 'sl-avatar sl-avatar--more', `+${people.length - 6}`));
    return row;
  }

  function poster(item) {
    const frame = el('div', 'sl-poster');
    if (item.image) {
      const image = el('img');
      image.src = item.image;
      image.alt = '';
      image.loading = 'lazy';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', () => {
        image.remove();
        frame.appendChild(el('span', 'sl-poster-fallback', item.title.slice(0, 1).toUpperCase()));
      });
      frame.appendChild(image);
    } else {
      frame.appendChild(el('span', 'sl-poster-fallback', item.title.slice(0, 1).toUpperCase()));
    }
    return frame;
  }

  function names(people) {
    const list = people.map(person => (person.you ? 'you' : person.username));
    if (list.length <= 1) return list.join('');
    return `${list.slice(0, -1).join(', ')} and ${list[list.length - 1]}`;
  }

  async function share(url, text, statusNode, buttonNode) {
    if (navigator.share) {
      try {
        await navigator.share({ title: 'OmniTrackr shared list', text, url });
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      const label = buttonNode.textContent;
      buttonNode.textContent = 'Link copied';
      setTimeout(() => { buttonNode.textContent = label; }, 2200);
    } catch (error) {
      statusNode.textContent = 'Copy the link from the box above.';
    }
  }

  // ------------------------------------------------------------------ index

  async function showIndex() {
    const holder = root.querySelector('[data-list-index]');
    const form = root.querySelector('[data-list-create]');
    const status = form.querySelector('[data-list-status]');
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      status.textContent = '';
      try {
        const data = await api('/api/lists', { method: 'POST', body: {
          name: form.elements.name.value, description: form.elements.description.value || null } });
        window.location.href = `${data.url}#invite`;
      } catch (error) {
        status.textContent = error.message;
        submit.disabled = false;
      }
    });
    let data;
    try {
      data = await api('/api/lists');
    } catch (error) {
      holder.replaceChildren(el('p', 'sl-status', error.message));
      return;
    }
    holder.replaceChildren();
    if (!data.lists.length) {
      const empty = el('div', 'sl-empty');
      empty.appendChild(el('h2', null, 'No shared lists yet'));
      empty.appendChild(el('p', null, 'Start one above, then send the link to whoever you watch, read or play with. '
        + "They can join even if they don't have an account yet."));
      const ideas = el('ul', 'sl-ideas');
      ['Date night movies', 'Group chat anime queue', 'Book club shortlist', 'Co-op games to try']
        .forEach(idea => {
          const item = el('li');
          item.appendChild(button(idea, 'sl-chip', () => {
            form.elements.name.value = idea;
            form.elements.name.focus();
          }));
          ideas.appendChild(item);
        });
      empty.appendChild(ideas);
      holder.appendChild(empty);
      return;
    }
    // Members coming back want their lists first; starting another one can wait below.
    form.before(holder);
    holder.appendChild(el('h2', 'sl-index__title', 'Your lists'));
    const grid = el('ul', 'sl-cards');
    data.lists.forEach(list => {
      const card = el('li', 'sl-card');
      const link = el('a', 'sl-card__link');
      link.href = `/lists/${list.id}`;
      const mosaic = el('div', 'sl-card__covers');
      list.covers.forEach(cover => mosaic.appendChild(poster(cover)));
      for (let index = list.covers.length; index < 4; index += 1) mosaic.appendChild(el('div', 'sl-poster sl-poster--blank'));
      link.appendChild(mosaic);
      const body = el('div', 'sl-card__body');
      const title = el('h3', null, list.name);
      if (list.new_count) title.appendChild(el('span', 'sl-new', `${list.new_count} new`));
      body.appendChild(title);
      if (list.description) body.appendChild(el('p', 'sl-card__about', list.description));
      const meta = el('p', 'sl-card__meta');
      meta.appendChild(avatars(list.members, true));
      const counts = [`${list.open_count} to go`];
      if (list.done_count) counts.push(`${list.done_count} done`);
      meta.appendChild(el('span', null, counts.join(' · ')));
      body.appendChild(meta);
      link.appendChild(body);
      card.appendChild(link);
      grid.appendChild(card);
    });
    holder.appendChild(grid);
  }

  // ------------------------------------------------------------------ one list

  const state = { data: null, filter: 'all', addPanel: null };

  function listId() {
    return root.dataset.listId;
  }

  async function reload() {
    state.data = await api(`/api/lists/${listId()}`);
    render();
  }

  async function act(node, work) {
    if (node) node.disabled = true;
    try {
      await work();
      await reload();
    } catch (error) {
      flashStatus(error.message);
      if (node) node.disabled = false;
    }
  }

  function flashStatus(message) {
    const status = root.querySelector('[data-list-flash]');
    if (status) status.textContent = message;
  }

  function addPanel() {
    const panel = el('section', 'sl-add');
    panel.setAttribute('aria-labelledby', 'slAddTitle');
    panel.appendChild(el('h2', null, 'Add a title')).id = 'slAddTitle';

    const searchLabel = el('label', null, 'Search titles');
    searchLabel.htmlFor = 'slSearch';
    const search = el('input');
    Object.assign(search, { id: 'slSearch', type: 'search', maxLength: 80, autocomplete: 'off',
      placeholder: 'Try Dune, Frieren or Hades' });
    const results = el('ul', 'sl-results');
    results.hidden = true;
    panel.append(searchLabel, search, results);

    const manual = el('form', 'sl-manual');
    const manualLabel = el('p', 'sl-manual__label', "Can't find it? Add it by name.");
    const row = el('div', 'sl-row');
    const kind = el('select');
    kind.setAttribute('aria-label', 'Kind of title');
    KINDS.forEach(([value, label]) => {
      const option = el('option', null, label);
      option.value = value;
      kind.appendChild(option);
    });
    const title = el('input');
    Object.assign(title, { type: 'text', maxLength: 200, autocomplete: 'off', placeholder: 'Title', required: true });
    title.setAttribute('aria-label', 'Title');
    const year = el('input');
    Object.assign(year, { type: 'number', min: 1800, max: 2100, placeholder: 'Year' });
    year.setAttribute('aria-label', 'Year (optional)');
    year.className = 'sl-year';
    const add = el('button', 'button button--small', 'Add');
    add.type = 'submit';
    row.append(kind, title, year, add);
    manual.append(manualLabel, row);
    panel.appendChild(manual);

    async function addItem(body, node) {
      node.disabled = true;
      try {
        const data = await api(`/api/lists/${listId()}/items`, { method: 'POST', body });
        flashStatus(data.state === 'existing' ? `${data.title} is already on the list.` : `Added ${data.title}.`);
        search.value = '';
        results.hidden = true;
        results.replaceChildren();
        title.value = '';
        year.value = '';
        node.disabled = false;
        await reload();
      } catch (error) {
        flashStatus(error.message);
        node.disabled = false;
      }
    }

    manual.addEventListener('submit', event => {
      event.preventDefault();
      const value = Number(year.value);
      addItem({ kind: kind.value, title: title.value, year: Number.isInteger(value) && value >= 1800 ? value : null }, add);
    });

    let timer = null;
    let ticket = 0;
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
        (data.results || []).forEach(result => {
          const item = el('li');
          const pick = button('', 'sl-result', () => addItem({ kind: result.kind, title: result.title, year: result.year, slug: result.slug }, pick));
          pick.appendChild(poster(result));
          const text = el('span', 'sl-result__text');
          text.appendChild(el('strong', null, result.title));
          text.appendChild(el('small', null, [result.label, result.year].filter(Boolean).join(' · ')));
          pick.appendChild(text);
          pick.appendChild(el('span', 'sl-result__add', 'Add'));
          item.appendChild(pick);
          results.appendChild(item);
        });
        if (!results.children.length) {
          results.appendChild(el('li', 'sl-muted', 'Nothing matched. Add it by name below.'));
          title.value = query;
        }
        results.hidden = false;
      }, 220);
    });
    return panel;
  }

  function itemCard(item, done) {
    const card = el('li', done ? 'sl-item sl-item--done' : 'sl-item');
    card.appendChild(poster(item));
    const body = el('div', 'sl-item__body');
    const heading = el('h3', 'sl-item__title');
    if (item.url) {
      const link = el('a', null, item.title);
      link.href = item.url;
      heading.appendChild(link);
    } else {
      heading.textContent = item.title;
    }
    if (item.new) heading.appendChild(el('span', 'sl-new', 'New'));
    body.appendChild(heading);
    body.appendChild(el('p', 'sl-item__meta', [item.label, item.year].filter(Boolean).join(' · ')));
    const credit = el('p', 'sl-item__credit');
    if (done && item.done_by) {
      credit.textContent = `${DONE_WORD[item.kind] || 'Done'} · marked by ${item.done_by.you ? 'you' : item.done_by.username}`;
    } else {
      credit.textContent = item.added_by ? `Added by ${item.added_by.you ? 'you' : item.added_by.username}` : 'Added by someone who left';
    }
    body.appendChild(credit);
    if (item.note) body.appendChild(el('p', 'sl-item__note', item.note));

    const actions = el('div', 'sl-item__actions');
    if (!done) {
      const vote = button('', item.voted ? 'sl-vote sl-vote--on' : 'sl-vote', event =>
        act(event.currentTarget, () => api(`/api/lists/${listId()}/items/${item.id}/vote`, { method: 'PUT', body: { wanted: !item.voted } })));
      vote.setAttribute('aria-pressed', item.voted ? 'true' : 'false');
      vote.appendChild(el('span', null, item.voted ? "I'm in" : 'Count me in'));
      if (item.votes.length) vote.appendChild(avatars(item.votes, true));
      vote.title = item.votes.length ? `In: ${names(item.votes)}` : 'Nobody yet';
      actions.appendChild(vote);
      actions.appendChild(button(DONE_WORD[item.kind] || 'Done', 'sl-action', event =>
        act(event.currentTarget, () => api(`/api/lists/${listId()}/items/${item.id}`, { method: 'PATCH', body: { done: true } }))));
    } else {
      actions.appendChild(button('Put back', 'sl-action', event =>
        act(event.currentTarget, () => api(`/api/lists/${listId()}/items/${item.id}`, { method: 'PATCH', body: { done: false } }))));
    }
    if (item.in_library) {
      actions.appendChild(el('span', 'sl-tag', 'In your library'));
    } else {
      actions.appendChild(button('Add to my library', 'sl-action', event =>
        act(event.currentTarget, async () => {
          const data = await api(`/api/lists/${listId()}/items/${item.id}/library`, { method: 'POST' });
          flashStatus(data.state === 'created' ? `${data.title} is in your library now.` : `${data.title} was already in your library.`);
        })));
    }
    if (item.can_remove) {
      const remove = button('Remove', 'sl-action sl-action--quiet', event =>
        act(event.currentTarget, () => api(`/api/lists/${listId()}/items/${item.id}`, { method: 'DELETE' })));
      remove.setAttribute('aria-label', `Remove ${item.title} from the list`);
      actions.appendChild(remove);
    }
    body.appendChild(actions);
    card.appendChild(body);
    return card;
  }

  function pickOne(items, output) {
    // Titles more people are in for come up more often.
    const pool = items.flatMap(item => Array(1 + item.votes.length).fill(item));
    const choice = pool[Math.floor(Math.random() * pool.length)];
    output.replaceChildren();
    output.appendChild(el('span', 'sl-pick__label', 'Tonight:'));
    output.appendChild(el('strong', null, choice.title));
    if (choice.votes.length) output.appendChild(el('span', 'sl-muted', `${names(choice.votes)} ${choice.votes.length === 1 && !choice.votes[0].you ? 'is' : 'are'} in`));
    output.hidden = false;
  }

  function invitePanel() {
    const data = state.data;
    const panel = el('section', 'sl-invite');
    panel.id = 'invite';
    panel.setAttribute('aria-labelledby', 'slInviteTitle');
    panel.appendChild(el('h2', null, 'Bring people in')).id = 'slInviteTitle';
    panel.appendChild(el('p', 'sl-muted', `Anyone with the link can join, with or without an account. Up to ${data.members_max} people.`));
    const row = el('div', 'sl-row');
    const link = el('input', 'sl-link');
    Object.assign(link, { type: 'text', readOnly: true, value: data.join_url });
    link.setAttribute('aria-label', 'Join link');
    link.addEventListener('focus', () => link.select());
    const status = el('p', 'sl-status');
    status.setAttribute('role', 'status');
    const shareButton = button('Share link', 'button button--small', () =>
      share(link.value, `Join our list "${data.name}" on OmniTrackr`, status, shareButton));
    row.append(link, shareButton);
    panel.append(row, status);
    if (data.is_owner) {
      panel.appendChild(button('Make a new link', 'sl-action sl-action--quiet', async event => {
        if (!window.confirm || !window.confirm('The old link will stop working. People already in the list stay in it.')) return;
        await act(event.currentTarget, () => api(`/api/lists/${listId()}/link`, { method: 'POST', body: { reset: true } }));
        flashStatus('New link ready. The old one no longer works.');
      }));
    }
    const friends = el('div', 'sl-friends');
    panel.appendChild(friends);
    api(`/api/lists/${listId()}/friends`).then(result => {
      if (!result.friends.length) return;
      friends.appendChild(el('h3', null, 'Add a friend'));
      const list = el('ul', 'sl-friend-list');
      result.friends.forEach(friend => {
        const item = el('li');
        item.appendChild(avatar({ username: friend.username, initials: friend.username.slice(0, 2).toUpperCase() }, true));
        item.appendChild(el('span', null, friend.username));
        item.appendChild(button('Add', 'sl-action', event =>
          act(event.currentTarget, async () => {
            await api(`/api/lists/${listId()}/members`, { method: 'POST', body: { user_id: friend.id } });
            flashStatus(`${friend.username} is in. They'll get a notification.`);
          })));
        list.appendChild(item);
      });
      friends.appendChild(list);
    }).catch(() => {});
    return panel;
  }

  function settingsPanel() {
    const data = state.data;
    const panel = el('details', 'sl-settings');
    panel.appendChild(el('summary', null, data.is_owner ? 'List settings' : 'People and settings'));
    const people = el('ul', 'sl-people');
    data.members.forEach(person => {
      const item = el('li');
      item.appendChild(avatar(person, true));
      item.appendChild(el('span', null, person.you ? `${person.username} (you)` : person.username));
      if (person.owner) item.appendChild(el('span', 'sl-tag', 'Made the list'));
      if (data.is_owner && !person.owner) {
        item.appendChild(button('Remove', 'sl-action sl-action--quiet', event => {
          if (window.confirm && !window.confirm(`Remove ${person.username} from this list? The titles they added stay. The list gets a new join link so the old one can't bring them back.`)) return;
          act(event.currentTarget, () => api(`/api/lists/${listId()}/members/${person.id}`, { method: 'DELETE' }));
        }));
      }
      people.appendChild(item);
    });
    panel.appendChild(people);
    if (data.is_owner) {
      const form = el('form', 'sl-rename');
      const name = el('input');
      Object.assign(name, { type: 'text', maxLength: 80, value: data.name, required: true });
      name.setAttribute('aria-label', 'List name');
      const about = el('input');
      Object.assign(about, { type: 'text', maxLength: 300, value: data.description, placeholder: "What it's for (optional)" });
      about.setAttribute('aria-label', "What it's for");
      const save = el('button', 'button button--small', 'Save');
      save.type = 'submit';
      form.append(name, about, save);
      form.addEventListener('submit', event => {
        event.preventDefault();
        act(save, () => api(`/api/lists/${listId()}`, { method: 'PATCH', body: { name: name.value, description: about.value } }));
      });
      panel.appendChild(form);
      panel.appendChild(button('Delete this list', 'sl-action sl-action--danger', event => {
        if (!window.confirm || !window.confirm('Delete this list for everyone in it? Nobody\'s library changes.')) return;
        const node = event.currentTarget;
        node.disabled = true;
        api(`/api/lists/${listId()}`, { method: 'DELETE' })
          .then(() => { window.location.href = '/lists'; })
          .catch(error => { flashStatus(error.message); node.disabled = false; });
      }));
    } else {
      const me = data.members.find(person => person.you);
      panel.appendChild(button('Leave this list', 'sl-action sl-action--danger', event => {
        if (!me || (window.confirm && !window.confirm('Leave this list? The titles you added stay on it.'))) return;
        const node = event.currentTarget;
        node.disabled = true;
        api(`/api/lists/${listId()}/members/${me.id}`, { method: 'DELETE' })
          .then(() => { window.location.href = '/lists'; })
          .catch(error => { flashStatus(error.message); node.disabled = false; });
      }));
    }
    return panel;
  }

  function render() {
    const data = state.data;
    const focusId = document.activeElement && document.activeElement.id;
    const openSettings = root.querySelector('.sl-settings[open]') !== null;
    document.title = `${data.name} | OmniTrackr`;
    const head = el('header', 'sl-head');
    head.appendChild(el('p', 'eyebrow', 'SHARED LIST'));
    head.appendChild(el('h1', null, data.name));
    if (data.description) head.appendChild(el('p', 'sl-head__about', data.description));
    const who = el('p', 'sl-head__who');
    who.appendChild(avatars(data.members));
    who.appendChild(el('span', null, data.members.length === 1 ? 'Just you so far' : names(data.members)));
    head.appendChild(who);

    const flash = el('p', 'sl-flash');
    flash.dataset.listFlash = '';
    flash.setAttribute('role', 'status');

    // Until someone else joins, inviting is the next step, so phones show it first.
    const layout = el('div', data.members.length === 1 ? 'sl-layout sl-layout--solo' : 'sl-layout');
    const main = el('div', 'sl-main');
    const side = el('aside', 'sl-side');

    // Built once and moved into each new render, so typing during a refresh isn't lost.
    if (!state.addPanel) state.addPanel = addPanel();
    main.appendChild(state.addPanel);

    const kinds = [...new Set(data.open.map(item => item.kind))];
    if (state.filter !== 'all' && !kinds.includes(state.filter)) state.filter = 'all';
    const shown = data.open.filter(item => state.filter === 'all' || item.kind === state.filter);
    const upNext = el('section', 'sl-section');
    const top = el('div', 'sl-section__head');
    top.appendChild(el('h2', null, `Up next (${data.open.length})`));
    if (data.open.length > 1) {
      const output = el('p', 'sl-pick');
      output.hidden = true;
      output.setAttribute('role', 'status');
      top.appendChild(button('Pick one for us', 'sl-action', () => pickOne(shown.length ? shown : data.open, output)));
      upNext.appendChild(top);
      upNext.appendChild(output);
    } else {
      upNext.appendChild(top);
    }
    if (kinds.length > 1) {
      const chips = el('div', 'sl-filters');
      chips.setAttribute('role', 'group');
      chips.setAttribute('aria-label', 'Show');
      [['all', 'All'], ...KINDS.filter(([value]) => kinds.includes(value)).map(([value, , plural]) => [value, plural])]
        .forEach(([value, label]) => {
          const chip = button(label, state.filter === value ? 'sl-chip sl-chip--on' : 'sl-chip', () => {
            state.filter = value;
            render();
          });
          chip.setAttribute('aria-pressed', state.filter === value ? 'true' : 'false');
          chips.appendChild(chip);
        });
      upNext.appendChild(chips);
    }
    if (!data.open.length) {
      upNext.appendChild(el('p', 'sl-empty-line', data.done.length
        ? 'Everything here is done. Add what you want to get to next.'
        : 'Nothing here yet. Search above to add the first title, then share the link so others can add theirs.'));
    } else {
      upNext.appendChild(el('p', 'sl-muted sl-hint', "Tap I'm in on what you want to get to. Titles more people are in for move to the top."));
      const list = el('ul', 'sl-items');
      shown.forEach(item => list.appendChild(itemCard(item, false)));
      upNext.appendChild(list);
    }
    main.appendChild(upNext);

    if (data.done.length) {
      const doneSection = el('details', 'sl-section sl-done');
      doneSection.appendChild(el('summary', null, `Done together (${data.done.length})`));
      const list = el('ul', 'sl-items');
      data.done.forEach(item => list.appendChild(itemCard(item, true)));
      doneSection.appendChild(list);
      main.appendChild(doneSection);
    }

    side.appendChild(invitePanel());
    const settings = settingsPanel();
    settings.open = openSettings;
    side.appendChild(settings);
    layout.append(main, side);

    const back = el('p', 'sl-back');
    const backLink = el('a', null, '← All shared lists');
    backLink.href = '/lists';
    back.appendChild(backLink);
    const previous = root.querySelector('[data-list-flash]');
    if (previous && previous.textContent) flash.textContent = previous.textContent;
    root.replaceChildren(back, head, flash, layout);
    if (focusId) {
      const again = document.getElementById(focusId);
      if (again) again.focus();
    }
  }

  async function showList() {
    try {
      await reload();
    } catch (error) {
      root.querySelector('.sl-loading').textContent = error.message;
      return;
    }
    if (window.location.hash === '#invite') {
      const invite = document.getElementById('invite');
      if (invite) invite.scrollIntoView({ block: 'start' });
    }
  }

  // ------------------------------------------------------------------ join

  function showJoin() {
    const join = root.querySelector('[data-list-join]');
    if (!join) return;
    const status = root.querySelector('[data-list-status]');
    join.addEventListener('click', async () => {
      join.disabled = true;
      try {
        const data = await api(`/api/lists/join/${encodeURIComponent(join.dataset.token)}`, { method: 'POST' });
        window.location.href = data.url;
      } catch (error) {
        status.textContent = error.message;
        join.disabled = false;
      }
    });
  }

  if (root.dataset.view === 'index') showIndex();
  else if (root.dataset.view === 'list') showList();
  else if (root.dataset.view === 'join') showJoin();
}());
