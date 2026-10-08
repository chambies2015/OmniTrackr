function categoryToId(category) {
  const idMap = {
    'movies': 'movies',
    'tv-shows': 'tvShows',
    'anime': 'anime',
    'video-games': 'videoGames',
    'library-insights': 'libraryInsights',
    'music': 'music',
    'books': 'books'
  };
  return idMap[category] || category;
}

function toggleCategoryAccordion(category) {
  const idPrefix = categoryToId(category);
  const contentId = `${idPrefix}StatsContent`;
  const iconId = `${idPrefix}StatsIcon`;
  const content = document.getElementById(contentId);
  const icon = document.getElementById(iconId);
  
  if (!content || !icon) {
    console.error(`Could not find elements for category ${category}: contentId=${contentId}, iconId=${iconId}`);
    return;
  }
  
  const isExpanded = isElementShown(content);
  
  if (isExpanded) {
    content.style.display = 'none';
    icon.textContent = '▶';
  } else {
    content.style.display = 'block';
    icon.textContent = '▼';
    
    if (!categoryStatsCache[category]) {
      loadCategoryStatistics(category);
    } else {
      displayCategoryStatistics(categoryStatsCache[category], category);
    }
  }
}

async function loadCategoryStatistics(category) {
  const idPrefix = categoryToId(category);
  const loadingId = `${idPrefix}StatsLoading`;
  const dataId = `${idPrefix}StatsData`;
  const loading = document.getElementById(loadingId);
  const dataContainer = document.getElementById(dataId);
  
  if (!loading || !dataContainer) {
    console.error(`Could not find elements for loading stats: loadingId=${loadingId}, dataId=${dataId}`);
    return;
  }
  
  try {
    loading.style.display = 'block';
    dataContainer.innerHTML = '';
    
    const categoryMap = {
      'movies': 'movies',
      'tv-shows': 'tv-shows',
      'anime': 'anime',
      'video-games': 'video-games',
      'library-insights': 'insights',
      'music': 'music',
      'books': 'books'
    };
    
    const endpoint = categoryMap[category];
    if (!endpoint) return;
    
    const response = await authenticatedFetch(`${API_BASE}/statistics/${endpoint}/`);
    if (!response.ok) {
      throw new Error('Failed to load category statistics');
    }
    
    const stats = await response.json();
    categoryStatsCache[category] = stats;
    displayCategoryStatistics(stats, category);
    
    loading.style.display = 'none';
  } catch (error) {
    console.error(`Error loading ${category} statistics:`, error);
    loading.style.display = 'none';
    dataContainer.innerHTML = `<p class="content-error">Error loading statistics: ${escapeHtml(error.message)}</p>`;
  }
}

