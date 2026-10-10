// Friend Profile Functions
// ============================================================================

let currentFriendId = null;
let friendProfileGeneration = 0;
function currentFriendRequest(friendId) {
  const generation = friendProfileGeneration;
  return () => currentFriendId === friendId && generation === friendProfileGeneration;
}
const FRIEND_PROFILE_SECTIONS = ['movies', 'tvShows', 'anime', 'videoGames', 'music', 'books', 'statistics'];
function freshAccordionStates() {
  return Object.fromEntries(FRIEND_PROFILE_SECTIONS.map(section => [section, false]));
}
let accordionStates = freshAccordionStates();
let currentFriendMovies = [];
let currentFriendTVShows = [];
let currentFriendAnime = [];
let currentFriendVideoGames = [];
let currentFriendMusic = [];
let currentFriendBooks = [];

// Friend list errors go in the list container so the search box survives for the next friend.
function showFriendListError(containerId, detail, fallback) {
  const container = document.getElementById(containerId);
  if (container) container.innerHTML = `<p class="error-message">${escapeHtml(detail || fallback)}</p>`;
}

window.openFriendProfile = async function (friendId) {
  closeFriendProfile();
  currentFriendId = friendId;
  document.getElementById('friendProfileUsername').textContent = 'Loading profile…';
  const picture = document.getElementById('friendProfilePicture');
  if (picture) picture.src = '/static/default-avatar.svg';
  FRIEND_PROFILE_SECTIONS.forEach(section => {
    const summary = document.getElementById(`${section}Summary`);
    if (summary) summary.textContent = 'Loading…';
  });
  document.getElementById('friendProfileModal').style.display = 'flex';
  await loadFriendProfile(friendId);
}

window.closeFriendProfile = function () {
  friendProfileGeneration++;
  document.getElementById('friendProfileModal').style.display = 'none';
  currentFriendId = null;
  currentFriendMovies = [];
  currentFriendTVShows = [];
  currentFriendAnime = [];
  currentFriendVideoGames = [];
  currentFriendMusic = [];
  currentFriendBooks = [];
  accordionStates = freshAccordionStates();
  // Reset accordion states
  FRIEND_PROFILE_SECTIONS.forEach(section => {
    const content = document.getElementById(`${section}Content`);
    const icon = document.getElementById(`${section}Icon`);
    if (content && icon) {
      content.classList.remove('active');
      icon.textContent = '▼';
    }
  });
  ['friendMoviesListContainer', 'friendTVShowsListContainer', 'friendAnimeListContainer',
    'friendVideoGamesListContainer', 'friendMusicListContainer', 'friendBooksListContainer', 'statisticsData']
    .forEach(id => { const node = document.getElementById(id); if (node) node.innerHTML = ''; });
  // Clear search inputs
  const moviesSearch = document.getElementById('friendMoviesSearch');
  const tvShowsSearch = document.getElementById('friendTVShowsSearch');
  const animeSearch = document.getElementById('friendAnimeSearch');
  const videoGamesSearch = document.getElementById('friendVideoGamesSearch');
  if (moviesSearch) moviesSearch.value = '';
  if (tvShowsSearch) tvShowsSearch.value = '';
  if (animeSearch) animeSearch.value = '';
  if (videoGamesSearch) videoGamesSearch.value = '';
  ['friendMusicSearch', 'friendBooksSearch'].forEach(id => {
    const input = document.getElementById(id);
    if (input) input.value = '';
  });
}

