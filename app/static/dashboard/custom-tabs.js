let customTabs = [];
let customTabFieldCounter = 0;
const getAuthTokenValue = () => (typeof getToken === 'function' ? getToken() : localStorage.getItem('omnitrackr_token'));
const hasStoredAuth = () => (typeof isAuthenticated === 'function' ? isAuthenticated() : !!getAuthTokenValue() || !!localStorage.getItem('omnitrackr_user'));
const authFetchOptions = (options = {}) => {
  const token = getAuthTokenValue();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return {
    ...options,
    credentials: options.credentials || 'same-origin',
    headers
  };
};

async function loadCustomTabs() {
  try {
    if (!hasStoredAuth()) return;
    
    const response = await authenticatedFetch(`${API_BASE}/custom-tabs/`);
    
    if (response.ok) {
      customTabs = await response.json();
      renderCustomTabs();
    } else if (response.status === 401) {
      console.error('Unauthorized - token may be expired');
    } else {
      console.error('Failed to load custom tabs:', response.status);
    }
  } catch (error) {
    console.error('Error loading custom tabs:', error);
  }
}

function renderCustomTabs() {
  const container = document.getElementById('customTabsContainer');
  if (!container) return;
  const mainContainer = document.getElementById('mainContainer');
  if (mainContainer) {
    mainContainer.querySelectorAll('.tab-content[id^="custom-"]').forEach(el => el.remove());
  }
  container.innerHTML = '';
  
  customTabs.forEach(tab => {
    const tabButton = document.createElement('button');
    tabButton.className = 'tab';
    tabButton.textContent = tab.name;
    tabButton.dataset.switchTab = `custom-${tab.id}`;
    container.appendChild(tabButton);
    
    createCustomTabContent(tab);
  });
}

function createCustomTabContent(tab) {
  const mainContainer = document.getElementById('mainContainer');
  if (!mainContainer) return;
  
  const tabContent = document.createElement('div');
  tabContent.id = `custom-${tab.id}-tab`;
  tabContent.className = 'tab-content';
  
  tabContent.innerHTML = `
    <div class="card">
      <div class="collapsible-header" data-toggle-collapsible="customTab${tab.id}Form">
        <h2 class="custom-tab-header-title">Add ${escapeHtml(tab.name)}</h2>
        <span class="collapsible-icon" id="customTab${tab.id}FormIcon">▼</span>
      </div>
      <div class="collapsible-content" id="customTab${tab.id}FormContent" hidden>
        <form id="addCustomTab${tab.id}Form">
          <div>
            <input type="text" id="customTab${tab.id}Title" placeholder="Title" required>
          </div>
          ${generateCustomTabFormFields(tab)}
          ${tab.allow_uploads ? `
            <div>
              <label>Poster URL <input type="text" id="customTab${tab.id}PosterUrl" placeholder="Optional poster URL"></label>
            </div>
            <div>
              <label>Or Upload Poster <input type="file" id="customTab${tab.id}PosterFile" accept="image/*"></label>
            </div>
          ` : ''}
          <button type="submit" class="action-btn">Add ${escapeHtml(tab.name)}</button>
        </form>
      </div>
    </div>
    <div class="card">
      <div class="custom-tab-list-header">
        <h2 class="custom-tab-list-title">${escapeHtml(tab.name)}</h2>
        <span id="customTab${tab.id}Count" class="custom-tab-count"></span>
      </div>
      <div class="custom-tab-toolbar">
        <input type="text" id="customTab${tab.id}Search" placeholder="Search" class="custom-tab-toolbar-input">
        <button id="loadCustomTab${tab.id}" class="action-btn custom-tab-toolbar-button">Refresh</button>
      </div>
      <div class="table-container">
        <table id="customTab${tab.id}Table">
          <thead id="customTab${tab.id}TableHead"></thead>
          <tbody id="customTab${tab.id}TableBody"></tbody>
        </table>
      </div>
    </div>
  `;
  
  mainContainer.appendChild(tabContent);
  
  const form = document.getElementById(`addCustomTab${tab.id}Form`);
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (form.dataset.editingItemId) {
        handleUpdateCustomTabItem(tab, parseInt(form.dataset.editingItemId));
      } else {
        handleAddCustomTabItem(tab);
      }
    });
  }
  
  document.getElementById(`loadCustomTab${tab.id}`).addEventListener('click', () => {
    loadCustomTabItems(tab);
  });
  
  document.getElementById(`customTab${tab.id}Search`).addEventListener('input', (e) => {
    filterCustomTabItems(tab, e.target.value);
  });
  
  loadCustomTabItems(tab);
}

