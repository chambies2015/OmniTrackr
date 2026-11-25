// Yearbook pages (/yearbook, /yearbook/<token>). The shared page is drawn on the server; this script
// signs it. The member page (/yearbook) is drawn here from /api/yearbook. Server text is only ever set
// as textContent.
(function () {
  'use strict';

  const PICKS_MAX = 4;

  function safePath(path) {
    return typeof path === 'string' && /^\/yearbook(?:\/[A-Za-z0-9_-]{16,40}|#[a-z]+)?$/.test(path) ? path : '/yearbook';
  }

  function safeImage(url) {
    return typeof url === 'string' && /^https:\/\/[^\s"'<>]+$/.test(url) ? url : null;
  }

  function safeTitleUrl(url) {
    return typeof url === 'string' && /^\/titles\/[a-z-]+\/[A-Za-z0-9._~%-]+$/.test(url) ? url : null;
  }

  // Picks kept in the order the member ticked them, never more than four.
  function togglePick(picks, pick) {
    const key = `${pick.category}:${pick.id}`;
    const at = picks.findIndex(entry => `${entry.category}:${entry.id}` === key);
    if (at >= 0) return picks.filter((_, index) => index !== at);
    if (picks.length >= PICKS_MAX) return picks;
    return picks.concat([{ category: pick.category, id: pick.id }]);
  }

  function plural(count, one, many) {
    return `${count} ${count === 1 ? one : (many || `${one}s`)}`;
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = { safePath, safeImage, safeTitleUrl, togglePick, plural, PICKS_MAX };
    return;
  }

  const reported = new Set();
  function report(event) {
    if (reported.has(event) || !navigator.sendBeacon) return;
    reported.add(event);
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  }
  document.addEventListener('click', event => {
    if (event.target.closest && event.target.closest('[data-yearbook-signup]')) report('yearbook_signup_clicked');
  });

  const root = document.getElementById('yearbookApp');
  if (!root) return;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(label, className, onClick, type = 'button') {
    const node = el('button', className, label);
    node.type = type;
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    if (response.status === 401 && options.member) {
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

  // A button that asks once, in place, before doing something that can't be taken back.
  function confirmButton(text, question, yes, className, action, said) {
    const wrap = el('div', 'yb-confirm');
    const first = button(text, className || 'yb-link-button');
    first.addEventListener('click', () => {
      wrap.replaceChildren();
      wrap.appendChild(el('p', 'yb-confirm__ask', question));
      const row = el('div', 'yb-row');
      const go = button(yes, 'yb-pill yb-pill--primary yb-pill--small', async () => {
        go.disabled = true;
        try {
          await action();
        } catch (error) {
          if (said) { said.textContent = error.message; said.dataset.tone = 'error'; }
          go.disabled = false;
        }
      });
      row.appendChild(go);
      row.appendChild(button('Not now', 'yb-pill yb-pill--small', () => { wrap.replaceChildren(first); first.focus(); }));
      wrap.appendChild(row);
      go.focus();
    });
    wrap.appendChild(first);
    return wrap;
  }

  async function copyText(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      return false;
    }
  }

  // ------------------------------------------------------------------ the shared page: signing

  function signPage() {
    const form = root.querySelector('[data-yearbook-sign]');
    const cover = (root.querySelector('.yb-cover__name') || {}).textContent || 'They';
    if (!form) return;
    const status = form.querySelector('[data-yearbook-status]');
    const note = form.querySelector('textarea[name="note"]');
    const counter = form.querySelector('[data-yearbook-count]');
    const say = (text, tone) => {
      status.textContent = text;
      if (tone) status.dataset.tone = tone; else delete status.dataset.tone;
    };
    const count = () => { if (counter && note) counter.textContent = String(note.value.length); };
    note?.addEventListener('input', count);
    count();
    const token = form.dataset.token;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const name = form.querySelector('input[name="name"]');
      const vote = form.querySelector('input[name="superlative"]:checked');
      const trap = form.querySelector('input[name="website"]');
      if (name && !name.value.trim()) { say('Add your name so they know who wrote it.', 'error'); name.focus(); return; }
      if (!note.value.trim()) { say('Write a few words first.', 'error'); note.focus(); return; }
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      say('Signing…');
      try {
        const result = await api(`/api/yearbook/sign/${encodeURIComponent(token)}`, {
          method: 'POST',
          body: { name: name ? name.value : null, note: note.value, superlative: vote ? vote.value || null : null,
            website: trap ? trap.value : '' },
        });
        if (!name && result.status === 'shown') {
          window.location.hash = 'notes';
          window.location.reload();
          return;
        }
        const done = el('div', 'yb-thanks');
        done.setAttribute('role', 'status');
        done.appendChild(el('h3', null, result.new ? 'Signed. Thank you.' : 'Saved.'));
        done.appendChild(el('p', null, result.status === 'shown'
          ? 'Your note is in the yearbook.'
          : `${cover} reads each note before it shows here, so yours will appear once they let it in.`));
        if (name) {
          done.appendChild(el('p', null, 'Want people to sign yours? It takes a minute, and OmniTrackr is free.'));
          const own = el('a', 'button', 'Make my yearbook');
          own.href = '/?next=%2Fyearbook#signup';
          own.rel = 'nofollow';
          own.dataset.yearbookSignup = '';
          done.appendChild(own);
        }
        form.replaceWith(done);
      } catch (error) {
        say(error.message, 'error');
        submit.disabled = false;
      }
    });
    root.querySelector('[data-yearbook-unsign]')?.addEventListener('click', async () => {
      try {
        await api(`/api/yearbook/sign/${encodeURIComponent(token)}`, { method: 'DELETE', member: true });
        window.location.reload();
      } catch (error) {
        say(error.message, 'error');
      }
    });
  }

  // ------------------------------------------------------------------ the member page

  const body = root.querySelector('[data-yearbook-body]');
  const year = Number(root.dataset.year) || new Date().getFullYear();
  let data = null;
  let flash = '';

  function statusLine() {
    const line = el('p', 'yb-status');
    line.setAttribute('role', 'status');
    line.setAttribute('aria-live', 'polite');
    return line;
  }

  function section(id, title, lead) {
    const box = el('section', 'yb-card');
    if (id) box.id = id;
    const heading = el('h2', null, title);
    heading.id = `${id || 'yb'}Title`;
    box.setAttribute('aria-labelledby', heading.id);
    box.appendChild(heading);
    if (lead) box.appendChild(el('p', 'yb-hint', lead));
    return box;
  }

  function field(labelText, control, hint) {
    const wrap = el('div', 'yb-field');
    const label = el('label', null, labelText);
    label.htmlFor = control.id;
    wrap.appendChild(label);
    wrap.appendChild(control);
    if (hint) wrap.appendChild(el('p', 'yb-hint', hint));
    return wrap;
  }

  function check(labelText, checked, id) {
    const label = el('label', 'yb-check');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = !!checked;
    box.id = id;
    label.appendChild(box);
    label.appendChild(el('span', null, labelText));
    return { label, box };
  }

  function pickTile(pick, chosen, onToggle) {
    const item = el('li', 'yb-option');
    const tile = el('button', 'yb-option__button');
    tile.type = 'button';
    tile.setAttribute('aria-pressed', chosen ? 'true' : 'false');
    const art = el('span', 'yb-option__art');
    const image = safeImage(pick.image);
    if (image) {
      const img = document.createElement('img');
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.width = 72;
      img.height = 108;
      art.appendChild(img);
    } else {
      art.appendChild(el('span', 'yb-pick__blank', (pick.title || '?').slice(0, 1).toUpperCase()));
    }
    tile.appendChild(art);
    const words = el('span', 'yb-option__words');
    words.appendChild(el('span', 'yb-option__title', pick.title));
    words.appendChild(el('span', 'yb-option__facts', [pick.format, pick.year].filter(Boolean).join(' · ')));
    if (pick.this_year) words.appendChild(el('span', 'yb-option__badge', `Finished in ${year}`));
    tile.appendChild(words);
    tile.appendChild(el('span', 'yb-option__tick', chosen ? '✓' : '+'));
    tile.setAttribute('aria-label', `${pick.title}${chosen ? ', on your cover' : ''}`);
    tile.addEventListener('click', () => onToggle(pick));
    item.appendChild(tile);
    return item;
  }

  function setupForm(book) {
    const fresh = !book;
    const box = section('setup', fresh ? `Make your ${year} yearbook` : 'Your page',
      fresh ? 'Three things and you have a page to send. You can change all of it until signing closes.'
        : 'Change any of this until signing closes. People see the new version the next time they open the link.');
    const form = el('form', 'yb-form');
    form.noValidate = true;
    const cover = document.createElement('input');
    cover.type = 'text';
    cover.id = 'ybCoverName';
    cover.maxLength = data.limits.cover;
    cover.value = book ? book.cover_name : data.defaults.cover_name;
    cover.autocomplete = 'nickname';
    form.appendChild(field('Name on the cover', cover, 'Your first name, a nickname, or your username.'));
    const quote = document.createElement('input');
    quote.type = 'text';
    quote.id = 'ybQuote';
    quote.maxLength = data.limits.quote;
    quote.value = book ? book.quote : '';
    quote.placeholder = 'One line about your year';
    const quoteField = field('Your yearbook quote', quote);
    const ideas = el('div', 'yb-ideas');
    ideas.appendChild(el('span', 'yb-hint', 'Stuck? Borrow one:'));
    for (const idea of data.quote_ideas || []) {
      ideas.appendChild(button(idea, 'yb-chip', () => { quote.value = idea; quote.focus(); }));
    }
    quoteField.appendChild(ideas);
    form.appendChild(quoteField);

    let picks = book ? (book.picks || []).slice() : [];
    const pickBox = el('fieldset', 'yb-field yb-picker');
    pickBox.appendChild(el('legend', null, `Picks of the year (up to ${data.limits.picks})`));
    const options = data.options || [];
    const counter = el('p', 'yb-hint');
    const grid = el('ul', 'yb-options');
    const draw = () => {
      const chosen = new Set(picks.map(pick => `${pick.category}:${pick.id}`));
      grid.replaceChildren(...options.map(option => pickTile(option, chosen.has(`${option.category}:${option.id}`), pick => {
        const before = picks.length;
        picks = togglePick(picks, pick);
        if (picks.length === before && !chosen.has(`${pick.category}:${pick.id}`)) {
          counter.textContent = `That's ${data.limits.picks} already. Untick one to swap it.`;
          return;
        }
        draw();
      })));
      counter.textContent = picks.length ? `${plural(picks.length, 'pick')} on your cover.`
        : 'Tap the ones you want on your cover.';
    };
    if (options.length) {
      pickBox.appendChild(counter);
      pickBox.appendChild(grid);
      draw();
    } else {
      pickBox.appendChild(el('p', 'yb-hint', data.shelves_shared
        ? `Finish something in ${year}, or score something 8 or more, and it shows up here to pick.`
        : 'All your shelves are hidden or private, so there\'s nothing to pick from. The rest of the page still works.'));
    }
    form.appendChild(pickBox);

    const total = data.numbers ? data.numbers.total : 0;
    const numbers = check(total
      ? `Show how many titles I finished in ${year} (${total} so far)`
      : `Show how many titles I finished in ${year}`, book ? book.show_numbers : true, 'ybShowNumbers');
    form.appendChild(numbers.label);
    const listed = check('List it on the class page, where other members can find it and sign',
      book ? book.listed : false, 'ybListed');
    form.appendChild(listed.label);
    form.appendChild(el('p', 'yb-hint', 'Only shelves you show and haven\'t made private are used. Scores, notes and '
      + 'reviews never appear on the page.'));
    const save = button(fresh ? 'Make my yearbook' : 'Save changes', 'button', null, 'submit');
    const row = el('div', 'yb-row');
    row.appendChild(save);
    form.appendChild(row);
    const said = statusLine();
    form.appendChild(said);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!cover.value.trim()) {
        said.textContent = 'Put a name on the cover.';
        said.dataset.tone = 'error';
        cover.focus();
        return;
      }
      save.disabled = true;
      said.textContent = 'Saving…';
      delete said.dataset.tone;
      try {
        const result = await api('/api/yearbook', {
          method: 'PUT', member: true,
          body: { year, cover_name: cover.value, quote: quote.value, picks, show_numbers: numbers.box.checked,
            listed: listed.box.checked },
        });
        data = result;
        flash = result.made ? 'made' : 'saved';
        render();
        if (result.made) document.getElementById('share')?.scrollIntoView({ block: 'start' });
      } catch (error) {
        said.textContent = error.message;
        said.dataset.tone = 'error';
        save.disabled = false;
      }
    });
    box.appendChild(form);
    return box;
  }

  function shareBox(book) {
    const fresh = flash === 'made';
    const box = section('share', fresh ? 'Your yearbook is ready. Send the link.' : 'Send the link',
      book.url ? 'Post it in the group chat, on your story, or send it to one person at a time. Nobody needs an '
        + 'account to sign.' : 'Your link is off, so nobody can open the page or sign it.');
    if (fresh) box.classList.add('yb-card--fresh');
    const said = statusLine();
    if (book.url) {
      const row = el('div', 'yb-share__row');
      const link = document.createElement('input');
      link.type = 'text';
      link.readOnly = true;
      link.value = book.url;
      link.id = 'ybLink';
      link.setAttribute('aria-label', 'Your yearbook link');
      link.addEventListener('focus', () => link.select());
      row.appendChild(link);
      row.appendChild(button('Copy link', 'yb-pill yb-pill--primary', async () => {
        const ok = await copyText(book.url);
        if (!ok) { link.focus(); link.select(); }
        said.textContent = ok ? 'Link copied. Paste it wherever your people are.' : 'Select the link and copy it.';
        report('yearbook_shared');
      }));
      if (navigator.share) {
        row.appendChild(button('Share…', 'yb-pill', async () => {
          try {
            await navigator.share({ title: `Sign my ${year} yearbook`, text: `Sign my ${year} yearbook: leave a note and vote me "most likely to" something.`, url: book.url });
            report('yearbook_shared');
          } catch (error) { /* closed the share sheet */ }
        }));
      }
      box.appendChild(row);
      const more = el('p', 'yb-share__more');
      const look = el('a', 'yb-link', 'See it the way others do');
      look.href = safePath(book.path);
      more.appendChild(look);
      if (book.opened) more.appendChild(el('span', 'yb-muted', ` · Opened ${plural(book.opened, 'time')} by other people`));
      box.appendChild(more);
      if (book.card) {
        const figure = el('figure', 'yb-share__card');
        const img = document.createElement('img');
        img.src = `${safePath(book.path)}/card.png`;
        img.alt = 'The picture chat apps show with your link';
        img.width = 600;
        img.height = 315;
        img.loading = 'lazy';
        figure.appendChild(img);
        figure.appendChild(el('figcaption', 'yb-hint', 'What chat apps show with your link.'));
        box.appendChild(figure);
      }
      if (book.story) box.appendChild(storyButton(book, said));
    }
    const controls = el('div', 'yb-row yb-share__controls');
    if (book.url) {
      controls.appendChild(confirmButton('Make a new link', 'Make a new link? The old one stops working. Notes already in stay in.',
        'Make a new link', 'yb-link-button', async () => {
          await api(`/api/yearbook/link?year=${year}`, { method: 'POST', member: true });
          await load();
        }, said));
      controls.appendChild(confirmButton('Turn the link off',
        'Turn the link off? Nobody can open your yearbook until you turn it on again, which makes a new link.',
        'Turn it off', 'yb-link-button', async () => {
          await api(`/api/yearbook/link?year=${year}`, { method: 'DELETE', member: true });
          await load();
        }, said));
    } else {
      controls.appendChild(button('Turn the link on', 'button', async () => {
        try {
          await api(`/api/yearbook/link?year=${year}`, { method: 'POST', member: true });
          await load();
        } catch (error) {
          said.textContent = error.message;
          said.dataset.tone = 'error';
        }
      }));
    }
    box.appendChild(controls);
    box.appendChild(said);
    return box;
  }

  // A tall picture for Instagram or WhatsApp stories: shared straight to the app where the phone allows it,
  // downloaded everywhere else.
  function storyButton(book, said) {
    const row = el('div', 'yb-row yb-share__story');
    const go = button('Save a picture for your story', 'yb-pill', async () => {
      const src = `${safePath(book.path)}/story.png`;
      if (!/^\/yearbook\/[A-Za-z0-9_-]{16,40}\/story\.png$/.test(src)) return;
      go.disabled = true;
      said.textContent = 'Getting your picture ready…';
      try {
        const response = await fetch(src, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        const file = typeof File === 'function' ? new File([blob], `yearbook-${year}.png`, { type: 'image/png' }) : null;
        report('yearbook_story_saved');
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          try {
            await navigator.share({ files: [file], title: `Sign my ${year} yearbook` });
            said.textContent = 'Add a link sticker with your yearbook link so people can tap through.';
          } catch (error) {
            said.textContent = error && error.name === 'AbortError' ? '' : 'Sharing didn\u2019t open. Try again, or save the picture instead.';
          }
        } else {
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = `yearbook-${year}.png`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(link.href), 4000);
          said.textContent = 'Picture saved. Post it to your story with a link sticker for your yearbook link.';
        }
      } catch (error) {
        said.textContent = 'The picture didn\u2019t load. Try again in a minute.';
      } finally {
        go.disabled = false;
      }
    });
    row.appendChild(go);
    return row;
  }

  function noteItem(note, actions) {
    const item = el('li', `yb-note yb-note--${note.status}`);
    const words = el('div', 'yb-note__body');
    for (const line of String(note.note || '').split('\n')) if (line.trim()) words.appendChild(el('p', null, line));
    item.appendChild(words);
    if (note.superlative) {
      const vote = el('p', 'yb-note__vote');
      const star = el('span', null, '★');
      star.setAttribute('aria-hidden', 'true');
      vote.appendChild(star);
      vote.appendChild(document.createTextNode(` ${note.superlative}`));
      item.appendChild(vote);
    }
    const by = el('p', 'yb-note__by', note.name);
    if (note.guest) by.appendChild(el('span', 'yb-note__tag', 'no account'));
    by.appendChild(el('span', 'yb-note__when', `${note.when}${note.edited ? ' · edited' : ''}`));
    item.appendChild(by);
    if (actions.length) {
      const row = el('div', 'yb-note__actions');
      const said = el('p', 'yb-status yb-status--small');
      said.setAttribute('role', 'status');
      for (const [label, action, className] of actions) {
        if (action === 'delete') {
          row.appendChild(confirmButton(label, `Delete ${note.name}'s note for good?`, 'Delete it', className,
            () => moderate(note, action), said));
        } else {
          const go = button(label, className || 'yb-pill yb-pill--small', async () => {
            go.disabled = true;
            try {
              await moderate(note, action);
            } catch (error) {
              said.textContent = error.message;
              said.dataset.tone = 'error';
              go.disabled = false;
            }
          });
          row.appendChild(go);
        }
      }
      item.appendChild(row);
      item.appendChild(said);
    }
    return item;
  }

  async function moderate(note, action) {
    if (action === 'delete') await api(`/api/yearbook/notes/${note.id}?year=${year}`, { method: 'DELETE', member: true });
    else await api(`/api/yearbook/notes/${note.id}?year=${year}`, { method: 'PATCH', member: true, body: { action } });
    await load();
  }

  function notesBoxes(book) {
    const boxes = [];
    const closed = data.state === 'closed';
    const waiting = book.notes.waiting || [];
    if (waiting.length) {
      const box = section('waiting', `Waiting for you (${waiting.length})`,
        'These came from people who aren\'t your friends on OmniTrackr, or from people without an account. Nobody '
        + 'else sees them until you let them in.');
      const list = el('ul', 'yb-notes__wall yb-notes__wall--manage');
      for (const note of waiting) {
        list.appendChild(noteItem(note, [['Let it in', 'show', 'yb-pill yb-pill--primary yb-pill--small'],
          ['Hide', 'hide'], ['Delete', 'delete', 'yb-link-button']]));
      }
      box.appendChild(list);
      boxes.push(box);
    }
    const shown = book.notes.shown || [];
    const box = section('notes', shown.length ? `Signed by ${plural(shown.length, 'person', 'people')}` : 'Notes',
      shown.length ? null : (closed ? 'Nobody signed this one.' : 'No notes yet. They show up here as people sign.'));
    if (book.tally && book.tally.length) {
      const tally = el('ul', 'yb-tally yb-tally--manage');
      tally.setAttribute('aria-label', 'Votes so far');
      for (const entry of book.tally) {
        const item = el('li');
        item.appendChild(el('strong', null, plural(entry.votes, 'vote')));
        item.appendChild(document.createTextNode(` ${entry.label}`));
        tally.appendChild(item);
      }
      box.appendChild(tally);
    }
    if (shown.length) {
      const list = el('ul', 'yb-notes__wall yb-notes__wall--manage');
      for (const note of shown) list.appendChild(noteItem(note, [['Hide', 'hide']]));
      box.appendChild(list);
    }
    const hidden = book.notes.hidden || [];
    if (hidden.length) {
      const fold = el('details', 'yb-hidden');
      fold.appendChild(el('summary', null, `Hidden (${hidden.length})`));
      const list = el('ul', 'yb-notes__wall yb-notes__wall--manage');
      for (const note of hidden) {
        list.appendChild(noteItem(note, [['Show it', 'show'], ['Delete', 'delete', 'yb-link-button']]));
      }
      fold.appendChild(list);
      box.appendChild(fold);
    }
    boxes.push(box);
    return boxes;
  }

  function friendsBox() {
    const friends = data.friends || [];
    if (!friends.length) return null;
    const box = section('friends', 'Friends\' yearbooks', 'Sign theirs and they\'ll probably sign yours back.');
    const list = el('ul', 'yb-friends');
    for (const friend of friends) {
      const item = el('li', 'yb-friends__item');
      const sameName = String(friend.cover || '').toLowerCase() === String(friend.name || '').toLowerCase();
      item.appendChild(el('span', 'yb-friends__name', friend.cover && !sameName ? `${friend.cover} (${friend.name})` : friend.name));
      const go = el('a', friend.signed ? 'yb-pill yb-pill--small' : 'yb-pill yb-pill--primary yb-pill--small',
        friend.signed ? 'Signed · change it' : 'Sign it');
      go.href = `${safePath(friend.path)}#sign`;
      item.appendChild(go);
      list.appendChild(item);
    }
    box.appendChild(list);
    return box;
  }

  function classLink() {
    const line = el('p', 'yb-class-link');
    const link = el('a', 'yb-link', `See the class of ${year}`);
    link.href = `/yearbook/class/${year}`;
    line.appendChild(link);
    line.appendChild(el('span', 'yb-muted', ' · members who listed their yearbook for anyone on OmniTrackr to sign'));
    return line;
  }

  function render() {
    const parts = [];
    const book = data.book;
    if (data.preview) parts.push(el('p', 'yb-banner', `Preview: yearbooks open for everyone on ${data.opens}. Only site admins see this.`));
    if (data.state === 'soon' && !data.can_edit) {
      const box = section('soon', `Yearbooks open on ${data.opens}`,
        'Come back then to make yours. Signing stays open until the end of New Year\'s Day.');
      parts.push(box);
    } else if (!book && data.state === 'closed') {
      parts.push(section('closed', 'Signing is closed for this year',
        'Yearbooks open again next December. Your Year in Review is still there to look back on.'));
    } else if (!book) {
      parts.push(setupForm(null));
    } else {
      if (flash === 'saved') parts.push(el('p', 'yb-banner yb-banner--ok', 'Saved. Anyone with the link sees the new version.'));
      if (data.state === 'closed') {
        parts.push(el('p', 'yb-banner', `Signing closed after New Year's Day. ${plural((book.notes.shown || []).length, 'note')} to keep.`));
      }
      if (data.state !== 'closed' || book.url) parts.push(shareBox(book));
      parts.push(...notesBoxes(book));
      if (data.can_edit) parts.push(setupForm(book));
    }
    const friends = friendsBox();
    if (friends) parts.push(friends);
    if (data.state !== 'soon' || data.preview) parts.push(classLink());
    body.replaceChildren(...parts);
    flash = '';
    if (window.location.hash) {
      const target = document.getElementById(window.location.hash.slice(1));
      if (target && !render.scrolled) { render.scrolled = true; target.scrollIntoView({ block: 'start' }); }
    }
  }

  async function load() {
    try {
      data = await api(`/api/yearbook?year=${year}&seen=true`, { member: true });
      render();
    } catch (error) {
      body.replaceChildren(el('p', 'yb-status', error.message));
    }
  }

  if (root.dataset.view === 'book') signPage();
  else if (root.dataset.view === 'mine' && body) load();
})();
