function isCurrentQuickCaptureSearch(search) {
  return quickCaptureSearch === search && !search.controller.signal.aborted
    && isElementShown(document.getElementById('quickCaptureModal'))
    && document.getElementById('quickCaptureQuery')?.value.trim() === search.query
    && quickCaptureCategory === search.category;
}

function openQuickCapture() {
  const modal = document.getElementById('quickCaptureModal');
  const query = document.getElementById('quickCaptureQuery');
  if (!modal || !query) return;
  quickCaptureReturnFocus = document.activeElement;
  closeLibrarySearch();
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
  window.setTimeout(() => {
    query.focus();
    query.select();
  }, 0);
}

function closeQuickCapture() {
  const modal = document.getElementById('quickCaptureModal');
  if (!modal) return;
  resetQuickCaptureSearch();
  modal.style.display = 'none';
  document.body.style.overflow = '';
  if (quickCaptureReturnFocus instanceof HTMLElement) quickCaptureReturnFocus.focus();
}

function selectQuickCaptureCategory(category) {
  if (category !== 'all' && !QUICK_CAPTURE_CATEGORIES[category]) return;
  const changed = quickCaptureCategory !== category;
  quickCaptureCategory = category;
  document.querySelectorAll('[data-quick-category]').forEach(button => {
    const selected = button.dataset.quickCategory === category;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  if (changed) resetQuickCaptureSearch();
}

function quickCaptureImage(url, alt) {
  const frame = document.createElement('span');
  frame.className = 'quick-capture-result__image';
  if (url) {
    const image = document.createElement('img');
    image.src = url;
    image.alt = '';
    image.loading = 'lazy';
    image.referrerPolicy = 'no-referrer';
    image.dataset.hideOnError = 'true';
    frame.appendChild(image);
  } else {
    frame.textContent = String(alt || '?').slice(0, 1).toUpperCase();
  }
  return frame;
}

function normalizeQuickCapturePayload(category, payload) {
  const result = (title, meta, image, raw) => ({ category, title, meta, image, raw });
  if (category === 'movies' || category === 'tv-shows') {
    if (!payload?.Title || payload.Error) return [];
    return [result(payload.Title, [payload.Year, payload.Genre].filter(value => value && value !== 'N/A').join(' · '), payload.Poster !== 'N/A' ? payload.Poster : '', payload)];
  }
  if (category === 'anime') {
    return (payload?.data || []).slice(0, 4).map(item => result(
      item.title_english || item.title,
      [item.year, item.type, item.episodes ? `${item.episodes} episodes` : ''].filter(Boolean).join(' · '),
      item.images?.jpg?.large_image_url || item.images?.jpg?.image_url || '',
      item
    ));
  }
  if (category === 'video-games') {
    return (payload?.results || []).slice(0, 4).map(item => result(
      item.name,
      [item.released?.slice(0, 4), (item.genres || []).slice(0, 2).map(genre => genre.name).join(', ')].filter(Boolean).join(' · '),
      item.background_image || '',
      item
    ));
  }
  if (category === 'music') {
    return (payload?.results || []).slice(0, 4).map(item => result(
      item.collectionName || item.trackName,
      [item.artistName, item.releaseDate?.slice(0, 4), item.primaryGenreName].filter(Boolean).join(' · '),
      item.artworkUrl100 || item.artworkUrl60 || '',
      item
    ));
  }
  if (category === 'books') {
    return (payload?.docs || []).slice(0, 4).map(item => {
      const coverId = item.cover_i || item.isbn?.[0];
      return result(
        item.title,
        [item.author_name?.[0], item.first_publish_year].filter(Boolean).join(' · '),
        coverId ? `https://covers.openlibrary.org/b/id/${coverId}-M.jpg` : '',
        item
      );
    });
  }
  return [];
}

async function fetchQuickCaptureCategory(category, query, signal) {
  const source = QUICK_CAPTURE_CATEGORIES[category];
  const controller = new AbortController();
  const unavailable = reason => ({ category, results: [], unavailable: true, reason });
  let stop;
  const stopped = new Promise(resolve => { stop = resolve; });
  const cancel = () => { controller.abort(); stop(unavailable('cancelled')); };
  signal.addEventListener('abort', cancel, { once: true });
  const timeout = window.setTimeout(() => {
    controller.abort();
    stop(unavailable('timeout'));
  }, QUICK_CAPTURE_TIMEOUT_MS);
  try {
    if (signal.aborted) { cancel(); return unavailable('cancelled'); }
    const request = (async () => {
      try {
        const response = await fetch(`${API_BASE}${source.endpoint(query)}`, {
          signal: controller.signal, credentials: 'same-origin', headers: { Accept: 'application/json' },
        });
        if (!response.ok) return unavailable(response.status === 429 ? 'busy' : response.status === 401 ? 'signin' : 'unavailable');
        const payload = await response.json();
        // OMDB also uses HTTP 200 for quota/key errors, not just title misses.
        if ((category === 'movies' || category === 'tv-shows') && (payload?.Error || payload?.Response === 'False')) {
          return /^(movie|series|episode) not found[.!]?$/i.test(String(payload.Error || '').trim())
            ? { category, results: [], unavailable: false }
            : unavailable('unavailable');
        }
        const valid = category === 'movies' || category === 'tv-shows' ? typeof payload?.Title === 'string'
          : Array.isArray(payload?.[{ anime: 'data', 'video-games': 'results', music: 'results', books: 'docs' }[category]]);
        if (!valid) return unavailable('unavailable');
        return { category, results: normalizeQuickCapturePayload(category, payload), unavailable: false };
      } catch (_) {
        return unavailable('unavailable');
      }
    })();
    // Settle even if a slow response body does not react promptly to abort.
    return await Promise.race([request, stopped]);
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener('abort', cancel);
  }
}

function updateQuickCaptureStatus(search) {
  if (!isCurrentQuickCaptureSearch(search)) return;
  const status = document.getElementById('quickCaptureStatus');
  if (!status) return;
  if (search.manualRequested) {
    status.textContent = 'Choose Movies, TV, Anime, Games, Music, or Books before continuing manually.';
    return;
  }
  const groups = Array.from(search.groups.values());
  const pending = groups.filter(group => group.state === 'loading').length;
  const unavailable = groups.filter(group => group.state === 'unavailable').length;
  const count = quickCaptureResults.length;
  if (count) {
    status.textContent = `${count} match${count === 1 ? '' : 'es'} for “${search.query}”. Choose one to review before saving.`;
  } else if (pending) {
    status.textContent = `Searching for “${search.query}”… You can enter a title manually at any time.`;
  } else {
    status.textContent = unavailable === groups.length
      ? 'Metadata search is temporarily unavailable. Retry a source below, or choose a media type and enter manually.'
      : `No close matches for “${search.query}”. Try another phrase or use manual entry.`;
  }
  if (pending) status.textContent += ` ${pending} source${pending === 1 ? ' is' : 's are'} still searching.`;
  if (unavailable && unavailable !== groups.length) status.textContent += ` ${unavailable} source${unavailable === 1 ? ' is' : 's are'} unavailable; retry below.`;
}

function createQuickCaptureGroups(search, categories, container) {
  for (const category of categories) {
    const section = document.createElement('section');
    section.className = 'quick-capture-group';
    section.dataset.quickSource = category;
    const heading = document.createElement('h3');
    heading.textContent = `${QUICK_CAPTURE_CATEGORIES[category].icon} ${QUICK_CAPTURE_CATEGORIES[category].label}`;
    const note = document.createElement('p');
    note.className = 'quick-capture-source-status';
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'quick-capture-retry';
    retry.dataset.action = 'retry-quick-capture-source';
    retry.dataset.quickCategory = category;
    retry.textContent = `Retry ${QUICK_CAPTURE_CATEGORIES[category].label.toLowerCase()}`;
    retry.hidden = true;
    const grid = document.createElement('div');
    grid.className = 'quick-capture-result-grid';
    section.append(heading, note, retry, grid);
    container.appendChild(section);
    search.groups.set(category, { category, state: 'loading', note, retry, grid, attempt: null });
  }
}

function renderQuickCaptureResults(search, group, result) {
  if (!isCurrentQuickCaptureSearch(search)) return;
  group.state = result.unavailable ? 'unavailable' : 'ready';
  const messages = {
    timeout: 'This source took too long. Try it again or enter the title manually.',
    busy: 'This source is busy. Try again shortly.',
    signin: 'Your session has expired. Sign in again to search this source.',
    unavailable: 'This source is unavailable right now.',
  };
  group.note.textContent = result.unavailable ? messages[result.reason] || messages.unavailable
    : result.results.length ? '' : 'No matches from this source.';
  group.note.hidden = !group.note.textContent;
  group.retry.hidden = !result.unavailable;
  group.retry.disabled = false;
  if (result.results.length) {
    // Append stable indices; another source must not replace a focused result.
    result.results.forEach(item => {
      const index = quickCaptureResults.push(item) - 1;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'quick-capture-result';
      button.dataset.action = 'choose-quick-capture-result';
      button.dataset.quickResultIndex = String(index);
      button.appendChild(quickCaptureImage(item.image, item.title));
      const copy = document.createElement('span');
      copy.className = 'quick-capture-result__copy';
      const title = document.createElement('strong');
      title.textContent = item.title || 'Untitled';
      const meta = document.createElement('small');
      meta.textContent = item.meta || QUICK_CAPTURE_CATEGORIES[item.category].label;
      copy.append(title, meta);
      const action = document.createElement('span');
      action.className = 'quick-capture-result__action';
      action.textContent = 'Use →';
      button.append(copy, action);
      group.grid.appendChild(button);
    });
  }
  updateQuickCaptureStatus(search);
}

async function runQuickCaptureSource(search, group) {
  const attempt = {};
  group.attempt = attempt;
  group.state = 'loading';
  group.note.hidden = false;
  group.note.textContent = 'Searching…';
  group.retry.disabled = true;
  updateQuickCaptureStatus(search);
  const result = await fetchQuickCaptureCategory(group.category, search.query, search.controller.signal);
  if (!isCurrentQuickCaptureSearch(search) || group.attempt !== attempt) return;
  renderQuickCaptureResults(search, group, result);
}

function retryQuickCaptureCategory(category) {
  const search = quickCaptureSearch;
  if (!search || !isCurrentQuickCaptureSearch(search)) return;
  const group = search.groups.get(category);
  if (!group || group.state !== 'unavailable') return;
  return runQuickCaptureSource(search, group);
}

async function searchQuickCapture(event) {
  event.preventDefault();
  const queryInput = document.getElementById('quickCaptureQuery');
  const results = document.getElementById('quickCaptureResults');
  const status = document.getElementById('quickCaptureStatus');
  const query = queryInput?.value.trim();
  if (!query || query.length < 2 || query.length > 200 || !results || !status) return;
  if (quickCaptureSearch && isCurrentQuickCaptureSearch(quickCaptureSearch)
    && Array.from(quickCaptureSearch.groups.values()).some(group => group.state === 'loading')) return;
  resetQuickCaptureSearch();
  const controller = new AbortController();
  quickCaptureController = controller;
  const categories = quickCaptureCategory === 'all' ? QUICK_CAPTURE_CATEGORY_ORDER : [quickCaptureCategory];
  const search = { query, category: quickCaptureCategory, controller, groups: new Map() };
  quickCaptureSearch = search;
  createQuickCaptureGroups(search, categories, results);
  // Each source renders independently; completion never gates the first result.
  await Promise.allSettled(Array.from(search.groups.values(), group => runQuickCaptureSource(search, group)));
}

function setQuickCaptureField(id, value) {
  const input = document.getElementById(id);
  if (input) input.value = value ?? '';
}

function prepareQuickCaptureDestination(category, title) {
  const destinations = {
    movies: { form: 'movieForm', title: 'movieTitle', completed: 'movieWatched' },
    'tv-shows': { form: 'tvForm', title: 'tvTitle', completed: 'tvWatched' },
    anime: { form: 'animeForm', title: 'animeTitle', completed: 'animeWatched' },
    'video-games': { form: 'videoGameForm', title: 'videoGameTitle', completed: 'videoGamePlayed' },
    music: { form: 'musicForm', title: 'musicTitle', completed: 'musicListened' },
    books: { form: 'bookForm', title: 'bookTitle', completed: 'bookRead' },
  };
  const destination = destinations[category];
  if (!destination) return null;
  const form = document.getElementById({
    movies: 'addMovieForm',
    'tv-shows': 'addTVShowForm',
    anime: 'addAnimeForm',
    'video-games': 'addVideoGameForm',
    music: 'addMusicForm',
    books: 'addBookForm',
  }[category]);
  const hasDraft = form && Array.from(form.elements).some(field => {
    if (field.type === 'submit' || field.type === 'button') return false;
    if (field.type === 'checkbox' || field.type === 'radio') return field.checked;
    return String(field.value || '').trim().length > 0;
  });
  if (hasDraft && !window.confirm('Replace the unsaved entry currently in this form?')) return null;
  form?.reset();
  const tabButton = getTabButton(category);
  const tabWasHidden = tabButton?.style.display === 'none';
  if (tabWasHidden) tabButton.style.display = '';
  openLaunchpadAddItem(category);
  if (tabWasHidden) tabButton.style.display = 'none';
  const titleInput = document.getElementById(destination.title);
  if (!titleInput) return null;
  titleInput.value = title || '';
  ['posterUrl', 'coverArtUrl', 'releaseDate', 'rawgLink'].forEach(key => delete titleInput.dataset[key]);
  const completed = document.getElementById(destination.completed);
  const intent = document.getElementById('quickCaptureIntent')?.value || 'saved';
  if (completed) completed.checked = intent === 'completed';
  return { ...destination, titleInput };
}

function applyQuickCaptureResult(index) {
  if (!quickCaptureSearch || !isCurrentQuickCaptureSearch(quickCaptureSearch)) return;
  const item = quickCaptureResults[index];
  if (!item) return;
  const destination = prepareQuickCaptureDestination(item.category, item.title);
  if (!destination) return;
  const data = item.raw || {};

  if (item.category === 'movies') {
    setQuickCaptureField('movieDirector', data.Director !== 'N/A' ? data.Director : '');
    setQuickCaptureField('movieYear', parseInt(String(data.Year || '').split('-')[0], 10) || '');
    if (data.Poster && data.Poster !== 'N/A') destination.titleInput.dataset.posterUrl = data.Poster;
  } else if (item.category === 'tv-shows') {
    setQuickCaptureField('tvYear', parseInt(String(data.Year || '').split('-')[0], 10) || '');
    setQuickCaptureField('tvSeasons', parseInt(data.totalSeasons, 10) || '');
    if (data.Poster && data.Poster !== 'N/A') destination.titleInput.dataset.posterUrl = data.Poster;
  } else if (item.category === 'anime') {
    setQuickCaptureField('animeYear', data.year || '');
    setQuickCaptureField('animeSeasons', data.seasons || '');
    setQuickCaptureField('animeEpisodes', data.episodes || '');
    const poster = data.images?.jpg?.large_image_url || data.images?.jpg?.image_url;
    if (poster) destination.titleInput.dataset.posterUrl = poster;
  } else if (item.category === 'video-games') {
    setQuickCaptureField('videoGameGenres', (data.genres || []).map(genre => genre.name).join(', '));
    if (data.released) destination.titleInput.dataset.releaseDate = data.released;
    if (data.background_image) destination.titleInput.dataset.coverArtUrl = data.background_image;
    if (data.slug) destination.titleInput.dataset.rawgLink = `https://rawg.io/games/${data.slug}`;
  } else if (item.category === 'music') {
    setQuickCaptureField('musicArtist', data.artistName || '');
    setQuickCaptureField('musicYear', parseInt(String(data.releaseDate || '').slice(0, 4), 10) || '');
    setQuickCaptureField('musicGenre', data.primaryGenreName || '');
    const cover = data.artworkUrl100 || data.artworkUrl60;
    if (cover) destination.titleInput.dataset.coverArtUrl = cover;
  } else if (item.category === 'books') {
    setQuickCaptureField('bookAuthor', data.author_name?.[0] || '');
    setQuickCaptureField('bookYear', data.first_publish_year || data.publish_year?.[0] || '');
    setQuickCaptureField('bookGenre', (data.subject || []).slice(0, 3).join(', '));
    const coverId = data.cover_i || data.isbn?.[0];
    if (coverId) destination.titleInput.dataset.coverArtUrl = `https://covers.openlibrary.org/b/id/${coverId}-L.jpg`;
  }

  closeQuickCapture();
  const formContent = document.getElementById(`${destination.form}Content`);
  formContent?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  window.setTimeout(() => destination.titleInput.focus(), 250);
}

function openQuickCaptureManual() {
  const status = document.getElementById('quickCaptureStatus');
  if (quickCaptureCategory === 'all') {
    if (quickCaptureSearch) quickCaptureSearch.manualRequested = true;
    if (status) status.textContent = 'Choose Movies, TV, Anime, Games, Music, or Books before continuing manually.';
    document.querySelector('[data-quick-category="movies"]')?.focus();
    return;
  }
  const query = document.getElementById('quickCaptureQuery')?.value.trim() || '';
  const destination = prepareQuickCaptureDestination(quickCaptureCategory, query);
  if (!destination) return;
  closeQuickCapture();
  document.getElementById(`${destination.form}Content`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  window.setTimeout(() => destination.titleInput.focus(), 250);
}

