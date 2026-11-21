// Most members are not moderators: after one 401/403 stop asking on every Collections visit.
let moderatorInsightsDenied = false;

async function loadModeratorInsights() {
  const panel = document.getElementById('moderatorInsightsPanel');
  if (!panel) return;
  if (moderatorInsightsDenied) {
    panel.hidden = true;
    return;
  }
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/moderation/insights`);
    if (response.status === 401 || response.status === 403) moderatorInsightsDenied = true;
    if (!response.ok) throw new Error('Moderator insights unavailable');
    renderModeratorInsights(await response.json());
  } catch (error) {
    panel.hidden = true;
  }
}

async function createCollection(event) {
  event.preventDefault();
  const name = document.getElementById('collectionName').value;
  const description = document.getElementById('collectionDescription').value;
  const rankedInput = document.getElementById('collectionRanked');
  const ranked = rankedInput?.value === '1';
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description, ranked }),
    });
    if (!response.ok) throw new Error('Unable to create collection');
    const created = await response.json().catch(() => null);
    event.target.reset();
    if (rankedInput) rankedInput.value = '';
    await loadCollections();
    // Straight into the editor, where titles can be added by search.
    if (created?.id) openCollectionStudio(created.id);
  } catch (error) {
    showNotice('Could not create that collection. Please try again.');
  }
}

function openCollectionStudio(collectionId) {
  const collection = collectionsCache.find(item => item.id === collectionId);
  if (!collection) return;
  document.getElementById('collectionStudioId').value = String(collection.id);
  document.getElementById('collectionStudioName').value = collection.name || '';
  document.getElementById('collectionStudioDescription').value = collection.description || '';
  document.getElementById('collectionStudioCover').value = collection.cover_url || '';
  document.getElementById('collectionStudioPublic').checked = Boolean(collection.is_public);
  const ranked = document.getElementById('collectionStudioRanked');
  if (ranked) ranked.checked = Boolean(collection.ranked);
  const search = document.getElementById('collectionStudioSearch');
  if (search) search.value = '';
  document.getElementById('collectionStudioResults')?.replaceChildren();
  const error = document.getElementById('collectionStudioError');
  error.textContent = '';
  error.hidden = true;
  renderCollectionReadinessChecklist(collection);
  renderCollectionStudioExtras(collection);
  document.getElementById('collectionStudioModal').style.display = 'flex';
}

function applyCollectionStarter(button) {
  const name = document.getElementById('collectionName');
  if (!name || !button) return;
  name.value = button.dataset.starterName || '';
  const ranked = document.getElementById('collectionRanked');
  if (ranked) ranked.value = button.dataset.starterRanked === '1' ? '1' : '';
  name.focus();
  name.select();
}

function studioCollection() {
  const collectionId = Number(document.getElementById('collectionStudioId')?.value);
  return collectionsCache.find(item => item.id === collectionId) || null;
}

function collectionShareUrl(path) {
  try { return new URL(path, window.location.origin).href; } catch (error) { return path; }
}

function renderCollectionStudioExtras(collection) {
  const available = collection.items.filter(item => item.available).length;
  const count = document.getElementById('collectionStudioCount');
  if (count) {
    count.textContent = available
      ? `${available} title${available === 1 ? '' : 's'} on this list. Reorder them and add notes on the list's card.`
      : 'Nothing on this list yet. Search above, or use Collect on any library card.';
  }
  const panel = document.getElementById('collectionStudioLink');
  if (!panel) return;
  panel.replaceChildren();
  if (collection.link_url) {
    const url = collectionShareUrl(collection.link_url);
    const field = document.createElement('input');
    field.type = 'text';
    field.readOnly = true;
    field.value = url;
    field.className = 'collection-studio-link__url';
    field.setAttribute('aria-label', 'Share link');
    field.addEventListener('focus', () => field.select());
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'action-btn';
    copy.textContent = navigator.share ? 'Share' : 'Copy link';
    copy.addEventListener('click', async () => {
      try {
        if (navigator.share) {
          await navigator.share({ title: collection.name, url });
          return;
        }
        await navigator.clipboard.writeText(url);
        copy.textContent = 'Copied';
        setTimeout(() => { copy.textContent = 'Copy link'; }, 2000);
      } catch (error) {
        if (error?.name === 'AbortError') return;
        field.focus();
        field.select();
      }
    });
    const open = document.createElement('a');
    open.href = collection.link_url;
    open.target = '_blank';
    open.rel = 'noopener';
    open.textContent = 'Open ↗';
    const off = document.createElement('button');
    off.type = 'button';
    off.className = 'completion-ritual-modal__skip';
    off.textContent = 'Turn link off';
    off.addEventListener('click', () => setCollectionShareLink(collection.id, false));
    const row = document.createElement('div');
    row.className = 'collection-studio-link__row';
    row.append(copy, open, off);
    panel.append(field, row);
    if (!collection.readiness?.link_ready) {
      const note = document.createElement('p');
      note.className = 'collection-studio-modal__error';
      note.textContent = available < 3
        ? `The link shows a "not shared anymore" page until the list has 3 titles again.`
        : 'The link is paused: something in the title, introduction or notes needs rewording.';
      panel.appendChild(note);
    }
    return;
  }
  if (available < 3) {
    const note = document.createElement('p');
    note.className = 'collection-studio-modal__hint';
    note.textContent = `Add ${3 - available} more title${3 - available === 1 ? '' : 's'} and you can share this list by link.`;
    panel.appendChild(note);
    return;
  }
  const make = document.createElement('button');
  make.type = 'button';
  make.className = 'action-btn';
  make.textContent = 'Make a share link';
  make.addEventListener('click', () => setCollectionShareLink(collection.id, true));
  panel.appendChild(make);
}