function generateCustomTabFormFields(tab) {
  return tab.fields.map(field => {
    const required = field.required ? 'required' : '';
    let input = '';
    
    switch (field.field_type) {
      case 'text':
        input = `<input type="text" id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)}" ${required}>`;
        break;
      case 'number':
        input = `<input type="number" id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)}" ${required}>`;
        break;
      case 'date':
        input = `<input type="date" id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)}" ${required}>`;
        break;
      case 'boolean':
        input = `<label>${escapeHtml(field.label)} <input type="checkbox" id="customTab${tab.id}Field${field.key}"></label>`;
        break;
      case 'rating':
        input = `<input type="number" min="0" max="10" step="0.1" id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)} (0-10.0)" ${required}>`;
        break;
      case 'review':
        input = `<textarea id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)}" rows="1" ${required}></textarea>`;
        break;
      case 'status':
        input = `<label>${escapeHtml(field.label)} <input type="checkbox" id="customTab${tab.id}Field${field.key}"></label>`;
        break;
      default:
        input = `<input type="text" id="customTab${tab.id}Field${field.key}" placeholder="${escapeHtml(field.label)}" ${required}>`;
    }
    
    return `<div>${input}</div>`;
  }).join('');
}

async function handleAddCustomTabItem(tab) {
  try {
    if (!hasStoredAuth()) {
      alert('You must be logged in to add items');
      return;
    }
    
    const titleInput = document.getElementById(`customTab${tab.id}Title`);
    const submitBtn = titleInput?.closest('form')?.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn?.textContent;
    
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Adding...';
    }
    
    const title = titleInput.value.trim();
    
    if (!title) {
      alert('Title is required');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
      return;
    }
    
    if (title.length > 500) {
      alert('Title is too long (max 500 characters)');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
      return;
    }
    
    const fieldValues = {};
    tab.fields.forEach(field => {
      const input = document.getElementById(`customTab${tab.id}Field${field.key}`);
      if (input) {
        if (field.field_type === 'boolean' || field.field_type === 'status') {
          fieldValues[field.key] = input.checked;
        } else {
          const value = input.value.trim();
          if (value) {
            if (field.field_type === 'number' || field.field_type === 'rating') {
              fieldValues[field.key] = parseFloat(value);
            } else {
              fieldValues[field.key] = value;
            }
          }
        }
      }
    });
    
    let posterUrl = null;
    // Keep the chosen file itself: the form is cleared before the upload runs.
    let posterFile = null;
    if (tab.allow_uploads) {
      const posterUrlInput = document.getElementById(`customTab${tab.id}PosterUrl`);
      const posterFileInput = document.getElementById(`customTab${tab.id}PosterFile`);
      
      if (posterUrlInput && posterUrlInput.value.trim()) {
        posterUrl = posterUrlInput.value.trim();
      } else if (posterFileInput && posterFileInput.files.length > 0) {
        posterFile = posterFileInput.files[0];
      }
    }
    
    if (tab.source_type !== 'none' && title) {
      await fetchMetadataForCustomTab(tab, title, fieldValues, posterUrl, posterFile);
      return;
    }
    
    const response = await fetch(`${API_BASE}/custom-tabs/${tab.id}/items`, {
      method: 'POST',
      ...authFetchOptions({ headers: { 'Content-Type': 'application/json' } }),
      body: JSON.stringify({
        title,
        field_values: fieldValues,
        poster_url: posterUrl
      })
    });
    
    if (response.ok) {
      const item = await response.json();
      titleInput.value = '';
      tab.fields.forEach(field => {
        const input = document.getElementById(`customTab${tab.id}Field${field.key}`);
        if (input) {
          if (input.type === 'checkbox') {
            input.checked = false;
          } else {
            input.value = '';
          }
        }
      });
      if (tab.allow_uploads) {
        const posterUrlInput = document.getElementById(`customTab${tab.id}PosterUrl`);
        const posterFileInput = document.getElementById(`customTab${tab.id}PosterFile`);
        if (posterUrlInput) posterUrlInput.value = '';
        if (posterFileInput) posterFileInput.value = '';
      }
      
      if (posterFile) {
        await uploadCustomTabPoster(tab.id, item.id, posterFile);
      }
      
      loadCustomTabItems(tab);
    } else {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to add item' }));
      alert(errorData.detail || 'Failed to add item');
    }
  } catch (error) {
    if (error.message === 'Validation failed') {
      return;
    }
    console.error('Error adding custom tab item:', error);
    alert('Failed to add item. Please try again.');
  } finally {
    const titleInput = document.getElementById(`customTab${tab.id}Title`);
    const submitBtn = titleInput?.closest('form')?.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = `Add ${tab.name}`;
    }
  }
}

