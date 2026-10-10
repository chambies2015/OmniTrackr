// @lazy-chunk lazy/postcards.js
function switchTab(tabName) {
  if (tabName !== 'statistics') {
    const tabButton = getTabButton(tabName);
    if (tabButton && tabButton.style.display === 'none') {
      return;
    }
  }

  window.OmniProgress?.navigate();
  if (document.body?.dataset) document.body.dataset.activeTab = tabName;
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  const targetTab = getTabButton(tabName);
  if (targetTab) {
    targetTab.classList.add('active');
  }

  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  const tabContent = document.getElementById(`${tabName}-tab`);
  if (tabContent) {
    tabContent.classList.add('active');
  }

  const statsContent = document.getElementById('statsContent');
  if (statsContent) {
    if (tabName === 'statistics') {
    } else {
      statsContent.style.display = 'none';
    }
  }

  currentTab = tabName;

  if (tabName === 'movies') {
    return loadMovies();
  } else if (tabName === 'tv-shows') {
    return loadTVShows();
  } else if (tabName === 'anime') {
    return loadAnime();
  } else if (tabName === 'video-games') {
    return loadVideoGames();
  } else if (tabName === 'music') {
    return loadMusic();
  } else if (tabName === 'books') {
    return loadBooks();
  } else if (tabName === 'activity') {
    loadActivityJournal();
  } else if (tabName === 'recommendations') {
    loadRecommendationPostcards();
  } else if (tabName === 'collections') {
    return loadCollections();
  } else if (tabName === 'statistics') {
    loadStatistics();
  }
}

function disableOtherRowButtons(currentRow, tableId) {
  enhanceLibraryCards(tableId);
  const buttons = document.querySelectorAll(`#${tableId} button.action-btn`);
  buttons.forEach(btn => {
    const btnRow = btn.closest('tr');
    if (!btnRow.isSameNode(currentRow)) {
      btn.disabled = true;
    }
  });
}

function enableAllRowButtons(tableId) {
  const buttons = document.querySelectorAll(`#${tableId} button.action-btn`);
  buttons.forEach(btn => {
    btn.disabled = false;
  });
}

// Dark mode toggle
document.getElementById('toggleMode').addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  const btn = document.getElementById('toggleMode');
  btn.textContent = document.body.classList.contains('dark-mode') ? 'Light Mode' : 'Night Mode';
});

// Movie functions
let isLoadingMovies = false;

