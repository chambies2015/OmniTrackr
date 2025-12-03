const isLocal = (location.protocol === 'file:' || location.origin === 'null' || location.origin === '');
const API_BASE = isLocal ? 'http://127.0.0.1:8000' : '';

let editingRowId = null;
let editingRowElement = null;
let currentTab = 'movies';
let notificationCountInterval = null;

// Poster fetch deduplication - prevent multiple simultaneous OMDB API calls for same movie/show
const posterFetchInProgress = new Set();
const posterFetchQueue = new Map(); // title+year -> Promise

// Utility HTML escaping function
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Image popup functions
function showImagePopup(imageUrl, altText) {
  const modal = document.getElementById('imagePopupModal');
  const img = document.getElementById('popupImage');
  if (modal && img) {
    img.src = imageUrl;
    img.alt = altText || 'Enlarged image';
    modal.style.display = 'flex';
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
  }
}

function closeImagePopup() {
  const modal = document.getElementById('imagePopupModal');
  if (modal) {
    modal.style.display = 'none';
    // Restore body scroll
    document.body.style.overflow = '';
  }
}

// Close image popup on Escape key
document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    const modal = document.getElementById('imagePopupModal');
    if (modal && modal.style.display !== 'none') {
      closeImagePopup();
    }
  }
});

// Tab switching functionality
function switchTab(tabName) {
  // Check if tab is visible (only for media tabs, statistics is always visible)
  if (tabName !== 'statistics') {
    const tabButton = document.querySelector(`[onclick="switchTab('${tabName}')"]`);
    if (tabButton && tabButton.style.display === 'none') {
      // Tab is hidden, don't switch to it
      return;
    }
  }

  // Update tab buttons
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  const targetTab = document.querySelector(`[onclick="switchTab('${tabName}')"]`);
  if (targetTab) {
    targetTab.classList.add('active');
  }

  // Update tab content
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  const tabContent = document.getElementById(`${tabName}-tab`);
  if (tabContent) {
    tabContent.classList.add('active');
  }

  currentTab = tabName;

  // Load data for the active tab
  if (tabName === 'movies') {
    loadMovies();
  } else if (tabName === 'tv-shows') {
    loadTVShows();
  } else if (tabName === 'anime') {
    loadAnime();
  } else if (tabName === 'video-games') {
    loadVideoGames();
  } else if (tabName === 'statistics') {
    loadStatistics();
  }
}