async function fetchMetadataForCustomTab(tab, title, fieldValues, posterUrl, posterFile = null) {
  try {
    let metadataFetched = false;
    
    if (tab.source_type === 'omdb') {
      try {
        const year = fieldValues.year || '';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        const response = await fetch(`${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}${year ? '&year=' + encodeURIComponent(year) : ''}`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          if (data.Response === 'True' && data.Poster && data.Poster !== 'N/A') {
            posterUrl = posterUrl || data.Poster;
            if (data.Title) fieldValues.title = data.Title;
            if (data.Year) fieldValues.year = parseInt(data.Year);
            if (data.Director && data.Director !== 'N/A') fieldValues.director = data.Director;
            metadataFetched = true;
          }
        }
      } catch (fetchError) {
        if (fetchError.name !== 'AbortError') {
          console.warn('OMDB API fetch failed:', fetchError);
        }
      }
    } else if (tab.source_type === 'jikan') {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        const response = await fetch(`${API_BASE}/api/proxy/jikan?query=${encodeURIComponent(title)}`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          if (data.data && data.data.length > 0) {
            const anime = data.data[0];
            const posterUrlFromApi = anime.images?.jpg?.large_image_url || anime.images?.jpg?.image_url;
            if (posterUrlFromApi) {
              posterUrl = posterUrl || posterUrlFromApi;
              if (anime.title) fieldValues.title = anime.title;
              if (anime.year) fieldValues.year = anime.year;
              if (anime.seasons) fieldValues.seasons = anime.seasons;
              if (anime.episodes) fieldValues.episodes = anime.episodes;
              metadataFetched = true;
            }
          }
        }
      } catch (fetchError) {
        if (fetchError.name !== 'AbortError') {
          console.warn('Jikan API fetch failed:', fetchError);
        }
      }
    } else if (tab.source_type === 'rawg') {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        const response = await fetch(`${API_BASE}/api/proxy/rawg?search=${encodeURIComponent(title)}`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          const data = await response.json();
          if (data.results && data.results.length > 0) {
            const game = data.results[0];
            if (game.background_image) {
              posterUrl = posterUrl || game.background_image;
              if (game.name) fieldValues.title = game.name;
              if (game.released) fieldValues.release_date = game.released;
              if (game.genres && game.genres.length > 0) {
                fieldValues.genres = game.genres.map(g => g.name).join(', ');
              }
              if (game.slug) {
                fieldValues.rawg_link = `https://rawg.io/games/${game.slug}`;
              }
              metadataFetched = true;
            }
          }
        }
      } catch (fetchError) {
        if (fetchError.name !== 'AbortError') {
          console.warn('RAWG API fetch failed:', fetchError);
        }
      }
    }
    
    const finalTitle = fieldValues.title || title;
    delete fieldValues.title;
    
    await createCustomTabItemAfterMetadata(tab, finalTitle, fieldValues, posterUrl, posterFile);
  } catch (error) {
    console.error('Error fetching metadata:', error);
    if (error.name === 'AbortError') {
      console.warn('Metadata fetch timed out. Adding item without metadata.');
    } else {
      console.warn('Failed to fetch metadata. Adding item without metadata.');
    }
    
    const finalTitle = fieldValues.title || title;
    delete fieldValues.title;
    
    await createCustomTabItemAfterMetadata(tab, finalTitle, fieldValues, posterUrl, posterFile);
  }
}

