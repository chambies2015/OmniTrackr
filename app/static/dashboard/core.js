const isLocal = (location.protocol === 'file:' || location.origin === 'null' || location.origin === '');
const API_BASE = isLocal ? 'http://127.0.0.1:8000' : '';

let editingRowId = null;
let editingRowElement = null;
let currentTab = 'movies';
let notificationCountInterval = null;
let dashboardTabVisibilityReady = Promise.resolve();

const LIBRARY_SEARCH_SOURCES = [
  { endpoint: '/movies/', tab: 'movies', label: 'Movie', input: 'movieSearch', status: item => item.watched ? 'Watched' : 'Not watched' },
  { endpoint: '/tv-shows/', tab: 'tv-shows', label: 'TV show', input: 'tvSearch', status: item => item.watched ? 'Watched' : 'In progress' },
  { endpoint: '/anime/', tab: 'anime', label: 'Anime', input: 'animeSearch', status: item => item.watched ? 'Watched' : 'In progress' },
  { endpoint: '/video-games/', tab: 'video-games', label: 'Game', input: 'videoGameSearch', status: item => item.played ? 'Played' : 'Not played' },
  { endpoint: '/music/', tab: 'music', label: 'Album', input: 'musicSearch', status: item => item.listened ? 'Listened' : 'Not listened' },
  { endpoint: '/books/', tab: 'books', label: 'Book', input: 'bookSearch', status: item => item.read ? 'Read' : 'Not read' },
];
let librarySearchIndex = [];
let librarySearchIndexReady = false;
let librarySearchIndexPromise = null;
let librarySearchRequest = 0;
let librarySearchTimer;
let librarySearchController;
const libraryPages = new Map();
const libraryFilters = new Map();
let libraryBrowseEpoch = 0;
const LIBRARY_PAGE_SIZE = 50;
const dailyDashboardState = { items: [], expanded: false, epoch: 0, openRequest: 0, mutationPending: false, mutationRequest: 0, refreshAfterMutation: false };

function libraryPageConfig(category) {
  return {
    movies: ['movieTable', 'movieSort', loadMovies],
    'tv-shows': ['tvShowTable', 'tvSort', loadTVShows],
    anime: ['animeTable', 'animeSort', loadAnime],
    'video-games': ['videoGameTable', 'videoGameSort', loadVideoGames],
    music: ['musicTable', 'musicSort', loadMusic], books: ['bookTable', 'bookSort', loadBooks],
  }[category];
}

function getLibraryFilters(category) {
  return libraryFilters.get(category) || { completion: 'all', unrated: false, hasProgress: false };
}

function libraryPageSignature(category) {
  const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
  const [, sortId] = libraryPageConfig(category);
  const filters = getLibraryFilters(category);
  return JSON.stringify([document.getElementById(source.input).value, document.getElementById(sortId).value,
    filters.completion, filters.unrated, filters.hasProgress]);
}

function renderLibraryFilters(category) {
  const [tableId] = libraryPageConfig(category);
  const host = document.getElementById(`${tableId}Filters`);
  if (!host) return;
  const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
  if (!host.childElementCount) {
    const labels = {
      movies: ['Not watched', 'Watched'], 'tv-shows': ['Not finished', 'Finished'],
      anime: ['Not finished', 'Finished'], 'video-games': ['Not played', 'Played'],
      music: ['Not listened', 'Listened'], books: ['Not read', 'Read'],
    }[category];
    const group = document.createElement('div');
    group.className = 'library-filter-completion';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', 'Completion status');
    for (const [value, label] of [['all', 'All'], ['unfinished', labels[0]], ['finished', labels[1]]]) {
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = label; button.dataset.completion = value;
      button.addEventListener('click', () => applyLibraryFilters(category, { completion: value }));
      group.appendChild(button);
    }
    host.appendChild(group);
    const options = [['unrated', 'Unrated']];
    if (['tv-shows', 'anime', 'books'].includes(category)) options.push(['hasProgress', 'Has saved progress']);
    for (const [key, labelText] of options) {
      const label = document.createElement('label');
      label.className = 'library-filter-option';
      const input = document.createElement('input');
      input.type = 'checkbox'; input.dataset.libraryFilter = key;
      input.addEventListener('change', () => {
        applyLibraryFilters(category, { [key]: input.checked });
        renderLibraryFilters(category);
      });
      const text = document.createElement('span'); text.textContent = labelText;
      label.append(input, text); host.appendChild(label);
    }
    const reset = document.createElement('button');
    reset.type = 'button'; reset.className = 'library-filter-reset'; reset.textContent = 'Clear search & filters';
    reset.addEventListener('click', () => applyLibraryFilters(category,
      { completion: 'all', unrated: false, hasProgress: false }, { clearSearch: true }));
    host.appendChild(reset);
    const feedback = document.createElement('p');
    feedback.id = `${tableId}FilterStatus`; feedback.className = 'library-filter-status';
    feedback.setAttribute('role', 'status'); host.appendChild(feedback);
  }
  const filters = getLibraryFilters(category);
  host.querySelectorAll('[data-completion]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.completion === filters.completion));
  });
  host.querySelectorAll('[data-library-filter]').forEach(input => { input.checked = filters[input.dataset.libraryFilter]; });
  host.querySelector('.library-filter-reset').disabled = filters.completion === 'all' && !filters.unrated
    && !filters.hasProgress && !document.getElementById(source.input).value;
}