function disableOtherRowButtons(currentRow, tableId) {
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
    const res = await authenticatedFetch(url);
    if (res.ok) {
      const movies = await res.json();
      const tbody = document.querySelector('#movieTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('movieCount');
      if (countElem) countElem.textContent = `${movies.length} Movies`;
      movies.forEach((movie) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="movie-poster-${movie.id}"></td>
          <td>${movie.title}</td>
          <td>${movie.director}</td>
          <td>${movie.year}</td>
          <td>${movie.rating !== null && movie.rating !== undefined ? parseFloat(movie.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${movie.watched ? 'watched' : 'unwatched'}">${movie.watched ? '✓' : '✗'}</span></td>
          <td>${movie.review ? movie.review : ''}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(movie.title)}" target="_blank">Search</a></td>
          <td>
            <button class="action-btn edit-movie-btn" data-movie-id="${movie.id}" data-movie-title="${escapeHtml(movie.title)}" data-movie-director="${escapeHtml(movie.director)}" data-movie-year="${movie.year}" data-movie-rating="${movie.rating ?? ''}" data-movie-watched="${movie.watched}" data-movie-review="${escapeHtml(movie.review || '')}">Edit</button>
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
    altText = escapeHtml(altText);
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
        const posterUrl = await existingPromise;
        if (posterUrl) {
          displayMoviePoster(id, posterUrl, title);
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  // Mark as in progress
  posterFetchInProgress.add(cacheKey);

  try {
    // Use backend proxy endpoint to keep API key secure
    const proxyUrl = `${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}`;
    const res = await fetch(proxyUrl);

    if (!res.ok) {
      // Handle rate limiting (429 Too Many Requests)
      if (res.status === 429) {
        console.warn('OMDB API rate limit reached. Posters will be fetched later.');
        return;
      }
      if (res.status === 503) {
        console.warn('OMDB API not configured on server.');
        return;
      }
      return;
    }

    const data = await res.json();

    // Check for API errors
    if (data.Error) {
      console.warn(`OMDB API error for "${title}": ${data.Error}`);
      return;
    }

    if (data && data.Poster && data.Poster !== 'N/A') {
      // Save the poster URL to the database
      await saveMoviePosterUrl(id, data.Poster);
      // Display the poster
      displayMoviePoster(id, data.Poster, title);

      // Store result in queue for other waiting requests
      posterFetchQueue.set(cacheKey, Promise.resolve(data.Poster));
      return data.Poster;
    }
  } catch (err) {
    console.error('Error fetching movie poster:', err);
    // Store failed promise to prevent retries
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    // Remove from in-progress set after a delay to allow queued requests
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveMoviePosterUrl(id, posterUrl) {
  try {
    await authenticatedFetch(`${API_BASE}/movies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ poster_url: posterUrl }),
    });
  } catch (err) {
    console.error('Error saving poster URL:', err);
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
  const year = parseInt(btn.dataset.movieYear, 10);
  const ratingVal = btn.dataset.movieRating || '';
  const watched = btn.dataset.movieWatched === 'true';
  const review = btn.dataset.movieReview || '';
  row.cells[1].innerHTML = `<input type="text" id="edit-movie-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="text" id="edit-movie-director" value="${escapeHtml(director)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-movie-year" value="${escapeHtml(year)}">`;
  row.cells[4].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-movie-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[5].innerHTML = `<input type="checkbox" id="edit-movie-watched" ${watched ? 'checked' : ''}>`;
  // Escape HTML for textarea content
  row.cells[6].innerHTML = `<textarea id="edit-movie-review" class="review-textarea">${escapeHtml(review)}</textarea>`;
  // Auto-resize textarea to content
  const movieReviewTextarea = document.getElementById('edit-movie-review');
  if (movieReviewTextarea) {
    movieReviewTextarea.style.height = 'auto';
    movieReviewTextarea.style.height = Math.max(60, movieReviewTextarea.scrollHeight) + 'px';
    movieReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
  }
  row.cells[8].innerHTML = `
    <button class="action-btn save-movie-btn" data-movie-id="${id}">Save</button>
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
  if (ratingVal) updated.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-movie-review') ? document.getElementById('edit-movie-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const res = await authenticatedFetch(`${API_BASE}/movies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
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
    const res = await authenticatedFetch(url);
    if (res.ok) {
      const tvShows = await res.json();
      const tbody = document.querySelector('#tvShowTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('tvShowCount');
      if (countElem) countElem.textContent = `${tvShows.length} TV Shows`;
      tvShows.forEach((tvShow) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="tv-poster-${tvShow.id}"></td>
          <td>${tvShow.title}</td>
          <td>${tvShow.year}</td>
          <td>${tvShow.seasons ?? ''}</td>
          <td>${tvShow.episodes ?? ''}</td>
          <td>${tvShow.rating !== null && tvShow.rating !== undefined ? parseFloat(tvShow.rating).toFixed(1) + '/10' : ''}</td>
          <td><span class="watched-icon ${tvShow.watched ? 'watched' : 'unwatched'}">${tvShow.watched ? '✓' : '✗'}</span></td>
          <td>${tvShow.review ? tvShow.review : ''}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(tvShow.title)}" target="_blank">Search</a></td>
          <td>
            <button class="action-btn edit-tv-btn" data-tv-id="${tvShow.id}" data-tv-title="${escapeHtml(tvShow.title)}" data-tv-year="${tvShow.year}" data-tv-seasons="${tvShow.seasons ?? ''}" data-tv-episodes="${tvShow.episodes ?? ''}" data-tv-rating="${tvShow.rating ?? ''}" data-tv-watched="${tvShow.watched}" data-tv-review="${escapeHtml(tvShow.review || '')}">Edit</button>
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
    const res = await authenticatedFetch(url);
    if (res.ok) {
      const anime = await res.json();
      const tbody = document.querySelector('#animeTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('animeCount');
      if (countElem) countElem.textContent = `${anime.length} Anime`;
      anime.forEach((animeItem) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td id="anime-poster-${animeItem.id}"></td>
          <td>${animeItem.title}</td>
          <td style="text-align: center;">${animeItem.year}</td>
          <td style="text-align: center;">${animeItem.seasons ?? ''}</td>
          <td style="text-align: center;">${animeItem.episodes ?? ''}</td>
          <td style="text-align: center;">${animeItem.rating !== null && animeItem.rating !== undefined ? parseFloat(animeItem.rating).toFixed(1) + '/10' : ''}</td>
          <td style="text-align: center;"><span class="watched-icon ${animeItem.watched ? 'watched' : 'unwatched'}">${animeItem.watched ? '✓' : '✗'}</span></td>
          <td>${animeItem.review ? animeItem.review : ''}</td>
          <td><a href="https://www.imdb.com/find?q=${encodeURIComponent(animeItem.title)}" target="_blank">Search</a></td>
          <td>
            <button class="action-btn edit-anime-btn" data-anime-id="${animeItem.id}" data-anime-title="${escapeHtml(animeItem.title)}" data-anime-year="${animeItem.year}" data-anime-seasons="${animeItem.seasons ?? ''}" data-anime-episodes="${animeItem.episodes ?? ''}" data-anime-rating="${animeItem.rating ?? ''}" data-anime-watched="${animeItem.watched}" data-anime-review="${escapeHtml(animeItem.review || '')}">Edit</button>
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
        const posterUrl = await existingPromise;
        if (posterUrl) {
          displayTVPoster(id, posterUrl, title);
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  // Mark as in progress
  posterFetchInProgress.add(cacheKey);

  try {
    const url = `https://www.omdbapi.com/?t=${encodeURIComponent(title)}&y=${encodeURIComponent(year)}&apikey=${OMDB_API_KEY}`;
    const res = await fetch(url);

    if (!res.ok) {
      // Handle rate limiting (429 Too Many Requests)
      if (res.status === 429) {
        console.warn('OMDB API rate limit reached. Posters will be fetched later.');
        return;
      }
      return;
    }

    const data = await res.json();

    // Check for API errors
    if (data.Error) {
      console.warn(`OMDB API error for "${title}": ${data.Error}`);
      return;
    }

    if (data && data.Poster && data.Poster !== 'N/A') {
      // Save the poster URL to the database
      await saveTVPosterUrl(id, data.Poster);
      // Display the poster
      displayTVPoster(id, data.Poster, title);

      // Store result in queue for other waiting requests
      posterFetchQueue.set(cacheKey, Promise.resolve(data.Poster));
      return data.Poster;
    }
  } catch (err) {
    console.error('Error fetching TV show poster:', err);
    // Store failed promise to prevent retries
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    // Remove from in-progress set after a delay to allow queued requests
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveTVPosterUrl(id, posterUrl) {
  try {
    await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ poster_url: posterUrl }),
    });
  } catch (err) {
    console.error('Error saving TV show poster URL:', err);
  }
}

async function fetchAnimePoster(id, title, year) {
  // Create unique key for deduplication
  const cacheKey = `anime-${title}-${year}`;

  // Check if already fetching this poster
  if (posterFetchInProgress.has(cacheKey)) {
    // Wait for existing fetch to complete
    const existingPromise = posterFetchQueue.get(cacheKey);
    if (existingPromise) {
      try {
        const posterUrl = await existingPromise;
        if (posterUrl) {
          displayAnimePoster(id, posterUrl, title);
        }
      } catch (err) {
        // Ignore errors from other fetch
      }
    }
    return;
  }

  // Mark as in progress
  posterFetchInProgress.add(cacheKey);

  try {
    const url = `https://www.omdbapi.com/?t=${encodeURIComponent(title)}&y=${encodeURIComponent(year)}&apikey=${OMDB_API_KEY}`;
    const res = await fetch(url);

    if (!res.ok) {
      // Handle rate limiting (429 Too Many Requests)
      if (res.status === 429) {
        console.warn('OMDB API rate limit reached. Posters will be fetched later.');
        return;
      }
      return;
    }

    const data = await res.json();

    // Check for API errors
    if (data.Error) {
      console.warn(`OMDB API error for "${title}": ${data.Error}`);
      return;
    }

    if (data && data.Poster && data.Poster !== 'N/A') {
      // Save the poster URL to the database
      await saveAnimePosterUrl(id, data.Poster);
      // Display the poster
      displayAnimePoster(id, data.Poster, title);

      // Store result in queue for other waiting requests
      posterFetchQueue.set(cacheKey, Promise.resolve(data.Poster));
      return data.Poster;
    }
  } catch (err) {
    console.error('Error fetching anime poster:', err);
    // Store failed promise to prevent retries
    posterFetchQueue.set(cacheKey, Promise.resolve(null));
  } finally {
    // Remove from in-progress set after a delay to allow queued requests
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveAnimePosterUrl(id, posterUrl) {
  try {
    await authenticatedFetch(`${API_BASE}/anime/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ poster_url: posterUrl }),
    });
  } catch (err) {
    console.error('Error saving anime poster URL:', err);
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
    const res = await authenticatedFetch(url);
    if (res.ok) {
      const videoGames = await res.json();
      const tbody = document.querySelector('#videoGameTable tbody');
      tbody.innerHTML = '';
      const countElem = document.getElementById('videoGameCount');
      if (countElem) countElem.textContent = `${videoGames.length} Video Games`;
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
          <td>${game.rawg_link ? `<a href="${game.rawg_link}" target="_blank">View on RAWG</a>` : ''}</td>
          <td>${game.review ? escapeHtml(game.review) : ''}</td>
          <td>
            <button class="action-btn edit-video-game-btn" data-game-id="${game.id}" data-game-title="${escapeHtml(game.title)}" data-game-release-date="${game.release_date ? game.release_date.split('T')[0] : ''}" data-game-genres="${escapeHtml(game.genres || '')}" data-game-rating="${game.rating ?? ''}" data-game-played="${game.played}" data-game-review="${escapeHtml(game.review || '')}">Edit</button>
            <button class="action-btn delete-video-game-btn" data-game-id="${game.id}">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached cover art or fetch new one
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
    altText = escapeHtml(altText);
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

function updateVideoGameRowMetadata(id, genres, rawgLink, releaseDate) {
  // Find the row for this video game
  const row = document.querySelector(`#video-game-poster-${id}`)?.closest('tr');
  if (!row) return;

  // Update release date (cell index 2)
  if (releaseDate && row.cells[2]) {
    const date = new Date(releaseDate);
    row.cells[2].textContent = date.toLocaleDateString();
  }

  // Update genres (cell index 3)
  if (row.cells[3]) {
    row.cells[3].textContent = genres ? escapeHtml(genres) : '';
  }

  // Update RAWG link (cell index 6)
  if (row.cells[6]) {
    if (rawgLink) {
      row.cells[6].innerHTML = `<a href="${rawgLink}" target="_blank">View on RAWG</a>`;
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
          displayVideoGamePoster(id, result.cover_art_url, title);
          await saveVideoGameMetadata(id, result.cover_art_url, result.genres, result.rawg_link, result.release_date);
          updateVideoGameRowMetadata(id, result.genres, result.rawg_link, result.release_date);
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
      // Use backend proxy endpoint to keep API key secure
      const proxyUrl = `${API_BASE}/api/proxy/rawg?search=${encodeURIComponent(title)}`;
      const res = await fetch(proxyUrl);

      if (!res.ok) {
        // Handle rate limiting (429 Too Many Requests)
        if (res.status === 429) {
          console.warn('RAWG API rate limit reached. Metadata will be fetched later.');
          return null;
        }
        if (res.status === 503) {
          console.warn('RAWG API not configured on server.');
          return null;
        }
        return null;
      }

      const data = await res.json();

      // Check for API errors
      if (data.error) {
        console.warn(`RAWG API error for "${title}": ${data.error}`);
        return null;
      }

      // Get first result
      if (data && data.results && data.results.length > 0) {
        const game = data.results[0];
        const coverArtUrl = game.background_image || null;
        const genres = game.genres ? game.genres.map(g => g.name).join(', ') : null;
        const rawgLink = game.slug ? `https://rawg.io/games/${game.slug}` : null;
        const releaseDate = game.released || null; // RAWG API returns date as "YYYY-MM-DD" string

        if (coverArtUrl) {
          // Save the metadata to the database
          await saveVideoGameMetadata(id, coverArtUrl, genres, rawgLink, releaseDate);
          // Display the cover art
          displayVideoGamePoster(id, coverArtUrl, title);
          // Update the table row with metadata
          updateVideoGameRowMetadata(id, genres, rawgLink, releaseDate);

          return { cover_art_url: coverArtUrl, genres: genres, rawg_link: rawgLink, release_date: releaseDate };
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
        displayVideoGamePoster(id, result.cover_art_url, title);
        await saveVideoGameMetadata(id, result.cover_art_url, result.genres, result.rawg_link, result.release_date);
        updateVideoGameRowMetadata(id, result.genres, result.rawg_link, result.release_date);
      }
    } catch (err) {
      // Ignore errors from other fetch
    }
    return;
  }
  
  // Add our promise to the queue
  posterFetchQueue.set(cacheKey, fetchPromise);
  // Mark as in progress AFTER adding to queue
  posterFetchInProgress.add(cacheKey);

  try {
    const result = await fetchPromise;
    return result;
  } finally {
    // Remove from in-progress set after a delay to allow queued requests
    setTimeout(() => {
      posterFetchInProgress.delete(cacheKey);
      posterFetchQueue.delete(cacheKey);
    }, 1000);
  }
}

async function saveVideoGameMetadata(id, coverArtUrl, genres, rawgLink, releaseDate) {
  try {
    const updateData = { cover_art_url: coverArtUrl };
    if (genres) updateData.genres = genres;
    if (rawgLink) updateData.rawg_link = rawgLink;
    if (releaseDate) updateData.release_date = releaseDate;
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
  row.cells[1].innerHTML = `<input type="text" id="edit-video-game-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="date" id="edit-video-game-release-date" value="${releaseDate}">`;
  row.cells[3].innerHTML = `<input type="text" id="edit-video-game-genres" value="${escapeHtml(genres)}">`;
  row.cells[4].innerHTML = `<input type="checkbox" id="edit-video-game-played" ${played ? 'checked' : ''}>`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-video-game-rating" value="${ratingVal}">`;
  // Keep RAWG link as is (preserve HTML to maintain clickable link - don't modify this cell)
  // Review cell is at index 7, replace it with textarea for editing
  row.cells[7].innerHTML = `<textarea id="edit-video-game-review" class="review-textarea">${escapeHtml(review)}</textarea>`;
  // Auto-resize textarea to content
  const videoGameReviewTextarea = document.getElementById('edit-video-game-review');
  if (videoGameReviewTextarea) {
    videoGameReviewTextarea.style.height = 'auto';
    videoGameReviewTextarea.style.height = Math.max(60, videoGameReviewTextarea.scrollHeight) + 'px';
    videoGameReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
  }
  // Actions cell is always the last cell, so use length - 1 to get the correct index
  const actionsCellIndex = row.cells.length - 1;
  row.cells[actionsCellIndex].innerHTML = `
    <button class="action-btn save-video-game-btn" data-game-id="${id}">Save</button>
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
  if (releaseDate) updateData.release_date = releaseDate;
  if (genres) updateData.genres = genres;
  updateData.played = played;
  if (ratingVal) updateData.rating = parseFloat(ratingVal);
  if (reviewVal !== undefined) updateData.review = reviewVal;

  const res = await authenticatedFetch(`${API_BASE}/video-games/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updateData),
  });

  if (res.ok) {
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
  const year = parseInt(btn.dataset.animeYear, 10);
  const seasons = btn.dataset.animeSeasons || '';
  const episodes = btn.dataset.animeEpisodes || '';
  const ratingVal = btn.dataset.animeRating || '';
  const watched = btn.dataset.animeWatched === 'true';
  const review = btn.dataset.animeReview || '';
  row.cells[1].innerHTML = `<input type="text" id="edit-anime-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="number" id="edit-anime-year" value="${escapeHtml(year)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-anime-seasons" value="${escapeHtml(seasons)}">`;
  row.cells[4].innerHTML = `<input type="number" id="edit-anime-episodes" value="${escapeHtml(episodes)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-anime-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-anime-watched" ${watched ? 'checked' : ''}>`;
  // Escape HTML for textarea content
  row.cells[7].innerHTML = `<textarea id="edit-anime-review" class="review-textarea">${escapeHtml(review)}</textarea>`;
  // Auto-resize textarea to content
  const animeReviewTextarea = document.getElementById('edit-anime-review');
  if (animeReviewTextarea) {
    animeReviewTextarea.style.height = 'auto';
    animeReviewTextarea.style.height = Math.max(60, animeReviewTextarea.scrollHeight) + 'px';
    animeReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
  }
  row.cells[9].innerHTML = `
    <button class="action-btn save-anime-btn" data-anime-id="${id}">Save</button>
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
  if (seasonsVal) updated.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('edit-anime-episodes').value;
  if (episodesVal) updated.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('edit-anime-rating').value;
  if (ratingVal) updated.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-anime-review') ? document.getElementById('edit-anime-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const res = await authenticatedFetch(`${API_BASE}/anime/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
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
  const year = parseInt(btn.dataset.tvYear, 10);
  const seasons = btn.dataset.tvSeasons || '';
  const episodes = btn.dataset.tvEpisodes || '';
  const ratingVal = btn.dataset.tvRating || '';
  const watched = btn.dataset.tvWatched === 'true';
  const review = btn.dataset.tvReview || '';
  row.cells[1].innerHTML = `<input type="text" id="edit-tv-title" value="${escapeHtml(title)}">`;
  row.cells[2].innerHTML = `<input type="number" id="edit-tv-year" value="${escapeHtml(year)}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-tv-seasons" value="${escapeHtml(seasons)}">`;
  row.cells[4].innerHTML = `<input type="number" id="edit-tv-episodes" value="${escapeHtml(episodes)}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-tv-rating" value="${escapeHtml(ratingVal)}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-tv-watched" ${watched ? 'checked' : ''}>`;
  // Escape HTML for textarea content
  row.cells[7].innerHTML = `<textarea id="edit-tv-review" class="review-textarea">${escapeHtml(review)}</textarea>`;
  // Auto-resize textarea to content
  const tvReviewTextarea = document.getElementById('edit-tv-review');
  if (tvReviewTextarea) {
    tvReviewTextarea.style.height = 'auto';
    tvReviewTextarea.style.height = Math.max(60, tvReviewTextarea.scrollHeight) + 'px';
    tvReviewTextarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.max(60, this.scrollHeight) + 'px';
    });
  }
  row.cells[9].innerHTML = `
    <button class="action-btn save-tv-btn" data-tv-id="${id}">Save</button>
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
  if (seasonsVal) updated.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('edit-tv-episodes').value;
  if (episodesVal) updated.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('edit-tv-rating').value;
  if (ratingVal) updated.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('edit-tv-review') ? document.getElementById('edit-tv-review').value : '';
  if (reviewVal !== undefined) updated.review = reviewVal;
  const res = await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updated),
  });
  if (res.ok) {
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

// Form submissions
document.getElementById('addMovieForm').onsubmit = async function (e) {
  e.preventDefault();
  const movie = {
    title: document.getElementById('movieTitle').value,
    director: document.getElementById('movieDirector').value,
    year: parseInt(document.getElementById('movieYear').value, 10),
    watched: document.getElementById('movieWatched').checked,
  };
  const ratingVal = document.getElementById('movieRating').value;
  if (ratingVal) movie.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('movieReview').value;
  if (reviewVal) movie.review = reviewVal;
  const response = await authenticatedFetch(`${API_BASE}/movies/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(movie),
  });
  if (response.ok) {
    document.getElementById('addMovieForm').reset();
    loadMovies();
  }
};

document.getElementById('addTVShowForm').onsubmit = async function (e) {
  e.preventDefault();
  const tvShow = {
    title: document.getElementById('tvTitle').value,
    year: parseInt(document.getElementById('tvYear').value, 10),
    watched: document.getElementById('tvWatched').checked,
  };
  const seasonsVal = document.getElementById('tvSeasons').value;
  if (seasonsVal) tvShow.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('tvEpisodes').value;
  if (episodesVal) tvShow.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('tvRating').value;
  if (ratingVal) tvShow.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('tvReview').value;
  if (reviewVal) tvShow.review = reviewVal;
  const response = await authenticatedFetch(`${API_BASE}/tv-shows/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tvShow),
  });
  if (response.ok) {
    document.getElementById('addTVShowForm').reset();
    loadTVShows();
  }
};

document.getElementById('addAnimeForm').onsubmit = async function (e) {
  e.preventDefault();
  const anime = {
    title: document.getElementById('animeTitle').value,
    year: parseInt(document.getElementById('animeYear').value, 10),
    watched: document.getElementById('animeWatched').checked,
  };
  const seasonsVal = document.getElementById('animeSeasons').value;
  if (seasonsVal) anime.seasons = parseInt(seasonsVal, 10);
  const episodesVal = document.getElementById('animeEpisodes').value;
  if (episodesVal) anime.episodes = parseInt(episodesVal, 10);
  const ratingVal = document.getElementById('animeRating').value;
  if (ratingVal) anime.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('animeReview').value;
  if (reviewVal) anime.review = reviewVal;
  const response = await authenticatedFetch(`${API_BASE}/anime/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(anime),
  });
  if (response.ok) {
    document.getElementById('addAnimeForm').reset();
    toggleCollapsible('animeForm');
    loadAnime();
  }
};

document.getElementById('addVideoGameForm').onsubmit = async function (e) {
  e.preventDefault();
  const videoGame = {
    title: document.getElementById('videoGameTitle').value,
    played: document.getElementById('videoGamePlayed').checked,
  };
  // Release date will be fetched from RAWG API metadata, not user input
  const genresVal = document.getElementById('videoGameGenres').value;
  if (genresVal) videoGame.genres = genresVal;
  const ratingVal = document.getElementById('videoGameRating').value;
  if (ratingVal) videoGame.rating = parseFloat(ratingVal);
  const reviewVal = document.getElementById('videoGameReview').value;
  if (reviewVal) videoGame.review = reviewVal;
  const response = await authenticatedFetch(`${API_BASE}/video-games/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(videoGame),
  });
  if (response.ok) {
    document.getElementById('addVideoGameForm').reset();
    toggleCollapsible('videoGameForm');
    loadVideoGames();
  }
};

// Export/Import functions
async function exportData() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/export/`);
    if (!response.ok) {
      throw new Error('Export failed');
    }

    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `omnitrackr-export-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    alert(`Export successful! Exported ${data.export_metadata.total_movies} movies, ${data.export_metadata.total_tv_shows} TV shows, ${data.export_metadata.total_anime || 0} anime, and ${data.export_metadata.total_video_games || 0} video games.`);
  } catch (error) {
    alert('Export failed: ' + error.message);
  }
}

async function importData(fileInput) {
  const file = fileInput.files[0];
  if (!file) return;

  if (!file.name.endsWith('.json')) {
    alert('Please select a JSON file.');
    return;
  }

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await authenticatedFetch(`${API_BASE}/import/file/`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Import failed');
    }

    const result = await response.json();
    let message = `Import completed!\n`;
    message += `Movies: ${result.movies_created} created, ${result.movies_updated} updated\n`;
    message += `TV Shows: ${result.tv_shows_created} created, ${result.tv_shows_updated} updated\n`;
    message += `Anime: ${result.anime_created || 0} created, ${result.anime_updated || 0} updated\n`;
    message += `Video Games: ${result.video_games_created || 0} created, ${result.video_games_updated || 0} updated`;

    if (result.errors.length > 0) {
      message += `\n\nErrors:\n${result.errors.join('\n')}`;
    }

    alert(message);

    // Refresh the current tab
    if (currentTab === 'movies') {
      loadMovies();
    } else if (currentTab === 'tv-shows') {
      loadTVShows();
    } else if (currentTab === 'anime') {
      loadAnime();
    } else if (currentTab === 'video-games') {
      loadVideoGames();
    }

    // Clear the file input
    fileInput.value = '';
  } catch (error) {
    alert('Import failed: ' + error.message);
    fileInput.value = '';
  }
}

// Statistics functions
async function loadStatistics() {
  try {
    document.getElementById('statsLoading').style.display = 'block';
    document.getElementById('statsContent').style.display = 'none';

    const response = await authenticatedFetch(`${API_BASE}/statistics/`);
    if (!response.ok) {
      throw new Error('Failed to load statistics');
    }

    const stats = await response.json();
    displayStatistics(stats);

    document.getElementById('statsLoading').style.display = 'none';
    document.getElementById('statsContent').style.display = 'block';
  } catch (error) {
    console.error('Error loading statistics:', error);
    document.getElementById('statsLoading').innerHTML = '<p style="color: red;">Error loading statistics: ' + error.message + '</p>';
  }
}

function displayStatistics(stats) {
  // Watch statistics with animation
  animateValue('totalItems', 0, stats.watch_stats.total_items, 800);
  animateValue('watchedItems', 0, stats.watch_stats.watched_items, 800);
  animateValue('unwatchedItems', 0, stats.watch_stats.unwatched_items, 800);
  animatePercentage('completionPercentage', 0, stats.watch_stats.completion_percentage, 1000);

  // Progress bar with animation
  const progressFill = document.getElementById('progressFill');
  setTimeout(() => {
    progressFill.style.width = stats.watch_stats.completion_percentage + '%';
  }, 100);

  // Rating statistics with animation
  animateDecimal('averageRating', 0, parseFloat(stats.rating_stats.average_rating), 800);
  animateValue('totalRatedItems', 0, stats.rating_stats.total_rated_items, 800);

  // Rating distribution
  displayRatingDistribution(stats.rating_stats.rating_distribution);

  // Highest rated items
  displayHighestRated(stats.rating_stats.highest_rated);

  // Year statistics
  const oldestYear = stats.year_stats.oldest_year || '-';
  const newestYear = stats.year_stats.newest_year || '-';
  if (oldestYear !== '-') {
    animateValue('oldestYear', parseInt(oldestYear) - 10, oldestYear, 600);
  } else {
    document.getElementById('oldestYear').textContent = '-';
  }
  if (newestYear !== '-') {
    animateValue('newestYear', parseInt(newestYear) - 10, newestYear, 600);
  } else {
    document.getElementById('newestYear').textContent = '-';
  }

  // Decade statistics
  displayDecadeStats(stats.year_stats.decade_stats);

  // Director statistics
  displayTopDirectors(stats.director_stats.top_directors);
  displayHighestRatedDirectors(stats.director_stats.highest_rated_directors);
}

// Animation helper functions
function animateValue(elementId, start, end, duration) {
  const element = document.getElementById(elementId);
  if (!element) return;

  const startTime = performance.now();
  const isPercentage = elementId === 'completionPercentage';

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeOut = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(start + (end - start) * easeOut);

    element.textContent = isPercentage ? current + '%' : current;

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = isPercentage ? end + '%' : end;
    }
  }

  requestAnimationFrame(update);
}

function animatePercentage(elementId, start, end, duration) {
  animateValue(elementId, start, end, duration);
}

function animateDecimal(elementId, start, end, duration) {
  const element = document.getElementById(elementId);
  if (!element) return;

  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeOut = 1 - Math.pow(1 - progress, 3);
    const current = start + (end - start) * easeOut;

    element.textContent = current.toFixed(1);

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = end.toFixed(1);
    }
  }

  requestAnimationFrame(update);
}

function displayRatingDistribution(distribution) {
  const container = document.getElementById('ratingBars');
  container.innerHTML = '';

  // Get all counts and find the maximum
  const counts = Object.values(distribution).map(Number);
  const maxCount = counts.length > 0 ? Math.max(...counts) : 1;

  for (let rating = 1; rating <= 10; rating++) {
    const count = distribution[rating.toString()] || 0;
    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;

    const barDiv = document.createElement('div');
    barDiv.className = 'rating-bar';
    barDiv.style.opacity = '0';
    barDiv.style.transform = 'translateX(-20px)';

    const labelDiv = document.createElement('div');
    labelDiv.className = 'rating-bar-label';
    labelDiv.textContent = rating;

    // Create a wrapper for the fill bar to control its width properly
    const fillWrapper = document.createElement('div');
    fillWrapper.style.flex = '1';
    fillWrapper.style.minWidth = '0';
    fillWrapper.style.position = 'relative';

    const fillDiv = document.createElement('div');
    fillDiv.className = 'rating-bar-fill';
    fillDiv.style.width = '0%';
    fillDiv.style.position = 'absolute';
    fillDiv.style.left = '0';
    fillDiv.style.top = '0';
    fillDiv.style.bottom = '0';

    fillWrapper.appendChild(fillDiv);

    const countDiv = document.createElement('div');
    countDiv.className = 'rating-bar-count';
    countDiv.textContent = count;

    barDiv.appendChild(labelDiv);
    barDiv.appendChild(fillWrapper);
    barDiv.appendChild(countDiv);
    container.appendChild(barDiv);

    // Animate bar appearance
    setTimeout(() => {
      barDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      barDiv.style.opacity = '1';
      barDiv.style.transform = 'translateX(0)';
      setTimeout(() => {
        fillDiv.style.width = percentage + '%';
      }, 100);
    }, rating * 50);
  }
}

function displayHighestRated(items) {
  const container = document.getElementById('highestRatedList');
  container.innerHTML = '';

  if (items.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--fg); opacity: 0.6; padding: 20px;">No rated items found.</p>';
    return;
  }

  items.forEach((item, index) => {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'rated-item';
    itemDiv.style.opacity = '0';
    itemDiv.style.transform = 'translateY(10px)';
    itemDiv.innerHTML = `
      <div class="rated-item-title">${item.title} <span style="opacity: 0.6; font-size: 0.9em;">(${item.type})</span></div>
      <div class="rated-item-rating">${parseFloat(item.rating).toFixed(1)}/10</div>
    `;
    container.appendChild(itemDiv);

    // Animate item appearance
    setTimeout(() => {
      itemDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      itemDiv.style.opacity = '1';
      itemDiv.style.transform = 'translateY(0)';
    }, index * 100);
  });
}

function displayDecadeStats(decadeStats) {
  const container = document.getElementById('decadeBars');
  container.innerHTML = '';

  const decades = Object.keys(decadeStats).sort();

  // Calculate totals for each decade and find the maximum
  const totals = decades.map(decade =>
    (decadeStats[decade].movies || 0) + (decadeStats[decade].tv_shows || 0) + (decadeStats[decade].anime || 0)
  );
  const maxCount = totals.length > 0 ? Math.max(...totals) : 1;

  decades.forEach((decade, index) => {
    const total = (decadeStats[decade].movies || 0) + (decadeStats[decade].tv_shows || 0) + (decadeStats[decade].anime || 0);
    const percentage = maxCount > 0 ? (total / maxCount) * 100 : 0;

    const barDiv = document.createElement('div');
    barDiv.className = 'decade-bar';
    barDiv.style.opacity = '0';
    barDiv.style.transform = 'translateX(-20px)';

    const labelDiv = document.createElement('div');
    labelDiv.className = 'decade-bar-label';
    labelDiv.textContent = decade;

    // Create a wrapper for the fill bar to control its width properly
    const fillWrapper = document.createElement('div');
    fillWrapper.style.flex = '1';
    fillWrapper.style.minWidth = '0';
    fillWrapper.style.position = 'relative';

    const fillDiv = document.createElement('div');
    fillDiv.className = 'decade-bar-fill';
    fillDiv.style.width = '0%';
    fillDiv.style.position = 'absolute';
    fillDiv.style.left = '0';
    fillDiv.style.top = '0';
    fillDiv.style.bottom = '0';

    fillWrapper.appendChild(fillDiv);

    const countDiv = document.createElement('div');
    countDiv.className = 'decade-bar-count';
    countDiv.textContent = total;

    barDiv.appendChild(labelDiv);
    barDiv.appendChild(fillWrapper);
    barDiv.appendChild(countDiv);
    container.appendChild(barDiv);

    // Animate bar appearance
    setTimeout(() => {
      barDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      barDiv.style.opacity = '1';
      barDiv.style.transform = 'translateX(0)';
      setTimeout(() => {
        fillDiv.style.width = percentage + '%';
      }, 100);
    }, index * 80);
  });
}

function displayTopDirectors(directors) {
  const container = document.getElementById('topDirectorsList');
  container.innerHTML = '';

  if (directors.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--fg); opacity: 0.6; padding: 20px;">No directors found.</p>';
    return;
  }

  directors.forEach((director, index) => {
    const directorDiv = document.createElement('div');
    directorDiv.className = 'director-item';
    directorDiv.style.opacity = '0';
    directorDiv.style.transform = 'translateX(-10px)';
    directorDiv.innerHTML = `
      <div class="director-name">${director.director}</div>
      <div class="director-rating">${director.count} ${director.count === 1 ? 'movie' : 'movies'}</div>
    `;
    container.appendChild(directorDiv);

    // Animate item appearance
    setTimeout(() => {
      directorDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      directorDiv.style.opacity = '1';
      directorDiv.style.transform = 'translateX(0)';
    }, index * 80);
  });
}

function displayHighestRatedDirectors(directors) {
  const container = document.getElementById('highestRatedDirectorsList');
  container.innerHTML = '';

  if (directors.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--fg); opacity: 0.6; padding: 20px;">No rated directors found.</p>';
    return;
  }

  directors.forEach((director, index) => {
    const directorDiv = document.createElement('div');
    directorDiv.className = 'director-item';
    directorDiv.style.opacity = '0';
    directorDiv.style.transform = 'translateX(-10px)';
    directorDiv.innerHTML = `
      <div class="director-name">${director.director}</div>
      <div class="director-rating">${director.avg_rating.toFixed(1)}/10 <span style="opacity: 0.7; font-size: 0.9em;">(${director.count} ${director.count === 1 ? 'movie' : 'movies'})</span></div>
    `;
    container.appendChild(directorDiv);

    // Animate item appearance
    setTimeout(() => {
      directorDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      directorDiv.style.opacity = '1';
      directorDiv.style.transform = 'translateX(0)';
    }, index * 80);
  });
}

// Event listeners
document.getElementById('loadMovies').addEventListener('click', loadMovies);
document.getElementById('loadTVShows').addEventListener('click', loadTVShows);
document.getElementById('loadAnime').addEventListener('click', loadAnime);
document.getElementById('loadVideoGames').addEventListener('click', loadVideoGames);

// Automatic sorting and search
document.getElementById('movieSort').addEventListener('change', loadMovies);
document.getElementById('tvSort').addEventListener('change', loadTVShows);
document.getElementById('animeSort').addEventListener('change', loadAnime);
document.getElementById('videoGameSort').addEventListener('change', loadVideoGames);

// Automatic search with debounce
let movieSearchTimeout;
document.getElementById('movieSearch').addEventListener('input', (e) => {
  clearTimeout(movieSearchTimeout);
  movieSearchTimeout = setTimeout(() => {
    loadMovies();
  }, 300); // Wait 300ms after user stops typing
});

let tvSearchTimeout;
document.getElementById('tvSearch').addEventListener('input', (e) => {
  clearTimeout(tvSearchTimeout);
  tvSearchTimeout = setTimeout(() => {
    loadTVShows();
  }, 300); // Wait 300ms after user stops typing
});

let animeSearchTimeout;
document.getElementById('animeSearch').addEventListener('input', (e) => {
  clearTimeout(animeSearchTimeout);
  animeSearchTimeout = setTimeout(() => {
    loadAnime();
  }, 300); // Wait 300ms after user stops typing
});

let videoGameSearchTimeout;
document.getElementById('videoGameSearch').addEventListener('input', (e) => {
  clearTimeout(videoGameSearchTimeout);
  videoGameSearchTimeout = setTimeout(() => {
    loadVideoGames();
  }, 300); // Wait 300ms after user stops typing
});

// Export/Import event listeners
document.getElementById('exportMovies').addEventListener('click', exportData);
document.getElementById('exportTVShows').addEventListener('click', exportData);
document.getElementById('exportAnime').addEventListener('click', exportData);
document.getElementById('exportVideoGames').addEventListener('click', exportData);
document.getElementById('importMovies').addEventListener('click', () => document.getElementById('importFile').click());
document.getElementById('importTVShows').addEventListener('click', () => document.getElementById('importTVFile').click());
document.getElementById('importAnime').addEventListener('click', () => document.getElementById('importAnimeFile').click());
document.getElementById('importVideoGames').addEventListener('click', () => document.getElementById('importVideoGameFile').click());
document.getElementById('importFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importTVFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importAnimeFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importVideoGameFile').addEventListener('change', (e) => importData(e.target));

// Auto-resize textarea for movie review
const movieReviewTextarea = document.getElementById('movieReview');
if (movieReviewTextarea) {
  movieReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for TV show review
const tvReviewTextarea = document.getElementById('tvReview');
if (tvReviewTextarea) {
  tvReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for anime review
const animeReviewTextarea = document.getElementById('animeReview');
if (animeReviewTextarea) {
  animeReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for video game review
const videoGameReviewTextarea = document.getElementById('videoGameReview');
if (videoGameReviewTextarea) {
  videoGameReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Collapsible form toggle function
window.toggleCollapsible = function (formId) {
  const content = document.getElementById(formId + 'Content');
  const icon = document.getElementById(formId + 'Icon');

  if (content.style.display === 'none' || !content.classList.contains('expanded')) {
    content.style.display = 'block';
    content.classList.add('expanded');
    icon.classList.add('rotated');
  } else {
    content.classList.remove('expanded');
    icon.classList.remove('rotated');
    // Wait for animation to complete before hiding
    setTimeout(() => {
      if (!content.classList.contains('expanded')) {
        content.style.display = 'none';
      }
    }, 300);
  }
};

// Account Management Functions
window.openAccountModal = async function () {
  const modal = document.getElementById('accountModal');
  modal.style.display = 'flex';
  await loadAccountInfo();
}

window.closeAccountModal = function () {
  const modal = document.getElementById('accountModal');
  modal.style.display = 'none';
  // Clear all form errors and success messages
  document.querySelectorAll('.error-message, .success-message').forEach(el => {
    el.textContent = '';
    el.style.display = 'none';
  });
  // Reset forms
  document.getElementById('changeUsernameForm').reset();
  document.getElementById('changeEmailForm').reset();
  document.getElementById('changePasswordForm').reset();
  document.getElementById('deactivateAccountForm').reset();
}

window.loadAccountInfo = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/me`);
    if (response.ok) {
      const user = await response.json();
      document.getElementById('accountUsername').textContent = user.username;
      document.getElementById('accountEmail').textContent = user.email;

      // Format created date
      if (user.created_at) {
        const createdDate = new Date(user.created_at);
        document.getElementById('accountCreated').textContent = createdDate.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });
      } else {
        document.getElementById('accountCreated').textContent = 'Unknown';
      }

      // Email verification status
      document.getElementById('accountVerified').textContent = user.is_verified ? '✓ Verified' : '✗ Not Verified';
      document.getElementById('accountVerified').style.color = user.is_verified ? '#4caf50' : '#f44336';
    } else {
      console.error('Failed to load account info');
    }
  } catch (error) {
    console.error('Error loading account info:', error);
  }
}

window.changeUsername = async function (event) {
  event.preventDefault();
  const newUsername = document.getElementById('newUsername').value;
  const password = document.getElementById('usernamePassword').value;
  const errorEl = document.getElementById('usernameError');
  const successEl = document.getElementById('usernameSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/username`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_username: newUsername, password: password })
    });

    if (response.ok) {
      const updatedUser = await response.json();

      // Close the modal first
      closeAccountModal();

      // Show success message and inform user to relogin
      alert('Username changed successfully! Please login again with your new username.');

      // Force logout without confirmation (JWT token contains old username and is now invalid)
      // Use clearAuth from auth.js (available globally)
      if (typeof clearAuth === 'function') {
        clearAuth();
      } else {
        // Fallback: clear localStorage directly
        localStorage.removeItem('omnitrackr_token');
        localStorage.removeItem('omnitrackr_user');
      }
      location.reload();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change username';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change username. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.changeEmail = async function (event) {
  event.preventDefault();
  const newEmail = document.getElementById('newEmail').value;
  const password = document.getElementById('emailPassword').value;
  const errorEl = document.getElementById('emailError');
  const successEl = document.getElementById('emailSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/email`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_email: newEmail, password: password })
    });

    if (response.ok) {
      const data = await response.json();
      successEl.textContent = data.message || 'Verification email sent to new address. Please check your email.';
      successEl.style.display = 'block';
      document.getElementById('changeEmailForm').reset();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change email';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change email. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.changePassword = async function (event) {
  event.preventDefault();
  const currentPassword = document.getElementById('currentPassword').value;
  const newPassword = document.getElementById('accountNewPassword').value;
  const confirmPassword = document.getElementById('accountConfirmNewPassword').value;
  const errorEl = document.getElementById('passwordError');
  const successEl = document.getElementById('passwordSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  if (newPassword !== confirmPassword) {
    errorEl.textContent = 'New passwords do not match';
    errorEl.style.display = 'block';
    return;
  }

  if (newPassword.length < 6) {
    errorEl.textContent = 'Password must be at least 6 characters';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });

    if (response.ok) {
      const data = await response.json();
      successEl.textContent = data.message || 'Password changed successfully!';
      successEl.style.display = 'block';
      document.getElementById('changePasswordForm').reset();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change password';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change password. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.deactivateAccount = async function (event) {
  event.preventDefault();
  const password = document.getElementById('deactivatePassword').value;
  const errorEl = document.getElementById('deactivateError');

  errorEl.textContent = '';
  errorEl.style.display = 'none';

  if (!confirm('Are you sure you want to deactivate your account? You can reactivate within 90 days, but after that your account will be permanently deleted.')) {
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/deactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password })
    });

    if (response.ok) {
      const data = await response.json();
      alert(data.message || 'Account deactivated successfully. You will be logged out.');
      logout();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to deactivate account';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to deactivate account. Please try again.';
    errorEl.style.display = 'block';
  }
}

// Privacy Settings Functions
window.loadPrivacySettings = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/privacy`);
    if (response.ok) {
      const privacy = await response.json();
      document.getElementById('moviesPrivate').checked = privacy.movies_private;
      document.getElementById('tvShowsPrivate').checked = privacy.tv_shows_private;
      document.getElementById('animePrivate').checked = privacy.anime_private;
      document.getElementById('videoGamesPrivate').checked = privacy.video_games_private;
      document.getElementById('statisticsPrivate').checked = privacy.statistics_private;
    }
  } catch (error) {
    console.error('Failed to load privacy settings:', error);
  }
}

window.updatePrivacySettings = async function (event) {
  event.preventDefault();

  const moviesPrivate = document.getElementById('moviesPrivate').checked;
  const tvShowsPrivate = document.getElementById('tvShowsPrivate').checked;
  const animePrivate = document.getElementById('animePrivate').checked;
  const videoGamesPrivate = document.getElementById('videoGamesPrivate').checked;
  const statisticsPrivate = document.getElementById('statisticsPrivate').checked;

  const errorDiv = document.getElementById('privacyError');
  const successDiv = document.getElementById('privacySuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/privacy`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        movies_private: moviesPrivate,
        tv_shows_private: tvShowsPrivate,
        anime_private: animePrivate,
        video_games_private: videoGamesPrivate,
        statistics_private: statisticsPrivate
      })
    });

    if (response.ok) {
      successDiv.textContent = 'Privacy settings updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to update privacy settings';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to update privacy settings';
    errorDiv.style.display = 'block';
    console.error('Error updating privacy settings:', error);
  }
}

window.loadTabVisibility = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/tab-visibility`);
    if (response.ok) {
      const tabVisibility = await response.json();
      document.getElementById('moviesVisible').checked = tabVisibility.movies_visible;
      document.getElementById('tvShowsVisible').checked = tabVisibility.tv_shows_visible;
      document.getElementById('animeVisible').checked = tabVisibility.anime_visible;
      document.getElementById('videoGamesVisible').checked = tabVisibility.video_games_visible;
      // Update tab visibility in UI
      updateTabVisibilityUI(tabVisibility);
    }
  } catch (error) {
    console.error('Failed to load tab visibility settings:', error);
    // Default to all visible if loading fails
    updateTabVisibilityUI({
      movies_visible: true,
      tv_shows_visible: true,
      anime_visible: true,
      video_games_visible: true
    });
  }
}

window.updateTabVisibility = async function (event) {
  event.preventDefault();

  const moviesVisible = document.getElementById('moviesVisible').checked;
  const tvShowsVisible = document.getElementById('tvShowsVisible').checked;
  const animeVisible = document.getElementById('animeVisible').checked;
  const videoGamesVisible = document.getElementById('videoGamesVisible').checked;

  const errorDiv = document.getElementById('tabVisibilityError');
  const successDiv = document.getElementById('tabVisibilitySuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/tab-visibility`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        movies_visible: moviesVisible,
        tv_shows_visible: tvShowsVisible,
        anime_visible: animeVisible,
        video_games_visible: videoGamesVisible
      })
    });

    if (response.ok) {
      const tabVisibility = await response.json();
      // Update UI immediately
      updateTabVisibilityUI(tabVisibility);
      
      successDiv.textContent = 'Tab visibility updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to update tab visibility';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to update tab visibility';
    errorDiv.style.display = 'block';
    console.error('Error updating tab visibility:', error);
  }
}