async function createCustomTabItemAfterMetadata(tab, title, fieldValues, posterUrl, posterFile = null) {
  try {
    const response = await fetch(`${API_BASE}/custom-tabs/${tab.id}/items`, {
      method: 'POST',
      ...authFetchOptions({ headers: { 'Content-Type': 'application/json' } }),
      body: JSON.stringify({
        title,
        field_values: fieldValues,
        poster_url: posterUrl
      })
    });
    
    if (response.ok) {
      const item = await response.json();
      document.getElementById(`customTab${tab.id}Title`).value = '';
      tab.fields.forEach(field => {
        const input = document.getElementById(`customTab${tab.id}Field${field.key}`);
        if (input) {
          if (input.type === 'checkbox') {
            input.checked = false;
          } else {
            input.value = '';
          }
        }
      });
      if (tab.allow_uploads) {
        const posterUrlInput = document.getElementById(`customTab${tab.id}PosterUrl`);
        const posterFileInput = document.getElementById(`customTab${tab.id}PosterFile`);
        if (posterUrlInput) posterUrlInput.value = '';
        if (posterFileInput) posterFileInput.value = '';
      }
      
      // A poster the member chose themselves wins over one found by the metadata lookup.
      if (posterFile) {
        await uploadCustomTabPoster(tab.id, item.id, posterFile);
      }
      
      loadCustomTabItems(tab);
    } else {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to add item' }));
      alert(errorData.detail || 'Failed to add item');
    }
  } catch (createError) {
    console.error('Error creating item:', createError);
    alert('Failed to add item. Please try again.');
  }
}

async function uploadCustomTabPoster(tabId, itemId, file) {
  if (!hasStoredAuth()) return false;
  if (file.size > 5 * 1024 * 1024) {
    alert('The poster must be 5 MB or smaller. Choose a smaller image and try again.');
    return false;
  }
  try {
    const body = new FormData(); body.append('file', file);
    const response = await fetch(`${API_BASE}/custom-tabs/${tabId}/items/${itemId}/poster`, {
      method: 'POST', ...authFetchOptions(), body,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      alert(typeof error.detail === 'string' ? error.detail : 'The item was saved, but its poster could not be uploaded. Please try again.');
      return false;
    }
    return true;
  } catch (error) {
    console.error('Error uploading poster:', error);
    alert('The item was saved, but its poster could not be uploaded. Please try again.');
    return false;
  }
}

async function loadCustomTabItems(tab) {
  try {
    if (!hasStoredAuth()) return;
    
    const tableBody = document.getElementById(`customTab${tab.id}TableBody`);
    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="100%" class="custom-tab-list-status">Loading...</td></tr>';
    }
    
    const response = await fetch(`${API_BASE}/custom-tabs/${tab.id}/items`, authFetchOptions());
    
    if (response.ok) {
      const items = await response.json();
      renderCustomTabItems(tab, items);
    } else if (response.status === 404) {
      if (tableBody) {
        tableBody.innerHTML = '<tr><td colspan="100%" class="custom-tab-list-status">Tab not found</td></tr>';
      }
    } else {
      if (tableBody) {
        tableBody.innerHTML = '<tr><td colspan="100%" class="custom-tab-list-status custom-tab-list-status-danger">Failed to load items</td></tr>';
      }
    }
  } catch (error) {
    console.error('Error loading custom tab items:', error);
    const tableBody = document.getElementById(`customTab${tab.id}TableBody`);
    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="100%" class="custom-tab-list-status custom-tab-list-status-danger">Error loading items</td></tr>';
    }
  }
}