async function setCollectionShareLink(collectionId, enabled) {
  const error = document.getElementById('collectionStudioError');
  error.hidden = true;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/link`, { method: enabled ? 'POST' : 'DELETE' });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      error.textContent = apiErrorText(body, 'Could not change the share link. Please try again.');
      error.hidden = false;
      return;
    }
    await loadCollections();
    const collection = collectionsCache.find(item => item.id === collectionId);
    if (collection && studioCollection()?.id === collectionId) renderCollectionStudioExtras(collection);
    showNotice(enabled ? 'Share link ready. Anyone with it can see this list.' : 'Share link turned off.', 'success');
  } catch (requestError) {
    error.textContent = 'Could not change the share link. Please try again.';
    error.hidden = false;
  }
}

let collectionStudioSearchTimer = null;
let collectionStudioSearchSequence = 0;

function searchCollectionStudioLibrary() {
  clearTimeout(collectionStudioSearchTimer);
  collectionStudioSearchTimer = setTimeout(runCollectionStudioSearch, 220);
}

async function runCollectionStudioSearch() {
  const input = document.getElementById('collectionStudioSearch');
  const results = document.getElementById('collectionStudioResults');
  const collection = studioCollection();
  if (!input || !results || !collection) return;
  const query = input.value.trim();
  const sequence = ++collectionStudioSearchSequence;
  if (!query) { results.replaceChildren(); return; }
  try {
    const response = await authenticatedFetch(`${API_BASE}/library/search?q=${encodeURIComponent(query)}`);
    if (sequence !== collectionStudioSearchSequence) return;
    if (!response.ok) throw new Error('search');
    const matches = await response.json();
    if (sequence !== collectionStudioSearchSequence) return;
    results.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'collection-studio-modal__hint';
      empty.textContent = 'Nothing in your library matches that yet.';
      results.appendChild(empty);
      return;
    }
    const current = studioCollection() || collection;
    const onList = new Set(current.items.map(item => `${item.category}:${item.item_id}`));
    matches.forEach(match => {
      const row = document.createElement('div');
      row.className = 'collection-studio-add__row';
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = match.title;
      const meta = document.createElement('small');
      meta.textContent = `${match.label} · ${match.status}`;
      copy.append(title, meta);
      const add = document.createElement('button');
      add.type = 'button';
      const already = onList.has(`${match.tab}:${match.id}`);
      add.textContent = already ? 'On the list' : 'Add';
      add.disabled = already;
      add.setAttribute('aria-label', already ? `${match.title} is on the list` : `Add ${match.title} to the list`);
      add.addEventListener('click', () => addStudioSearchResult(current.id, match, add));
      row.append(copy, add);
      results.appendChild(row);
    });
  } catch (error) {
    if (sequence !== collectionStudioSearchSequence) return;
    results.replaceChildren();
    const failed = document.createElement('p');
    failed.className = 'collection-studio-modal__hint';
    failed.textContent = 'Search is unavailable right now. Please try again.';
    results.appendChild(failed);
  }
}

async function addStudioSearchResult(collectionId, match, button) {
  button.disabled = true;
  button.textContent = 'Adding…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: match.tab, item_id: match.id }),
    });
    if (response.status === 409) { button.textContent = 'On the list'; return; }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(apiErrorText(body, 'Could not add that title. Please try again.'));
    }
    button.textContent = 'Added';
    await loadCollections();
    const collection = collectionsCache.find(item => item.id === collectionId);
    if (collection && studioCollection()?.id === collectionId) {
      renderCollectionReadinessChecklist(collection);
      renderCollectionStudioExtras(collection);
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = 'Add';
    showNotice(error.message || 'Could not add that title. Please try again.');
  }
}

function renderCollectionReadinessChecklist(collection) {
  const list = document.getElementById('collectionReadinessChecklist');
  if (!list || !collection) return;
  const description = document.getElementById('collectionStudioDescription')?.value.trim() || '';
  const title = document.getElementById('collectionStudioName')?.value.trim() || '';
  const availableItems = collection.items.filter(item => item.available).length;
  const savedTextIsCurrent = description === (collection.description || '').trim() && title === collection.name;
  const rows = [
    [availableItems >= 3, `${Math.min(availableItems, 3)}/3 titles (enough for a share link and the gallery)`],
    [description.length >= 300, `${Math.min(description.length, 300)}/300 introduction characters (gallery only)`],
    [
      savedTextIsCurrent ? Boolean(collection.readiness?.discover_ready) : null,
      savedTextIsCurrent
        ? (collection.readiness?.discover_ready ? 'Automated discovery checks passed' : 'Revise the title or introduction to pass the remaining discovery checks')
        : 'Automated discovery checks run when you save',
    ],
  ];
  list.replaceChildren();
  rows.forEach(([ready, label]) => {
    const item = document.createElement('li');
    item.className = ready === true ? 'is-ready' : ready === false ? 'needs-work' : 'is-pending';
    item.textContent = `${ready === true ? '✓' : ready === false ? '•' : '…'} ${label}`;
    list.appendChild(item);
  });
}

function updateCollectionReadinessDraft() {
  const collectionId = Number(document.getElementById('collectionStudioId')?.value);
  const collection = collectionsCache.find(item => item.id === collectionId);
  if (collection) renderCollectionReadinessChecklist(collection);
}

function closeCollectionStudio() {
  const modal = document.getElementById('collectionStudioModal');
  if (modal) modal.style.display = 'none';
}

async function saveCollectionStudio(event) {
  event.preventDefault();
  const collectionId = Number(document.getElementById('collectionStudioId').value);
  if (!Number.isInteger(collectionId) || collectionId < 1) return;
  const error = document.getElementById('collectionStudioError');
  const payload = {
    name: document.getElementById('collectionStudioName').value,
    description: document.getElementById('collectionStudioDescription').value,
    cover_url: document.getElementById('collectionStudioCover').value || null,
    is_public: document.getElementById('collectionStudioPublic').checked,
    ranked: Boolean(document.getElementById('collectionStudioRanked')?.checked),
  };
  error.hidden = true;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      error.textContent = body.detail || 'Could not save this collection. Please try again.';
      error.hidden = false;
      return;
    }
    closeCollectionStudio();
    await loadCollections();
  } catch (requestError) {
    error.textContent = 'Could not save this collection. Please try again.';
    error.hidden = false;
  }
}

async function openCollectionPicker(category, itemId, itemTitle) {
  if (!category || !Number.isInteger(itemId) || itemId < 1) return;
  const target = collectionPickerTarget = { category, itemId, itemTitle: itemTitle || 'this item' };
  const collections = await loadCollections();
  if (collectionPickerTarget !== target || !Array.isArray(collections) || !hasStoredAuth()) return;
  const options = document.getElementById('collectionPickerOptions');
  const title = document.getElementById('collectionPickerItemTitle');
  if (!options || !title) return;
  title.textContent = `Choose a collection for ${target.itemTitle}.`;
  options.replaceChildren();
  if (!collections.length) {
    const empty = document.createElement('p');
    empty.textContent = 'Create your first collection in the Collections tab, then come back to add this item.';
    options.appendChild(empty);
  } else {
    collections.forEach((collection) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'collection-picker-modal__option';
      button.dataset.action = 'add-to-collection';
      button.dataset.collectionId = collection.id;
      button.textContent = collection.name;
      options.appendChild(button);
    });
  }
  document.getElementById('collectionPickerModal').style.display = 'flex';
}

function closeCollectionPicker() {
  const modal = document.getElementById('collectionPickerModal');
  if (modal) modal.style.display = 'none';
  collectionPickerTarget = null;
}

async function addToCollection(collectionId) {
  if (!collectionPickerTarget || !collectionId) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: collectionPickerTarget.category, item_id: collectionPickerTarget.itemId }),
    });
    if (response.status === 409) { showNotice('That item is already in this collection.'); return; }
    if (!response.ok) throw new Error('Unable to add item');
    closeCollectionPicker();
    loadCollections();
  } catch (error) {
    showNotice('Could not add that item to the collection. Please try again.');
  }
}

async function moveCollectionItem(collectionId, itemId, position) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}/position`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ position }),
    });
    if (!response.ok) throw new Error('Unable to move item');
    loadCollections();
  } catch (error) { showNotice('Could not reorder this collection. Please try again.'); }
}

async function editCollectionItemNote(collectionId, itemId) {
  const collection = collectionsCache.find(item => item.id === collectionId);
  const item = collection?.items.find(entry => entry.id === itemId);
  if (!item) return;
  const curatorNote = prompt('What should readers notice about this pick?', item.curator_note || '');
  if (curatorNote === null) return;
  if (curatorNote.length > 500) {
    showNotice('Curator notes can be up to 500 characters.');
    return;
  }
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ curator_note: curatorNote }),
    });
    if (!response.ok) throw new Error('Unable to update note');
    loadCollections();
  } catch (error) { showNotice('Could not save that curator note. Please try again.'); }
}

async function removeCollectionItem(collectionId, itemId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to remove item');
    loadCollections();
  } catch (error) { showNotice('Could not remove that item. Please try again.'); }
}

async function deleteCollection(collectionId) {
  if (!confirm('Delete this collection? Its media entries will stay in your library.')) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to delete collection');
    loadCollections();
  } catch (error) { showNotice('Could not delete that collection. Please try again.'); }
}

// ============================================================================