function updateTabVisibilityUI(tabVisibility) {
  // Update tab buttons visibility
  const moviesTab = document.querySelector('[onclick="switchTab(\'movies\')"]');
  const tvShowsTab = document.querySelector('[onclick="switchTab(\'tv-shows\')"]');
  const animeTab = document.querySelector('[onclick="switchTab(\'anime\')"]');
  const videoGamesTab = document.querySelector('[onclick="switchTab(\'video-games\')"]');
  
  if (moviesTab) {
    moviesTab.style.display = tabVisibility.movies_visible ? '' : 'none';
  }
  if (tvShowsTab) {
    tvShowsTab.style.display = tabVisibility.tv_shows_visible ? '' : 'none';
  }
  if (animeTab) {
    animeTab.style.display = tabVisibility.anime_visible ? '' : 'none';
  }
  if (videoGamesTab) {
    videoGamesTab.style.display = tabVisibility.video_games_visible ? '' : 'none';
  }
  
  // If current tab is hidden, switch to first visible tab
  const currentTabElement = document.querySelector('.tab.active');
  if (currentTabElement && currentTabElement.style.display === 'none') {
    // Find first visible tab
    const allTabs = document.querySelectorAll('.tab');
    for (const tab of allTabs) {
      if (tab.style.display !== 'none') {
        const onclickStr = tab.getAttribute('onclick');
        if (onclickStr) {
          const match = onclickStr.match(/switchTab\('([^']+)'\)/);
          if (match) {
            switchTab(match[1]);
            break;
          }
        }
      }
    }
  }
}