function renderCustomTabItems(tab, items) {
  const tableHead = document.getElementById(`customTab${tab.id}TableHead`);
  const tableBody = document.getElementById(`customTab${tab.id}TableBody`);
  const countSpan = document.getElementById(`customTab${tab.id}Count`);
  
  if (!tableHead || !tableBody) return;
  
  countSpan.textContent = `${items.length} ${items.length === 1 ? 'item' : 'items'}`;
  
  if (items.length === 0) {
    tableHead.innerHTML = '';
    tableBody.innerHTML = '<tr><td colspan="100%" class="custom-tab-list-status custom-tab-list-status-muted">No items yet. Add your first item above!</td></tr>';
    return;
  }
  
  const headers = ['Poster', 'Title'];
  tab.fields.forEach(field => {
    headers.push(field.label);
  });
  headers.push('Actions');
  
  tableHead.innerHTML = `<tr>${headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`;
  
  tableBody.innerHTML = items.map(item => {
    const cells = [
      `<td id="custom-poster-${item.id}"></td>`,
      `<td>${escapeHtml(item.title)}</td>`
    ];
    
    tab.fields.forEach(field => {
      const value = item.field_values?.[field.key];
      let displayValue = '';
      if (value !== undefined && value !== null && value !== '') {
        if (field.field_type === 'boolean' || field.field_type === 'status') {
          displayValue = value ? '✓' : '✗';
        } else if (field.field_type === 'date' && value) {
          displayValue = escapeHtml(String(value));
        } else if (field.field_type === 'rating' && value !== null) {
          displayValue = escapeHtml(parseFloat(value).toFixed(1));
        } else {
          displayValue = escapeHtml(String(value));
        }
      }
      cells.push(`<td>${displayValue}</td>`);
    });
    
    cells.push(`
      <td>
        <button class="action-btn" data-action="edit-custom-tab-item" data-tab-id="${tab.id}" data-item-id="${item.id}" title="Edit item">Edit</button>
        <button class="action-btn btn-danger" data-action="delete-custom-tab-item" data-tab-id="${tab.id}" data-item-id="${item.id}" title="Delete item">Delete</button>
      </td>
    `);
    
    return `<tr>${cells.join('')}</tr>`;
  }).join('');
  
  items.forEach(item => {
    if (item.poster_url) {
      setTimeout(() => displayCustomTabPoster(item.id, item.poster_url, item.title), 0);
    }
  });
}

function displayCustomTabPoster(id, posterUrl, title) {
  const cell = document.getElementById(`custom-poster-${id}`);
  if (cell && posterUrl) {
    if (cell.querySelector('img')) return;
    
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = `${title} poster`;
    img.style.width = '50px';
    img.style.height = '75px';
    img.style.objectFit = 'cover';
    img.style.cursor = 'pointer';
    img.style.borderRadius = '4px';
    img.onclick = () => showImagePopup(posterUrl, `${title} poster`);
    img.onerror = () => {
      img.style.display = 'none';
      cell.innerHTML = '<span class="search-result-meta-small text-secondary">No image</span>';
    };
    cell.appendChild(img);
  }
}

function filterCustomTabItems(tab, searchTerm) {
  const tableBody = document.getElementById(`customTab${tab.id}TableBody`);
  if (!tableBody) return;
  
  const rows = tableBody.querySelectorAll('tr');
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    if (text.includes(searchTerm.toLowerCase())) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

async function deleteCustomTabItem(tabId, itemId) {
  if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) return;
  
  try {
    if (!hasStoredAuth()) {
      alert('You must be logged in to delete items');
      return;
    }
    
    const response = await fetch(`${API_BASE}/custom-tabs/${tabId}/items/${itemId}`, {
      method: 'DELETE',
      ...authFetchOptions()
    });
    
    if (response.ok) {
      const tab = customTabs.find(t => t.id === tabId);
      if (tab) {
        loadCustomTabItems(tab);
      }
    } else {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to delete item' }));
      alert(errorData.detail || 'Failed to delete item');
    }
  } catch (error) {
    console.error('Error deleting item:', error);
    alert('Failed to delete item. Please try again.');
  }
}