function applyLibraryFilters(category, changes, { clearSearch = false } = {}) {
  if (!libraryPageConfig(category)) return false;
  if (editingRowId !== null) {
    alert('Save or cancel your current edit before changing filters.');
    return false;
  }
  const previous = getLibraryFilters(category);
  const next = { ...previous, ...changes };
  if (!['all', 'unfinished', 'finished'].includes(next.completion)) return false;
  next.unrated = !!next.unrated;
  next.hasProgress = ['tv-shows', 'anime', 'books'].includes(category) && !!next.hasProgress;
  const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
  if (clearSearch) document.getElementById(source.input).value = '';
  libraryFilters.set(category, next);
  const oldPage = libraryPages.get(category);
  libraryPages.set(category, { offset: 0, total: 0, signature: libraryPageSignature(category), loadedKey: oldPage?.loadedKey });
  renderLibraryFilters(category);
  libraryPageConfig(category)[2]();
  return true;
}

function resetLibraryBrowsing() {
  libraryBrowseEpoch++;
  libraryFilters.clear();
  libraryPages.clear();
  for (const source of LIBRARY_SEARCH_SOURCES) {
    const input = document.getElementById(source.input);
    if (input) input.value = '';
    const [tableId, sortId] = libraryPageConfig(source.tab);
    const sort = document.getElementById(sortId);
    if (sort) sort.value = '';
    renderLibraryFilters(source.tab);
    const status = document.getElementById(`${tableId}FilterStatus`);
    if (status) status.textContent = '';
  }
}
window.resetLibraryBrowsing = resetLibraryBrowsing;
window.addEventListener('storage', event => {
  if (event.key === null || ['omnitrackr_user', 'omnitrackr_token'].includes(event.key)) resetLibraryBrowsing();
});

function renderLibraryPager(category, page, loading = false, error = '') {
  const [tableId] = libraryPageConfig(category);
  const table = document.getElementById(tableId);
  table.setAttribute('aria-busy', String(loading));
  if (editingRowId === null) {
    table.querySelectorAll('button').forEach(button => { button.disabled = loading; });
  }
  renderLibraryFilters(category);
  const feedback = document.getElementById(`${tableId}FilterStatus`);
  const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
  const filters = getLibraryFilters(category);
  const filtered = filters.completion !== 'all' || filters.unrated || filters.hasProgress
    || !!document.getElementById(source.input).value;
  if (feedback) feedback.textContent = error || (loading ? 'Loading titles…' : page.total
    ? `${page.total} ${page.total === 1 ? 'title' : 'titles'}${filtered ? (page.total === 1 ? ' matches your view' : ' match your view') : ' in this library'}.`
    : filtered ? 'No titles match. Try another search or clear your filters.'
      : 'Your library is ready for its first title. Use Add anything to get started.');
  let pager = document.getElementById(`${tableId}Pager`);
  if (!pager) {
    pager = document.createElement('nav');
    pager.id = `${tableId}Pager`;
    pager.className = 'library-pager';
    pager.setAttribute('aria-label', `${category} pages`);
    document.getElementById(tableId).after(pager);
  }
  pager.replaceChildren();
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  status.textContent = error || (loading ? 'Loading titles…' : page.total
    ? `${page.offset + 1}–${Math.min(page.offset + LIBRARY_PAGE_SIZE, page.total)} of ${page.total}`
    : 'No matching titles');
  pager.appendChild(status);
  for (const [label, delta] of [['Previous', -1], ['Next', 1]]) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'action-btn'; button.textContent = label;
    button.disabled = loading || (delta < 0 ? page.offset === 0 : page.offset + LIBRARY_PAGE_SIZE >= page.total);
    button.addEventListener('click', () => {
      if (editingRowId !== null) { alert('Save or cancel your current edit before changing pages.'); return; }
      page.offset = Math.max(0, page.offset + delta * LIBRARY_PAGE_SIZE);
      libraryPageConfig(category)[2]();
    });
    pager.appendChild(button);
  }
}