function displayCategoryStatistics(stats, category) {
  if (category === 'library-insights') {
    displayLibraryInsights(stats);
    return;
  }

  const idPrefix = categoryToId(category);
  const dataContainer = document.getElementById(`${idPrefix}StatsData`);
  if (!dataContainer) {
    console.error(`Could not find data container for category ${category}: ${idPrefix}StatsData`);
    return;
  }
  
  let html = '';
  
  html += '<div class="stats-subsection">';
  const progressLabel = category === 'video-games' ? 'Play Progress' : category === 'music' ? 'Listen Progress' : category === 'books' ? 'Read Progress' : 'Watch Progress';
  html += `<h4>📈 ${progressLabel}</h4>`;
  html += '<div class="stats-grid">';
  html += `<div class="stat-card"><div class="stat-number">${stats.watch_stats.total_items}</div><div class="stat-label">Total Items</div></div>`;
  let watchedLabel = 'Watched';
  let unwatchedLabel = 'Unwatched';
  if (category === 'video-games') {
    watchedLabel = 'Played';
    unwatchedLabel = 'Unplayed';
  } else if (category === 'music') {
    watchedLabel = 'Listened';
    unwatchedLabel = 'Unlistened';
  } else if (category === 'books') {
    watchedLabel = 'Read';
    unwatchedLabel = 'Unread';
  }
  html += `<div class="stat-card"><div class="stat-number">${stats.watch_stats.watched_items}</div><div class="stat-label">${watchedLabel}</div></div>`;
  html += `<div class="stat-card"><div class="stat-number">${stats.watch_stats.unwatched_items}</div><div class="stat-label">${unwatchedLabel}</div></div>`;
  html += `<div class="stat-card"><div class="stat-number">${stats.watch_stats.completion_percentage.toFixed(1)}%</div><div class="stat-label">Completion</div></div>`;
  html += '</div>';
  html += `<div class="progress-bar"><div class="progress-fill" data-fill-width="${stats.watch_stats.completion_percentage}"></div></div>`;
  html += '</div>';
  
  html += '<div class="stats-subsection">';
  html += '<h4>⭐ Rating Analysis</h4>';
  html += '<div class="stats-grid">';
  html += `<div class="stat-card"><div class="stat-number">${stats.rating_stats.average_rating.toFixed(1)}</div><div class="stat-label">Average Rating</div></div>`;
  html += `<div class="stat-card"><div class="stat-number">${stats.rating_stats.total_rated_items}</div><div class="stat-label">Rated Items</div></div>`;
  html += '</div>';
  html += '<div class="rating-distribution"><h5>Rating Distribution</h5><div id="ratingBars' + idPrefix + '"></div></div>';
  html += '<div class="top-rated"><h5>🏆 Highest Rated</h5><div id="highestRatedList' + idPrefix + '"></div></div>';
  html += '</div>';
  
  html += '<div class="stats-subsection">';
  html += '<h4>📅 Year Analysis</h4>';
  html += '<div class="stats-grid">';
  html += `<div class="stat-card"><div class="stat-number">${stats.year_stats.oldest_year || '-'}</div><div class="stat-label">Oldest Year</div></div>`;
  html += `<div class="stat-card"><div class="stat-number">${stats.year_stats.newest_year || '-'}</div><div class="stat-label">Newest Year</div></div>`;
  html += '</div>';
  html += '<div class="decade-stats"><h5>Decade Breakdown</h5><div id="decadeBars' + idPrefix + '"></div></div>';
  html += '</div>';
  
  if (category === 'movies' && stats.director_stats) {
    html += '<div class="stats-subsection">';
    html += '<h4>🎬 Director Analysis</h4>';
    html += '<div class="director-stats">';
    html += '<div class="director-column"><h5>Most Prolific Directors</h5><div id="topDirectorsList' + idPrefix + '"></div></div>';
    html += '<div class="director-column"><h5>Highest Rated Directors</h5><div id="highestRatedDirectorsList' + idPrefix + '"></div></div>';
    html += '</div>';
    html += '</div>';
  }
  
  if ((category === 'tv-shows' || category === 'anime') && stats.seasons_episodes_stats) {
    html += '<div class="stats-subsection">';
    html += '<h4>📺 Seasons & Episodes</h4>';
    html += '<div class="stats-grid">';
    html += `<div class="stat-card"><div class="stat-number">${stats.seasons_episodes_stats.total_seasons}</div><div class="stat-label">Total Seasons</div></div>`;
    html += `<div class="stat-card"><div class="stat-number">${stats.seasons_episodes_stats.total_episodes}</div><div class="stat-label">Total Episodes</div></div>`;
    html += `<div class="stat-card"><div class="stat-number">${stats.seasons_episodes_stats.average_seasons.toFixed(1)}</div><div class="stat-label">Avg Seasons</div></div>`;
    html += `<div class="stat-card"><div class="stat-number">${stats.seasons_episodes_stats.average_episodes.toFixed(1)}</div><div class="stat-label">Avg Episodes</div></div>`;
    html += '</div>';
    html += '<div class="stats-grid-two">';
    html += '<div><h5>Most Seasons</h5><div id="mostSeasonsList' + idPrefix + '"></div></div>';
    html += '<div><h5>Most Episodes</h5><div id="mostEpisodesList' + idPrefix + '"></div></div>';
    html += '</div>';
    html += '</div>';
  }
  
  if (category === 'video-games' && stats.genre_stats) {
    html += '<div class="stats-subsection">';
    html += '<h4>🎮 Genre Analysis</h4>';
    html += '<div class="genre-stats"><h5>Genre Distribution</h5><div id="genreBars' + idPrefix + '"></div></div>';
    html += '<div class="stats-grid-two">';
    html += '<div><h5>Top Genres</h5><div id="topGenresList' + idPrefix + '"></div></div>';
    html += '<div><h5>Most Played Genres</h5><div id="mostPlayedGenresList' + idPrefix + '"></div></div>';
    html += '</div>';
    html += '</div>';
  }
  
  dataContainer.innerHTML = html;
  applyDataFillWidths(dataContainer);
  
  displayCategoryRatingDistribution(stats.rating_stats.rating_distribution, idPrefix);
  displayCategoryHighestRated(stats.rating_stats.highest_rated, idPrefix);
  displayCategoryDecadeStats(stats.year_stats.decade_stats, idPrefix);
  
  if (category === 'movies' && stats.director_stats) {
    displayCategoryTopDirectors(stats.director_stats.top_directors, idPrefix);
    displayCategoryHighestRatedDirectors(stats.director_stats.highest_rated_directors, idPrefix);
  }
  
  if ((category === 'tv-shows' || category === 'anime') && stats.seasons_episodes_stats) {
    displaySeasonsEpisodesStats(stats.seasons_episodes_stats, idPrefix);
  }
  
  if (category === 'video-games' && stats.genre_stats) {
    displayGenreStats(stats.genre_stats, idPrefix);
  }
}