function resetCustomTabItemForm(tab) {
  const form = document.getElementById(`addCustomTab${tab.id}Form`);
  if (!form) return;
  form.dataset.editRequest = String(Number(form.dataset.editRequest || 0) + 1);
  delete form.dataset.editingItemId;
  const title = document.getElementById(`customTab${tab.id}Title`);
  if (title) title.value = '';
  tab.fields.forEach(field => {
    const input = document.getElementById(`customTab${tab.id}Field${field.key}`);
    if (!input) return;
    if (input.type === 'checkbox') input.checked = false;
    else input.value = '';
  });
  for (const suffix of ['PosterUrl', 'PosterFile']) {
    const input = document.getElementById(`customTab${tab.id}${suffix}`);
    if (input) input.value = '';
  }
  const submit = form.querySelector('button[type="submit"]');
  if (submit) { submit.textContent = `Add ${tab.name}`; submit.onclick = null; }
  form.querySelector('[data-custom-tab-cancel]')?.remove();
}

async function editCustomTabItem(tabId, itemId) {
  const tab = customTabs.find(t => t.id === tabId);
  const form = document.getElementById(`addCustomTab${tabId}Form`);
  if (!hasStoredAuth() || !tab || !form || form.dataset.savingItem) return;
  const request = String(Number(form.dataset.editRequest || 0) + 1);
  form.dataset.editRequest = request;
  const current = () => form.dataset.editRequest === request && !form.dataset.savingItem && hasStoredAuth();
  try {
    const response = await fetch(`${API_BASE}/custom-tabs/${tabId}/items/${itemId}`, authFetchOptions());
    if (!current()) return;
    if (!response.ok) { alert('Failed to load item for editing'); return; }
    const item = await response.json();
    if (!current()) return;
    // Every field belongs to this item, including its absent optional values.
    resetCustomTabItemForm(tab);
    const titleInput = document.getElementById(`customTab${tabId}Title`);
    if (!titleInput) return;
    titleInput.value = item.title;
    const content = document.getElementById(`customTab${tabId}FormContent`);
    if (content && !isElementShown(content)) toggleCollapsible(`customTab${tabId}Form`);
    tab.fields.forEach(field => {
      const input = document.getElementById(`customTab${tabId}Field${field.key}`);
      const value = item.field_values?.[field.key];
      if (!input) return;
      if (input.type === 'checkbox') input.checked = value === true;
      else input.value = value ?? '';
    });
    const posterUrl = document.getElementById(`customTab${tabId}PosterUrl`);
    if (posterUrl) posterUrl.value = item.poster_url || '';
    form.dataset.editingItemId = String(itemId);
    const submit = form.querySelector('button[type="submit"]');
    if (submit) {
      submit.textContent = `Update ${tab.name}`;
      // The form's submit listener preserves native required/number validation.
      const cancel = document.createElement('button');
      cancel.type = 'button'; cancel.className = 'action-btn';
      cancel.dataset.customTabCancel = 'true'; cancel.textContent = 'Cancel';
      cancel.onclick = () => { if (!form.dataset.savingItem) resetCustomTabItemForm(tab); };
      submit.parentElement.appendChild(cancel);
    }
    titleInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (error) {
    if (!current()) return;
    console.error('Error loading item for editing:', error);
    alert('Failed to load item for editing');
  }
}

async function handleUpdateCustomTabItem(tab, itemId) {
  const form = document.getElementById(`addCustomTab${tab.id}Form`);
  if (!hasStoredAuth() || !form || form.dataset.savingItem
      || Number(form.dataset.editingItemId) !== itemId || form.reportValidity?.() === false) return;
  const titleInput = document.getElementById(`customTab${tab.id}Title`);
  const title = titleInput.value.trim();
  if (!title || title.length > 500) { alert('Enter a title of 1 to 500 characters.'); return; }
  const submit = form.querySelector('button[type="submit"]');
  const fields = {};
  tab.fields.forEach(field => {
    const input = document.getElementById(`customTab${tab.id}Field${field.key}`);
    if (!input) return;
    if (field.field_type === 'boolean' || field.field_type === 'status') fields[field.key] = input.checked;
    else if (input.value.trim()) fields[field.key] = ['number', 'rating'].includes(field.field_type)
      ? Number(input.value) : input.value.trim();
  });
  const posterFile = tab.allow_uploads ? document.getElementById(`customTab${tab.id}PosterFile`)?.files?.[0] : null;
  const posterUrl = tab.allow_uploads ? document.getElementById(`customTab${tab.id}PosterUrl`)?.value.trim() || null : null;
  form.dataset.savingItem = String(itemId);
  if (submit) { submit.disabled = true; submit.textContent = 'Updating...'; }
  try {
    const response = await fetch(`${API_BASE}/custom-tabs/${tab.id}/items/${itemId}`, {
      method: 'PUT', ...authFetchOptions({ headers: { 'Content-Type': 'application/json' } }),
      body: JSON.stringify({ title, field_values: fields, poster_url: posterUrl }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      alert(typeof error.detail === 'string' ? error.detail : 'Failed to update item');
      return;
    }
    // Keep the draft and file available if the artwork could not be uploaded.
    if (posterFile && !await uploadCustomTabPoster(tab.id, itemId, posterFile)) return;
    resetCustomTabItemForm(tab);
    await loadCustomTabItems(tab);
  } catch (error) {
    console.error('Error updating custom tab item:', error);
    alert('Failed to update item. Your form has not been cleared. Please try again.');
  } finally {
    delete form.dataset.savingItem;
    if (submit) {
      submit.disabled = false;
      submit.textContent = form.dataset.editingItemId ? `Update ${tab.name}` : `Add ${tab.name}`;
    }
  }
}

// @lazy-chunk lazy/custom-tab-manager.js
function bindCustomTabForm() {
  const form = document.getElementById('newCustomTabForm');
  if (!form || form.dataset.bound === 'true') return;
  form.dataset.bound = 'true';
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    try {
      if (!hasStoredAuth()) {
        alert('You must be logged in to create custom tabs');
        return;
      }
      
      const submitBtn = e.target.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn?.textContent;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = e.target.dataset.editingTabId ? 'Updating...' : 'Creating...';
      }
      
      const name = document.getElementById('customTabName').value.trim();
      if (!name) {
        alert('Tab name is required');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
        return;
      }
      
      if (name.length > 100) {
        alert('Tab name is too long (max 100 characters)');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
        return;
      }
      
      const editingTabId = e.target.dataset.editingTabId;
      const existingTabsCount = customTabs.length;
      if (!editingTabId && existingTabsCount >= 20) {
        alert('Maximum of 20 custom tabs allowed per user');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
        return;
      }
      
      const sourceType = document.getElementById('customTabSourceType').value;
      const allowUploads = document.getElementById('customTabAllowUploads').checked;
      
      const fields = [];
      const fieldKeys = new Set();
      const fieldDivs = Array.from(document.getElementById('customTabFieldsList').children);
      
      for (const div of fieldDivs) {
        const fieldId = div.className.match(/custom-tab-field-(\d+)/)?.[1];
        if (!fieldId) continue;
        
        const key = div.querySelector(`#fieldKey${fieldId}`)?.value.trim();
        const label = div.querySelector(`#fieldLabel${fieldId}`)?.value.trim();
        const fieldType = div.querySelector(`#fieldType${fieldId}`)?.value;
        const required = div.querySelector(`#fieldRequired${fieldId}`)?.checked;
        
        if (!key || !label || !fieldType) continue;
        
        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) {
          alert(`Field key "${key}" is invalid. Must start with a letter or underscore and contain only alphanumeric characters and underscores.`);
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalBtnText;
          }
          return;
        }
        
        if (fieldKeys.has(key)) {
          alert(`Duplicate field key: "${key}". Each field key must be unique.`);
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalBtnText;
          }
          return;
        }
        
        fieldKeys.add(key);
        fields.push({ key, label, field_type: fieldType, required });
      }
      
      if (fields.length > 30) {
        alert('Maximum of 30 fields allowed per tab');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
        return;
      }
      
      const response = await fetch(`${API_BASE}/custom-tabs${editingTabId ? `/${editingTabId}` : ''}`, {
        method: editingTabId ? 'PUT' : 'POST',
        ...authFetchOptions({ headers: { 'Content-Type': 'application/json' } }),
        body: JSON.stringify({
          name,
          source_type: sourceType,
          allow_uploads: allowUploads,
          fields
        })
      });
      
      if (response.ok) {
        resetCustomTabFormState();
        await loadCustomTabs();
        loadCustomTabsList();
        alert(editingTabId ? 'Custom tab updated successfully!' : 'Custom tab created successfully!');
      } else {
        const errorData = await response.json().catch(() => ({ detail: editingTabId ? 'Failed to update custom tab' : 'Failed to create custom tab' }));
        alert(errorData.detail || (editingTabId ? 'Failed to update custom tab' : 'Failed to create custom tab'));
      }
    } catch (error) {
      console.error('Error saving custom tab:', error);
      alert('Failed to save custom tab. Please try again.');
    } finally {
      const submitBtn = e.target.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = e.target.dataset.editingTabId ? 'Update Tab' : 'Create Tab';
      }
    }
  });
}

