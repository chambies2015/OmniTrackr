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
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description }),
    });
    if (!response.ok) throw new Error('Unable to create collection');
    event.target.reset();
    await loadCollections();
  } catch (error) {
    alert('Could not create that collection. Please try again.');
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
  const error = document.getElementById('collectionStudioError');
  error.textContent = '';
  error.hidden = true;
  renderCollectionReadinessChecklist(collection);
  document.getElementById('collectionStudioModal').style.display = 'flex';
}

function renderCollectionReadinessChecklist(collection) {
  const list = document.getElementById('collectionReadinessChecklist');
  if (!list || !collection) return;
  const description = document.getElementById('collectionStudioDescription')?.value.trim() || '';
  const title = document.getElementById('collectionStudioName')?.value.trim() || '';
  const availableItems = collection.items.filter(item => item.available).length;
  const savedTextIsCurrent = description === (collection.description || '').trim() && title === collection.name;
  const rows = [
    [description.length >= 300, `${Math.min(description.length, 300)}/300 introduction characters`],
    [availableItems >= 3, `${Math.min(availableItems, 3)}/3 available titles`],
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
    if (response.status === 409) { alert('That item is already in this collection.'); return; }
    if (!response.ok) throw new Error('Unable to add item');
    closeCollectionPicker();
    loadCollections();
  } catch (error) {
    alert('Could not add that item to the collection. Please try again.');
  }
}

async function moveCollectionItem(collectionId, itemId, position) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}/position`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ position }),
    });
    if (!response.ok) throw new Error('Unable to move item');
    loadCollections();
  } catch (error) { alert('Could not reorder this collection. Please try again.'); }
}

async function editCollectionItemNote(collectionId, itemId) {
  const collection = collectionsCache.find(item => item.id === collectionId);
  const item = collection?.items.find(entry => entry.id === itemId);
  if (!item) return;
  const curatorNote = prompt('What should readers notice about this pick?', item.curator_note || '');
  if (curatorNote === null) return;
  if (curatorNote.length > 500) {
    alert('Curator notes can be up to 500 characters.');
    return;
  }
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ curator_note: curatorNote }),
    });
    if (!response.ok) throw new Error('Unable to update note');
    loadCollections();
  } catch (error) { alert('Could not save that curator note. Please try again.'); }
}

async function removeCollectionItem(collectionId, itemId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}/items/${itemId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to remove item');
    loadCollections();
  } catch (error) { alert('Could not remove that item. Please try again.'); }
}

async function deleteCollection(collectionId) {
  if (!confirm('Delete this collection? Its media entries will stay in your library.')) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/${collectionId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to delete collection');
    loadCollections();
  } catch (error) { alert('Could not delete that collection. Please try again.'); }
}

// ============================================================================