function displayLibraryInsights(stats) {
  const container = document.getElementById('libraryInsightsStatsData');
  if (!container) return;

  const topCategory = stats.top_category?.label || 'None yet';
  const mostComplete = stats.most_complete_category?.label || 'None yet';
  const publicReviewText = stats.public_reviews === 1 ? '1 public review' : `${stats.public_reviews} public reviews`;
  const categoryRows = (stats.categories || []).map((category) => `
    <div class="rated-item">
      <div class="rated-item-title">${escapeHtml(category.label)}</div>
      <div class="rated-item-rating">${category.completed}/${category.total} complete (${Number(category.completion_percentage).toFixed(1)}%)</div>
    </div>
  `).join('');

  container.innerHTML = `
    <div class="stats-subsection">
      <h4>Library Snapshot</h4>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-number">${stats.total_items}</div><div class="stat-label">Total Items</div></div>
        <div class="stat-card"><div class="stat-number">${stats.backlog_items}</div><div class="stat-label">Backlog Items</div></div>
        <div class="stat-card"><div class="stat-number">${Number(stats.completion_percentage).toFixed(1)}%</div><div class="stat-label">Complete</div></div>
        <div class="stat-card"><div class="stat-number">${Number(stats.rating_coverage_percentage).toFixed(1)}%</div><div class="stat-label">Rated</div></div>
      </div>
      <div class="progress-bar"><div class="progress-fill" data-fill-width="${stats.completion_percentage}"></div></div>
    </div>
    <div class="stats-subsection">
      <h4>Quality Signals</h4>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-number">${stats.reviewed_items}</div><div class="stat-label">Written Reviews</div></div>
        <div class="stat-card"><div class="stat-number">${stats.public_reviews}</div><div class="stat-label">Public Reviews</div></div>
        <div class="stat-card"><div class="stat-number">${Number(stats.review_coverage_percentage).toFixed(1)}%</div><div class="stat-label">Review Coverage</div></div>
        <div class="stat-card"><div class="stat-number">${stats.rated_items}</div><div class="stat-label">Rated Items</div></div>
      </div>
      <p class="content-muted">Your largest category is ${escapeHtml(topCategory)}. Your most complete category is ${escapeHtml(mostComplete)}. You currently have ${escapeHtml(publicReviewText)}.</p>
    </div>
    <div class="stats-subsection">
      <h4>Category Progress</h4>
      <div>${categoryRows || '<p class="content-muted">Add items to start building category insights.</p>'}</div>
    </div>
  `;
  applyDataFillWidths(container);
}

function displayCategoryRatingDistribution(distribution, idPrefix) {
  const container = document.getElementById(`ratingBars${idPrefix}`);
  if (!container) return;
  container.innerHTML = '';
  
  const counts = Object.values(distribution).map(Number);
  const maxCount = counts.length > 0 ? Math.max(...counts) : 1;
  
  for (let rating = 1; rating <= 10; rating++) {
    const count = distribution[rating.toString()] || 0;
    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
    
    const barDiv = document.createElement('div');
    barDiv.className = 'rating-bar';
    barDiv.innerHTML = `
      <div class="rating-bar-label">${rating}</div>
      <div class="bar-track-flex">
        <div class="rating-bar-fill bar-fill-absolute" data-fill-width="${percentage}"></div>
      </div>
      <div class="rating-bar-count">${count}</div>
    `;
    applyDataFillWidths(barDiv);
    container.appendChild(barDiv);
  }
}