// Profile Picture Functions
window.handleProfilePictureSelect = async function (event) {
  const file = event.target.files[0];
  if (!file) return;

  // Validate file type
  const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
  if (!allowedTypes.includes(file.type)) {
    document.getElementById('profilePictureError').textContent = 'Invalid file type. Allowed: JPEG, PNG, GIF, WebP';
    document.getElementById('profilePictureError').style.display = 'block';
    return;
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    document.getElementById('profilePictureError').textContent = 'File size exceeds 5MB limit';
    document.getElementById('profilePictureError').style.display = 'block';
    return;
  }

  // Preview image
  const reader = new FileReader();
  reader.onload = function (e) {
    document.getElementById('profilePicturePreview').src = e.target.result;
  };
  reader.readAsDataURL(file);

  // Upload file
  const formData = new FormData();
  formData.append('file', file);

  const errorDiv = document.getElementById('profilePictureError');
  const successDiv = document.getElementById('profilePictureSuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/profile-picture`, {
      method: 'POST',
      body: formData
    });

    if (response.ok) {
      const updatedUser = await response.json();
      // Update stored user data (getUser and saveAuthData are in auth.js)
      if (typeof getUser !== 'undefined' && typeof saveAuthData !== 'undefined' && typeof getToken !== 'undefined') {
        const user = getUser();
        const token = getToken();
        if (user && token) {
          user.profile_picture_url = updatedUser.profile_picture_url;
          saveAuthData(token, user);
        }

        // Update display
        if (typeof updateUserDisplay !== 'undefined') {
          updateUserDisplay();
        }
      }

      successDiv.textContent = 'Profile picture updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);

      // Show reset button
      document.getElementById('resetProfilePictureBtn').style.display = 'inline-block';
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to upload profile picture';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to upload profile picture';
    errorDiv.style.display = 'block';
    console.error('Error uploading profile picture:', error);
  }
}