async function loadMovies() {
  // Prevent duplicate simultaneous loads
  if (isLoadingMovies) {
    return;
  }

  isLoadingMovies = true;

  try {
    const search = document.getElementById('movieSearch').value;
    const sortVal = document.getElementById('movieSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/movies/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const movies = await res.json();
      const tbody = document.querySelector('#movieTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('movieCount');
      if (countElem) countElem.textContent = `${res.total} Movie${res.total === 1 ? '' : 's'}`;
      movies.forEach((movie) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="movie-poster-${movie.id}"></td>
          <td>${escapeHtml(movie.title ?? '')}</td>
          <td>${escapeHtml(movie.director ?? '')}</td>
          <td>${movie.year ?? ''}</td>
          <td>${movie.rating !== null && movie.rating !== undefined ? parseFloat(movie.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${movie.watched ? 'watched' : 'unwatched'}">${movie.watched ? '✓' : '✗'}</span></td>
          <td class="review-cell">${getReviewCellContent(movie.review, movie.title, [movie.director, movie.year].filter(Boolean).join(' \u2022 '))}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(movie.title)}" target="_blank">Search</a></td>
          <td><span class="watched-icon ${movie.review_public ? 'watched' : 'unwatched'}">${movie.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-movie-btn" data-movie-id="${movie.id}" data-movie-title="${escapeHtml(movie.title)}" data-movie-director="${escapeHtml(movie.director ?? '')}" data-movie-year="${movie.year ?? ''}" data-movie-rating="${movie.rating ?? ''}" data-movie-watched="${movie.watched}" data-movie-review="${escapeHtml(movie.review || '')}" data-movie-review-public="${movie.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="movies" data-next-up-item-id="${movie.id}">Next up</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="movies" data-collection-item-id="${movie.id}" data-collection-item-title="${escapeHtml(movie.title)}">Collect</button>
            ${movie.watched ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="movies" data-completion-item-id="${movie.id}">Reflect</button>` : ''}
            <button class="action-btn delete-movie-btn" data-movie-id="${movie.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached poster or fetch new one
        if (movie.poster_url) {
          displayMoviePoster(movie.id, movie.poster_url, movie.title);
        } else {
          // API keys are now proxied through backend
          fetchMoviePoster(movie.id, movie.title, movie.year);
        }
      });
    }
  } finally {
    isLoadingMovies = false;
  }
}

function displayMoviePoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`movie-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'Movie poster';
    if (title) {
      altText = `${title} movie poster`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} movie poster`;
      }
    }
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.innerHTML = '';
    cell.appendChild(img);
  }
}

async function fetchMoviePoster(id, title, year) {
  // Create unique key for deduplication
  const cacheKey = `movie-${title}-${year}`;

  // Check if already fetching this poster
  if (posterFetchInProgress.has(cacheKey)) {
    // Wait for existing fetch to complete
    const existingPromise = posterFetchQueue.get(cacheKey);
    if (existingPromise) {
      try {
        const result = await existingPromise;
        if (result && result.posterUrl) {
          displayMoviePoster(id, result.posterUrl, result.normalizedTitle || title);
          if (result.normalizedTitle) {
            updateMovieRowMetadata(id, result.normalizedTitle);
          }
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  await waitForPosterSlot();
  posterFetchInProgress.add(cacheKey);

  try {
    const proxyUrl = `${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}`;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    let res;
    try {
      res = await cachedProxyFetch(proxyUrl, {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json'
        }
      });
      clearTimeout(timeoutId);
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        console.warn(`OMDB API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
      } else {
        console.warn(`Network error fetching poster for "${title}":`, fetchError.message);
      }
      return;
    }

    if (!res.ok) {
      if (res.status === 429) {
        console.warn('OMDB API rate limit reached. Posters will be fetched later.');
        return;
      }
      if (res.status === 503) {
        console.warn('OMDB API not configured on server.');
        return;
      }
      if (res.status === 504) {
        console.warn(`OMDB API timeout for "${title}". This may be due to network issues or VPN blocking.`);
        return;
      }
      if (res.status >= 500) {
        console.warn(`OMDB API server error (${res.status}) for "${title}". This may be due to network issues.`);
        return;
      }
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (jsonError) {
      console.warn(`Failed to parse OMDB API response for "${title}":`, jsonError);
      return;
    }

    if (data.Error) {
      console.warn(`OMDB API error for "${title}": ${data.Error}`);
      return;
    }

    if (data && data.Poster && data.Poster !== 'N/A') {
      const normalizedTitle = data.Title && data.Title !== 'N/A' ? data.Title : null;
      await saveMoviePosterUrl(id, data.Poster, normalizedTitle);
      displayMoviePoster(id, data.Poster, normalizedTitle || title);
      if (normalizedTitle) {
        updateMovieRowMetadata(id, normalizedTitle);
      }

      const result = { posterUrl: data.Poster, normalizedTitle: normalizedTitle };
      posterFetchQueue.set(cacheKey, Promise.resolve(result));
      return result;
    }
  } catch (err) {
    console.error('Error fetching movie poster:', err);
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    releasePosterSlot();
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveMoviePosterUrl(id, posterUrl, normalizedTitle) {
  try {
    const updateData = { poster_url: posterUrl };
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/movies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving poster URL:', err);
  }
}

function updateMovieRowMetadata(id, normalizedTitle) {
  const row = document.querySelector(`#movie-poster-${id}`)?.closest('tr');
  if (!row || row === editingRowElement) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }
}

async function deleteMovie(id) {
  if (!confirm('Are you sure you want to delete this movie?')) return;
  const res = await authenticatedFetch(`${API_BASE}/movies/${id}`, { method: 'DELETE' });
  if (res.ok) loadMovies();
}

window.enableMovieEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.movieId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  // Read data from dataset (browsers handle this securely)
  const title = btn.dataset.movieTitle || '';
  const director = btn.dataset.movieDirector || '';
  const year = btn.dataset.movieYear || '';
  const ratingVal = btn.dataset.movieRating || '';
  const watched = btn.dataset.movieWatched === 'true';
  const review = btn.dataset.movieReview || '';
  const reviewPublic = btn.dataset.movieReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-movie-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="text" id="edit-movie-director" value="${escapeHtml(director)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-movie-year" value="${escapeHtml(year)}">`;
  row.cells[4].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-movie-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[5].innerHTML = `<input type="checkbox" id="edit-movie-watched" ${watched ? 'checked' : ''}>`;
  row.cells[6].innerHTML = `<textarea id="edit-movie-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-movie-review')}`;
  const movieReviewTextarea = document.getElementById('edit-movie-review');
  if (movieReviewTextarea) {
    movieReviewTextarea.style.height = 'auto';
    movieReviewTextarea.style.height = Math.max(60, movieReviewTextarea.scrollHeight) + 'px';
    movieReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(movieReviewTextarea);
  }
  row.cells[8].innerHTML = `<input type="checkbox" id="edit-movie-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[9].innerHTML = `
    <button class="action-btn save-movie-btn" data-movie-id="${id}" data-was-complete="${watched}" data-completion-category="movies">Save</button>
    <button class="action-btn cancel-movie-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'movieTable');
};

window.saveMovieEdit = async function (btn) {
  const id = parseInt(btn.dataset.movieId, 10);
  if (editingRowId !== id) return;
  const updated = {
    title: document.getElementById('edit-movie-title').value,
    director: document.getElementById('edit-movie-director').value,
    year: parseInt(document.getElementById('edit-movie-year').value, 10),
    watched: document.getElementById('edit-movie-watched').checked,
  };
  const ratingVal = document.getElementById('edit-movie-rating').value;
  updated.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-movie-review') ? document.getElementById('edit-movie-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-movie-review-public');
  if (reviewPublicEl) updated.review_public = reviewPublicEl.checked;
  const res = await authenticatedFetch(`${API_BASE}/movies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && updated.watched) openCompletionMoment('movies', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('movieTable');
    loadMovies();
  }
};

window.cancelMovieEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('movieTable');
  loadMovies();
};

// TV Show functions
let isLoadingTVShows = false;

async function loadTVShows() {
  // Prevent duplicate simultaneous loads
  if (isLoadingTVShows) {
    return;
  }

  isLoadingTVShows = true;

  try {
    const search = document.getElementById('tvSearch').value;
    const sortVal = document.getElementById('tvSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/tv-shows/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const tvShows = await res.json();
      const tbody = document.querySelector('#tvShowTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('tvShowCount');
      if (countElem) countElem.textContent = `${res.total} TV Show${res.total === 1 ? '' : 's'}`;
      tvShows.forEach((tvShow) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="tv-poster-${tvShow.id}"></td>
          <td>${escapeHtml(tvShow.title ?? '')}</td>
          <td>${tvShow.year ?? ''}</td>
          <td>${tvShow.seasons ?? ''}</td>
          <td>${tvShow.episodes ?? ''}</td>
          <td>${tvShow.rating !== null && tvShow.rating !== undefined ? parseFloat(tvShow.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${tvShow.watched ? 'watched' : 'unwatched'}">${tvShow.watched ? '✓' : '✗'}</span></td>
          <td class="review-cell">${getReviewCellContent(tvShow.review, tvShow.title, tvShow.year ? String(tvShow.year) : '')}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(tvShow.title)}" target="_blank">Search</a></td>
          <td><span class="watched-icon ${tvShow.review_public ? 'watched' : 'unwatched'}">${tvShow.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-tv-btn" data-tv-id="${tvShow.id}" data-tv-title="${escapeHtml(tvShow.title)}" data-tv-year="${tvShow.year ?? ''}" data-tv-seasons="${tvShow.seasons ?? ''}" data-tv-episodes="${tvShow.episodes ?? ''}" data-tv-rating="${tvShow.rating ?? ''}" data-tv-watched="${tvShow.watched}" data-tv-review="${escapeHtml(tvShow.review || '')}" data-tv-review-public="${tvShow.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="tv-shows" data-next-up-item-id="${tvShow.id}">Next up</button>
            <button type="button" class="action-btn" data-progress-category="tv-shows" data-progress-item-id="${tvShow.id}" data-progress-title="${escapeHtml(tvShow.title)}">Update progress</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="tv-shows" data-collection-item-id="${tvShow.id}" data-collection-item-title="${escapeHtml(tvShow.title)}">Collect</button>
            ${tvShow.watched ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="tv-shows" data-completion-item-id="${tvShow.id}">Reflect</button>` : ''}
            <button class="action-btn delete-tv-btn" data-tv-id="${tvShow.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached poster or fetch new one
        if (tvShow.poster_url) {
          displayTVPoster(tvShow.id, tvShow.poster_url, tvShow.title);
        } else {
          // API keys are now proxied through backend
          fetchTVPoster(tvShow.id, tvShow.title, tvShow.year);
        }
      });
    }
  } finally {
    isLoadingTVShows = false;
  }
}

// Anime functions
let isLoadingAnime = false;

async function loadAnime() {
  // Prevent duplicate simultaneous loads
  if (isLoadingAnime) {
    return;
  }

  isLoadingAnime = true;

  try {
    const search = document.getElementById('animeSearch').value;
    const sortVal = document.getElementById('animeSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/anime/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const anime = await res.json();
      const tbody = document.querySelector('#animeTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('animeCount');
      if (countElem) countElem.textContent = `${res.total} Anime`;
      anime.forEach((animeItem) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="anime-poster-${animeItem.id}"></td>
          <td>${escapeHtml(animeItem.title ?? '')}</td>
          <td class="table-cell-center">${animeItem.year ?? ''}</td>
          <td class="table-cell-center">${animeItem.seasons ?? ''}</td>
          <td class="table-cell-center">${animeItem.episodes ?? ''}</td>
          <td class="table-cell-center">${animeItem.rating !== null && animeItem.rating !== undefined ? parseFloat(animeItem.rating).toFixed(1) + '/10' : ''}</td>
          <td class="table-cell-center"><span class="watched-icon ${animeItem.watched ? 'watched' : 'unwatched'}">${animeItem.watched ? '✓' : '✗'}</span></td>
          <td class="review-cell">${getReviewCellContent(animeItem.review, animeItem.title, animeItem.year ? String(animeItem.year) : '')}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(animeItem.title)}" target="_blank">Search</a></td>
          <td><span class="watched-icon ${animeItem.review_public ? 'watched' : 'unwatched'}">${animeItem.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-anime-btn" data-anime-id="${animeItem.id}" data-anime-title="${escapeHtml(animeItem.title)}" data-anime-year="${animeItem.year ?? ''}" data-anime-seasons="${animeItem.seasons ?? ''}" data-anime-episodes="${animeItem.episodes ?? ''}" data-anime-rating="${animeItem.rating ?? ''}" data-anime-watched="${animeItem.watched}" data-anime-review="${escapeHtml(animeItem.review || '')}" data-anime-review-public="${animeItem.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="anime" data-next-up-item-id="${animeItem.id}">Next up</button>
            <button type="button" class="action-btn" data-progress-category="anime" data-progress-item-id="${animeItem.id}" data-progress-title="${escapeHtml(animeItem.title)}">Update progress</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="anime" data-collection-item-id="${animeItem.id}" data-collection-item-title="${escapeHtml(animeItem.title)}">Collect</button>
            ${animeItem.watched ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="anime" data-completion-item-id="${animeItem.id}">Reflect</button>` : ''}
            <button class="action-btn delete-anime-btn" data-anime-id="${animeItem.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached poster or fetch new one
        if (animeItem.poster_url) {
          displayAnimePoster(animeItem.id, animeItem.poster_url, animeItem.title);
        } else {
          // API keys are now proxied through backend
          fetchAnimePoster(animeItem.id, animeItem.title, animeItem.year);
        }
      });
    }
  } finally {
    isLoadingAnime = false;
  }
}

function displayAnimePoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`anime-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'Anime poster';
    if (title) {
      altText = `${title} anime poster`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} anime poster`;
      }
    }
    // Construct image via DOM methods to avoid XSS
    cell.innerHTML = '';
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.appendChild(img);
  }
}

function displayTVPoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`tv-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'TV show poster';
    if (title) {
      altText = `${title} TV show poster`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} TV show poster`;
      }
    }
    // Construct image via DOM methods to avoid XSS
    cell.innerHTML = '';
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.appendChild(img);
  }
}

async function fetchTVPoster(id, title, year) {
  // Create unique key for deduplication
  const cacheKey = `tv-${title}-${year}`;

  // Check if already fetching this poster
  if (posterFetchInProgress.has(cacheKey)) {
    // Wait for existing fetch to complete
    const existingPromise = posterFetchQueue.get(cacheKey);
    if (existingPromise) {
      try {
        const result = await existingPromise;
        if (result && result.posterUrl) {
          displayTVPoster(id, result.posterUrl, result.normalizedTitle || title);
          if (result.normalizedTitle) {
            updateTVRowMetadata(id, result.normalizedTitle);
          }
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  await waitForPosterSlot();
  posterFetchInProgress.add(cacheKey);

  try {
    const proxyUrl = `${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}`;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    let res;
    try {
      res = await cachedProxyFetch(proxyUrl, {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json'
        }
      });
      clearTimeout(timeoutId);
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        console.warn(`OMDB API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
      } else {
        console.warn(`Network error fetching poster for "${title}":`, fetchError.message);
      }
      return;
    }

    if (!res.ok) {
      if (res.status === 429) {
        console.warn('OMDB API rate limit reached. Posters will be fetched later.');
        return;
      }
      if (res.status === 503) {
        console.warn('OMDB API not configured on server.');
        return;
      }
      if (res.status === 504) {
        console.warn(`OMDB API timeout for "${title}". This may be due to network issues or VPN blocking.`);
        return;
      }
      if (res.status >= 500) {
        console.warn(`OMDB API server error (${res.status}) for "${title}". This may be due to network issues.`);
        return;
      }
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (jsonError) {
      console.warn(`Failed to parse OMDB API response for "${title}":`, jsonError);
      return;
    }

    if (data.Error) {
      console.warn(`OMDB API error for "${title}": ${data.Error}`);
      return;
    }

    if (data && data.Poster && data.Poster !== 'N/A') {
      const normalizedTitle = data.Title && data.Title !== 'N/A' ? data.Title : null;
      await saveTVPosterUrl(id, data.Poster, normalizedTitle);
      displayTVPoster(id, data.Poster, normalizedTitle || title);
      if (normalizedTitle) {
        updateTVRowMetadata(id, normalizedTitle);
      }

      const result = { posterUrl: data.Poster, normalizedTitle: normalizedTitle };
      posterFetchQueue.set(cacheKey, Promise.resolve(result));
      return result;
    }
  } catch (err) {
    console.error('Error fetching TV show poster:', err);
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    releasePosterSlot();
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveTVPosterUrl(id, posterUrl, normalizedTitle) {
  try {
    const updateData = { poster_url: posterUrl };
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving TV show poster URL:', err);
  }
}

function updateTVRowMetadata(id, normalizedTitle) {
  const row = document.querySelector(`#tv-poster-${id}`)?.closest('tr');
  if (!row) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }
}

async function fetchAnimePoster(id, title, year) {
  const cacheKey = `anime-${title}-${year}`;

  if (posterFetchInProgress.has(cacheKey)) {
    const existingPromise = posterFetchQueue.get(cacheKey);
    if (existingPromise) {
      try {
        const result = await existingPromise;
        if (result && result.posterUrl) {
          displayAnimePoster(id, result.posterUrl, result.normalizedTitle || title);
          if (result.normalizedTitle) {
            updateAnimeRowMetadata(id, result.normalizedTitle);
          }
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  await waitForPosterSlot();
  posterFetchInProgress.add(cacheKey);

  try {
    const proxyUrl = `${API_BASE}/api/proxy/jikan?query=${encodeURIComponent(title)}`;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    
    let res;
    try {
      res = await cachedProxyFetch(proxyUrl, {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json'
        }
      });
      clearTimeout(timeoutId);
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        console.warn(`Jikan API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
      } else {
        console.warn(`Network error fetching poster for "${title}":`, fetchError.message);
      }
      return;
    }

    if (!res.ok) {
      if (res.status === 429) {
        console.warn('Jikan API rate limit reached. Posters will be fetched later.');
        return;
      }
      if (res.status === 504) {
        console.warn(`Jikan API timeout for "${title}". This may be due to network issues or VPN blocking.`);
        return;
      }
      if (res.status >= 500) {
        console.warn(`Jikan API server error (${res.status}) for "${title}". This may be due to network issues.`);
        return;
      }
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (jsonError) {
      console.warn(`Failed to parse Jikan API response for "${title}":`, jsonError);
      return;
    }

    if (data && data.data && data.data.length > 0) {
      const anime = data.data[0];
      const posterUrl = anime.images?.jpg?.large_image_url || anime.images?.jpg?.image_url || null;
      const normalizedTitle = anime.title_english || anime.title || null;

      if (posterUrl) {
        await saveAnimePosterUrl(id, posterUrl, normalizedTitle);
        displayAnimePoster(id, posterUrl, normalizedTitle || title);
        if (normalizedTitle) {
          updateAnimeRowMetadata(id, normalizedTitle);
        }

        const result = { posterUrl: posterUrl, normalizedTitle: normalizedTitle };
        posterFetchQueue.set(cacheKey, Promise.resolve(result));
        return result;
      }
    }
  } catch (err) {
    console.error('Error fetching anime poster:', err);
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    releasePosterSlot();
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveAnimePosterUrl(id, posterUrl, normalizedTitle) {
  try {
    const updateData = { poster_url: posterUrl };
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/anime/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving anime poster URL:', err);
  }
}

function updateAnimeRowMetadata(id, normalizedTitle) {
  const row = document.querySelector(`#anime-poster-${id}`)?.closest('tr');
  if (!row) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }
}

// Video Game functions
let isLoadingVideoGames = false;

async function loadVideoGames() {
  // Prevent duplicate simultaneous loads
  if (isLoadingVideoGames) {
    return;
  }

  isLoadingVideoGames = true;

  try {
    const search = document.getElementById('videoGameSearch').value;
    const sortVal = document.getElementById('videoGameSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/video-games/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const videoGames = await res.json();
      const tbody = document.querySelector('#videoGameTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('videoGameCount');
      if (countElem) countElem.textContent = `${res.total} Video Game${res.total === 1 ? '' : 's'}`;
      videoGames.forEach((game) => {
        const tr = document.createElement('tr');
        const releaseDateStr = game.release_date ? new Date(game.release_date).toLocaleDateString() : '';
        tr.innerHTML = `
          <td id="video-game-poster-${game.id}"></td>
          <td>${escapeHtml(game.title)}</td>
          <td>${releaseDateStr}</td>
          <td>${game.genres ? escapeHtml(game.genres) : ''}</td>
          <td><span class="watched-icon ${game.played ? 'watched' : 'unwatched'}">${game.played ? '✓' : '✗'}</span></td>
          <td>${game.rating !== null && game.rating !== undefined ? parseFloat(game.rating).toFixed(1) + '/10' : ''}</td>
          <td>${safeHttpUrl(game.rawg_link) ? `<a href="${escapeHtml(safeHttpUrl(game.rawg_link))}" target="_blank" rel="noopener noreferrer">View on RAWG</a>` : ''}</td>
          <td class="review-cell">${getReviewCellContent(game.review, game.title, game.release_date ? new Date(game.release_date).toLocaleDateString() : (game.genres || ''))}</td>
          <td><span class="watched-icon ${game.review_public ? 'watched' : 'unwatched'}">${game.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-video-game-btn" data-game-id="${game.id}" data-game-title="${escapeHtml(game.title)}" data-game-release-date="${game.release_date ? game.release_date.split('T')[0] : ''}" data-game-genres="${escapeHtml(game.genres || '')}" data-game-rating="${game.rating ?? ''}" data-game-played="${game.played}" data-game-review="${escapeHtml(game.review || '')}" data-game-review-public="${game.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="video-games" data-next-up-item-id="${game.id}">Next up</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="video-games" data-collection-item-id="${game.id}" data-collection-item-title="${escapeHtml(game.title)}">Collect</button>
            ${game.played ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="video-games" data-completion-item-id="${game.id}">Reflect</button>` : ''}
            <button class="action-btn delete-video-game-btn" data-game-id="${game.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        if (game.cover_art_url) {
          displayVideoGamePoster(game.id, game.cover_art_url, game.title);
        } else {
          // API keys are now proxied through backend
          fetchVideoGameMetadata(game.id, game.title);
        }
      });
    }
  } finally {
    isLoadingVideoGames = false;
  }
}

function displayVideoGamePoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`video-game-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'Video game cover art';
    if (title) {
      altText = `${title} video game cover art`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} video game cover art`;
      }
    }
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.innerHTML = '';
    cell.appendChild(img);
  }
}

function updateVideoGameRowMetadata(id, genres, rawgLink, releaseDate, normalizedTitle) {
  const row = document.querySelector(`#video-game-poster-${id}`)?.closest('tr');
  if (!row) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }

  if (releaseDate && row.cells[2]) {
    const date = new Date(releaseDate);
    row.cells[2].textContent = date.toLocaleDateString();
  }

  if (row.cells[3]) {
    row.cells[3].textContent = genres || '';
  }

  if (row.cells[6]) {
    if (safeHttpUrl(rawgLink)) {
      row.cells[6].innerHTML = `<a href="${escapeHtml(safeHttpUrl(rawgLink))}" target="_blank" rel="noopener noreferrer">View on RAWG</a>`;
    } else {
      row.cells[6].textContent = '';
    }
  }
}

async function fetchVideoGameMetadata(id, title) {
  // Create unique key for deduplication
  const cacheKey = `video-game-${title}`;

  // Check if already fetching this metadata
  if (posterFetchInProgress.has(cacheKey)) {
    // Wait for existing fetch to complete
    const existingPromise = posterFetchQueue.get(cacheKey);
    if (existingPromise) {
      try {
        const result = await existingPromise;
        if (result && result.cover_art_url) {
          displayVideoGamePoster(id, result.cover_art_url, result.normalized_title || title);
          await saveVideoGameMetadata(id, result.cover_art_url, result.genres, result.rawg_link, result.release_date, result.normalized_title);
          updateVideoGameRowMetadata(id, result.genres, result.rawg_link, result.release_date, result.normalized_title);
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  // Create the fetch promise first and add it to the queue BEFORE marking as in progress
  // This prevents race conditions where concurrent requests might not find the promise
  // Double-check pattern: verify it's still not in progress after creating promise
  const fetchPromise = (async () => {
    try {
      const proxyUrl = `${API_BASE}/api/proxy/rawg?search=${encodeURIComponent(title)}`;
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      let res;
      try {
        res = await cachedProxyFetch(proxyUrl, {
          signal: controller.signal,
          headers: {
            'Accept': 'application/json'
          }
        });
        clearTimeout(timeoutId);
      } catch (fetchError) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          console.warn(`RAWG API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
        } else {
          console.warn(`Network error fetching metadata for "${title}":`, fetchError.message);
        }
        return null;
      }

      if (!res.ok) {
        if (res.status === 429) {
          console.warn('RAWG API rate limit reached. Metadata will be fetched later.');
          return null;
        }
        if (res.status === 503) {
          console.warn('RAWG API not configured on server.');
          return null;
        }
        if (res.status === 504) {
          console.warn(`RAWG API timeout for "${title}". This may be due to network issues or VPN blocking.`);
          return null;
        }
        if (res.status >= 500) {
          console.warn(`RAWG API server error (${res.status}) for "${title}". This may be due to network issues.`);
          return null;
        }
        return null;
      }

      let data;
      try {
        data = await res.json();
      } catch (jsonError) {
        console.warn(`Failed to parse RAWG API response for "${title}":`, jsonError);
        return null;
      }

      if (data.error) {
        console.warn(`RAWG API error for "${title}": ${data.error}`);
        return null;
      }
      if (data && data.results && data.results.length > 0) {
        const game = data.results[0];
        const coverArtUrl = game.background_image || null;
        const genres = game.genres ? game.genres.map(g => g.name).join(', ') : null;
        const rawgLink = game.slug ? `https://rawg.io/games/${game.slug}` : null;
        const releaseDate = game.released || null;
        const normalizedTitle = game.name || null;

        if (coverArtUrl) {
          await saveVideoGameMetadata(id, coverArtUrl, genres, rawgLink, releaseDate, normalizedTitle);
          displayVideoGamePoster(id, coverArtUrl, normalizedTitle || title);
          updateVideoGameRowMetadata(id, genres, rawgLink, releaseDate, normalizedTitle);

          return { cover_art_url: coverArtUrl, genres: genres, rawg_link: rawgLink, release_date: releaseDate, normalized_title: normalizedTitle };
        }
      }
      return null;
    } catch (err) {
      console.error('Error fetching video game metadata:', err);
      return null;
    }
  })();

  // Add promise to queue BEFORE marking as in progress to prevent race conditions
  // Double-check: if another request added it while we were creating the promise, use that one
  const existingPromise = posterFetchQueue.get(cacheKey);
  if (existingPromise) {
    // Another request beat us to it, use their promise
    try {
      const result = await existingPromise;
      if (result && result.cover_art_url) {
        displayVideoGamePoster(id, result.cover_art_url, result.normalized_title || title);
        await saveVideoGameMetadata(id, result.cover_art_url, result.genres, result.rawg_link, result.release_date, result.normalized_title);
        updateVideoGameRowMetadata(id, result.genres, result.rawg_link, result.release_date, result.normalized_title);
      }
    } catch (err) {
      // Ignore errors from other fetch
    }
    return;
  }
  
  await waitForPosterSlot();
  posterFetchQueue.set(cacheKey, fetchPromise);
  posterFetchInProgress.add(cacheKey);

  try {
    const result = await fetchPromise;
    return result;
  } finally {
    releasePosterSlot();
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveVideoGameMetadata(id, coverArtUrl, genres, rawgLink, releaseDate, normalizedTitle) {
  try {
    const updateData = { cover_art_url: coverArtUrl };
    if (genres) updateData.genres = genres;
    if (rawgLink) updateData.rawg_link = rawgLink;
    if (releaseDate) updateData.release_date = releaseDate;
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/video-games/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving video game metadata:', err);
  }
}

async function deleteVideoGame(id) {
  if (!confirm('Are you sure you want to delete this video game?')) return;
  const res = await authenticatedFetch(`${API_BASE}/video-games/${id}`, { method: 'DELETE' });
  if (res.ok) loadVideoGames();
}

window.enableVideoGameEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.gameId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  const title = btn.dataset.gameTitle || '';
  const releaseDate = btn.dataset.gameReleaseDate || '';
  const genres = btn.dataset.gameGenres || '';
  const ratingVal = btn.dataset.gameRating || '';
  const played = btn.dataset.gamePlayed === 'true';
  const review = btn.dataset.gameReview || '';
  const reviewPublic = btn.dataset.gameReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-video-game-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="date" id="edit-video-game-release-date" value="${releaseDate}">`;
  row.cells[3].innerHTML = `<input type="text" id="edit-video-game-genres" value="${escapeHtml(genres)}">`;
  row.cells[4].innerHTML = `<input type="checkbox" id="edit-video-game-played" ${played ? 'checked' : ''}>`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-video-game-rating" value="${ratingVal}">`;
  row.cells[7].innerHTML = `<textarea id="edit-video-game-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-video-game-review')}`;
  const videoGameReviewTextarea = document.getElementById('edit-video-game-review');
  if (videoGameReviewTextarea) {
    videoGameReviewTextarea.style.height = 'auto';
    videoGameReviewTextarea.style.height = Math.max(60, videoGameReviewTextarea.scrollHeight) + 'px';
    videoGameReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(videoGameReviewTextarea);
  }
  row.cells[8].innerHTML = `<input type="checkbox" id="edit-video-game-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[9].innerHTML = `
    <button class="action-btn save-video-game-btn" data-game-id="${id}" data-was-complete="${played}" data-completion-category="video-games">Save</button>
    <button class="action-btn cancel-video-game-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'videoGameTable');
};

window.saveVideoGameEdit = async function (btn) {
  const id = parseInt(btn.dataset.gameId, 10);
  const title = document.getElementById('edit-video-game-title').value;
  const releaseDate = document.getElementById('edit-video-game-release-date').value;
  const genres = document.getElementById('edit-video-game-genres').value;
  const played = document.getElementById('edit-video-game-played').checked;
  const ratingVal = document.getElementById('edit-video-game-rating').value;
  const reviewVal = document.getElementById('edit-video-game-review') ? document.getElementById('edit-video-game-review').value : '';

  const updateData = { title };
  updateData.release_date = releaseDate || null;
  updateData.genres = genres || null;
  updateData.played = played;
  updateData.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  if (reviewVal !== undefined) updateData.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-video-game-review-public');
  if (reviewPublicEl) updateData.review_public = reviewPublicEl.checked;

  const res = await authenticatedFetch(`${API_BASE}/video-games/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updateData),
  });

  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && played) openCompletionMoment('video-games', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('videoGameTable');
    loadVideoGames();
  }
};

window.cancelVideoGameEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('videoGameTable');
  loadVideoGames();
};

let isLoadingMusic = false;

async function loadMusic() {
  if (isLoadingMusic) {
    return;
  }

  isLoadingMusic = true;

  try {
    const search = document.getElementById('musicSearch').value;
    const sortVal = document.getElementById('musicSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/music/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const music = await res.json();
      const tbody = document.querySelector('#musicTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('musicCount');
      if (countElem) countElem.textContent = `${res.total} Music`;
      music.forEach((item) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="music-poster-${item.id}"></td>
          <td>${escapeHtml(item.title)}</td>
          <td>${escapeHtml(item.artist ?? '')}</td>
          <td>${item.year ?? ''}</td>
          <td>${item.genre ? escapeHtml(item.genre) : ''}</td>
          <td>${item.rating !== null && item.rating !== undefined ? parseFloat(item.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${item.listened ? 'watched' : 'unwatched'}">${item.listened ? '✓' : '✗'}</span></td>
          <td class="review-cell">${getReviewCellContent(item.review, item.title, item.artist || '')}</td>
          <td><span class="watched-icon ${item.review_public ? 'watched' : 'unwatched'}">${item.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-music-btn" data-music-id="${item.id}" data-music-title="${escapeHtml(item.title)}" data-music-artist="${escapeHtml(item.artist ?? '')}" data-music-year="${item.year ?? ''}" data-music-genre="${escapeHtml(item.genre || '')}" data-music-rating="${item.rating ?? ''}" data-music-listened="${item.listened}" data-music-review="${escapeHtml(item.review || '')}" data-music-review-public="${item.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="music" data-next-up-item-id="${item.id}">Next up</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="music" data-collection-item-id="${item.id}" data-collection-item-title="${escapeHtml(item.title)}">Collect</button>
            ${item.listened ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="music" data-completion-item-id="${item.id}">Reflect</button>` : ''}
            <button class="action-btn delete-music-btn" data-music-id="${item.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        if (item.cover_art_url) {
          displayMusicPoster(item.id, item.cover_art_url, item.title);
        } else {
          fetchMusicMetadata(item.id, item.title, item.artist);
        }
      });
    }
  } finally {
    isLoadingMusic = false;
  }
}

function displayMusicPoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`music-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'Music cover art';
    if (title) {
      altText = `${title} music cover art`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} music cover art`;
      }
    }
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.innerHTML = '';
    cell.appendChild(img);
  }
}

async function fetchMusicMetadata(id, title, artist) {
  const cacheKey = `music-${title}-${artist}`;
  const row = document.querySelector(`#music-poster-${id}`)?.closest('tr');
  const current = () => row && row !== editingRowElement
    && document.querySelector(`#music-poster-${id}`)?.closest('tr') === row;
  let pending = posterFetchQueue.get(cacheKey);
  if (!pending) {
    posterFetchInProgress.add(cacheKey);
    pending = (async () => {
      await waitForPosterSlot();
      try {
        try {
          const searchQuery = artist ? `${title} ${artist}` : title;
          const proxyUrl = `${API_BASE}/api/proxy/itunes?query=${encodeURIComponent(searchQuery)}&entity=album`;

          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000);

          let res;
          try {
            res = await cachedProxyFetch(proxyUrl, {
              signal: controller.signal,
              headers: {
                'Accept': 'application/json'
              }
            });
            clearTimeout(timeoutId);
          } catch (fetchError) {
            clearTimeout(timeoutId);
            if (fetchError.name === 'AbortError') {
              console.warn(`iTunes API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
            } else {
              console.warn(`Network error fetching metadata for "${title}":`, fetchError.message);
            }
            return null;
          }

          if (!res.ok) {
            if (res.status === 429) {
              console.warn('iTunes API rate limit reached. Metadata will be fetched later.');
              return null;
            }
            if (res.status === 503) {
              console.warn('iTunes API not available.');
              return null;
            }
            if (res.status === 504) {
              console.warn(`iTunes API timeout for "${title}". This may be due to network issues or VPN blocking.`);
              return null;
            }
            if (res.status >= 500) {
              console.warn(`iTunes API server error (${res.status}) for "${title}". This may be due to network issues.`);
              return null;
            }
            return null;
          }

          let data;
          try {
            data = await res.json();
          } catch (jsonError) {
            console.warn(`Failed to parse iTunes API response for "${title}":`, jsonError);
            return null;
          }

          if (data.errorMessage) {
            console.warn(`iTunes API error for "${title}": ${data.errorMessage}`);
            return null;
          }
          if (data && data.results && data.results.length > 0) {
            const album = data.results[0];
            const coverArtUrl = album.artworkUrl100 || album.artworkUrl60 || null;
            const normalizedTitle = album.collectionName || album.trackName || null;
            const albumArtist = album.artistName || null;
            const albumYear = album.releaseDate ? parseInt(album.releaseDate.split('-')[0]) : null;
            const albumGenres = album.primaryGenreName || null;

            if (coverArtUrl) {

              return { cover_art_url: coverArtUrl, artist: albumArtist, year: albumYear, genre: albumGenres, normalized_title: normalizedTitle };
            }
          }
          return null;
        } catch (err) {
          console.error('Error fetching music metadata:', err);
          return null;
        }

      } finally { releasePosterSlot(); }
    })();
    posterFetchQueue.set(cacheKey, pending);
    pending.finally(() => setTimeout(() => {
      if (posterFetchQueue.get(cacheKey) === pending) {
        posterFetchQueue.delete(cacheKey); posterFetchInProgress.delete(cacheKey);
      }
    }, 1000)).catch(() => {});
  }
  try {
    const result = await pending;
    if (!result?.cover_art_url || !current()) return;
    await saveMusicMetadata(id, result.cover_art_url, result.artist, result.year, result.genre, result.normalized_title);
    if (!current()) return;
    displayMusicPoster(id, result.cover_art_url, result.normalized_title || title);
    updateMusicRowMetadata(id, result.artist, result.year, result.genre, result.normalized_title);
  } catch (error) { console.error('Error fetching music metadata:', error); }
}

function updateMusicRowMetadata(id, artist, year, genre, normalizedTitle) {
  const row = document.querySelector(`#music-poster-${id}`)?.closest('tr');
  if (!row || row === editingRowElement) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }

  if (artist && row.cells[2]) {
    row.cells[2].textContent = artist;
  }

  if (year && row.cells[3]) {
    row.cells[3].textContent = year;
  }

  if (genre && row.cells[4]) {
    row.cells[4].textContent = genre;
  }
}

async function saveMusicMetadata(id, coverArtUrl, artist, year, genre, normalizedTitle) {
  try {
    const updateData = { cover_art_url: coverArtUrl };
    if (artist) updateData.artist = artist;
    if (year) updateData.year = year;
    if (genre) updateData.genre = genre;
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/music/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving music metadata:', err);
  }
}

async function deleteMusic(id) {
  if (!confirm('Are you sure you want to delete this music?')) return;
  const res = await authenticatedFetch(`${API_BASE}/music/${id}`, { method: 'DELETE' });
  if (res.ok) loadMusic();
}

window.enableMusicEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.musicId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  const title = btn.dataset.musicTitle || '';
  const artist = btn.dataset.musicArtist || '';
  const year = btn.dataset.musicYear || '';
  const genre = btn.dataset.musicGenre || '';
  const ratingVal = btn.dataset.musicRating || '';
  const listened = btn.dataset.musicListened === 'true';
  const review = btn.dataset.musicReview || '';
  const reviewPublic = btn.dataset.musicReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-music-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="text" id="edit-music-artist" value="${escapeHtml(artist)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-music-year" value="${escapeHtml(year)}">`;
  row.cells[4].innerHTML = `<input type="text" id="edit-music-genre" value="${escapeHtml(genre)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-music-rating" value="${ratingVal}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-music-listened" ${listened ? 'checked' : ''}>`;
  row.cells[7].innerHTML = `<textarea id="edit-music-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-music-review')}`;
  const musicReviewTextarea = document.getElementById('edit-music-review');
  if (musicReviewTextarea) {
    musicReviewTextarea.style.height = 'auto';
    musicReviewTextarea.style.height = Math.max(60, musicReviewTextarea.scrollHeight) + 'px';
    musicReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(musicReviewTextarea);
  }
  row.cells[8].innerHTML = `<input type="checkbox" id="edit-music-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[9].innerHTML = `
    <button class="action-btn save-music-btn" data-music-id="${id}" data-was-complete="${listened}" data-completion-category="music">Save</button>
    <button class="action-btn cancel-music-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'musicTable');
};

window.saveMusicEdit = async function (btn) {
  const id = parseInt(btn.dataset.musicId, 10);
  const title = document.getElementById('edit-music-title').value;
  const artist = document.getElementById('edit-music-artist').value;
  const year = parseInt(document.getElementById('edit-music-year').value, 10);
  const genre = document.getElementById('edit-music-genre').value;
  const listened = document.getElementById('edit-music-listened').checked;
  const ratingVal = document.getElementById('edit-music-rating').value;
  const reviewVal = document.getElementById('edit-music-review') ? document.getElementById('edit-music-review').value : '';

  const updateData = { title, artist, year };
  updateData.genre = genre || null;
  updateData.listened = listened;
  updateData.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  if (reviewVal !== undefined) updateData.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-music-review-public');
  if (reviewPublicEl) updateData.review_public = reviewPublicEl.checked;

  const res = await authenticatedFetch(`${API_BASE}/music/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updateData),
  });

  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && listened) openCompletionMoment('music', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('musicTable');
    loadMusic();
  }
};

window.cancelMusicEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('musicTable');
  loadMusic();
};

let isLoadingBooks = false;

async function loadBooks() {
  if (isLoadingBooks) {
    return;
  }

  isLoadingBooks = true;

  try {
    const search = document.getElementById('bookSearch').value;
    const sortVal = document.getElementById('bookSort').value;
    let sortField = '';
    let order = '';
    if (sortVal) {
      const parts = sortVal.split('-');
      sortField = parts[0];
      order = parts[1] || '';
    }
    let url = `${API_BASE}/books/?`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    if (sortField) url += `sort_by=${encodeURIComponent(sortField)}&`;
    if (order) url += `order=${encodeURIComponent(order)}`;
    const res = await fetchLibraryPage(url);
    if (res.ok) {
      const books = await res.json();
      const tbody = document.querySelector('#bookTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('bookCount');
      if (countElem) countElem.textContent = `${res.total} Book${res.total === 1 ? '' : 's'}`;
      books.forEach((book) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="book-poster-${book.id}"></td>
          <td>${escapeHtml(book.title)}</td>
          <td>${escapeHtml(book.author ?? '')}</td>
          <td>${book.year ?? ''}</td>
          <td>${book.genre ? escapeHtml(book.genre) : ''}</td>
          <td>${book.rating !== null && book.rating !== undefined ? parseFloat(book.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${book.read ? 'watched' : 'unwatched'}">${book.read ? '✓' : '✗'}</span></td>
          <td class="review-cell">${getReviewCellContent(book.review, book.title, book.author || '')}</td>
          <td><span class="watched-icon ${book.review_public ? 'watched' : 'unwatched'}">${book.review_public ? '✓' : '✗'}</span></td>
          <td>
            <button class="action-btn edit-book-btn" data-book-id="${book.id}" data-book-title="${escapeHtml(book.title)}" data-book-author="${escapeHtml(book.author ?? '')}" data-book-year="${book.year ?? ''}" data-book-genre="${escapeHtml(book.genre || '')}" data-book-rating="${book.rating ?? ''}" data-book-read="${book.read}" data-book-review="${escapeHtml(book.review || '')}" data-book-review-public="${book.review_public || false}">Edit</button>
            <button type="button" class="action-btn" data-action="add-next-up" data-next-up-category="books" data-next-up-item-id="${book.id}">Next up</button>
            <button type="button" class="action-btn" data-progress-category="books" data-progress-item-id="${book.id}" data-progress-title="${escapeHtml(book.title)}">Update progress</button>
            <button type="button" class="action-btn" data-action="open-collection-picker" data-collection-category="books" data-collection-item-id="${book.id}" data-collection-item-title="${escapeHtml(book.title)}">Collect</button>
            ${book.read ? `<button type="button" class="action-btn" data-action="begin-completion-ritual" data-completion-category="books" data-completion-item-id="${book.id}">Reflect</button>` : ''}
            <button class="action-btn delete-book-btn" data-book-id="${book.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        if (book.cover_art_url) {
          displayBookPoster(book.id, book.cover_art_url, book.title);
        } else {
          fetchBookMetadata(book.id, book.title, book.author);
        }
      });
    }
  } finally {
    isLoadingBooks = false;
  }
}

function displayBookPoster(id, posterUrl, title = null) {
  const cell = document.getElementById(`book-poster-${id}`);
  if (cell && posterUrl) {
    let altText = 'Book cover art';
    if (title) {
      altText = `${title} book cover art`;
    } else {
      const row = cell.closest('tr');
      if (row && row.cells[1]) {
        altText = `${row.cells[1].textContent} book cover art`;
      }
    }
    const img = document.createElement('img');
    img.src = posterUrl;
    img.alt = altText;
    img.style.width = '60px';
    img.style.maxHeight = '90px';
    img.style.objectFit = 'cover';
    img.style.borderRadius = '4px';
    img.loading = 'lazy';
    img.onclick = () => showImagePopup(posterUrl, altText);
    cell.innerHTML = '';
    cell.appendChild(img);
  }
}

async function fetchBookMetadata(id, title, author) {
  const cacheKey = `book-${title}-${author}`;
  const row = document.querySelector(`#book-poster-${id}`)?.closest('tr');
  const current = () => row && row !== editingRowElement
    && document.querySelector(`#book-poster-${id}`)?.closest('tr') === row;
  let pending = posterFetchQueue.get(cacheKey);
  if (!pending) {
    posterFetchInProgress.add(cacheKey);
    pending = (async () => {
      await waitForPosterSlot();
      try {
        try {
          const searchQuery = author ? `${title} ${author}` : title;
          const proxyUrl = `${API_BASE}/api/proxy/openlibrary?query=${encodeURIComponent(searchQuery)}`;

          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000);

          let res;
          try {
            res = await cachedProxyFetch(proxyUrl, {
              signal: controller.signal,
              headers: {
                'Accept': 'application/json'
              }
            });
            clearTimeout(timeoutId);
          } catch (fetchError) {
            clearTimeout(timeoutId);
            if (fetchError.name === 'AbortError') {
              console.warn(`Open Library API request timeout for "${title}". This may be due to network issues or VPN blocking.`);
            } else {
              console.warn(`Network error fetching metadata for "${title}":`, fetchError.message);
            }
            return null;
          }

          if (!res.ok) {
            if (res.status === 429) {
              console.warn('Open Library API rate limit reached. Metadata will be fetched later.');
              return null;
            }
            if (res.status === 504) {
              console.warn(`Open Library API timeout for "${title}". This may be due to network issues or VPN blocking.`);
              return null;
            }
            if (res.status >= 500) {
              console.warn(`Open Library API server error (${res.status}) for "${title}". This may be due to network issues.`);
              return null;
            }
            return null;
          }

          let data;
          try {
            data = await res.json();
          } catch (jsonError) {
            console.warn(`Failed to parse Open Library API response for "${title}":`, jsonError);
            return null;
          }

          if (data && data.docs && data.docs.length > 0) {
            const book = data.docs[0];
            const coverId = book.cover_i || book.isbn?.[0] || null;
            const coverArtUrl = coverId ? `https://covers.openlibrary.org/b/id/${coverId}-L.jpg` : null;
            const normalizedTitle = book.title || null;
            const bookAuthor = book.author_name && book.author_name.length > 0 ? book.author_name[0] : null;
            const bookYear = book.first_publish_year || book.publish_year?.[0] || null;
            const bookGenres = book.subject ? book.subject.slice(0, 3).join(', ') : null;

            if (coverArtUrl) {

              return { cover_art_url: coverArtUrl, author: bookAuthor, year: bookYear, genre: bookGenres, normalized_title: normalizedTitle };
            }
          }
          return null;
        } catch (err) {
          console.error('Error fetching book metadata:', err);
          return null;
        }

      } finally { releasePosterSlot(); }
    })();
    posterFetchQueue.set(cacheKey, pending);
    pending.finally(() => setTimeout(() => {
      if (posterFetchQueue.get(cacheKey) === pending) {
        posterFetchQueue.delete(cacheKey); posterFetchInProgress.delete(cacheKey);
      }
    }, 1000)).catch(() => {});
  }
  try {
    const result = await pending;
    if (!result?.cover_art_url || !current()) return;
    await saveBookMetadata(id, result.cover_art_url, result.author, result.year, result.genre, result.normalized_title);
    if (!current()) return;
    displayBookPoster(id, result.cover_art_url, result.normalized_title || title);
    updateBookRowMetadata(id, result.author, result.year, result.genre, result.normalized_title);
  } catch (error) { console.error('Error fetching book metadata:', error); }
}

function updateBookRowMetadata(id, author, year, genre, normalizedTitle) {
  const row = document.querySelector(`#book-poster-${id}`)?.closest('tr');
  if (!row || row === editingRowElement) return;

  if (normalizedTitle && row.cells[1]) {
    row.cells[1].textContent = normalizedTitle;
  }

  if (author && row.cells[2]) {
    row.cells[2].textContent = author;
  }

  if (year && row.cells[3]) {
    row.cells[3].textContent = year;
  }

  if (genre && row.cells[4]) {
    row.cells[4].textContent = genre;
  }
}

async function saveBookMetadata(id, coverArtUrl, author, year, genre, normalizedTitle) {
  try {
    const updateData = { cover_art_url: coverArtUrl };
    if (author) updateData.author = author;
    if (year) updateData.year = year;
    if (genre) updateData.genre = genre;
    if (normalizedTitle) updateData.title = normalizedTitle;
    await authenticatedFetch(`${API_BASE}/books/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData),
    });
  } catch (err) {
    console.error('Error saving book metadata:', err);
  }
}

async function deleteBook(id) {
  if (!confirm('Are you sure you want to delete this book?')) return;
  const res = await authenticatedFetch(`${API_BASE}/books/${id}`, { method: 'DELETE' });
  if (res.ok) loadBooks();
}

window.enableBookEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.bookId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  const title = btn.dataset.bookTitle || '';
  const author = btn.dataset.bookAuthor || '';
  const year = btn.dataset.bookYear || '';
  const genre = btn.dataset.bookGenre || '';
  const ratingVal = btn.dataset.bookRating || '';
  const read = btn.dataset.bookRead === 'true';
  const review = btn.dataset.bookReview || '';
  const reviewPublic = btn.dataset.bookReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-book-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="text" id="edit-book-author" value="${escapeHtml(author)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-book-year" value="${escapeHtml(year)}">`;
  row.cells[4].innerHTML = `<input type="text" id="edit-book-genre" value="${escapeHtml(genre)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-book-rating" value="${ratingVal}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-book-read" ${read ? 'checked' : ''}>`;
  row.cells[7].innerHTML = `<textarea id="edit-book-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-book-review')}`;
  const bookReviewTextarea = document.getElementById('edit-book-review');
  if (bookReviewTextarea) {
    bookReviewTextarea.style.height = 'auto';
    bookReviewTextarea.style.height = Math.max(60, bookReviewTextarea.scrollHeight) + 'px';
    bookReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(bookReviewTextarea);
  }
  row.cells[8].innerHTML = `<input type="checkbox" id="edit-book-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[9].innerHTML = `
    <button class="action-btn save-book-btn" data-book-id="${id}" data-was-complete="${read}" data-completion-category="books">Save</button>
    <button class="action-btn cancel-book-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'bookTable');
};

window.saveBookEdit = async function (btn) {
  const id = parseInt(btn.dataset.bookId, 10);
  const title = document.getElementById('edit-book-title').value;
  const author = document.getElementById('edit-book-author').value;
  const year = parseInt(document.getElementById('edit-book-year').value, 10);
  const genre = document.getElementById('edit-book-genre').value;
  const read = document.getElementById('edit-book-read').checked;
  const ratingVal = document.getElementById('edit-book-rating').value;
  const reviewVal = document.getElementById('edit-book-review') ? document.getElementById('edit-book-review').value : '';

  const updateData = { title, author, year };
  updateData.genre = genre || null;
  updateData.read = read;
  updateData.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  if (reviewVal !== undefined) updateData.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-book-review-public');
  if (reviewPublicEl) updateData.review_public = reviewPublicEl.checked;

  const res = await authenticatedFetch(`${API_BASE}/books/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updateData),
  });

  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && read) openCompletionMoment('books', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('bookTable');
    loadBooks();
  }
};

window.cancelBookEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('bookTable');
  loadBooks();
};

async function deleteAnime(id) {
  if (!confirm('Are you sure you want to delete this anime?')) return;
  const res = await authenticatedFetch(`${API_BASE}/anime/${id}`, { method: 'DELETE' });
  if (res.ok) loadAnime();
}

window.enableAnimeEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.animeId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  // Read data from dataset (browsers handle this securely)
  const title = btn.dataset.animeTitle || '';
  const year = btn.dataset.animeYear || '';
  const seasons = btn.dataset.animeSeasons || '';
  const episodes = btn.dataset.animeEpisodes || '';
  const ratingVal = btn.dataset.animeRating || '';
  const watched = btn.dataset.animeWatched === 'true';
  const review = btn.dataset.animeReview || '';
  const reviewPublic = btn.dataset.animeReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-anime-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="number" id="edit-anime-year" value="${escapeHtml(year)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-anime-seasons" value="${escapeHtml(seasons)}">`;
  row.cells[4].innerHTML = `<input type="number" id="edit-anime-episodes" value="${escapeHtml(episodes)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-anime-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-anime-watched" ${watched ? 'checked' : ''}>`;
  row.cells[7].innerHTML = `<textarea id="edit-anime-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-anime-review')}`;
  const animeReviewTextarea = document.getElementById('edit-anime-review');
  if (animeReviewTextarea) {
    animeReviewTextarea.style.height = 'auto';
    animeReviewTextarea.style.height = Math.max(60, animeReviewTextarea.scrollHeight) + 'px';
    animeReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(animeReviewTextarea);
  }
  row.cells[9].innerHTML = `<input type="checkbox" id="edit-anime-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[10].innerHTML = `
    <button class="action-btn save-anime-btn" data-anime-id="${id}" data-was-complete="${watched}" data-completion-category="anime">Save</button>
    <button class="action-btn cancel-anime-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'animeTable');
};

window.saveAnimeEdit = async function (btn) {
  const id = parseInt(btn.dataset.animeId, 10);
  if (editingRowId !== id) return;
  const updated = {
    title: document.getElementById('edit-anime-title').value,
    year: parseInt(document.getElementById('edit-anime-year').value, 10),
    watched: document.getElementById('edit-anime-watched').checked,
  };
  const seasonsVal = document.getElementById('edit-anime-seasons').value;
  updated.seasons = seasonsVal === '' ? null : parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('edit-anime-episodes').value;
  updated.episodes = episodesVal === '' ? null : parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('edit-anime-rating').value;
  updated.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-anime-review') ? document.getElementById('edit-anime-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-anime-review-public');
  if (reviewPublicEl) updated.review_public = reviewPublicEl.checked;
  const res = await authenticatedFetch(`${API_BASE}/anime/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && updated.watched) openCompletionMoment('anime', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('animeTable');
    loadAnime();
  }
};

window.cancelAnimeEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('animeTable');
  loadAnime();
};

async function deleteTVShow(id) {
  if (!confirm('Are you sure you want to delete this TV show?')) return;
  const res = await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, { method: 'DELETE' });
  if (res.ok) loadTVShows();
}

window.enableTVEdit = function (btn) {
  if (editingRowId !== null) return;
  const id = parseInt(btn.dataset.tvId, 10);
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  // Read data from dataset (browsers handle this securely)
  const title = btn.dataset.tvTitle || '';
  const year = btn.dataset.tvYear || '';
  const seasons = btn.dataset.tvSeasons || '';
  const episodes = btn.dataset.tvEpisodes || '';
  const ratingVal = btn.dataset.tvRating || '';
  const watched = btn.dataset.tvWatched === 'true';
  const review = btn.dataset.tvReview || '';
  const reviewPublic = btn.dataset.tvReviewPublic === 'true';
  row.cells[1].innerHTML = `<input type="text" id="edit-tv-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="number" id="edit-tv-year" value="${escapeHtml(year)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-tv-seasons" value="${escapeHtml(seasons)}">`;
  row.cells[4].innerHTML = `<input type="number" id="edit-tv-episodes" value="${escapeHtml(episodes)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-tv-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-tv-watched" ${watched ? 'checked' : ''}>`;
  row.cells[7].innerHTML = `<textarea id="edit-tv-review" class="review-textarea" data-review-quality-input>${escapeHtml(review)}</textarea>${reviewQualityHintHtml('edit-tv-review')}`;
  const tvReviewTextarea = document.getElementById('edit-tv-review');
  if (tvReviewTextarea) {
    tvReviewTextarea.style.height = 'auto';
    tvReviewTextarea.style.height = Math.max(60, tvReviewTextarea.scrollHeight) + 'px';
    tvReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
    setupReviewQualityCounter(tvReviewTextarea);
  }
  row.cells[9].innerHTML = `<input type="checkbox" id="edit-tv-review-public" ${reviewPublic ? 'checked' : ''}>`;
  row.cells[10].innerHTML = `
    <button class="action-btn save-tv-btn" data-tv-id="${id}" data-was-complete="${watched}" data-completion-category="tv-shows">Save</button>
    <button class="action-btn cancel-tv-btn">Cancel</button>
  `;
  disableOtherRowButtons(row, 'tvShowTable');
};

window.saveTVEdit = async function (btn) {
  const id = parseInt(btn.dataset.tvId, 10);
  if (editingRowId !== id) return;
  const updated = {
    title: document.getElementById('edit-tv-title').value,
    year: parseInt(document.getElementById('edit-tv-year').value, 10),
    watched: document.getElementById('edit-tv-watched').checked,
  };
  const seasonsVal = document.getElementById('edit-tv-seasons').value;
  updated.seasons = seasonsVal === '' ? null : parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('edit-tv-episodes').value;
  updated.episodes = episodesVal === '' ? null : parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('edit-tv-rating').value;
  updated.rating = ratingVal === '' ? null : parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-tv-review') ? document.getElementById('edit-tv-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const reviewPublicEl = document.getElementById('edit-tv-review-public');
  if (reviewPublicEl) updated.review_public = reviewPublicEl.checked;
  const res = await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
    if (btn.dataset.wasComplete !== 'true' && updated.watched) openCompletionMoment('tv-shows', id);
    editingRowId = null;
    editingRowElement = null;
    enableAllRowButtons('tvShowTable');
    loadTVShows();
  }
};

window.cancelTVEdit = function () {
  editingRowId = null;
  editingRowElement = null;
  enableAllRowButtons('tvShowTable');
  loadTVShows();
};

// @lazy-chunk lazy/metadata-movie.js
document.getElementById('searchMovieBtn').onclick = searchMovieMetadata;

document.getElementById('movieTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchMovieMetadata();
  }
});

// @lazy-chunk lazy/metadata-tv-anime-games.js
document.getElementById('searchTVShowBtn').onclick = searchTVShowMetadata;
document.getElementById('searchAnimeBtn').onclick = searchAnimeMetadata;
document.getElementById('searchVideoGameBtn').onclick = searchVideoGameMetadata;

document.getElementById('tvTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchTVShowMetadata();
  }
});

document.getElementById('animeTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchAnimeMetadata();
  }
});

document.getElementById('videoGameTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchVideoGameMetadata();
  }
});

document.getElementById('addMovieForm').onsubmit = async function (e) {
  e.preventDefault();
  const titleInput = document.getElementById('movieTitle');
  const directorInput = document.getElementById('movieDirector');
  const yearInput = document.getElementById('movieYear');
  
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter a movie title.');
    return;
  }
  
  const director = directorInput.value.trim();
  if (!director) {
    alert('Please enter a director or click "Search" to auto-fill movie information.');
    return;
  }
  
  const yearVal = yearInput.value.trim();
  if (!yearVal) {
    alert('Please enter a year or click "Search" to auto-fill movie information.');
    return;
  }
  
  const year = parseInt(yearVal, 10);
  if (isNaN(year) || year < 0) {
    alert('Please enter a valid year.');
    return;
  }
  
  const movie = {
    title: title,
    director: director,
    year: year,
    watched: document.getElementById('movieWatched').checked,
    review_public: document.getElementById('movieReviewPublic').checked,
  };
  
  const ratingVal = document.getElementById('movieRating').value;
  if (ratingVal) movie.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('movieReview').value;
  if (reviewVal) movie.review = reviewVal;
  
  if (titleInput.dataset.posterUrl) {
    movie.poster_url = titleInput.dataset.posterUrl;
  }
  
  const response = await authenticatedFetch(`${API_BASE}/movies/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(movie),
  });
  if (response.ok) {
    document.getElementById('addMovieForm').reset();
    if (titleInput.dataset.posterUrl) {
      delete titleInput.dataset.posterUrl;
    }
    loadMovies();
  } else {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to add movie' }));
    alert(errorData.detail || 'Failed to add movie');
  }
};

document.getElementById('addTVShowForm').onsubmit = async function (e) {
  e.preventDefault();
  const titleInput = document.getElementById('tvTitle');
  const yearInput = document.getElementById('tvYear');
  
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter a TV show title.');
    return;
  }
  
  const yearVal = yearInput.value.trim();
  if (!yearVal) {
    alert('Please enter a year or click "Search" to auto-fill TV show information.');
    return;
  }
  
  const year = parseInt(yearVal, 10);
  if (isNaN(year) || year < 0) {
    alert('Please enter a valid year.');
    return;
  }
  
  const tvShow = {
    title: title,
    year: year,
    watched: document.getElementById('tvWatched').checked,
    review_public: document.getElementById('tvReviewPublic').checked,
  };
  
  const seasonsVal = document.getElementById('tvSeasons').value;
  if (seasonsVal) tvShow.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('tvEpisodes').value;
  if (episodesVal) tvShow.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('tvRating').value;
  if (ratingVal) tvShow.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('tvReview').value;
  if (reviewVal) tvShow.review = reviewVal;
  
  if (titleInput.dataset.posterUrl) {
    tvShow.poster_url = titleInput.dataset.posterUrl;
  }
  
  const response = await authenticatedFetch(`${API_BASE}/tv-shows/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tvShow),
  });
  if (response.ok) {
    document.getElementById('addTVShowForm').reset();
    if (titleInput.dataset.posterUrl) {
      delete titleInput.dataset.posterUrl;
    }
    loadTVShows();
  } else {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to add TV show' }));
    alert(errorData.detail || 'Failed to add TV show');
  }
};