async function fetchLibraryPage(url) {
  const parsed = new URL(url, isLocal ? API_BASE : location.origin);
  const category = parsed.pathname.split('/').filter(Boolean)[0];
  const epoch = libraryBrowseEpoch;
  const fingerprint = () => libraryPageSignature(category);
  const signature = fingerprint();
  let page = libraryPages.get(category);
  if (!page || page.signature !== signature) {
    page = { offset: 0, total: 0, signature, loadedKey: page?.loadedKey };
    libraryPages.set(category, page);
  }
  parsed.searchParams.set('offset', String(page.offset));
  parsed.searchParams.set('limit', String(LIBRARY_PAGE_SIZE));
  const filters = getLibraryFilters(category);
  parsed.searchParams.set('completion', filters.completion);
  parsed.searchParams.set('unrated', String(filters.unrated));
  parsed.searchParams.set('has_progress', String(filters.hasProgress));
  if (page.focusId) parsed.searchParams.set('focus_id', String(page.focusId));
  renderLibraryPager(category, page, true);
  try {
    const response = await authenticatedFetch(`${API_BASE}/library/page/${category}?${parsed.searchParams}`);
    if (!response.ok) throw new Error('Could not load titles. Use Refresh to try again.');
    const data = await response.json();
    if (epoch !== libraryBrowseEpoch) return { ok: false };
    if (signature !== fingerprint() || libraryPages.get(category) !== page) {
      setTimeout(() => { if (epoch === libraryBrowseEpoch) libraryPageConfig(category)[2](); }, 0);
      return { ok: false };
    }
    page.offset = data.offset; page.total = data.total;
    const loadedKey = JSON.stringify([signature, data.offset]);
    page.browseOnly = page.loadedKey !== undefined && page.loadedKey !== loadedKey
      && Number(parsed.searchParams.get('offset')) === data.offset;
    page.loadedKey = loadedKey;
    renderLibraryPager(category, page);
    return { ok: true, total: data.total, json: async () => data.items };
  } catch (error) {
    if (epoch !== libraryBrowseEpoch) return { ok: false };
    if (signature !== fingerprint() || libraryPages.get(category) !== page) {
      setTimeout(() => { if (epoch === libraryBrowseEpoch) libraryPageConfig(category)[2](); }, 0);
      return { ok: false };
    }
    renderLibraryPager(category, page, false, 'Could not load titles. Use Refresh to try again.');
    return { ok: false };
  }
}

const posterFetchInProgress = new Set();

// Metadata lookups are repeated on every re-render for items without artwork.
// Remember successful proxy answers (including "not found") for this page load
// so those renders stop spending the OMDb/RAWG/iTunes quotas.
const proxyLookupCache = new Map();
async function cachedProxyFetch(url, options) {
  if (proxyLookupCache.has(url)) {
    return new Response(proxyLookupCache.get(url), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }
  const response = await fetch(url, options);
  if (response.ok) {
    try {
      const body = await response.clone().text();
      if (proxyLookupCache.size >= 500) proxyLookupCache.clear();
      proxyLookupCache.set(url, body);
    } catch (error) {
      // Leave uncached; the caller still reads the original response.
    }
  }
  return response;
}
const posterFetchQueue = new Map();

function getPosterConcurrencyLimit() {
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!conn) return 4;
  if (conn.saveData) return 1;
  const et = conn.effectiveType;
  if (et === 'slow-2g' || et === '2g') return 2;
  return 4;
}

let posterSlotsInUse = 0;
let posterSlotLimit = getPosterConcurrencyLimit();
const posterSlotWaiters = [];

function waitForPosterSlot() {
  if (posterSlotsInUse < posterSlotLimit) {
    posterSlotsInUse++;
    return Promise.resolve();
  }
  return new Promise(function (resolve) {
    posterSlotWaiters.push(resolve);
  });
}