window.resetProfilePicture = async function () {
  if (!confirm('Are you sure you want to remove your profile picture?')) {
    return;
  }

  const errorDiv = document.getElementById('profilePictureError');
  const successDiv = document.getElementById('profilePictureSuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/profile-picture`, {
      method: 'DELETE'
    });

    if (response.ok) {
      const updatedUser = await response.json();
      // Update stored user data (getUser and saveAuthData are in auth.js)
      if (typeof getUser !== 'undefined' && typeof saveAuthData !== 'undefined' && typeof getToken !== 'undefined') {
        const user = getUser();
        const token = getToken();
        if (user && token) {
          user.profile_picture_url = null;
          saveAuthData(token, user);
        }

        // Update display
        if (typeof updateUserDisplay !== 'undefined') {
          updateUserDisplay();
        }
      }

      // Reset preview
      document.getElementById('profilePicturePreview').src = '/static/default-avatar.svg';
      document.getElementById('profilePictureInput').value = '';
      document.getElementById('resetProfilePictureBtn').style.display = 'none';

      successDiv.textContent = 'Profile picture removed successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to remove profile picture';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to remove profile picture';
    errorDiv.style.display = 'block';
    console.error('Error removing profile picture:', error);
  }
}

// Update loadAccountInfo to also load privacy settings, tab visibility, and profile picture
const originalLoadAccountInfo = window.loadAccountInfo;
window.loadAccountInfo = async function () {
  await originalLoadAccountInfo();
  await loadPrivacySettings();
  await loadTabVisibility();

  // Load profile picture preview
  const user = getUser();
  const previewImg = document.getElementById('profilePicturePreview');
  const resetBtn = document.getElementById('resetProfilePictureBtn');

  if (previewImg) {
    if (user && user.profile_picture_url) {
      previewImg.src = user.profile_picture_url;
      if (resetBtn) resetBtn.style.display = 'inline-block';
    } else {
      previewImg.src = '/static/default-avatar.svg';
      if (resetBtn) resetBtn.style.display = 'none';
    }
  }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  const modal = document.getElementById('accountModal');
  if (e.target === modal) {
    closeAccountModal();
  }
});

// ============================================================================
// Friends Functions
// ============================================================================