// @lazy-chunk lazy/custom-tab-editor.js
function setupCustomTabSwitching() {
  if (typeof window.switchTab === 'function') {
    const originalSwitchTab = window.switchTab;
    window.switchTab = function(tabName) {
      if (tabName && tabName.startsWith('custom-')) {
        const tabId = parseInt(tabName.replace('custom-', ''));
        const tab = customTabs.find(t => t.id === tabId);
        if (tab) {
          document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
          const tabButton = getTabButton(`custom-${tabId}`);
          if (tabButton) tabButton.classList.add('active');

          document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
          const content = document.getElementById(`custom-${tabId}-tab`);
          if (content) {
            window.OmniProgress?.navigate();
            content.classList.add('active');
            currentTab = tabName;
            loadCustomTabItems(tab);
            return;
          }
        }
      }
      return originalSwitchTab.call(this, tabName);
    };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupReviewQualityCounters();
  document.getElementById('collectionStudioName')?.addEventListener('input', updateCollectionReadinessDraft);
  document.getElementById('collectionStudioDescription')?.addEventListener('input', updateCollectionReadinessDraft);
  setupCustomTabSwitching();
  bindCustomTabForm();
  if (hasStoredAuth()) {
    captureDemoStartGuidance();
    loadCustomTabs();
    openDashboardTargetFromLocation();
  }
});