document.getElementById('addAnimeForm').onsubmit = async function (e) {
  e.preventDefault();
  const titleInput = document.getElementById('animeTitle');
  const yearInput = document.getElementById('animeYear');
  
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter an anime title.');
    return;
  }
  
  const yearVal = yearInput.value.trim();
  if (!yearVal) {
    alert('Please enter a year or click "Search" to auto-fill anime information.');
    return;
  }
  
  const year = parseInt(yearVal, 10);
  if (isNaN(year) || year < 0) {
    alert('Please enter a valid year.');
    return;
  }
  
  const anime = {
    title: title,
    year: year,
    watched: document.getElementById('animeWatched').checked,
    review_public: document.getElementById('animeReviewPublic').checked,
  };
  
  const seasonsVal = document.getElementById('animeSeasons').value;
  if (seasonsVal) anime.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('animeEpisodes').value;
  if (episodesVal) anime.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('animeRating').value;
  if (ratingVal) anime.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('animeReview').value;
  if (reviewVal) anime.review = reviewVal;
  
  if (titleInput.dataset.posterUrl) {
    anime.poster_url = titleInput.dataset.posterUrl;
  }
  
  const response = await authenticatedFetch(`${API_BASE}/anime/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(anime),
  });
  if (response.ok) {
    document.getElementById('addAnimeForm').reset();
    if (titleInput.dataset.posterUrl) {
      delete titleInput.dataset.posterUrl;
    }
    toggleCollapsible('animeForm');
    loadAnime();
  } else {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to add anime' }));
    alert(errorData.detail || 'Failed to add anime');
  }
};

document.getElementById('addVideoGameForm').onsubmit = async function (e) {
  e.preventDefault();
  const titleInput = document.getElementById('videoGameTitle');
  
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter a video game title.');
    return;
  }
  
  const videoGame = {
    title: title,
    played: document.getElementById('videoGamePlayed').checked,
    review_public: document.getElementById('videoGameReviewPublic').checked,
  };
  
  const genresVal = document.getElementById('videoGameGenres').value;
  if (genresVal) videoGame.genres = genresVal;
  const ratingVal = document.getElementById('videoGameRating').value;
  if (ratingVal) videoGame.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('videoGameReview').value;
  if (reviewVal) videoGame.review = reviewVal;
  
  if (titleInput.dataset.releaseDate) {
    videoGame.release_date = titleInput.dataset.releaseDate;
  }
  if (titleInput.dataset.coverArtUrl) {
    videoGame.cover_art_url = titleInput.dataset.coverArtUrl;
  }
  if (titleInput.dataset.rawgLink) {
    videoGame.rawg_link = titleInput.dataset.rawgLink;
  }
  
  const response = await authenticatedFetch(`${API_BASE}/video-games/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(videoGame),
  });
  if (response.ok) {
    document.getElementById('addVideoGameForm').reset();
    if (titleInput.dataset.releaseDate) {
      delete titleInput.dataset.releaseDate;
    }
    if (titleInput.dataset.coverArtUrl) {
      delete titleInput.dataset.coverArtUrl;
    }
    if (titleInput.dataset.rawgLink) {
      delete titleInput.dataset.rawgLink;
    }
    toggleCollapsible('videoGameForm');
    loadVideoGames();
  } else {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to add video game' }));
    alert(errorData.detail || 'Failed to add video game');
  }
};