async function loadFriendsList() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends`);
    if (response.ok) {
      const friends = await response.json();
      const friendsList = document.getElementById('friendsList');

      if (friends.length === 0) {
        friendsList.innerHTML = '<p class="no-friends">No friends yet</p>';
        return;
      }

      friendsList.innerHTML = friends.map(friend => `
        <div class="friend-item" data-friend-id="${friend.friend.id}">
          <div class="friend-item-content">
            <img class="friend-profile-picture" src="${friend.friend.profile_picture_url || '/static/default-avatar.svg'}" alt="${escapeHtml(friend.friend.username)}" onerror="this.src='/static/default-avatar.svg'">
            <span class="friend-username clickable" onclick="openFriendProfile(${friend.friend.id})" title="View profile">${escapeHtml(friend.friend.username)}</span>
          </div>
          <button class="unfriend-btn" onclick="unfriendUser(${friend.friend.id})" title="Unfriend">✕</button>
        </div>
      `).join('');
    }
  } catch (error) {
    console.error('Failed to load friends list:', error);
  }
}

window.openFriendRequestModal = function () {
  document.getElementById('friendRequestModal').style.display = 'flex';
}

window.closeFriendRequestModal = function () {
  document.getElementById('friendRequestModal').style.display = 'none';
  document.getElementById('friendRequestForm').reset();
  document.getElementById('friendRequestError').style.display = 'none';
  document.getElementById('friendRequestMessage').style.display = 'none';
}

window.sendFriendRequest = async function (event) {
  event.preventDefault();
  const username = document.getElementById('friendRequestUsername').value.trim();
  const errorEl = document.getElementById('friendRequestError');
  const successEl = document.getElementById('friendRequestMessage');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  if (!username) {
    errorEl.textContent = 'Please enter a username';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ receiver_username: username })
    });

    if (response.ok) {
      successEl.textContent = `Friend request sent to ${username}!`;
      successEl.style.display = 'block';
      document.getElementById('friendRequestForm').reset();
      setTimeout(() => {
        closeFriendRequestModal();
        updateNotificationCount();
      }, 1500);
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to send friend request';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to send friend request. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.acceptFriendRequest = async function (requestId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/requests/${requestId}/accept`, {
      method: 'POST'
    });

    if (response.ok) {
      loadFriendsList();
      loadNotifications();
      updateNotificationCount();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to accept friend request');
    }
  } catch (error) {
    alert('Failed to accept friend request. Please try again.');
  }
}

window.denyFriendRequest = async function (requestId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/requests/${requestId}/deny`, {
      method: 'POST'
    });

    if (response.ok) {
      loadNotifications();
      updateNotificationCount();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to deny friend request');
    }
  } catch (error) {
    alert('Failed to deny friend request. Please try again.');
  }
}

window.cancelFriendRequest = async function (requestId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/requests/${requestId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      loadNotifications();
      updateNotificationCount();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to cancel friend request');
    }
  } catch (error) {
    alert('Failed to cancel friend request. Please try again.');
  }
}

window.unfriendUser = async function (friendId) {
  if (!confirm('Are you sure you want to unfriend this user?')) {
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      loadFriendsList();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to unfriend user');
    }
  } catch (error) {
    alert('Failed to unfriend user. Please try again.');
  }
}

// ============================================================================
// Friend Profile Functions
// ============================================================================

let currentFriendId = null;
let accordionStates = {
  movies: false,
  tvShows: false,
  anime: false,
  videoGames: false,
  statistics: false
};
let currentFriendMovies = [];
let currentFriendTVShows = [];
let currentFriendAnime = [];
let currentFriendVideoGames = [];

window.openFriendProfile = async function (friendId) {
  currentFriendId = friendId;
  document.getElementById('friendProfileModal').style.display = 'flex';
  await loadFriendProfile(friendId);
}

window.closeFriendProfile = function () {
  document.getElementById('friendProfileModal').style.display = 'none';
  currentFriendId = null;
  currentFriendMovies = [];
  currentFriendTVShows = [];
  currentFriendAnime = [];
  currentFriendVideoGames = [];
  accordionStates = {
    movies: false,
    tvShows: false,
    anime: false,
    videoGames: false,
    statistics: false
  };
  // Reset accordion states
  ['movies', 'tvShows', 'anime', 'videoGames', 'statistics'].forEach(section => {
    const content = document.getElementById(`${section}Content`);
    const icon = document.getElementById(`${section}Icon`);
    if (content && icon) {
      content.classList.remove('active');
      icon.textContent = '▼';
    }
  });
  // Clear search inputs
  const moviesSearch = document.getElementById('friendMoviesSearch');
  const tvShowsSearch = document.getElementById('friendTVShowsSearch');
  const animeSearch = document.getElementById('friendAnimeSearch');
  const videoGamesSearch = document.getElementById('friendVideoGamesSearch');
  if (moviesSearch) moviesSearch.value = '';
  if (tvShowsSearch) tvShowsSearch.value = '';
  if (animeSearch) animeSearch.value = '';
  if (videoGamesSearch) videoGamesSearch.value = '';
}

window.loadFriendProfile = async function (friendId) {
  try {
    // Get friend data from friends list to access profile picture
    const friendsResponse = await authenticatedFetch(`${API_BASE}/friends`);
    let friendProfilePictureUrl = '/static/default-avatar.svg';

    if (friendsResponse.ok) {
      const friends = await friendsResponse.json();
      const friend = friends.find(f => f.friend.id === friendId);
      if (friend && friend.friend.profile_picture_url) {
        friendProfilePictureUrl = friend.friend.profile_picture_url;
      }
    }

    // Update friend profile picture in modal header
    const friendProfilePicture = document.getElementById('friendProfilePicture');
    if (friendProfilePicture) {
      friendProfilePicture.src = friendProfilePictureUrl;
    }

    // Get profile summary
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/profile`);
    if (response.ok) {
      const profile = await response.json();
      document.getElementById('friendProfileUsername').textContent = profile.username;

      // Update summaries
      updateMoviesSummary(profile);
      updateTVShowsSummary(profile);
      updateAnimeSummary(profile);
      updateVideoGamesSummary(profile);
      updateStatisticsSummary(profile);
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to load friend profile');
      closeFriendProfile();
    }
  } catch (error) {
    console.error('Failed to load friend profile:', error);
    alert('Failed to load friend profile');
    closeFriendProfile();
  }
}

function updateMoviesSummary(profile) {
  const summaryDiv = document.getElementById('moviesSummary');
  if (profile.movies_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their movies private</p>';
  } else {
    const count = profile.movies_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} Movie${count !== 1 ? 's' : ''}</p>`;
  }
}

function updateTVShowsSummary(profile) {
  const summaryDiv = document.getElementById('tvShowsSummary');
  if (profile.tv_shows_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their TV shows private</p>';
  } else {
    const count = profile.tv_shows_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} TV Show${count !== 1 ? 's' : ''}</p>`;
  }
}

function updateAnimeSummary(profile) {
  const summaryDiv = document.getElementById('animeSummary');
  if (profile.anime_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their anime private</p>';
  } else {
    const count = profile.anime_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} Anime</p>`;
  }
}

function updateVideoGamesSummary(profile) {
  const summaryDiv = document.getElementById('videoGamesSummary');
  if (profile.video_games_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their video games private</p>';
  } else {
    const count = profile.video_games_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} Video Game${count !== 1 ? 's' : ''}</p>`;
  }
}

function updateStatisticsSummary(profile) {
  const summaryDiv = document.getElementById('statisticsSummary');
  if (profile.statistics_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their statistics private</p>';
  } else {
    summaryDiv.innerHTML = '<p class="summary-text">Statistics Available</p>';
  }
}

window.toggleAccordion = async function (section) {
  if (!currentFriendId) return;

  const content = document.getElementById(`${section}Content`);
  const icon = document.getElementById(`${section}Icon`);
  const isActive = accordionStates[section];

  if (!isActive) {
    // Expand - load full content
    accordionStates[section] = true;
    content.classList.add('active');
    icon.textContent = '▲';

    if (section === 'movies') {
      await loadFriendMovies(currentFriendId);
    } else if (section === 'tvShows') {
      await loadFriendTVShows(currentFriendId);
    } else if (section === 'anime') {
      await loadFriendAnime(currentFriendId);
    } else if (section === 'videoGames') {
      await loadFriendVideoGames(currentFriendId);
    } else if (section === 'statistics') {
      await loadFriendStatistics(currentFriendId);
    }
  } else {
    // Collapse
    accordionStates[section] = false;
    content.classList.remove('active');
    icon.textContent = '▼';
  }
}

function renderFriendMovies(movies) {
  const containerDiv = document.getElementById('friendMoviesListContainer');

  if (movies.length === 0) {
    containerDiv.innerHTML = '<p class="empty-message">No movies found</p>';
    return;
  }

  containerDiv.innerHTML = movies.map(movie => `
    <div class="friend-item-card">
      <div class="friend-item-header">
        <h4>${escapeHtml(movie.title)}</h4>
        ${movie.rating ? `<span class="rating-badge">${movie.rating.toFixed(1)}/10</span>` : ''}
      </div>
      <div class="friend-item-details">
        <span>Director: ${escapeHtml(movie.director)}</span>
        <span>Year: ${movie.year}</span>
        ${movie.watched ? '<span class="watched-badge">Watched</span>' : '<span class="unwatched-badge">Not Watched</span>'}
      </div>
      ${movie.review ? `<p class="friend-review">${escapeHtml(movie.review)}</p>` : ''}
    </div>
  `).join('');
}

window.loadFriendMovies = async function (friendId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/movies`);
    if (response.ok) {
      const data = await response.json();
      const listDiv = document.getElementById('moviesList');

      // Store full data for filtering
      currentFriendMovies = data.movies || [];

      if (currentFriendMovies.length === 0) {
        document.getElementById('friendMoviesListContainer').innerHTML = '<p class="empty-message">No movies yet</p>';
      } else {
        renderFriendMovies(currentFriendMovies);
      }
    } else {
      const error = await response.json();
      document.getElementById('moviesList').innerHTML = `<p class="error-message">${error.detail || 'Failed to load movies'}</p>`;
    }
  } catch (error) {
    console.error('Failed to load friend movies:', error);
    document.getElementById('moviesList').innerHTML = '<p class="error-message">Failed to load movies</p>';
  }
}

window.filterFriendMovies = function () {
  const searchInput = document.getElementById('friendMoviesSearch');
  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!searchTerm) {
    renderFriendMovies(currentFriendMovies);
    return;
  }

  const filtered = currentFriendMovies.filter(movie => {
    const title = (movie.title || '').toLowerCase();
    const director = (movie.director || '').toLowerCase();
    const year = String(movie.year || '');
    const review = (movie.review || '').toLowerCase();

    return title.includes(searchTerm) ||
      director.includes(searchTerm) ||
      year.includes(searchTerm) ||
      review.includes(searchTerm);
  });

  renderFriendMovies(filtered);
}

function renderFriendTVShows(tvShows) {
  const containerDiv = document.getElementById('friendTVShowsListContainer');

  if (tvShows.length === 0) {
    containerDiv.innerHTML = '<p class="empty-message">No TV shows found</p>';
    return;
  }

  containerDiv.innerHTML = tvShows.map(show => `
    <div class="friend-item-card">
      <div class="friend-item-header">
        <h4>${escapeHtml(show.title)}</h4>
        ${show.rating ? `<span class="rating-badge">${show.rating.toFixed(1)}/10</span>` : ''}
      </div>
      <div class="friend-item-details">
        <span>Year: ${show.year}</span>
        ${show.seasons ? `<span>Seasons: ${show.seasons}</span>` : ''}
        ${show.episodes ? `<span>Episodes: ${show.episodes}</span>` : ''}
        ${show.watched ? '<span class="watched-badge">Watched</span>' : '<span class="unwatched-badge">Not Watched</span>'}
      </div>
      ${show.review ? `<p class="friend-review">${escapeHtml(show.review)}</p>` : ''}
    </div>
  `).join('');
}

window.loadFriendTVShows = async function (friendId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/tv-shows`);
    if (response.ok) {
      const data = await response.json();
      const listDiv = document.getElementById('tvShowsList');

      // Store full data for filtering
      currentFriendTVShows = data.tv_shows || [];

      if (currentFriendTVShows.length === 0) {
        document.getElementById('friendTVShowsListContainer').innerHTML = '<p class="empty-message">No TV shows yet</p>';
      } else {
        renderFriendTVShows(currentFriendTVShows);
      }
    } else {
      const error = await response.json();
      document.getElementById('tvShowsList').innerHTML = `<p class="error-message">${error.detail || 'Failed to load TV shows'}</p>`;
    }
  } catch (error) {
    console.error('Failed to load friend TV shows:', error);
    document.getElementById('tvShowsList').innerHTML = '<p class="error-message">Failed to load TV shows</p>';
  }
}