window.loadFriendProfile = async function (friendId) {
  const current = currentFriendRequest(friendId);
  try {
    // Get friend data from friends list to access profile picture
    const friendsResponse = await authenticatedFetch(`${API_BASE}/friends`);
    if (!current()) return;
    let friendProfilePictureUrl = '/static/default-avatar.svg';

    if (friendsResponse.ok) {
      const friends = await friendsResponse.json();
      if (!current()) return;
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
    if (!current()) return;
    if (response.ok) {
      const profile = await response.json();
      if (!current()) return;
      document.getElementById('friendProfileUsername').textContent = profile.username;

      // Update summaries
      updateMoviesSummary(profile);
      updateTVShowsSummary(profile);
      updateAnimeSummary(profile);
      updateVideoGamesSummary(profile);
      updateMusicSummary(profile);
      updateBooksSummary(profile);
      updateStatisticsSummary(profile);
    } else {
      const error = await response.json();
      if (!current()) return;
      alert(error.detail || 'Failed to load friend profile');
      closeFriendProfile();
    }
  } catch (error) {
    if (!current()) return;
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

function updateMusicSummary(profile) {
  const summaryDiv = document.getElementById('musicSummary');
  if (!summaryDiv) return;
  if (profile.music_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their music private</p>';
  } else {
    const count = profile.music_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} Album${count !== 1 ? 's' : ''}</p>`;
  }
}

function updateBooksSummary(profile) {
  const summaryDiv = document.getElementById('booksSummary');
  if (!summaryDiv) return;
  if (profile.books_private) {
    summaryDiv.innerHTML = '<p class="privacy-message">This user has made their books private</p>';
  } else {
    const count = profile.books_count || 0;
    summaryDiv.innerHTML = `<p class="summary-text">${count} Book${count !== 1 ? 's' : ''}</p>`;
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
    } else if (section === 'music') {
      await loadFriendMusic(currentFriendId);
    } else if (section === 'books') {
      await loadFriendBooks(currentFriendId);
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
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/movies`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
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
      if (!current()) return;
      showFriendListError('friendMoviesListContainer', error.detail, 'Failed to load movies');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend movies:', error);
    showFriendListError('friendMoviesListContainer', '', 'Failed to load movies');
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
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/tv-shows`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
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
      if (!current()) return;
      showFriendListError('friendTVShowsListContainer', error.detail, 'Failed to load TV shows');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend TV shows:', error);
    showFriendListError('friendTVShowsListContainer', '', 'Failed to load TV shows');
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
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/anime`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
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
      if (!current()) return;
      showFriendListError('friendAnimeListContainer', error.detail, 'Failed to load anime');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend anime:', error);
    showFriendListError('friendAnimeListContainer', '', 'Failed to load anime');
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
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/video-games`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
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
      if (!current()) return;
      showFriendListError('friendVideoGamesListContainer', error.detail, 'Failed to load video games');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend video games:', error);
    showFriendListError('friendVideoGamesListContainer', '', 'Failed to load video games');
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
        ${safeHttpUrl(game.rawg_link) ? `<a href="${escapeHtml(safeHttpUrl(game.rawg_link))}" target="_blank" rel="noopener noreferrer" class="rawg-link">View on RAWG</a>` : ''}
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

function renderFriendShelf(containerId, items, emptyText, describe) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (items.length === 0) {
    container.innerHTML = `<p class="empty-message">${escapeHtml(emptyText)}</p>`;
    return;
  }
  container.innerHTML = items.map(item => {
    const { creatorLabel, creator, doneLabel, done } = describe(item);
    const rating = item.rating !== null && item.rating !== undefined ? `<span class="rating-badge">${parseFloat(item.rating).toFixed(1)}/10</span>` : '';
    return `
    <div class="friend-item-card">
      <div class="friend-item-header">
        <h4>${escapeHtml(item.title || '')}</h4>
        ${rating}
      </div>
      <div class="friend-item-details">
        ${creator ? `<span>${creatorLabel}: ${escapeHtml(creator)}</span>` : ''}
        ${item.year ? `<span>Year: ${escapeHtml(item.year)}</span>` : ''}
        ${item.genre ? `<span>Genre: ${escapeHtml(item.genre)}</span>` : ''}
        <span class="watched-badge ${done ? 'watched' : 'unwatched'}">${done ? doneLabel : `Not ${doneLabel}`}</span>
      </div>
      ${item.review ? `<p class="friend-item-review">${escapeHtml(item.review)}</p>` : ''}
    </div>
    `;
  }).join('');
}

function filterFriendShelf(items, searchId, fields) {
  const input = document.getElementById(searchId);
  const term = input ? input.value.toLowerCase().trim() : '';
  if (!term) return items;
  return items.filter(item => fields.some(field => String(item[field] ?? '').toLowerCase().includes(term)));
}

const describeFriendAlbum = item => ({ creatorLabel: 'Artist', creator: item.artist, doneLabel: 'Listened', done: item.listened });
const describeFriendBook = item => ({ creatorLabel: 'Author', creator: item.author, doneLabel: 'Read', done: item.read });

window.loadFriendMusic = async function (friendId) {
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/music`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
      currentFriendMusic = data.music || [];
      renderFriendShelf('friendMusicListContainer', currentFriendMusic, 'No music yet', describeFriendAlbum);
    } else {
      const error = await response.json().catch(() => ({}));
      if (!current()) return;
      showFriendListError('friendMusicListContainer', error.detail, 'Failed to load music');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend music:', error);
    showFriendListError('friendMusicListContainer', '', 'Failed to load music');
  }
}

window.filterFriendMusic = function () {
  const filtered = filterFriendShelf(currentFriendMusic, 'friendMusicSearch', ['title', 'artist', 'year', 'genre', 'review']);
  renderFriendShelf('friendMusicListContainer', filtered, 'No music found', describeFriendAlbum);
}

window.loadFriendBooks = async function (friendId) {
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/books`);
    if (!current()) return;
    if (response.ok) {
      const data = await response.json();
      if (!current()) return;
      currentFriendBooks = data.books || [];
      renderFriendShelf('friendBooksListContainer', currentFriendBooks, 'No books yet', describeFriendBook);
    } else {
      const error = await response.json().catch(() => ({}));
      if (!current()) return;
      showFriendListError('friendBooksListContainer', error.detail, 'Failed to load books');
    }
  } catch (error) {
    if (!current()) return;
    console.error('Failed to load friend books:', error);
    showFriendListError('friendBooksListContainer', '', 'Failed to load books');
  }
}

window.filterFriendBooks = function () {
  const filtered = filterFriendShelf(currentFriendBooks, 'friendBooksSearch', ['title', 'author', 'year', 'genre', 'review']);
  renderFriendShelf('friendBooksListContainer', filtered, 'No books found', describeFriendBook);
}

window.loadFriendStatistics = async function (friendId) {
  const current = currentFriendRequest(friendId);
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}/statistics`);
    if (!current()) return;
    if (response.ok) {
      const stats = await response.json();
      if (!current()) return;
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
      if (!current()) return;
      document.getElementById('statisticsData').innerHTML = `<p class="error-message">${escapeHtml(error.detail || 'Failed to load statistics')}</p>`;
    }
  } catch (error) {
    if (!current()) return;
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