// @lazy-chunk lazy/metadata-music.js
document.getElementById('searchMusicBtn').onclick = searchMusicMetadata;

document.getElementById('musicTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchMusicMetadata();
  }
});

document.getElementById('addMusicForm').onsubmit = async function (e) {
  e.preventDefault();
  const titleInput = document.getElementById('musicTitle');
  const artistInput = document.getElementById('musicArtist');
  const yearInput = document.getElementById('musicYear');
  
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter a music title.');
    return;
  }
  
  const artist = artistInput.value.trim();
  if (!artist) {
    alert('Please enter an artist or click "Search" to auto-fill music information.');
    return;
  }
  
  const yearVal = yearInput.value.trim();
  if (!yearVal) {
    alert('Please enter a year or click "Search" to auto-fill music information.');
    return;
  }
  
  const year = parseInt(yearVal, 10);
  if (isNaN(year) || year < 0) {
    alert('Please enter a valid year.');
    return;
  }
  
  const music = {
    title: title,
    artist: artist,
    year: year,
    listened: document.getElementById('musicListened').checked,
    review_public: document.getElementById('musicReviewPublic').checked,
  };
  
  const genreVal = document.getElementById('musicGenre').value;
  if (genreVal) music.genre = genreVal;
  const ratingVal = document.getElementById('musicRating').value;
  if (ratingVal) music.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('musicReview').value;
  if (reviewVal) music.review = reviewVal;
  
  if (titleInput.dataset.coverArtUrl) {
    music.cover_art_url = titleInput.dataset.coverArtUrl;
  }
  
  const response = await authenticatedFetch(`${API_BASE}/music/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(music),
  });
  if (response.ok) {
    document.getElementById('addMusicForm').reset();
    if (titleInput.dataset.coverArtUrl) {
      delete titleInput.dataset.coverArtUrl;
    }
    toggleCollapsible('musicForm');
    loadMusic();
  } else {
    const errorData = await response.json().catch(() => ({ detail: 'Failed to add music' }));
    alert(errorData.detail || 'Failed to add music');
  }
};

// @lazy-chunk lazy/metadata-books.js
document.getElementById('searchBookBtn').onclick = searchBookMetadata;

document.getElementById('bookTitle').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    searchBookMetadata();
  }
});

document.getElementById('addBookForm').onsubmit = async function (e) {
  e.preventDefault();
  const form = document.getElementById('addBookForm');
  if (form.dataset.saving === 'true') return;
  let status = document.getElementById('bookSaveStatus');
  if (!status) {
    status = document.createElement('p');
    status.id = 'bookSaveStatus';
    status.setAttribute('role', 'status');
    form.appendChild(status);
  }
  status.textContent = '';
  const titleInput = document.getElementById('bookTitle');
  const authorInput = document.getElementById('bookAuthor');
  const yearInput = document.getElementById('bookYear');
  
  const title = titleInput.value.trim();
  if (!title) {
    status.textContent = 'Please enter a book title.';
    titleInput.focus();
    return;
  }
  
  const author = authorInput.value.trim();
  if (!author) {
    status.textContent = 'Please enter an author or click "Search" to auto-fill book information.';
    authorInput.focus();
    return;
  }
  
  const yearVal = yearInput.value.trim();
  if (!yearVal) {
    status.textContent = 'Please enter a year or click "Search" to auto-fill book information.';
    yearInput.focus();
    return;
  }
  
  const year = parseInt(yearVal, 10);
  if (isNaN(year) || year < 0) {
    status.textContent = 'Please enter a valid year.';
    yearInput.focus();
    return;
  }
  
  const book = {
    title: title,
    author: author,
    year: year,
    read: document.getElementById('bookRead').checked,
    review_public: document.getElementById('bookReviewPublic').checked,
  };
  
  const genreVal = document.getElementById('bookGenre').value;
  if (genreVal) book.genre = genreVal;
  const ratingVal = document.getElementById('bookRating').value;
  if (ratingVal) book.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('bookReview').value;
  if (reviewVal) book.review = reviewVal;
  
  if (titleInput.dataset.coverArtUrl) {
    book.cover_art_url = titleInput.dataset.coverArtUrl;
  }
  
  form.dataset.saving = 'true';
  const submit = form.querySelector('button[type="submit"]');
  if (submit) submit.disabled = true;
  status.textContent = 'Saving your book…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/books/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(book),
    });
    if (response.ok) {
      status.textContent = '';
      form.reset();
      if (titleInput.dataset.coverArtUrl) {
        delete titleInput.dataset.coverArtUrl;
      }
      toggleCollapsible('bookForm');
      loadBooks();
    } else {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to add book' }));
      status.textContent = typeof errorData.detail === 'string' ? errorData.detail : 'Could not save this book. Check the fields and try again.';
    }
  } catch (error) {
    status.textContent = error.message === 'Session expired. Please login again.'
      ? 'Your session expired. Sign in again before saving. Your form has not been cleared.'
      : 'Could not confirm the save. Your form has not been cleared. Check your library before retrying to avoid a duplicate.';
  } finally {
    delete form.dataset.saving;
    if (submit) submit.disabled = false;
  }
};

// @lazy-chunk lazy/export-import.js
function enhanceLibraryCards(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.classList.add('mobile-library');
  table.setAttribute('role', 'table');
  const labels = Array.from(table.tHead.rows[0].cells, cell => cell.textContent.trim());
  table.querySelectorAll('thead tr, tbody tr').forEach(row => row.setAttribute('role', 'row'));
  table.querySelectorAll('th').forEach(cell => {
    cell.scope = 'col';
    cell.setAttribute('role', 'columnheader');
    cell.dataset.label = cell.textContent.trim();
  });
  Array.from(table.tBodies[0].rows).forEach((row, rowIndex) => {
    Array.from(row.cells).forEach((cell, index) => {
      const label = labels[index];
      cell.dataset.label = label === 'Public' ? 'Public review' : label;
      cell.setAttribute('role', 'cell');
      cell.classList.add('library-cell');
      const type = index === 0 ? 'cover' : index === 1 ? 'title'
        : label === 'Rating' ? 'rating' : ['Watched', 'Played', 'Listened', 'Read'].includes(label) ? 'status'
        : label === 'Actions' ? 'actions' : 'detail';
      cell.dataset.cardField = type;
      cell.querySelectorAll('input, textarea, select').forEach(input => {
        if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', cell.dataset.label);
      });
      if (type === 'status' || label === 'Public') {
        const icon = cell.querySelector('.watched-icon');
        if (icon) {
          const complete = icon.classList.contains('watched');
          icon.setAttribute('aria-label', label === 'Public' ? (complete ? 'Public review' : 'Private review')
            : (complete ? label : `Not ${label.toLowerCase()}`));
        }
      }
    });
    const actions = row.cells[row.cells.length - 1];
    if (!actions.querySelector('.library-card-details')) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'library-card-details';
      button.textContent = 'More details'; button.setAttribute('aria-expanded', 'false');
      const details = Array.from(row.cells).filter(cell => cell.dataset.cardField === 'detail');
      details.forEach((cell, index) => { cell.id = `${tableId}-card-${rowIndex}-detail-${index}`; });
      button.setAttribute('aria-controls', details.map(cell => cell.id).join(' '));
      button.addEventListener('click', () => {
        const expanded = row.classList.toggle('card-expanded');
        button.setAttribute('aria-expanded', String(expanded));
        button.textContent = expanded ? 'Less detail' : 'More details';
      });
      actions.appendChild(button);
    }
    groupRowActions(actions);
  });
}

// Keep Edit visible and tuck the other row actions into a small "More" menu.
// Buttons keep their classes and data attributes, so every existing handler still works.
function groupRowActions(cell) {
  if (!cell || cell.querySelector('.row-actions')) return;
  const buttons = Array.from(cell.children).filter(node => node.matches && node.matches('button.action-btn'));
  const primary = buttons.find(button => /\bedit-[\w-]+-btn\b/.test(button.className));
  if (!primary) return; // Edit mode (Save/Cancel) keeps its own layout.
  const secondary = buttons.filter(button => button !== primary);
  const wrapper = document.createElement('div');
  wrapper.className = 'row-actions';
  cell.insertBefore(wrapper, primary);
  wrapper.appendChild(primary);
  if (!secondary.length) return;
  const menu = document.createElement('details');
  menu.className = 'row-menu';
  const summary = document.createElement('summary');
  summary.textContent = 'More';
  summary.setAttribute('aria-label', 'More actions');
  const panel = document.createElement('div');
  panel.className = 'row-menu__panel';
  secondary.forEach(button => panel.appendChild(button));
  menu.append(summary, panel);
  wrapper.appendChild(menu);
  // Tables scroll sideways, which would clip a normal dropdown: pin the open menu to the viewport.
  const place = () => {
    const box = summary.getBoundingClientRect();
    const width = Math.max(168, panel.offsetWidth || 168);
    const left = Math.min(window.innerWidth - width - 8, Math.max(8, box.right - width));
    const below = box.bottom + 6;
    const height = panel.offsetHeight || 180;
    const top = below + height > window.innerHeight - 8 ? Math.max(8, box.top - height - 6) : below;
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  };
  menu.rowMenuPlace = place;
  menu.addEventListener('toggle', () => { if (menu.open) place(); });
}
['scroll', 'resize'].forEach(type => window.addEventListener(type, () => {
  document.querySelectorAll('details.row-menu[open]').forEach(menu => menu.rowMenuPlace?.());
}, { passive: true, capture: true }));

document.addEventListener('click', event => {
  document.querySelectorAll('details.row-menu[open]').forEach(menu => {
    const chosen = event.target.closest && event.target.closest('.row-menu__panel button');
    if (!menu.contains(event.target) || (chosen && menu.contains(chosen))) menu.removeAttribute('open');
  });
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  const open = document.querySelector('details.row-menu[open]');
  if (!open) return;
  open.removeAttribute('open');
  open.querySelector('summary')?.focus();
  event.stopPropagation();
}, true);

// Import Studio is loaded from /static/import-studio.js.

// Statistics functions
function loadStatistics() {
  document.getElementById('statsLoading').style.display = 'none';
  document.getElementById('statsContent').style.display = 'block';
  loadMonthlyReplay();
  loadTasteprint(false);
  if (!categoryStatsCache['library-insights']) {
    toggleCategoryAccordion('library-insights');
  }
}

const categoryStatsCache = {};