window.filterFriendTVShows = function () {
  const searchInput = document.getElementById('friendTVShowsSearch');
  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!searchTerm) {
    renderFriendTVShows(currentFriendTVShows);
    return;
  }

  const filtered = currentFriendTVShows.filter(show => {
    const title = (show.title || '').toLowerCase();
    const year = String(show.year || '');
    const review = (show.review || '').toLowerCase();
    const seasons = String(show.seasons || '');
    const episodes = String(show.episodes || '');

    return title.includes(searchTerm) ||
      year.includes(searchTerm) ||
      seasons.includes(searchTerm) ||
      episodes.includes(searchTerm) ||
      review.includes(searchTerm);
  });

  renderFriendTVShows(filtered);
}

window.loadFriendAnime = async function (friendId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/anime`);
    if (response.ok) {
      const data = await response.json();
      const listDiv = document.getElementById('animeList');

      // Store full data for filtering
      currentFriendAnime = data.anime || [];

      if (currentFriendAnime.length === 0) {
        document.getElementById('friendAnimeListContainer').innerHTML = '<p class="empty-message">No anime yet</p>';
      } else {
        renderFriendAnime(currentFriendAnime);
      }
    } else {
      const error = await response.json();
      document.getElementById('animeList').innerHTML = `<p class="error-message">${error.detail || 'Failed to load anime'}</p>`;
    }
  } catch (error) {
    console.error('Failed to load friend anime:', error);
    document.getElementById('animeList').innerHTML = '<p class="error-message">Failed to load anime</p>';
  }
}

window.renderFriendAnime = function (anime) {
  const container = document.getElementById('friendAnimeListContainer');
  if (!container) return;

  if (anime.length === 0) {
    container.innerHTML = '<p class="empty-message">No anime found</p>';
    return;
  }

  container.innerHTML = anime.map(animeItem => `
    <div class="friend-item-card">
      <div class="friend-item-header">
        <h4>${escapeHtml(animeItem.title)}</h4>
        <span class="friend-item-year">${animeItem.year}</span>
      </div>
      <div class="friend-item-details">
        ${animeItem.seasons ? `<span>Seasons: ${animeItem.seasons}</span>` : ''}
        ${animeItem.episodes ? `<span>Episodes: ${animeItem.episodes}</span>` : ''}
        ${animeItem.rating !== null && animeItem.rating !== undefined ? `<span>Rating: ${parseFloat(animeItem.rating).toFixed(1)}/10</span>` : ''}
        <span class="watched-badge ${animeItem.watched ? 'watched' : 'unwatched'}">${animeItem.watched ? 'Watched' : 'Not Watched'}</span>
      </div>
      ${animeItem.review ? `<p class="friend-item-review">${escapeHtml(animeItem.review)}</p>` : ''}
    </div>
  `).join('');
}

window.filterFriendAnime = function () {
  const searchInput = document.getElementById('friendAnimeSearch');
  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!searchTerm) {
    renderFriendAnime(currentFriendAnime);
    return;
  }

  const filtered = currentFriendAnime.filter(animeItem => {
    const title = (animeItem.title || '').toLowerCase();
    const year = String(animeItem.year || '');
    const review = (animeItem.review || '').toLowerCase();
    const seasons = String(animeItem.seasons || '');
    const episodes = String(animeItem.episodes || '');

    return title.includes(searchTerm) ||
      year.includes(searchTerm) ||
      seasons.includes(searchTerm) ||
      episodes.includes(searchTerm) ||
      review.includes(searchTerm);
  });

  renderFriendAnime(filtered);
}

window.loadFriendVideoGames = async function (friendId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/video-games`);
    if (response.ok) {
      const data = await response.json();
      const listDiv = document.getElementById('videoGamesList');

      // Store full data for filtering
      currentFriendVideoGames = data.video_games || [];

      if (currentFriendVideoGames.length === 0) {
        document.getElementById('friendVideoGamesListContainer').innerHTML = '<p class="empty-message">No video games yet</p>';
      } else {
        renderFriendVideoGames(currentFriendVideoGames);
      }
    } else {
      const error = await response.json();
      document.getElementById('videoGamesList').innerHTML = `<p class="error-message">${error.detail || 'Failed to load video games'}</p>`;
    }
  } catch (error) {
    console.error('Failed to load friend video games:', error);
    document.getElementById('videoGamesList').innerHTML = '<p class="error-message">Failed to load video games</p>';
  }
}

window.renderFriendVideoGames = function (videoGames) {
  const container = document.getElementById('friendVideoGamesListContainer');
  if (!container) return;

  if (videoGames.length === 0) {
    container.innerHTML = '<p class="empty-message">No video games found</p>';
    return;
  }

  container.innerHTML = videoGames.map(game => {
    const releaseDateStr = game.release_date ? new Date(game.release_date).toLocaleDateString() : '';
    return `
    <div class="friend-item-card">
      <div class="friend-item-header">
        <h4>${escapeHtml(game.title)}</h4>
        ${game.rating !== null && game.rating !== undefined ? `<span class="rating-badge">${parseFloat(game.rating).toFixed(1)}/10</span>` : ''}
      </div>
      <div class="friend-item-details">
        ${releaseDateStr ? `<span>Release Date: ${releaseDateStr}</span>` : ''}
        ${game.genres ? `<span>Genres: ${escapeHtml(game.genres)}</span>` : ''}
        <span class="watched-badge ${game.played ? 'watched' : 'unwatched'}">${game.played ? 'Played' : 'Not Played'}</span>
        ${game.rawg_link ? `<a href="${game.rawg_link}" target="_blank" class="rawg-link">View on RAWG</a>` : ''}
      </div>
      ${game.review ? `<p class="friend-item-review">${escapeHtml(game.review)}</p>` : ''}
    </div>
    `;
  }).join('');
}

window.filterFriendVideoGames = function () {
  const searchInput = document.getElementById('friendVideoGamesSearch');
  const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';

  if (!searchTerm) {
    renderFriendVideoGames(currentFriendVideoGames);
    return;
  }

  const filtered = currentFriendVideoGames.filter(game => {
    const title = (game.title || '').toLowerCase();
    const genres = (game.genres || '').toLowerCase();
    const releaseDate = game.release_date ? new Date(game.release_date).toLocaleDateString().toLowerCase() : '';
    const review = (game.review || '').toLowerCase();

    return title.includes(searchTerm) ||
      genres.includes(searchTerm) ||
      releaseDate.includes(searchTerm) ||
      review.includes(searchTerm);
  });

  renderFriendVideoGames(filtered);
}

window.loadFriendStatistics = async function (friendId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/statistics`);
    if (response.ok) {
      const stats = await response.json();
      const statsDiv = document.getElementById('statisticsData');

      // Compact statistics display
      statsDiv.innerHTML = `
        <div class="friend-stats-compact">
          <div class="stat-card">
            <h4>Watch Statistics</h4>
            <div class="stat-item">
              <span>Total Movies:</span>
              <span>${stats.watch_stats.total_movies}</span>
            </div>
            <div class="stat-item">
              <span>Watched Movies:</span>
              <span>${stats.watch_stats.watched_movies}</span>
            </div>
            <div class="stat-item">
              <span>Total TV Shows:</span>
              <span>${stats.watch_stats.total_tv_shows}</span>
            </div>
            <div class="stat-item">
              <span>Watched TV Shows:</span>
              <span>${stats.watch_stats.watched_tv_shows}</span>
            </div>
            <div class="stat-item">
              <span>Total Anime:</span>
              <span>${stats.watch_stats.total_anime || 0}</span>
            </div>
            <div class="stat-item">
              <span>Watched Anime:</span>
              <span>${stats.watch_stats.watched_anime || 0}</span>
            </div>
            <div class="stat-item">
              <span>Completion:</span>
              <span>${stats.watch_stats.completion_percentage.toFixed(1)}%</span>
            </div>
          </div>
          <div class="stat-card">
            <h4>Rating Statistics</h4>
            <div class="stat-item">
              <span>Average Rating:</span>
              <span>${stats.rating_stats.average_rating.toFixed(1)}/10</span>
            </div>
            <div class="stat-item">
              <span>Total Rated Items:</span>
              <span>${stats.rating_stats.total_rated_items}</span>
            </div>
          </div>
        </div>
      `;
      statsDiv.style.display = 'block';
    } else {
      const error = await response.json();
      document.getElementById('statisticsData').innerHTML = `<p class="error-message">${error.detail || 'Failed to load statistics'}</p>`;
    }
  } catch (error) {
    console.error('Failed to load friend statistics:', error);
    document.getElementById('statisticsData').innerHTML = '<p class="error-message">Failed to load statistics</p>';
  }
}

// Close friend profile modal when clicking outside
document.addEventListener('click', (e) => {
  const modal = document.getElementById('friendProfileModal');
  if (e.target === modal) {
    closeFriendProfile();
  }
});

// ============================================================================
// Notification Functions
// ============================================================================

async function loadNotifications() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications`);
    if (response.ok) {
      const notifications = await response.json();
      const notificationList = document.getElementById('notificationList');

      if (notifications.length === 0) {
        notificationList.innerHTML = '<p class="no-notifications">No notifications</p>';
        return;
      }

      notificationList.innerHTML = notifications.map(notif => {
        const date = new Date(notif.created_at);
        const timeAgo = getTimeAgo(date);
        let actionButtons = '';

        if (notif.type === 'friend_request_received' && notif.friend_request_id) {
          actionButtons = `
            <button class="notification-action-btn accept-btn" onclick="acceptFriendRequest(${notif.friend_request_id})">Accept</button>
            <button class="notification-action-btn deny-btn" onclick="denyFriendRequest(${notif.friend_request_id})">Deny</button>
          `;
        }

        return `
          <div class="notification-item ${notif.read_at ? 'read' : 'unread'}" data-notification-id="${notif.id}">
            <div class="notification-content">
              <p class="notification-message">${escapeHtml(notif.message)}</p>
              <span class="notification-time">${timeAgo}</span>
              ${actionButtons}
            </div>
            <button class="notification-dismiss" onclick="dismissNotification(${notif.id})" title="Dismiss">✕</button>
          </div>
        `;
      }).join('');
    }
  } catch (error) {
    console.error('Failed to load notifications:', error);
  }
}