function displayCategoryHighestRated(items, idPrefix) {
  const container = document.getElementById(`highestRatedList${idPrefix}`);
  if (!container) return;
  container.innerHTML = '';
  
  if (items.length === 0) {
    container.innerHTML = '<p class="content-muted">No rated items found.</p>';
    return;
  }
  
  items.forEach((item) => {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'rated-item';
    itemDiv.innerHTML = `
      <div class="rated-item-title">${escapeHtml(item.title ?? '')}</div>
      <div class="rated-item-rating">${parseFloat(item.rating).toFixed(1)}/10</div>
    `;
    container.appendChild(itemDiv);
  });
}

function displayCategoryDecadeStats(decadeStats, idPrefix) {
  const container = document.getElementById(`decadeBars${idPrefix}`);
  if (!container) return;
  container.innerHTML = '';
  
  const decades = Object.keys(decadeStats).sort();
  const totals = decades.map(decade => {
    const val = decadeStats[decade];
    return typeof val === 'number' ? val : (val.movies || 0) + (val.tv_shows || 0) + (val.anime || 0) + (val.video_games || 0);
  });
  const maxCount = totals.length > 0 ? Math.max(...totals) : 1;
  
  decades.forEach((decade) => {
    const val = decadeStats[decade];
    const total = typeof val === 'number' ? val : (val.movies || 0) + (val.tv_shows || 0) + (val.anime || 0) + (val.video_games || 0);
    const percentage = maxCount > 0 ? (total / maxCount) * 100 : 0;
    
    const barDiv = document.createElement('div');
    barDiv.className = 'decade-bar';
    barDiv.innerHTML = `
      <div class="decade-bar-label">${decade}</div>
      <div class="bar-track-flex">
        <div class="decade-bar-fill bar-fill-absolute" data-fill-width="${percentage}"></div>
      </div>
      <div class="decade-bar-count">${total}</div>
    `;
    applyDataFillWidths(barDiv);
    container.appendChild(barDiv);
  });
}

function displayCategoryTopDirectors(directors, idPrefix) {
  const container = document.getElementById(`topDirectorsList${idPrefix}`);
  if (!container) return;
  container.innerHTML = '';
  
  if (directors.length === 0) {
    container.innerHTML = '<p class="content-muted">No directors found.</p>';
    return;
  }
  
  directors.forEach((director) => {
    const directorDiv = document.createElement('div');
    directorDiv.className = 'director-item';
    directorDiv.innerHTML = `
      <div class="director-name">${escapeHtml(director.director ?? '')}</div>
      <div class="director-rating">${director.count} ${director.count === 1 ? 'movie' : 'movies'}</div>
    `;
    container.appendChild(directorDiv);
  });
}

function displayCategoryHighestRatedDirectors(directors, idPrefix) {
  const container = document.getElementById(`highestRatedDirectorsList${idPrefix}`);
  if (!container) return;
  container.innerHTML = '';
  
  if (directors.length === 0) {
    container.innerHTML = '<p class="content-muted">No rated directors found.</p>';
    return;
  }
  
  directors.forEach((director) => {
    const directorDiv = document.createElement('div');
    directorDiv.className = 'director-item';
    directorDiv.innerHTML = `
      <div class="director-name">${escapeHtml(director.director ?? '')}</div>
      <div class="director-rating">${director.avg_rating.toFixed(1)}/10 <span class="director-count-muted">(${director.count} ${director.count === 1 ? 'movie' : 'movies'})</span></div>
    `;
    container.appendChild(directorDiv);
  });
}

