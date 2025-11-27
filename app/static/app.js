const isLocal = (location.protocol === 'file:' || location.origin === 'null' || location.origin === '');
const API_BASE = isLocal ? 'http://127.0.0.1:8000' : '';

let editingRowId = null;
let editingRowElement = null;
let currentTab = 'movies';

// Poster fetch deduplication - prevent multiple simultaneous OMDB API calls for same movie/show
const posterFetchInProgress = new Set();
const posterFetchQueue = new Map(); // title+year -> Promise

// Tab switching functionality
function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  document.querySelector(`[onclick="switchTab('${tabName}')"]`).classList.add('active');

  // Update tab content
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  document.getElementById(`${tabName}-tab`).classList.add('active');

  currentTab = tabName;

  // Load data for the active tab
  if (tabName === 'movies') {
    loadMovies();
  } else if (tabName === 'tv-shows') {
    loadTVShows();
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
            <button class="action-btn" onclick="enableMovieEdit(this, ${movie.id}, '${encodeURIComponent(movie.title)}', '${encodeURIComponent(movie.director)}', ${movie.year}, ${movie.rating ?? 'null'}, ${movie.watched}, '${movie.review ? encodeURIComponent(movie.review) : ''}')">Edit</button>
            <button class="action-btn" onclick="deleteMovie(${movie.id})">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached poster or fetch new one
        if (movie.poster_url) {
          displayMoviePoster(movie.id, movie.poster_url, movie.title);
        } else if (OMDB_API_KEY) {
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
    cell.innerHTML = `<img src="${posterUrl}" alt="${altText}" style="width: 60px; max-height: 90px; object-fit: cover; border-radius: 4px;" loading="lazy">`;
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

window.enableMovieEdit = function (btn, id, encTitle, encDirector, year, rating, watched, encReview) {
  if (editingRowId !== null) return;
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  const title = decodeURIComponent(encTitle);
  const director = decodeURIComponent(encDirector);
  const ratingVal = (rating !== null && rating !== 'null') ? rating : '';
  const review = encReview ? decodeURIComponent(encReview) : '';
  row.cells[1].innerHTML = `<input type="text" id="edit-movie-title" value="${title}">`;
  row.cells[2].innerHTML = `<input type="text" id="edit-movie-director" value="${director}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-movie-year" value="${year}">`;
  row.cells[4].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-movie-rating" value="${ratingVal}">`;
  row.cells[5].innerHTML = `<input type="checkbox" id="edit-movie-watched" ${watched ? 'checked' : ''}>`;
  row.cells[6].innerHTML = `<input type="text" id="edit-movie-review" value="${review}">`;
  row.cells[8].innerHTML = `
    <button class="action-btn" onclick="saveMovieEdit(${id})">Save</button>
    <button class="action-btn" onclick="cancelMovieEdit()">Cancel</button>
  `;
  disableOtherRowButtons(row, 'movieTable');
};

window.saveMovieEdit = async function (id) {
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
            <button class="action-btn" onclick="enableTVEdit(this, ${tvShow.id}, '${encodeURIComponent(tvShow.title)}', ${tvShow.year}, ${tvShow.seasons ?? 'null'}, ${tvShow.episodes ?? 'null'}, ${tvShow.rating ?? 'null'}, ${tvShow.watched}, '${tvShow.review ? encodeURIComponent(tvShow.review) : ''}')">Edit</button>
            <button class="action-btn" onclick="deleteTVShow(${tvShow.id})">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);

        // Display cached poster or fetch new one
        if (tvShow.poster_url) {
          displayTVPoster(tvShow.id, tvShow.poster_url, tvShow.title);
        } else if (OMDB_API_KEY) {
          fetchTVPoster(tvShow.id, tvShow.title, tvShow.year);
        }
      });
    }
  } finally {
    isLoadingTVShows = false;
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
    cell.innerHTML = `<img src="${posterUrl}" alt="${altText}" style="width: 60px; max-height: 90px; object-fit: cover; border-radius: 4px;" loading="lazy">`;
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

async function deleteTVShow(id) {
  if (!confirm('Are you sure you want to delete this TV show?')) return;
  const res = await authenticatedFetch(`${API_BASE}/tv-shows/${id}`, { method: 'DELETE' });
  if (res.ok) loadTVShows();
}

window.enableTVEdit = function (btn, id, encTitle, year, seasons, episodes, rating, watched, encReview) {
  if (editingRowId !== null) return;
  editingRowId = id;
  const row = btn.closest('tr');
  editingRowElement = row;
  const title = decodeURIComponent(encTitle);
  const ratingVal = (rating !== null && rating !== 'null') ? rating : '';
  const review = encReview ? decodeURIComponent(encReview) : '';
  row.cells[1].innerHTML = `<input type="text" id="edit-tv-title" value="${title}">`;
  row.cells[2].innerHTML = `<input type="number" id="edit-tv-year" value="${year}">`;
  row.cells[3].innerHTML = `<input type="number" id="edit-tv-seasons" value="${seasons !== 'null' ? seasons : ''}">`;
  row.cells[4].innerHTML = `<input type="number" id="edit-tv-episodes" value="${episodes !== 'null' ? episodes : ''}">`;
  row.cells[5].innerHTML = `<input type="number" min="0" max="10" step="0.1" id="edit-tv-rating" value="${ratingVal}">`;
  row.cells[6].innerHTML = `<input type="checkbox" id="edit-tv-watched" ${watched ? 'checked' : ''}>`;
  row.cells[7].innerHTML = `<input type="text" id="edit-tv-review" value="${review}">`;
  row.cells[9].innerHTML = `
    <button class="action-btn" onclick="saveTVEdit(${id})">Save</button>
    <button class="action-btn" onclick="cancelTVEdit()">Cancel</button>
  `;
  disableOtherRowButtons(row, 'tvShowTable');
};

window.saveTVEdit = async function (id) {
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

    alert(`Export successful! Exported ${data.export_metadata.total_movies} movies and ${data.export_metadata.total_tv_shows} TV shows.`);
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
    message += `TV Shows: ${result.tv_shows_created} created, ${result.tv_shows_updated} updated`;

    if (result.errors.length > 0) {
      message += `\n\nErrors:\n${result.errors.join('\n')}`;
    }

    alert(message);

    // Refresh the current tab
    if (currentTab === 'movies') {
      loadMovies();
    } else if (currentTab === 'tv-shows') {
      loadTVShows();
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
    (decadeStats[decade].movies || 0) + (decadeStats[decade].tv_shows || 0)
  );
  const maxCount = totals.length > 0 ? Math.max(...totals) : 1;

  decades.forEach((decade, index) => {
    const total = (decadeStats[decade].movies || 0) + (decadeStats[decade].tv_shows || 0);
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

// Automatic sorting and search
document.getElementById('movieSort').addEventListener('change', loadMovies);
document.getElementById('tvSort').addEventListener('change', loadTVShows);

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

// Export/Import event listeners
document.getElementById('exportMovies').addEventListener('click', exportData);
document.getElementById('exportTVShows').addEventListener('click', exportData);
document.getElementById('importMovies').addEventListener('click', () => document.getElementById('importFile').click());
document.getElementById('importTVShows').addEventListener('click', () => document.getElementById('importTVFile').click());
document.getElementById('importFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importTVFile').addEventListener('change', (e) => importData(e.target));

// Collapsible form toggle function
window.toggleCollapsible = function(formId) {
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
window.openAccountModal = async function() {
  const modal = document.getElementById('accountModal');
  modal.style.display = 'flex';
  await loadAccountInfo();
}

window.closeAccountModal = function() {
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

window.loadAccountInfo = async function() {
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

window.changeUsername = async function(event) {
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
      successEl.textContent = 'Username changed successfully!';
      successEl.style.display = 'block';
      document.getElementById('changeUsernameForm').reset();
      
      // Update user display and localStorage
      const user = getUser();
      user.username = updatedUser.username;
      saveAuthData(getToken(), user);
      updateUserDisplay();
      
      // Reload account info
      await loadAccountInfo();
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

window.changeEmail = async function(event) {
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

window.changePassword = async function(event) {
  event.preventDefault();
  const currentPassword = document.getElementById('currentPassword').value;
  const newPassword = document.getElementById('newPassword').value;
  const confirmPassword = document.getElementById('confirmNewPassword').value;
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

window.deactivateAccount = async function(event) {
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

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  const modal = document.getElementById('accountModal');
  if (e.target === modal) {
    closeAccountModal();
  }
});

// Load initial data
loadMovies();