async function updateNotificationCount() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications/count`);
    if (response.ok) {
      const data = await response.json();
      const notificationDot = document.getElementById('notificationDot');

      if (!notificationDot) {
        console.warn('Notification dot element not found');
        return;
      }

      if (data.count > 0) {
        notificationDot.style.display = 'flex'; // Use flex to center the number
        notificationDot.textContent = data.count > 99 ? '99+' : data.count.toString();
        console.log(`Notification count updated: ${data.count}`);
      } else {
        notificationDot.style.display = 'none';
        console.log('No unread notifications');
      }
    } else {
      console.error('Failed to get notification count:', response.status, response.statusText);
    }
  } catch (error) {
    console.error('Failed to update notification count:', error);
  }
}

window.toggleNotificationDropdown = function () {
  const dropdown = document.getElementById('notificationDropdown');
  if (dropdown.style.display === 'none' || dropdown.style.display === '') {
    dropdown.style.display = 'block';
    loadNotifications();
  } else {
    dropdown.style.display = 'none';
  }
}

window.dismissNotification = async function (notificationId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications/${notificationId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      loadNotifications();
      updateNotificationCount();
    } else {
      alert('Failed to dismiss notification');
    }
  } catch (error) {
    alert('Failed to dismiss notification. Please try again.');
  }
}

function getTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 4) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

// Initialize friends and notifications
document.addEventListener('DOMContentLoaded', function () {
  // Event delegation for edit/delete/save/cancel buttons (prevents XSS from inline handlers)
  // Movies table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-movie-btn')) {
      e.preventDefault();
      enableMovieEdit(e.target);
    } else if (e.target.classList.contains('delete-movie-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.movieId, 10);
      deleteMovie(id);
    } else if (e.target.classList.contains('save-movie-btn')) {
      e.preventDefault();
      saveMovieEdit(e.target);
    } else if (e.target.classList.contains('cancel-movie-btn')) {
      e.preventDefault();
      cancelMovieEdit();
    }
  });

  // TV Shows table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-tv-btn')) {
      e.preventDefault();
      enableTVEdit(e.target);
    } else if (e.target.classList.contains('delete-tv-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.tvId, 10);
      deleteTVShow(id);
    } else if (e.target.classList.contains('save-tv-btn')) {
      e.preventDefault();
      saveTVEdit(e.target);
    } else if (e.target.classList.contains('cancel-tv-btn')) {
      e.preventDefault();
      cancelTVEdit();
    }
  });

  // Anime table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-anime-btn')) {
      e.preventDefault();
      enableAnimeEdit(e.target);
    } else if (e.target.classList.contains('delete-anime-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.animeId, 10);
      deleteAnime(id);
    } else if (e.target.classList.contains('save-anime-btn')) {
      e.preventDefault();
      saveAnimeEdit(e.target);
    } else if (e.target.classList.contains('cancel-anime-btn')) {
      e.preventDefault();
      cancelAnimeEdit();
    }
  });

  // Video Games table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-video-game-btn')) {
      e.preventDefault();
      enableVideoGameEdit(e.target);
    } else if (e.target.classList.contains('delete-video-game-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.gameId, 10);
      deleteVideoGame(id);
    } else if (e.target.classList.contains('save-video-game-btn')) {
      e.preventDefault();
      saveVideoGameEdit(e.target);
    } else if (e.target.classList.contains('cancel-video-game-btn')) {
      e.preventDefault();
      cancelVideoGameEdit();
    }
  });

  // Set up notification bell click handler
  const notificationBell = document.getElementById('notificationBell');
  if (notificationBell) {
    notificationBell.addEventListener('click', toggleNotificationDropdown);
  }

  // Set up friend request button
  const sendFriendRequestBtn = document.getElementById('sendFriendRequestBtn');
  if (sendFriendRequestBtn) {
    sendFriendRequestBtn.addEventListener('click', openFriendRequestModal);
  }

  // Close notification dropdown when clicking outside
  document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('notificationDropdown');
    const bell = document.getElementById('notificationBell');
    if (dropdown && bell && !dropdown.contains(e.target) && !bell.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });

  // Close friend request modal when clicking outside
  document.addEventListener('click', (e) => {
    const modal = document.getElementById('friendRequestModal');
    if (e.target === modal) {
      closeFriendRequestModal();
    }
  });

  // Set up friends sidebar toggle
  const toggleFriendsSidebarBtn = document.getElementById('toggleFriendsSidebar');
  if (toggleFriendsSidebarBtn) {
    toggleFriendsSidebarBtn.addEventListener('click', toggleFriendsSidebar);
  }

  // Set up floating toggle button
  const showFriendsSidebarBtn = document.getElementById('showFriendsSidebar');
  if (showFriendsSidebarBtn) {
    showFriendsSidebarBtn.addEventListener('click', showFriendsSidebar);
  }

  // Initialize FAQ accordion functionality
  const faqQuestions = document.querySelectorAll('.faq-question');
  faqQuestions.forEach(question => {
    question.addEventListener('click', function () {
      const isExpanded = this.getAttribute('aria-expanded') === 'true';
      const answer = this.nextElementSibling;

      // Close all other FAQ items
      faqQuestions.forEach(q => {
        if (q !== this) {
          q.setAttribute('aria-expanded', 'false');
          q.nextElementSibling.style.maxHeight = '0';
          q.nextElementSibling.style.padding = '0 24px';
        }
      });

      // Toggle current item
      if (isExpanded) {
        this.setAttribute('aria-expanded', 'false');
        answer.style.maxHeight = '0';
        answer.style.padding = '0 24px';
      } else {
        this.setAttribute('aria-expanded', 'true');
        answer.style.maxHeight = answer.scrollHeight + 'px';
        answer.style.padding = '0 24px 20px 24px';
      }
    });
  });

  // Load friends list and notification count on page load (if logged in)
  if (isAuthenticated()) {
    loadFriendsList();
    updateNotificationCount();
    
    // Load tab visibility settings
    loadTabVisibility();

    // Show friends sidebar
    const friendsSidebar = document.getElementById('friendsSidebar');
    if (friendsSidebar) {
      friendsSidebar.style.display = 'block';
    }

    // Restore sidebar state from localStorage
    restoreSidebarState();

    // Set up interval to refresh notification count every 30 seconds
    notificationCountInterval = setInterval(updateNotificationCount, 30000);
  }
});

// Toggle friends sidebar visibility
window.toggleFriendsSidebar = function () {
  const sidebar = document.getElementById('friendsSidebar');
  const container = document.querySelector('.container');
  const toggleBtn = document.getElementById('toggleFriendsSidebar');
  const floatingToggleBtn = document.getElementById('showFriendsSidebar');
  const footer = document.getElementById('mainFooter');
  const notificationBell = document.getElementById('notificationBell');
  const notificationDropdown = document.getElementById('notificationDropdown');

  if (!sidebar || !container) return;

  const isHidden = sidebar.classList.contains('hidden');

  if (isHidden) {
    // Show sidebar
    sidebar.classList.remove('hidden');
    container.classList.remove('sidebar-hidden');
    if (toggleBtn) {
      toggleBtn.textContent = '◀';
      toggleBtn.title = 'Hide Friends Sidebar';
    }
    if (floatingToggleBtn) floatingToggleBtn.style.display = 'none';
    if (footer) footer.classList.remove('sidebar-hidden');
    if (notificationBell) notificationBell.style.left = '270px';
    if (notificationDropdown) notificationDropdown.classList.remove('sidebar-hidden');
  } else {
    // Hide sidebar
    sidebar.classList.add('hidden');
    container.classList.add('sidebar-hidden');
    if (toggleBtn) {
      toggleBtn.textContent = '▶';
      toggleBtn.title = 'Show Friends Sidebar';
    }
    if (floatingToggleBtn) floatingToggleBtn.style.display = 'flex';
    if (footer) footer.classList.add('sidebar-hidden');
    if (notificationBell) notificationBell.style.left = '20px';
    if (notificationDropdown) notificationDropdown.classList.add('sidebar-hidden');
  }

  // Save preference to localStorage
  localStorage.setItem('friendsSidebarHidden', !isHidden);
};

// Show sidebar from floating button
window.showFriendsSidebar = function () {
  toggleFriendsSidebar();
};

// Restore sidebar state from localStorage (called from main DOMContentLoaded)
function restoreSidebarState() {
  const sidebarHidden = localStorage.getItem('friendsSidebarHidden') === 'true';
  if (sidebarHidden && isAuthenticated()) {
    // Wait a bit for sidebar to be shown first, then hide it
    setTimeout(() => {
      const sidebar = document.getElementById('friendsSidebar');
      const container = document.querySelector('.container');
      const toggleBtn = document.getElementById('toggleFriendsSidebar');
      const floatingToggleBtn = document.getElementById('showFriendsSidebar');
      const footer = document.getElementById('mainFooter');
      const notificationBell = document.getElementById('notificationBell');
      const notificationDropdown = document.getElementById('notificationDropdown');

      if (sidebar && container) {
        sidebar.classList.add('hidden');
        container.classList.add('sidebar-hidden');
        if (toggleBtn) {
          toggleBtn.textContent = '▶';
          toggleBtn.title = 'Show Friends Sidebar';
        }
        if (floatingToggleBtn) floatingToggleBtn.style.display = 'flex';
        if (footer) footer.classList.add('sidebar-hidden');
        if (notificationBell) notificationBell.style.left = '20px';
        if (notificationDropdown) notificationDropdown.classList.add('sidebar-hidden');
      }
    }, 100);
  }
}

// Load initial data
loadMovies();

// ============================================================================
// Landing Page Enhancements: Scroll Animations and User Count
// ============================================================================

// Intersection Observer for fade-in on scroll animations
let scrollObserver = null;

function initScrollAnimations() {
  // Only initialize if landing page is visible
  const landingPage = document.getElementById('landingPage');
  if (!landingPage || landingPage.style.display !== 'block') {
    return;
  }

  // Clean up existing observer if any
  if (scrollObserver) {
    scrollObserver.disconnect();
  }

  // Create Intersection Observer
  scrollObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        // Unobserve after animation to improve performance
        scrollObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  // Observe all elements with fade-in-on-scroll class
  const fadeElements = document.querySelectorAll('.fade-in-on-scroll');
  fadeElements.forEach(el => {
    scrollObserver.observe(el);
  });
}

// Fetch and display user count
async function fetchUserCount() {
  const userCountDisplay = document.getElementById('userCountDisplay');
  if (!userCountDisplay) return;

  // Only fetch if landing page is visible
  const landingPage = document.getElementById('landingPage');
  if (!landingPage || landingPage.style.display !== 'block') {
    userCountDisplay.style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/user-count`);
    if (!response.ok) {
      throw new Error('Failed to fetch user count');
    }
    const data = await response.json();
    const count = data.count || 0;
    userCountDisplay.textContent = `${count} users tracking their media already`;
    userCountDisplay.style.display = 'block';
  } catch (error) {
    // Graceful degradation: hide the element on error
    userCountDisplay.style.display = 'none';
    console.error('Error fetching user count:', error);
  }
}

// Initialize landing page enhancements when DOM is ready
function initLandingPageEnhancements() {
  const landingPage = document.getElementById('landingPage');
  if (!landingPage) return;

  // Add fade-in-on-scroll class to feature cards and FAQ items
  const featureCards = document.querySelectorAll('.feature-card');
  featureCards.forEach(card => {
    card.classList.add('fade-in-on-scroll');
  });

  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    item.classList.add('fade-in-on-scroll');
  });

  // Initialize scroll animations
  initScrollAnimations();

  // Fetch user count
  fetchUserCount();
}

// Call on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
  initLandingPageEnhancements();
});

// Also call when landing page becomes visible (after login/logout)
// This will be called from auth.js when showing/hiding landing page
window.initLandingPageEnhancements = initLandingPageEnhancements;

// Cleanup observer on page unload
window.addEventListener('beforeunload', function() {
  if (scrollObserver) {
    scrollObserver.disconnect();
    scrollObserver = null;
  }
});