function displaySeasonsEpisodesStats(stats, idPrefix) {
  const mostSeasonsContainer = document.getElementById(`mostSeasonsList${idPrefix}`);
  const mostEpisodesContainer = document.getElementById(`mostEpisodesList${idPrefix}`);
  
  if (mostSeasonsContainer) {
    mostSeasonsContainer.innerHTML = '';
    if (stats.shows_with_most_seasons.length === 0) {
      mostSeasonsContainer.innerHTML = '<p class="content-muted-compact">No data available.</p>';
    } else {
      stats.shows_with_most_seasons.forEach((show) => {
        const showDiv = document.createElement('div');
        showDiv.className = 'rated-item';
        showDiv.innerHTML = `
          <div class="rated-item-title">${escapeHtml(show.title ?? '')}</div>
          <div class="rated-item-rating">${show.seasons} ${show.seasons === 1 ? 'season' : 'seasons'}</div>
        `;
        mostSeasonsContainer.appendChild(showDiv);
      });
    }
  }
  
  if (mostEpisodesContainer) {
    mostEpisodesContainer.innerHTML = '';
    if (stats.shows_with_most_episodes.length === 0) {
      mostEpisodesContainer.innerHTML = '<p class="content-muted-compact">No data available.</p>';
    } else {
      stats.shows_with_most_episodes.forEach((show) => {
        const showDiv = document.createElement('div');
        showDiv.className = 'rated-item';
        showDiv.innerHTML = `
          <div class="rated-item-title">${escapeHtml(show.title ?? '')}</div>
          <div class="rated-item-rating">${show.episodes} ${show.episodes === 1 ? 'episode' : 'episodes'}</div>
        `;
        mostEpisodesContainer.appendChild(showDiv);
      });
    }
  }
}

function displayGenreStats(stats, idPrefix) {
  const genreBarsContainer = document.getElementById(`genreBars${idPrefix}`);
  const topGenresContainer = document.getElementById(`topGenresList${idPrefix}`);
  const mostPlayedContainer = document.getElementById(`mostPlayedGenresList${idPrefix}`);
  
  if (genreBarsContainer) {
    genreBarsContainer.innerHTML = '';
    const genres = Object.keys(stats.genre_distribution);
    const counts = Object.values(stats.genre_distribution).map(Number);
    const maxCount = counts.length > 0 ? Math.max(...counts) : 1;
    
    genres.sort((a, b) => stats.genre_distribution[b] - stats.genre_distribution[a]).slice(0, 10).forEach((genre) => {
      const count = stats.genre_distribution[genre];
      const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
      
      const barDiv = document.createElement('div');
      barDiv.className = 'rating-bar';
      barDiv.innerHTML = `
        <div class="rating-bar-label">${escapeHtml(genre)}</div>
        <div class="bar-track-flex">
          <div class="rating-bar-fill bar-fill-absolute" data-fill-width="${percentage}"></div>
        </div>
        <div class="rating-bar-count">${count}</div>
      `;
      applyDataFillWidths(barDiv);
      genreBarsContainer.appendChild(barDiv);
    });
  }
  
  if (topGenresContainer) {
    topGenresContainer.innerHTML = '';
    if (stats.top_genres.length === 0) {
      topGenresContainer.innerHTML = '<p class="content-muted-compact">No genres found.</p>';
    } else {
      stats.top_genres.forEach((genre) => {
        const genreDiv = document.createElement('div');
        genreDiv.className = 'rated-item';
        genreDiv.innerHTML = `
          <div class="rated-item-title">${escapeHtml(genre.genre ?? '')}</div>
          <div class="rated-item-rating">${genre.count} ${genre.count === 1 ? 'game' : 'games'}</div>
        `;
        topGenresContainer.appendChild(genreDiv);
      });
    }
  }
  
  if (mostPlayedContainer) {
    mostPlayedContainer.innerHTML = '';
    if (stats.most_played_genres.length === 0) {
      mostPlayedContainer.innerHTML = '<p class="content-muted-compact">No played genres found.</p>';
    } else {
      stats.most_played_genres.forEach((genre) => {
        const genreDiv = document.createElement('div');
        genreDiv.className = 'rated-item';
        genreDiv.innerHTML = `
          <div class="rated-item-title">${escapeHtml(genre.genre ?? '')}</div>
          <div class="rated-item-rating">${genre.count} ${genre.count === 1 ? 'game' : 'games'}</div>
        `;
        mostPlayedContainer.appendChild(genreDiv);
      });
    }
  }
}

