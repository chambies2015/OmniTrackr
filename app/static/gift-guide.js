// Holiday gift guide (/holidays/gifts) and shared gift lists (/gifts/<token>).
// Members build their list in the panel near the top of the guide; anyone with a
// list's link can mark a gift as theirs, and undo it from the same browser with the
// key the server handed back. Server text is only ever set as textContent.
(function () {
  'use strict';

  const CLAIMS_KEY = 'omnitrackr_gift_claims';

  function report(event) {
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  async function call(method, url, body) {
    const response = await fetch(url, {
      method, credentials: 'same-origin', headers: authHeaders(), body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data = {};
    try { data = await response.json(); } catch (error) { data = {}; }
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : 'That didn\'t work. Try again in a moment.';
      throw new Error(detail);
    }
    return data;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function safeImage(value) {
    return typeof value === 'string' && /^https:\/\/[^\s"'<>]+$/.test(value) ? value : null;
  }

  function art(entry, className) {
    const image = safeImage(entry.image);
    if (image) {
      const img = el('img', className);
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.width = 48;
      img.height = 72;
      return img;
    }
    const box = el('span', `${className} gg-box`);
    box.setAttribute('aria-hidden', 'true');
    box.appendChild(el('span', '', (entry.title || '?').slice(0, 1).toUpperCase()));
    return box;
  }

  function metaLine(entry) {
    return [entry.label, entry.year, entry.creator].filter(Boolean).join(' · ');
  }

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    if (target.closest('[data-gift-buy]')) report('gift_buy_clicked');
    if (target.closest('[data-gift-signup]')) report('gift_list_signup_clicked');
  });

  // ------------------------------------------------------------ the member's panel on the guide

  const panel = document.querySelector('[data-gift-panel]');
  const state = { list: null, suggestions: null };

  function setPanelStatus(text) {
    const status = panel && panel.querySelector('[data-gift-panel-status]');
    if (status) status.textContent = text || '';
  }

  function renderItems() {
    const list = state.list || { items: [], count: 0, max: 40 };
    const holder = panel.querySelector('[data-gift-items]');
    const count = panel.querySelector('[data-gift-count]');
    holder.replaceChildren();
    count.textContent = list.count ? `(${list.count} of ${list.max})` : '';
    if (!list.items.length) {
      holder.appendChild(el('li', 'gg-muted', 'Nothing on it yet. Add something from your library on the right, or from the guide below.'));
    }
    list.items.forEach(item => {
      const row = el('li', 'gg-item');
      row.appendChild(art(item, 'gg-item__art'));
      const body = el('div', 'gg-item__body');
      body.appendChild(el('strong', '', item.title));
      const meta = metaLine(item);
      if (meta) body.appendChild(el('small', '', meta));
      const noteId = `giftNote${item.id}`;
      const label = el('label', 'gg-visually-hidden', `Note for ${item.title}`);
      label.htmlFor = noteId;
      const note = el('input', 'gg-item__note');
      note.id = noteId;
      note.type = 'text';
      note.maxLength = 120;
      note.placeholder = 'Add a note (edition, size, colour…)';
      note.value = item.note || '';
      note.dataset.saved = note.value;
      note.addEventListener('change', async () => {
        if (note.value === note.dataset.saved) return;
        try {
          await call('PATCH', `/api/gift-list/items/${item.id}`, { note: note.value });
          note.dataset.saved = note.value;
          item.note = note.value;
          setPanelStatus(`Saved the note for ${item.title}.`);
        } catch (error) { setPanelStatus(error.message); }
      });
      body.append(label, note);
      const remove = el('button', 'gg-linkbutton gg-item__remove', 'Remove');
      remove.type = 'button';
      remove.setAttribute('aria-label', `Remove ${item.title} from your gift list`);
      remove.addEventListener('click', async () => {
        remove.disabled = true;
        try {
          const data = await call('DELETE', `/api/gift-list/items/${item.id}`);
          applyPayload(data);
          setPanelStatus(`Took ${item.title} off your list.`);
        } catch (error) { remove.disabled = false; setPanelStatus(error.message); }
      });
      row.append(body, remove);
      holder.appendChild(row);
    });
    renderShare();
  }

  function renderShare() {
    const list = state.list;
    const share = panel.querySelector('[data-gift-share]');
    if (!list || !list.exists) { share.hidden = true; return; }
    share.hidden = false;
    share.querySelector('[data-gift-link]').value = list.url || '';
    const open = share.querySelector('[data-gift-open]');
    if (typeof list.path === 'string' && /^\/gifts\/[A-Za-z0-9_-]{16,32}$/.test(list.path)) open.href = list.path;
    const message = share.querySelector('[data-gift-message]');
    if (document.activeElement !== message) message.value = list.message || '';
    share.querySelector('[data-gift-shared]').checked = Boolean(list.shared);
    share.querySelector('[data-gift-native-share]').hidden = typeof navigator.share !== 'function';
  }

  function renderIdeas() {
    const suggestions = state.suggestions || { waiting: [], favourites: [] };
    let total = 0;
    panel.querySelectorAll('[data-gift-ideas]').forEach(group => {
      const entries = suggestions[group.dataset.giftIdeas] || [];
      total += entries.length;
      group.hidden = !entries.length;
      const holder = group.querySelector('ul');
      holder.replaceChildren();
      entries.forEach(entry => {
        const row = el('li', 'gg-idea');
        row.appendChild(art(entry, 'gg-item__art'));
        const body = el('div', 'gg-item__body');
        body.appendChild(el('strong', '', entry.title));
        const meta = metaLine(entry);
        if (meta) body.appendChild(el('small', '', meta));
        const add = el('button', 'button button--ghost gg-idea__add', 'Add');
        add.type = 'button';
        add.setAttribute('aria-label', `Add ${entry.title} to your gift list`);
        add.addEventListener('click', () => addGift({ source: 'library', kind: entry.kind, item_id: entry.id }, add, entry.title));
        row.append(body, add);
        holder.appendChild(row);
      });
    });
    const empty = panel.querySelector('[data-gift-ideas-empty]');
    if (empty) empty.hidden = total > 0;
  }

  function applyPayload(data) {
    if (data.list) state.list = data.list;
    if (data.suggestions) state.suggestions = data.suggestions;
    renderItems();
    if (data.suggestions) renderIdeas();
  }

  async function addGift(body, button, title, status) {
    if (button) button.disabled = true;
    try {
      const data = await call('POST', '/api/gift-list/items', body);
      applyPayload(data);
      const text = data.state === 'existing' ? `${title || 'That'} is already on your list.` : `Added ${title || data.item.title} to your gift list.`;
      setPanelStatus(text);
      if (status) status.textContent = text;
      if (button && button.dataset.giftAddGuide) {
        button.textContent = 'On your gift list ✓';
        return;
      }
    } catch (error) {
      setPanelStatus(error.message);
      if (status) status.textContent = error.message;
    }
    if (button) button.disabled = false;
  }

  async function updateSettings(body, done) {
    try {
      const data = await call('PATCH', '/api/gift-list', body);
      state.list = data.list;
      renderShare();
      setPanelStatus(done);
    } catch (error) { setPanelStatus(error.message); }
  }

  if (panel) {
    call('GET', '/api/gift-list').then(applyPayload).catch(error => {
      panel.querySelector('[data-gift-items]').replaceChildren(el('li', 'gg-muted', error.message));
    });

    panel.querySelector('[data-gift-text]').addEventListener('submit', event => {
      event.preventDefault();
      const input = event.currentTarget.querySelector('input');
      const text = input.value.trim();
      if (!text) return;
      addGift({ source: 'text', text }, event.currentTarget.querySelector('button'), text).then(() => { input.value = ''; });
    });

    panel.querySelector('[data-gift-copy]').addEventListener('click', async () => {
      const input = panel.querySelector('[data-gift-link]');
      try {
        await navigator.clipboard.writeText(input.value);
        setPanelStatus('Link copied. Paste it into the family group chat.');
      } catch (error) {
        input.select();
        setPanelStatus('Select the link and copy it.');
      }
    });

    panel.querySelector('[data-gift-native-share]').addEventListener('click', async () => {
      try {
        await navigator.share({ title: 'My gift list', text: 'Here\'s my gift list. Mark what you\'re getting so nobody doubles up.', url: state.list.url });
      } catch (error) { /* closed the share sheet */ }
    });

    panel.querySelector('[data-gift-message-save]').addEventListener('click', () => {
      updateSettings({ message: panel.querySelector('[data-gift-message]').value }, 'Saved the note at the top of your list.');
    });

    panel.querySelector('[data-gift-shared]').addEventListener('change', event => {
      const on = event.currentTarget.checked;
      updateSettings({ shared: on }, on ? 'Your link works again.' : 'Your link is switched off. Anyone who opens it sees that it doesn\'t work.');
    });

    panel.querySelector('[data-gift-reset]').addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const data = await call('POST', '/api/gift-list/link');
        state.list = data.list;
        renderShare();
        setPanelStatus('Made a new link. The old one no longer works.');
      } catch (error) { setPanelStatus(error.message); }
      button.disabled = false;
    });

    document.querySelectorAll('[data-gift-add-guide]').forEach(button => {
      button.addEventListener('click', () => {
        const article = button.closest('.gg-gift');
        const title = article ? article.querySelector('h3').textContent : '';
        addGift({ source: 'guide', gift_id: button.dataset.giftAddGuide }, button, title, article && article.querySelector('[data-gift-status]'));
      });
    });
  }

  // ------------------------------------------------------------ a shared list: "I'm getting this"

  const shared = document.querySelector('[data-gift-token]');

  function readClaims() {
    try {
      const value = JSON.parse(localStorage.getItem(CLAIMS_KEY) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (error) { return {}; }
  }

  function writeClaims(claims) {
    try { localStorage.setItem(CLAIMS_KEY, JSON.stringify(claims)); } catch (error) { /* private mode */ }
  }

  function markTaken(row, mine) {
    row.classList.add('gg-wish--taken');
    const actions = row.querySelector('.gg-gift__actions');
    actions.querySelectorAll('[data-gift-claim], [data-gift-taken], [data-gift-unclaim]').forEach(node => node.remove());
    actions.appendChild(el('p', 'gg-wish__taken', mine ? 'You’re getting this' : 'Someone’s getting this'));
    if (mine) actions.appendChild(unclaimButton(row.dataset.giftItem));
  }

  function markOpen(row) {
    row.classList.remove('gg-wish--taken');
    const actions = row.querySelector('.gg-gift__actions');
    actions.querySelectorAll('[data-gift-claim], [data-gift-taken], .gg-wish__taken, [data-gift-unclaim]').forEach(node => node.remove());
    const button = el('button', 'button button--ghost gg-claim', 'I’m getting this');
    button.type = 'button';
    button.dataset.giftClaim = row.dataset.giftItem;
    button.addEventListener('click', () => claim(row, button));
    actions.appendChild(button);
  }

  function unclaimButton(itemId) {
    const button = el('button', 'gg-linkbutton', 'Changed my mind. Undo');
    button.type = 'button';
    button.dataset.giftUnclaim = itemId;
    button.addEventListener('click', () => unclaim(button.closest('[data-gift-item]'), button));
    return button;
  }

  function status(row, text) {
    const node = row.querySelector('[data-gift-status]');
    if (node) node.textContent = text;
  }

  async function claim(row, button) {
    const token = shared.dataset.giftToken;
    const itemId = row.dataset.giftItem;
    button.disabled = true;
    try {
      const data = await call('POST', `/api/gifts/${encodeURIComponent(token)}/items/${encodeURIComponent(itemId)}/claim`);
      const claims = readClaims();
      claims[`${token}:${itemId}`] = data.key;
      writeClaims(claims);
      markTaken(row, true);
      status(row, 'Marked as yours. Others will see it\'s taken, and the list\'s owner won\'t.');
    } catch (error) {
      button.disabled = false;
      status(row, error.message);
    }
  }

  async function unclaim(row, button) {
    const token = shared.dataset.giftToken;
    const itemId = row.dataset.giftItem;
    const claims = readClaims();
    const key = claims[`${token}:${itemId}`];
    if (!key) return;
    button.disabled = true;
    try {
      await call('POST', `/api/gifts/${encodeURIComponent(token)}/items/${encodeURIComponent(itemId)}/unclaim`, { key });
      delete claims[`${token}:${itemId}`];
      writeClaims(claims);
      markOpen(row);
      status(row, 'Undone. It\'s open for someone else again.');
    } catch (error) {
      button.disabled = false;
      status(row, error.message);
    }
  }

  if (shared) {
    const token = shared.dataset.giftToken;
    const claims = readClaims();
    shared.querySelectorAll('[data-gift-item]').forEach(row => {
      const claimButton = row.querySelector('[data-gift-claim]');
      if (claimButton) claimButton.addEventListener('click', () => claim(row, claimButton));
      if (row.querySelector('[data-gift-taken]') && claims[`${token}:${row.dataset.giftItem}`]) markTaken(row, true);
    });
  }
}());