function releasePosterSlot() {
  posterSlotsInUse--;
  if (posterSlotWaiters.length > 0) {
    posterSlotsInUse++;
    posterSlotWaiters.shift()();
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Only http(s) links may reach an href; anything else (javascript:, data:, junk) is dropped.
function safeHttpUrl(value) {
  if (!value) return '';
  try {
    const url = new URL(String(value), window.location.origin);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch (error) {
    return '';
  }
}

function normalizeLibrarySearchText(value) {
  return String(value ?? '').trim().toLocaleLowerCase();
}

function invalidateLibrarySearchIndex() {
  librarySearchIndexReady = false;
}

async function refreshLibrarySearchIndex() {
  if (librarySearchIndexReady) return librarySearchIndex;
  if (librarySearchIndexPromise) return librarySearchIndexPromise;
  librarySearchIndexPromise = Promise.all(LIBRARY_SEARCH_SOURCES.map(async source => {
    const response = await authenticatedFetch(`${API_BASE}${source.endpoint}`);
    if (!response.ok) return [];
    const items = await response.json();
    return items.map(item => ({
      id: item.id,
      tab: source.tab,
      label: source.label,
      title: String(item.title || 'Untitled'),
      status: source.status(item),
      haystack: normalizeLibrarySearchText([item.title, item.director, item.author, item.artist, item.genre, item.genres, item.year, item.review].filter(Boolean).join(' ')),
    }));
  })).then(groups => {
    librarySearchIndex = groups.flat();
    librarySearchIndexReady = true;
    return librarySearchIndex;
  }).catch(() => {
    librarySearchIndex = [];
    return librarySearchIndex;
  }).finally(() => {
    librarySearchIndexPromise = null;
  });
  return librarySearchIndexPromise;
}

function closeLibrarySearch() {
  ++librarySearchRequest;
  clearTimeout(librarySearchTimer);
  librarySearchController?.abort();
  const input = document.getElementById('librarySearchInput');
  const results = document.getElementById('librarySearchResults');
  if (results) results.setAttribute('hidden', '');
  input?.setAttribute('aria-expanded', 'false');
}

function renderLibrarySearch(query, items) {
  const input = document.getElementById('librarySearchInput');
  const results = document.getElementById('librarySearchResults');
  if (!input || !results) return;
  const needle = normalizeLibrarySearchText(query);
  results.replaceChildren();
  if (!needle) {
    closeLibrarySearch();
    return;
  }
  const matches = items.map(item => ({ item }));
  if (!matches.length) {
    const message = document.createElement('p');
    message.className = 'library-search__message';
    message.textContent = 'No matches in your private library yet.';
    results.appendChild(message);
  } else {
    matches.forEach(({ item }) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-search__result';
      button.dataset.action = 'open-library-search-result';
      button.dataset.searchTab = item.tab;
      button.dataset.searchTitle = item.title;
      button.dataset.searchId = String(item.id);
      button.setAttribute('role', 'option');
      const copy = document.createElement('span');
      copy.className = 'library-search__result-copy';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const meta = document.createElement('span');
      meta.textContent = `${item.label} · ${item.status}`;
      copy.append(title, meta);
      const action = document.createElement('span');
      action.className = 'library-search__result-action';
      action.textContent = 'Open →';
      button.append(copy, action);
      results.appendChild(button);
    });
  }
  results.removeAttribute('hidden');
  input.setAttribute('aria-expanded', 'true');
}

async function handleLibrarySearchInput() {
  const request = ++librarySearchRequest;
  clearTimeout(librarySearchTimer);
  librarySearchController?.abort();
  const input = document.getElementById('librarySearchInput');
  if (!input || !input.value.trim()) {
    closeLibrarySearch();
    return;
  }
  const query = input.value;
  const results = document.getElementById('librarySearchResults');
  results.textContent = 'Searching your private library…';
  results.removeAttribute('hidden');
  input.setAttribute('aria-expanded', 'true');
  librarySearchTimer = setTimeout(async () => {
    librarySearchController = new AbortController();
    try {
      const response = await authenticatedFetch(`${API_BASE}/library/search?q=${encodeURIComponent(query.trim())}`, { signal: librarySearchController.signal });
      if (!response.ok) throw new Error('Search unavailable');
      const items = await response.json();
      if (request === librarySearchRequest && input.value === query) renderLibrarySearch(query, items);
    } catch (error) {
      if (request === librarySearchRequest && error.name !== 'AbortError') results.textContent = 'Search could not load. Please try again.';
    }
  }, 250);
}

function openLibrarySearchResult(tab, title, id) {
  const source = LIBRARY_SEARCH_SOURCES.find(item => item.tab === tab);
  if (!source) return;
  closeLibrarySearch();
  const globalInput = document.getElementById('librarySearchInput');
  if (globalInput) globalInput.value = '';
  openLibraryItem({ category: tab, title, id });
}

function setupLibrarySearch() {
  const input = document.getElementById('librarySearchInput');
  if (!input) return;
  input.addEventListener('input', handleLibrarySearchInput);
  input.addEventListener('focus', () => {
    if (input.value.trim()) handleLibrarySearchInput();
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      input.value = '';
      closeLibrarySearch();
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      input.focus();
    }
    if (event.key === 'Escape' && document.activeElement !== input) closeLibrarySearch();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.library-search')) closeLibrarySearch();
  });
}

// ============================================================================
// Universal quick capture
// ============================================================================

const QUICK_CAPTURE_CATEGORY_ORDER = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books'];
const QUICK_CAPTURE_CATEGORIES = {
  movies: { label: 'Movies', icon: '🎬', endpoint: query => `/api/proxy/omdb?title=${encodeURIComponent(query)}&type=movie` },
  'tv-shows': { label: 'TV shows', icon: '📺', endpoint: query => `/api/proxy/omdb?title=${encodeURIComponent(query)}&type=series` },
  anime: { label: 'Anime', icon: '🎌', endpoint: query => `/api/proxy/jikan?query=${encodeURIComponent(query)}` },
  'video-games': { label: 'Video games', icon: '🎮', endpoint: query => `/api/proxy/rawg?search=${encodeURIComponent(query)}` },
  music: { label: 'Music', icon: '🎵', endpoint: query => `/api/proxy/itunes?query=${encodeURIComponent(query)}&entity=album` },
  books: { label: 'Books', icon: '📚', endpoint: query => `/api/proxy/openlibrary?query=${encodeURIComponent(query)}` },
};
let quickCaptureCategory = 'all';
let quickCaptureResults = [];
let quickCaptureController = null;
let quickCaptureReturnFocus = null;
let quickCaptureSearch = null;
const QUICK_CAPTURE_TIMEOUT_MS = 15000;

function resetQuickCaptureSearch() {
  quickCaptureController?.abort();
  quickCaptureController = null;
  quickCaptureSearch = null;
  quickCaptureResults = [];
  document.getElementById('quickCaptureResults')?.replaceChildren();
  const status = document.getElementById('quickCaptureStatus');
  if (status) status.textContent = quickCaptureCategory === 'all'
    ? 'Search every shelf. Results appear as each source responds.'
    : `Search ${QUICK_CAPTURE_CATEGORIES[quickCaptureCategory].label.toLowerCase()}, or continue with manual entry.`;
}

function handleQuickCaptureQueryInput() {
  const query = document.getElementById('quickCaptureQuery')?.value.trim();
  if (quickCaptureSearch && query !== quickCaptureSearch.query) resetQuickCaptureSearch();
}

// Template style="display: none" attributes become CSP classes on the server, so
// element.style.display starts empty; ask the computed style what is showing.
function isElementShown(element) {
  return !!element && !element.hidden && window.getComputedStyle(element).display !== 'none';
}

// @lazy-chunk lazy/quick-capture.js
function showImagePopup(imageUrl, altText) {
  const modal = document.getElementById('imagePopupModal');
  const img = document.getElementById('popupImage');
  if (modal && img) {
    img.src = imageUrl;
    img.alt = altText || 'Enlarged image';
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

function closeImagePopup() {
  const modal = document.getElementById('imagePopupModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

const REVIEW_PREVIEW_LEN = 60;
const PUBLIC_REVIEW_MIN_CHARS = 80;
const SEARCH_READY_REVIEW_MIN_CHARS = 240;
const SEARCH_READY_REVIEW_MIN_WORDS = 35;

function getReviewCellContent(review, title, subtitle) {
  if (!review || !String(review).trim()) return '';
  const safeTitle = escapeHtml(title);
  const safeSubtitle = escapeHtml(subtitle || '');
  const preview = String(review).length > REVIEW_PREVIEW_LEN ? String(review).slice(0, REVIEW_PREVIEW_LEN).trim() + '\u2026' : String(review);
  const safePreview = escapeHtml(preview);
  const safeReview = escapeHtml(review);
  return `<span class="review-cell-preview" title="${safePreview}">${safePreview}</span><button type="button" class="action-btn review-view-btn" data-action="open-review-modal">View review</button><span class="review-cell-full" hidden data-review="${safeReview}" data-title="${safeTitle}" data-subtitle="${safeSubtitle}"></span>`;
}

function openReviewModal(btn) {
  const cell = btn.closest('td');
  if (!cell) return;
  const fullEl = cell.querySelector('.review-cell-full');
  const title = fullEl ? fullEl.getAttribute('data-title') || '' : '';
  const subtitle = fullEl ? fullEl.getAttribute('data-subtitle') || '' : '';
  const reviewRaw = fullEl ? fullEl.getAttribute('data-review') || '' : '';
  const review = document.createElement('div');
  review.textContent = reviewRaw;
  const modal = document.getElementById('reviewModal');
  const titleEl = document.getElementById('reviewModalTitle');
  const subtitleEl = document.getElementById('reviewModalSubtitle');
  const bodyEl = document.getElementById('reviewModalBody');
  if (modal && titleEl && subtitleEl && bodyEl) {
    titleEl.textContent = title;
    subtitleEl.textContent = subtitle;
    subtitleEl.style.display = subtitle ? '' : 'none';
    bodyEl.replaceChildren(review);
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

function closeReviewModal() {
  const modal = document.getElementById('reviewModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function getReviewQualityMessage(reviewText) {
  const text = String(reviewText || '').trim();
  const length = text.length;
  const wordCount = (text.match(/[\w'-]+/gu) || []).length;
  const thoughtCount = (text.match(/[.!?…](?:\s|$)/gu) || []).length;
  if (length < PUBLIC_REVIEW_MIN_CHARS) {
    return `${length}/${PUBLIC_REVIEW_MIN_CHARS} characters - add context for the community feed`;
  }
  if (length < SEARCH_READY_REVIEW_MIN_CHARS) {
    return `Community-ready · ${length}/${SEARCH_READY_REVIEW_MIN_CHARS} characters toward search-ready`;
  }
  if (wordCount < SEARCH_READY_REVIEW_MIN_WORDS) {
    return `Community-ready · ${wordCount}/${SEARCH_READY_REVIEW_MIN_WORDS} words toward search-ready`;
  }
  if (thoughtCount < 2 && wordCount < 55) {
    return 'Community-ready · add a second complete thought for search-ready';
  }
  return 'Search-ready baseline met · automated safety checks apply when published';
}

function reviewQualityHintHtml(inputId) {
  return `<p class="review-quality-hint"><span class="review-quality-count" data-review-counter-for="${escapeHtml(inputId)}">0/${PUBLIC_REVIEW_MIN_CHARS} characters - add context for the community feed</span>. Search-ready reviews use 240+ characters, 35+ words, complete thoughts, varied language, and no links or contact details. <a href="/review-guidelines" target="_blank" rel="noopener noreferrer">Review guide</a></p>`;
}

function setupReviewQualityCounter(textarea) {
  if (!textarea || !textarea.id || textarea.dataset.reviewCounterBound === 'true') return;
  textarea.dataset.reviewCounterBound = 'true';
  const updateCounter = () => {
    const counter = document.querySelector(`[data-review-counter-for="${textarea.id}"]`);
    if (!counter) return;
    const length = textarea.value.trim().length;
    counter.textContent = getReviewQualityMessage(textarea.value);
    counter.classList.toggle('is-ready', length >= SEARCH_READY_REVIEW_MIN_CHARS);
  };
  textarea.addEventListener('input', updateCounter);
  // form.reset() does not fire "input"; refresh once the reset has cleared the value.
  textarea.form?.addEventListener('reset', () => setTimeout(updateCounter, 0));
  updateCounter();
}

function setupReviewQualityCounters(root = document) {
  root.querySelectorAll('[data-review-quality-input]').forEach(setupReviewQualityCounter);
}

function getTabButton(tabName) {
  return Array.from(document.querySelectorAll('.tab')).find((tab) => tab.dataset.switchTab === tabName);
}

function handleImageFallback(event) {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;
  if (image.dataset.hideOnError === 'true') {
    image.style.display = 'none';
    return;
  }
  if (!image.dataset.fallbackSrc) return;
  if (image.src.endsWith(image.dataset.fallbackSrc)) return;
  image.src = image.dataset.fallbackSrc;
}

function handleDelegatedClick(event) {
  const stopTarget = event.target.closest('[data-stop-propagation]');
  if (stopTarget) {
    event.stopPropagation();
  }

  const target = event.target.closest('[data-click-target], [data-switch-tab], [data-toggle-collapsible], [data-toggle-category-accordion], [data-toggle-accordion], [data-screenshot-src], [data-action], [data-close-on-backdrop]');
  if (!target) return;

  if (target.dataset.closeOnBackdrop && event.target === target) {
    const closeHandlers = {
      screenshot: () => closeScreenshotModal(event),
      review: closeReviewModal,
      'quick-capture': closeQuickCapture,
      'custom-tab-manager': closeCustomTabManager,
      'completion-ritual': closeCompletionRitual,
      'collection-picker': closeCollectionPicker,
      'collection-studio': closeCollectionStudio
    };
    closeHandlers[target.dataset.closeOnBackdrop]?.();
    return;
  }

  if (target.dataset.clickTarget) {
    document.getElementById(target.dataset.clickTarget)?.click();
    return;
  }

  if (target.dataset.switchTab) {
    navigateLibraryTab(target.dataset.switchTab);
    return;
  }

  if (target.dataset.toggleCollapsible) {
    toggleCollapsible(target.dataset.toggleCollapsible);
    return;
  }

  if (target.dataset.toggleCategoryAccordion) {
    toggleCategoryAccordion(target.dataset.toggleCategoryAccordion);
    return;
  }

  if (target.dataset.toggleAccordion) {
    toggleAccordion(target.dataset.toggleAccordion);
    return;
  }

  if (target.dataset.screenshotSrc) {
    openScreenshotModal(target.dataset.screenshotSrc, target.dataset.screenshotAlt || '');
    return;
  }

  const actionHandlers = {
    'open-review-modal': () => openReviewModal(target),
    'open-quick-capture': openQuickCapture,
    'close-quick-capture': closeQuickCapture,
    'select-quick-capture-category': () => selectQuickCaptureCategory(target.dataset.quickCategory),
    'retry-quick-capture-source': () => retryQuickCaptureCategory(target.dataset.quickCategory),
    'choose-quick-capture-result': () => applyQuickCaptureResult(Number(target.dataset.quickResultIndex)),
    'quick-capture-manual': openQuickCaptureManual,
    'open-friend-profile': () => openFriendProfile(Number(target.dataset.friendId)),
    'unfriend-user': () => unfriendUser(Number(target.dataset.friendId)),
    'accept-friend-request': () => acceptFriendRequest(Number(target.dataset.requestId)),
    'deny-friend-request': () => denyFriendRequest(Number(target.dataset.requestId)),
    'dismiss-notification': () => dismissNotification(Number(target.dataset.notificationId)),
    'edit-custom-tab-item': () => editCustomTabItem(Number(target.dataset.tabId), Number(target.dataset.itemId)),
    'delete-custom-tab-item': () => deleteCustomTabItem(Number(target.dataset.tabId), Number(target.dataset.itemId)),
    'edit-custom-tab': () => openEditCustomTab(Number(target.dataset.tabId)),
    'delete-custom-tab': () => deleteCustomTab(Number(target.dataset.tabId)),
    'remove-custom-tab-field': () => target.closest(`.custom-tab-field-${target.dataset.fieldId}`)?.remove(),
    'show-custom-tab-manager': showCustomTabManager,
    'close-account-modal': closeAccountModal,
    'reset-profile-picture': resetProfilePicture,
    'close-friend-request-modal': closeFriendRequestModal,
    'close-image-popup': closeImagePopup,
    'close-review-modal': closeReviewModal,
    'close-friend-profile': closeFriendProfile,
    'close-custom-tab-manager': closeCustomTabManager,
    'show-create-custom-tab-form': showCreateCustomTabForm,
    'add-custom-tab-field': () => addCustomTabField(),
    'cancel-create-custom-tab': cancelCreateCustomTab,
    'close-music-search-modal': closeMusicSearchModal,
    'close-book-search-modal': closeBookSearchModal,
    'close-screenshot-modal': () => closeScreenshotModal(event),
    'export-data-dashboard': exportData,
    'apply-library-import': applyLibraryImport,
    'confirm-library-import': confirmLibraryImport,
    'cancel-library-import': cancelLibraryImport,
    'download-import-template': downloadImportTemplate,
    'launchpad-add-item': openLaunchpadQuickCapture,
    'launchpad-choose-category': () => openLaunchpadQuickCapture(target.dataset.launchpadCategory),
    'launchpad-open-insights': openLaunchpadInsights,
    'launchpad-dismiss': dismissLibraryLaunchpad,
    'launchpad-import': openLaunchpadImport,
    'dismiss-return-deck': dismissReturnDeck,
    'open-return-deck-item': () => openReturnDeckItem(Number(target.dataset.returnDeckIndex)),
    'pulse-open-item': () => openDashboardItem(target),
    'activity-open-library': () => switchTab(target.dataset.pulseTab),
    'toggle-next-up': toggleNextUpQueue,
    'open-todays-pick': openTodaysPick,
    'open-library-search-result': () => openLibrarySearchResult(target.dataset.searchTab, target.dataset.searchTitle, Number(target.dataset.searchId)),
    'try-another-pick': tryAnotherPick,
    'add-next-up': () => addToNextUp(target.dataset.nextUpCategory, Number(target.dataset.nextUpItemId)),
    'move-next-up': () => moveNextUp(Number(target.dataset.nextUpId), Number(target.dataset.nextUpPosition)),
    'remove-next-up': () => removeNextUp(Number(target.dataset.nextUpId)),
    'begin-completion-ritual': () => openCompletionMoment(target.dataset.completionCategory, Number(target.dataset.completionItemId)),
    'close-completion-ritual': closeCompletionRitual,
    'save-completion-ritual': saveCompletionRitual,
    'activity-older-week': () => changeActivityWeek(1),
    'activity-newer-week': () => changeActivityWeek(-1),
    'activity-load-more': () => loadActivityTimeline(false),
    'delete-activity': () => deleteActivityEntry(Number(target.dataset.activityId)),
    'copy-recommendation-link': () => copyRecommendationLink(target.dataset.sharePath),
    'close-recommendation-request': () => closeRecommendationRequest(Number(target.dataset.requestId)),
    'invite-recommendation-friend': () => inviteRecommendationFriend(Number(target.dataset.requestId)),
    'triage-recommendation': () => triageRecommendation(Number(target.dataset.submissionId), target.dataset.triageAction),
    'open-recommendation-postcards': () => switchTab('recommendations'),
    'tasteprint-refresh': () => loadTasteprint(true),
    'tasteprint-download': downloadTasteprint,
    'tasteprint-copy': copyTasteprintText,
    'open-collection-picker': () => openCollectionPicker(target.dataset.collectionCategory, Number(target.dataset.collectionItemId), target.dataset.collectionItemTitle),
    'close-collection-picker': closeCollectionPicker,
    'open-collection-studio': () => openCollectionStudio(Number(target.dataset.collectionId)),
    'close-collection-studio': closeCollectionStudio,
    'add-to-collection': () => addToCollection(Number(target.dataset.collectionId)),
    'move-collection-item': () => moveCollectionItem(Number(target.dataset.collectionId), Number(target.dataset.collectionItemId), Number(target.dataset.collectionPosition)),
    'remove-collection-item': () => removeCollectionItem(Number(target.dataset.collectionId), Number(target.dataset.collectionItemId)),
    'edit-collection-note': () => editCollectionItemNote(Number(target.dataset.collectionId), Number(target.dataset.collectionItemId)),
    'delete-collection': () => deleteCollection(Number(target.dataset.collectionId)),
    'show-register-form': () => showRegisterForm(),
    'show-login-form': () => showLoginForm()
  };
  actionHandlers[target.dataset.action]?.();
}

function handleDelegatedSubmit(event) {
  const form = event.target.closest('[data-submit-action]');
  if (!form) return;

  const submitHandlers = {
    'search-quick-capture': searchQuickCapture,
    'change-username': changeUsername,
    'change-email': changeEmail,
    'change-password': changePassword,
    'update-privacy-settings': updatePrivacySettings,
    'update-tab-visibility': updateTabVisibility,
    'deactivate-account': deactivateAccount,
    'send-friend-request': sendFriendRequest,
    'create-collection': createCollection,
    'save-collection-studio': saveCollectionStudio,
    'create-activity': createActivityEntry,
    'create-recommendation-request': createRecommendationRequest,
    'respond-recommendation': respondToRecommendation,
    'preview-library-import': previewLibraryImport
  };
  submitHandlers[form.dataset.submitAction]?.(event);
}

function handleDelegatedChange(event) {
  const target = event.target.closest('[data-change-action]');
  if (!target) return;

  const changeHandlers = {
    'pick-category': () => { todaysPickOffset = 0; refreshTodaysPick(); },
    'profile-picture-select': handleProfilePictureSelect,
    'activity-category': populateActivityItems,
    'activity-filter': () => loadActivityTimeline(true),
    'tasteprint-category': () => loadTasteprint(true),
    'tasteprint-display': renderTasteprintCard,
    'tasteprint-insight': updateTasteprintSelection,
    'import-studio-file': inspectImportStudioFile,
    'import-studio-options': resetImportStudioPreview
  };
  changeHandlers[target.dataset.changeAction]?.(event);
}

document.addEventListener('click', handleDelegatedClick);
document.addEventListener('submit', handleDelegatedSubmit);
document.addEventListener('change', handleDelegatedChange);
const FRIEND_FILTERS = new Set(['Movies', 'TVShows', 'Anime', 'VideoGames', 'Music', 'Books']);
document.addEventListener('input', event => {
  if (event.target.id === 'quickCaptureQuery') handleQuickCaptureQueryInput();
  const friendFilter = event.target.dataset?.friendFilter;
  if (FRIEND_FILTERS.has(friendFilter)) window[`filterFriend${friendFilter}`]();
});
document.addEventListener('error', handleImageFallback, true);

function applyDataFillWidths(root = document) {
  root.querySelectorAll('[data-fill-width]').forEach((element) => {
    const rawValue = Number(element.dataset.fillWidth);
    const width = Number.isFinite(rawValue) ? Math.max(0, Math.min(100, rawValue)) : 0;
    element.style.width = `${width}%`;
  });
}

document.addEventListener('keydown', function(event) {
  const active = document.activeElement;
  const isTyping = active && (active.matches('input, textarea, select') || active.isContentEditable);
  if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !isTyping) {
    event.preventDefault();
    openQuickCapture();
    return;
  }
  if (event.key === 'Escape') {
    const quickCapture = document.getElementById('quickCaptureModal');
    if (isElementShown(quickCapture)) {
      closeQuickCapture();
      return;
    }
    const imageModal = document.getElementById('imagePopupModal');
    if (isElementShown(imageModal)) {
      closeImagePopup();
      return;
    }
    const reviewModal = document.getElementById('reviewModal');
    if (isElementShown(reviewModal)) {
      closeReviewModal();
      return;
    }
    closeTopmostModalOverlay(event);
  }
});

// Escape closes any other open dialog through its own close control, so each
// modal keeps its own cleanup logic (account, friends, collections, search...).
function closeTopmostModalOverlay(event) {
  const open = Array.from(document.querySelectorAll('.modal-overlay')).filter(isElementShown);
  const overlay = open[open.length - 1];
  const closer = overlay?.querySelector('[data-action^="close-"]');
  if (!closer) return;
  event.preventDefault();
  closer.click();
}