async function refreshLibraryProgressView(payload, shouldContinue) {
  const category = payload?.category;
  if (!['tv-shows', 'anime', 'books'].includes(category)) return;
  const epoch = libraryBrowseEpoch;
  const current = () => epoch === libraryBrowseEpoch && shouldContinue()
    && currentTab === category && editingRowId === null && getLibraryFilters(category).hasProgress;
  if (!current()) return;
  const busy = () => ({ 'tv-shows': isLoadingTVShows, anime: isLoadingAnime, books: isLoadingBooks })[category];
  // Let an older read finish before requesting the post-save filtered view.
  // Calling the loader while it is busy would otherwise discard this refresh.
  const deadline = Date.now() + 10000;
  while (busy() && Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, 50));
    if (!current()) return;
  }
  if (!current() || busy()) return;
  return libraryPageConfig(category)[2]();
}

window.OmniProgress?.configure({
  base: API_BASE,
  request: (...args) => authenticatedFetch(...args),
  sessionKey: () => {
    if (!hasStoredAuth()) return null;
    const user = typeof getUser === 'function' ? getUser() : null;
    return JSON.stringify([user?.id ?? user?.username ?? null,
      typeof getToken === 'function' ? getToken() : getAuthTokenValue()]);
  },
  contextKey: () => currentTab,
  canOpen: () => {
    if (editingRowId === null) return true;
    alert('Save or cancel your current title edit before updating progress.');
    return false;
  },
  onSaved: (payload, shouldContinue) => {
    if (!shouldContinue()) return;
    return Promise.allSettled([
      refreshNextUpQueue(shouldContinue), refreshLibraryPulse(shouldContinue),
      refreshLibraryProgressView(payload, shouldContinue),
    ]);
  },
});

