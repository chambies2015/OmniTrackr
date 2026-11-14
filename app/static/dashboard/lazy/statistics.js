// Statistics tab: an overview of the whole library, then one format at a time.
// The numbers come from the same /statistics/ endpoints as before; this file only
// decides how they are laid out. Bar and column sizes are set through the CSSOM
// (applyStatsSizes) because the dashboard CSP blocks style attributes.

const STATS_FORMATS = [
  { category: 'movies', id: 'movies', api: 'movies', insights: 'movies', label: 'Movies', one: 'movie', many: 'movies', done: 'Watched', left: 'Not watched yet' },
  { category: 'tv-shows', id: 'tvShows', api: 'tv-shows', insights: 'tv_shows', label: 'TV shows', one: 'show', many: 'shows', done: 'Watched', left: 'Not watched yet' },
  { category: 'anime', id: 'anime', api: 'anime', insights: 'anime', label: 'Anime', one: 'anime', many: 'anime', done: 'Watched', left: 'Not watched yet' },
  { category: 'video-games', id: 'videoGames', api: 'video-games', insights: 'video_games', label: 'Games', one: 'game', many: 'games', done: 'Played', left: 'Not played yet' },
  { category: 'music', id: 'music', api: 'music', insights: 'music', label: 'Music', one: 'album', many: 'albums', done: 'Listened to', left: 'Not heard yet' },
  { category: 'books', id: 'books', api: 'books', insights: 'books', label: 'Books', one: 'book', many: 'books', done: 'Read', left: 'Not read yet' },
  { category: 'manga', id: 'manga', api: 'manga', insights: 'manga', label: 'Manga', one: 'series', many: 'series', done: 'Read', left: 'Not read yet' },
  { category: 'podcasts', id: 'podcasts', api: 'podcasts', insights: 'podcasts', label: 'Podcasts', one: 'podcast', many: 'podcasts', done: 'Listened to', left: 'Not heard yet' },
  { category: 'audiobooks', id: 'audiobooks', api: 'audiobooks', insights: 'audiobooks', label: 'Audiobooks', one: 'audiobook', many: 'audiobooks', done: 'Listened to', left: 'Not heard yet' },
];

let statsSelectedFormat = null;
let statsLibraryTotal = 0;
let statsListenersBound = false;
let statsPageRequest = 0;

function statsFormat(category) {
  return STATS_FORMATS.find(format => format.category === category) || null;
}

function statsCount(value) {
  return Number(value || 0).toLocaleString();
}

function statsPlural(count, one, many) {
  return `${statsCount(count)} ${Number(count) === 1 ? one : many}`;
}

function statsPercent(value) {
  return `${Math.round(Number(value || 0))}%`;
}

// Widths and heights arrive as data attributes and are applied here, one custom property each.
function applyStatsSizes(root) {
  if (!root) return;
  root.querySelectorAll('[data-stats-w]').forEach((element) => {
    const value = Math.max(0, Math.min(100, Number(element.dataset.statsW) || 0));
    element.style.setProperty('--w', `${value}%`);
  });
  root.querySelectorAll('[data-stats-h]').forEach((element) => {
    const value = Math.max(0, Math.min(100, Number(element.dataset.statsH) || 0));
    element.style.setProperty('--h', `${value}%`);
  });
}

function statsTile(label, value, note = '') {
  return `<div class="stats-tile"><dt>${escapeHtml(label)}</dt><dd class="stats-tile__value">${escapeHtml(String(value))}</dd>${note ? `<dd class="stats-tile__note">${escapeHtml(note)}</dd>` : ''}</div>`;
}

function statsEmpty(message) {
  return `<p class="stats-empty">${escapeHtml(message)}</p>`;
}

// One column per rating, 1 to 10. Ratings under 0.5 land in a 0 bucket, shown only when used.
function statsHistogram(distribution, many) {
  const counts = distribution || {};
  const total = Object.values(counts).reduce((sum, count) => sum + Number(count || 0), 0);
  if (!total) return statsEmpty(`No ratings yet. Rate a few ${many} and the spread shows up here.`);
  const largest = Math.max(...Object.values(counts).map(Number), 1);
  let columns = '';
  for (let rating = counts['0'] ? 0 : 1; rating <= 10; rating += 1) {
    const count = Number(counts[String(rating)] || 0);
    const sentence = `Rated ${rating}: ${statsPlural(count, 'title', 'titles')}`;
    const height = count ? Math.max(4, (count / largest) * 100).toFixed(1) : 0;
    columns += `<li class="stats-hist__col" title="${escapeHtml(sentence)}">
      <span class="stats-hist__plot" aria-hidden="true">${count ? `<span class="stats-hist__count" data-stats-h="${height}">${statsCount(count)}</span>` : ''}<span class="stats-hist__bar" data-stats-h="${height}"></span></span>
      <span class="stats-hist__label" aria-hidden="true">${rating}</span>
      <span class="sr-only">${escapeHtml(sentence)}</span>
    </li>`;
  }
  return `<ol class="stats-hist" aria-label="How many titles got each rating, lowest to highest">${columns}</ol>`;
}

// Horizontal bars with the name on the left and the count on the right.
function statsBars(rows, label) {
  if (!rows.length) return '';
  const largest = Math.max(...rows.map(row => row.count), 1);
  const items = rows.map(row => `<li class="stats-bars__row">
      <span class="stats-bars__label">${escapeHtml(String(row.name))}</span>
      <span class="stats-bars__track" aria-hidden="true"><span class="stats-bars__fill" data-stats-w="${((row.count / largest) * 100).toFixed(1)}"></span></span>
      <span class="stats-bars__value">${statsCount(row.count)}</span>
    </li>`).join('');
  return `<ol class="stats-bars" aria-label="${escapeHtml(label)}">${items}</ol>`;
}

function statsRank(rows, emptyMessage) {
  if (!rows.length) return statsEmpty(emptyMessage);
  const items = rows.map(row => `<li><span class="stats-rank__name">${escapeHtml(String(row.name ?? ''))}</span><span class="stats-rank__value">${escapeHtml(String(row.value))}${row.note ? ` <small>${escapeHtml(String(row.note))}</small>` : ''}</span></li>`).join('');
  return `<ol class="stats-rank">${items}</ol>`;
}

function statsDecadeRows(decadeStats) {
  return Object.keys(decadeStats || {}).sort().map((decade) => {
    const value = decadeStats[decade];
    const count = typeof value === 'number' ? value : Object.values(value || {}).reduce((sum, part) => sum + Number(part || 0), 0);
    return { name: decade, count };
  }).filter(row => row.count > 0);
}

function statsYearSpan(yearStats) {
  if (!yearStats || !yearStats.oldest_year || !yearStats.newest_year) return '';
  return yearStats.oldest_year === yearStats.newest_year
    ? `Everything here came out in ${yearStats.oldest_year}.`
    : `From ${yearStats.oldest_year} to ${yearStats.newest_year}.`;
}

// Titles tied at one end of the member's ratings. The overview adds the format as a note.
function statsRatedTitles(items, emptyMessage, withType = false) {
  const rows = (items || []).map(item => ({ name: item.title, value: `${parseFloat(item.rating).toFixed(1)}/10`, note: withType ? item.type : '' }));
  return statsRank(rows, emptyMessage);
}

function statsCard(title, body, extraClass = '') {
  return `<section class="stats-card${extraClass ? ` ${extraClass}` : ''}"><h4 class="stats-card__title">${escapeHtml(title)}</h4>${body}</section>`;
}

/* ---------- The page ---------- */

function bindStatsListeners() {
  if (statsListenersBound) return;
  const tab = document.getElementById('statistics-tab');
  if (!tab || typeof tab.addEventListener !== 'function') return;
  statsListenersBound = true;
  tab.addEventListener('click', (event) => {
    const formatTarget = event.target.closest('[data-stats-format]');
    if (formatTarget) {
      // The overview rows jump down to the format's panel; the tabs are already there.
      showStatsFormat(formatTarget.dataset.statsFormat, { focus: formatTarget.getAttribute('role') !== 'tab' });
      return;
    }
    const jump = event.target.closest('[data-stats-jump]');
    if (jump) jumpToStatsSection(jump.dataset.statsJump);
  });
  tab.addEventListener('keydown', (event) => {
    const current = event.target.closest('[role="tab"][data-stats-format]');
    if (!current) return;
    const tabs = Array.from(document.querySelectorAll('#statsFormatTabs [role="tab"]'));
    const index = tabs.indexOf(current);
    let next = -1;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    if (next < 0) return;
    event.preventDefault();
    showStatsFormat(tabs[next].dataset.statsFormat);
    tabs[next].focus();
  });
}

function jumpToStatsSection(id) {
  const section = document.getElementById(id);
  if (!section || !isElementShown(section)) return;
  if (!section.hasAttribute('tabindex')) section.tabIndex = -1;
  const calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  section.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' });
  section.focus({ preventScroll: true });
}

async function renderStatsPage() {
  bindStatsListeners();
  const request = ++statsPageRequest;
  const loading = document.getElementById('libraryInsightsStatsLoading');
  const container = document.getElementById('libraryInsightsStatsData');
  if (!container) return;
  if (loading && !container.children.length) loading.hidden = false;
  try {
    // Only the ratings and release years are needed next to the counts. /statistics/ would also
    // recount every shelf and rank directors, a third more database work for nothing shown.
    const [insightsResponse, ratingsResponse, yearsResponse] = await Promise.all([
      authenticatedFetch(`${API_BASE}/statistics/insights/`),
      authenticatedFetch(`${API_BASE}/statistics/ratings/`),
      authenticatedFetch(`${API_BASE}/statistics/years/`),
    ]);
    if (!insightsResponse.ok) throw new Error('Failed to load library insights');
    const stats = await insightsResponse.json();
    // The ratings and decades are a bonus on the overview; the counts stand without them.
    const overall = {
      rating_stats: ratingsResponse.ok ? await ratingsResponse.json().catch(() => null) : null,
      year_stats: yearsResponse.ok ? await yearsResponse.json().catch(() => null) : null,
    };
    if (request !== statsPageRequest) return;
    displayLibraryInsights(stats, overall);
    renderStatsFormatTabs(stats);
  } catch (error) {
    if (request !== statsPageRequest) return;
    console.error('Error loading library statistics:', error);
    container.innerHTML = '<p class="content-error" role="alert">Your statistics did not load. Check your connection and open this tab again.</p>';
  } finally {
    if (loading && request === statsPageRequest) loading.hidden = true;
  }
}

function displayLibraryInsights(stats, overall = null) {
  const container = document.getElementById('libraryInsightsStatsData');
  if (!container) return;
  const lede = document.getElementById('statsLede');
  const formatsSection = document.getElementById('statsFormats');
  const categories = Array.isArray(stats.categories) ? stats.categories : [];
  const used = categories.filter(category => category.total > 0);

  statsLibraryTotal = Number(stats.total_items) || 0;
  if (!stats.total_items) {
    if (lede) lede.textContent = 'Nothing to count yet.';
    if (formatsSection) formatsSection.hidden = true;
    container.innerHTML = `<div class="stats-blank">
      <p class="stats-blank__title">Your numbers start with the first title you save</p>
      <p>Add something you have watched, played, read or listened to. Ratings, decades and time spent fill in from there.</p>
      <button type="button" class="action-btn" data-action="open-quick-capture">Add a title</button>
    </div>`;
    return;
  }
  if (formatsSection) formatsSection.hidden = false;
  if (lede) {
    lede.textContent = `${statsPlural(stats.total_items, 'title', 'titles')} across ${statsPlural(used.length, 'format', 'formats')}. `
      + `${statsCount(stats.completed_items)} finished, ${statsCount(stats.backlog_items)} still to go.`;
  }

  const rating = overall?.rating_stats || null;
  const mostComplete = stats.most_complete_category;
  const tiles = [
    statsTile('Titles saved', statsCount(stats.total_items), stats.top_category?.total ? `Biggest shelf: ${stats.top_category.label}` : ''),
    statsTile('Finished', statsCount(stats.completed_items), `${statsPercent(stats.completion_percentage)} of your library`),
    statsTile('Still to go', statsCount(stats.backlog_items), mostComplete?.completed ? `Furthest along: ${mostComplete.label}, ${statsPercent(mostComplete.completion_percentage)}` : ''),
    statsTile('Average rating', rating && rating.total_rated_items ? Number(rating.average_rating).toFixed(1) : 'None yet', `${statsPlural(stats.rated_items, 'title', 'titles')} rated`),
    statsTile('Reviews written', statsCount(stats.reviewed_items), stats.reviewed_items ? `${statsCount(stats.public_reviews)} public` : 'Notes on a title count here'),
  ].join('');

  const largest = Math.max(...categories.map(category => category.total), 1);
  const mixRows = STATS_FORMATS.map((format) => {
    const category = categories.find(entry => entry.key === format.insights);
    if (!category || !category.total) return '';
    const share = category.total ? (category.completed / category.total) * 100 : 0;
    return `<li><button type="button" class="stats-mix__row" data-stats-format="${format.category}" data-format="${format.category}">
        <span class="stats-mix__label"><span class="stats-mix__dot" aria-hidden="true"></span>${escapeHtml(format.label)}</span>
        <span class="stats-mix__track" aria-hidden="true"><span class="stats-mix__total" data-stats-w="${Math.max(3, (category.total / largest) * 100).toFixed(1)}"><span class="stats-mix__done" data-stats-w="${share.toFixed(1)}"></span></span></span>
        <span class="stats-mix__value"><strong>${statsCount(category.completed)}</strong> of ${statsCount(category.total)}<span class="sr-only"> finished. Show ${escapeHtml(format.label)} statistics</span></span>
      </button></li>`;
  }).join('');

  const decadeRows = statsDecadeRows(overall?.year_stats?.decade_stats);
  const ratedExtremes = rating && rating.total_rated_items ? `<div class="stats-pair">
      <div><h5>Highest rated</h5>${statsRatedTitles(rating.highest_rated, 'Nothing rated yet.', true)}</div>
      <div><h5>Lowest rated</h5>${statsRatedTitles(rating.lowest_rated, 'Nothing rated yet.', true)}</div>
    </div>` : '';

  container.innerHTML = `
    <dl class="stats-tiles">${tiles}</dl>
    <div class="stats-cards stats-cards--overview">
      ${statsCard('Finished, by format', `
        <p class="stats-legend" aria-hidden="true"><span class="stats-legend__key stats-legend__key--done"></span>Finished<span class="stats-legend__key stats-legend__key--left"></span>Still to go</p>
        <ul class="stats-mix">${mixRows}</ul>
        <p class="stats-card__note">Pick a format to see its ratings and details below.</p>`, 'stats-card--mix')}
      ${statsCard('How you rate', `
        ${statsHistogram(rating?.rating_distribution, 'titles')}
        ${ratedExtremes}`, 'stats-card--stacked')}
      ${statsCard('When it came out', decadeRows.length
        ? `${statsBars(decadeRows, 'Titles in your library by release decade')}<p class="stats-card__note">${escapeHtml(statsYearSpan(overall?.year_stats))}</p>`
        : statsEmpty('No release years saved yet.'))}
    </div>`;
  applyStatsSizes(container);
}

/* ---------- One format at a time ---------- */

function renderStatsFormatTabs(stats) {
  const tablist = document.getElementById('statsFormatTabs');
  const panels = document.getElementById('statsFormatPanels');
  if (!tablist || !panels) return;
  const categories = Array.isArray(stats.categories) ? stats.categories : [];
  const totals = new Map(categories.map(category => [category.key, category.total]));
  // A format the member hid from their tabs only shows here when it still holds titles.
  const shown = STATS_FORMATS.filter((format) => {
    if (totals.get(format.insights) > 0) return true;
    const tabButton = typeof getTabButton === 'function' ? getTabButton(format.category) : null;
    return !tabButton || tabButton.style.display !== 'none';
  });
  if (!shown.length) return;

  tablist.innerHTML = shown.map(format => `<button type="button" role="tab" class="stats-tab" id="statsTab-${format.id}" data-stats-format="${format.category}" data-format="${format.category}" aria-controls="${format.id}StatsContent" aria-selected="false" tabindex="-1">
      <span class="stats-tab__dot" aria-hidden="true"></span>${escapeHtml(format.label)}<span class="stats-tab__count">${statsCount(totals.get(format.insights))}<span class="sr-only"> titles</span></span>
    </button>`).join('');

  shown.forEach((format) => {
    if (document.getElementById(`${format.id}StatsContent`)) return;
    const panel = document.createElement('div');
    panel.id = `${format.id}StatsContent`;
    panel.className = 'stats-format';
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', `statsTab-${format.id}`);
    panel.dataset.format = format.category;
    panel.tabIndex = 0;
    panel.hidden = true;
    panel.innerHTML = `<div id="${format.id}StatsLoading" class="stats-loading" role="status" hidden><span class="stats-spinner" aria-hidden="true"></span><span>Loading ${escapeHtml(format.label.toLowerCase())}…</span></div><div id="${format.id}StatsData"></div>`;
    panels.appendChild(panel);
  });
  // Panels for formats that have since been hidden and emptied go away with their tab.
  STATS_FORMATS.filter(format => !shown.includes(format)).forEach(format => document.getElementById(`${format.id}StatsContent`)?.remove());

  const keep = shown.find(format => format.category === statsSelectedFormat);
  const biggest = shown.reduce((best, format) => ((totals.get(format.insights) || 0) > (totals.get(best.insights) || 0) ? format : best), shown[0]);
  showStatsFormat((keep || biggest).category, { reload: true });
}

function showStatsFormat(category, options = {}) {
  const format = statsFormat(category);
  const tab = format && document.getElementById(`statsTab-${format.id}`);
  const panel = format && document.getElementById(`${format.id}StatsContent`);
  if (!format || !tab || !panel) return;
  statsSelectedFormat = category;
  document.querySelectorAll('#statsFormatTabs [role="tab"]').forEach((button) => {
    const selected = button === tab;
    button.setAttribute('aria-selected', selected ? 'true' : 'false');
    button.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll('#statsFormatPanels > [role="tabpanel"]').forEach((other) => { other.hidden = other !== panel; });
  if (typeof tab.scrollIntoView === 'function' && !options.reload) tab.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  if (categoryStatsCache[category] && !options.reload) displayCategoryStatistics(categoryStatsCache[category], category);
  else loadCategoryStatistics(category);
  if (options.focus) jumpToStatsSection('statsFormats');
}

async function loadCategoryStatistics(category) {
  const format = statsFormat(category);
  if (!format) return;
  const loading = document.getElementById(`${format.id}StatsLoading`);
  const dataContainer = document.getElementById(`${format.id}StatsData`);
  if (!loading || !dataContainer) return;

  try {
    if (!dataContainer.children.length) loading.hidden = false;
    const response = await authenticatedFetch(`${API_BASE}/statistics/${format.api}/`);
    if (!response.ok) throw new Error('Failed to load category statistics');
    const stats = await response.json();
    categoryStatsCache[category] = stats;
    displayCategoryStatistics(stats, category);
  } catch (error) {
    console.error(`Error loading ${category} statistics:`, error);
    dataContainer.innerHTML = `<p class="content-error" role="alert">The ${escapeHtml(format.label.toLowerCase())} numbers did not load. Pick the format again to retry.</p>`;
  } finally {
    loading.hidden = true;
  }
}

function displayCategoryStatistics(stats, category) {
  const format = statsFormat(category);
  const dataContainer = format && document.getElementById(`${format.id}StatsData`);
  if (!dataContainer) return;

  const watch = stats.watch_stats || {};
  if (!watch.total_items) {
    dataContainer.innerHTML = `<div class="stats-blank">
      <p class="stats-blank__title">No ${escapeHtml(format.many)} yet</p>
      <p>Save one and its numbers show up here.</p>
      <button type="button" class="action-btn" data-switch-tab="${format.category}">Open ${escapeHtml(format.label)}</button>
    </div>`;
    return;
  }

  const rating = stats.rating_stats || {};
  const tiles = [
    statsTile('In your library', statsCount(watch.total_items), statsLibraryTotal >= watch.total_items ? `${statsPercent((watch.total_items / statsLibraryTotal) * 100)} of everything you saved` : ''),
    statsTile(format.done, statsCount(watch.watched_items), `${statsPercent(watch.completion_percentage)} of your ${format.many}`),
    statsTile(format.left, statsCount(watch.unwatched_items), watch.unwatched_items ? '' : 'All caught up'),
    statsTile('Average rating', rating.total_rated_items ? Number(rating.average_rating).toFixed(1) : 'None yet', `${statsPlural(rating.total_rated_items, 'rating', 'ratings')}`),
  ].join('');

  const decadeRows = statsDecadeRows(stats.year_stats?.decade_stats);
  const ratingsBody = `${statsHistogram(rating.rating_distribution, format.many)}${rating.total_rated_items ? `<div class="stats-pair">
      <div><h5>Highest rated</h5>${statsRatedTitles(rating.highest_rated, 'Nothing rated yet.')}</div>
      <div><h5>Lowest rated</h5>${statsRatedTitles(rating.lowest_rated, 'Nothing rated yet.')}</div>
    </div>` : ''}`;

  let cards = statsCard('Ratings', ratingsBody);
  cards += statsCard('Release decades', decadeRows.length
    ? `${statsBars(decadeRows, `${format.label} by release decade`)}<p class="stats-card__note">${escapeHtml(statsYearSpan(stats.year_stats))}</p>`
    : statsEmpty('No release years saved yet.'));

  if (category === 'movies' && stats.director_stats) {
    const most = (stats.director_stats.top_directors || []).map(director => ({ name: director.director, value: statsPlural(director.count, 'movie', 'movies') }));
    const best = (stats.director_stats.highest_rated_directors || []).map(director => ({ name: director.director, value: `${Number(director.avg_rating).toFixed(1)}/10`, note: statsPlural(director.count, 'movie', 'movies') }));
    cards += statsCard('Directors', `<div class="stats-pair">
        <div><h5>Most movies in your library</h5>${statsRank(most, 'No directors saved yet.')}</div>
        <div><h5>Highest average rating</h5>${statsRank(best, 'Rate a few movies to rank their directors.')}</div>
      </div>`, 'stats-card--wide');
  }

  if ((category === 'tv-shows' || category === 'anime') && stats.seasons_episodes_stats) {
    const lengths = stats.seasons_episodes_stats;
    const seasons = (lengths.shows_with_most_seasons || []).map(show => ({ name: show.title, value: statsPlural(show.seasons, 'season', 'seasons') }));
    const episodes = (lengths.shows_with_most_episodes || []).map(show => ({ name: show.title, value: statsPlural(show.episodes, 'episode', 'episodes') }));
    cards += statsCard('Seasons and episodes', `<dl class="stats-tiles stats-tiles--inset">
        ${statsTile('Seasons', statsCount(lengths.total_seasons), `${Number(lengths.average_seasons).toFixed(1)} a title on average`)}
        ${statsTile('Episodes', statsCount(lengths.total_episodes), `${Number(lengths.average_episodes).toFixed(1)} a title on average`)}
      </dl>
      <div class="stats-pair">
        <div><h5>Most seasons</h5>${statsRank(seasons, 'No season counts saved yet.')}</div>
        <div><h5>Most episodes</h5>${statsRank(episodes, 'No episode counts saved yet.')}</div>
      </div>`, 'stats-card--wide');
  }

  if (category === 'manga') {
    cards += statsCard('Volumes and chapters', `<dl class="stats-tiles stats-tiles--inset">
        ${statsTile('Volumes read', statsCount(stats.volumes_read), `of ${statsCount(stats.total_volumes)} on your shelf`)}
        ${statsTile('Chapters read', statsCount(stats.chapters_read), `of ${statsCount(stats.total_chapters)} on your shelf`)}
      </dl>
      <p class="stats-card__note">Read counts come from series you marked as read.</p>`);
  }

  if (category === 'podcasts') {
    cards += statsCard('Episodes', `<dl class="stats-tiles stats-tiles--inset">
        ${statsTile('Episodes heard', statsCount(stats.episodes_listened), `of ${statsCount(stats.total_episodes)} on your shelf`)}
      </dl>
      <p class="stats-card__note">Heard counts come from shows you marked as listened to.</p>`);
  }

  if (category === 'audiobooks') {
    const hours = value => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
    cards += statsCard('Listening hours', `<dl class="stats-tiles stats-tiles--inset">
        ${statsTile('Hours finished', hours(stats.hours_listened), `of ${hours(stats.total_hours)} on your shelf`)}
      </dl>
      <p class="stats-card__note">Finished hours come from audiobooks you marked as listened to.</p>`);
  }

  if (stats.genre_stats) {
    const verb = { manga: 'read', podcasts: 'heard', audiobooks: 'heard' }[category] || 'played';
    const shelf = Object.entries(stats.genre_stats.genre_distribution || {})
      .map(([name, count]) => ({ name, count: Number(count) }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
    const finished = (stats.genre_stats.most_played_genres || []).map(genre => ({ name: genre.genre, value: statsPlural(genre.count, format.one, format.many) }));
    cards += statsCard('Genres', shelf.length ? `<div class="stats-pair stats-pair--bars">
        <div><h5>On your shelf</h5>${statsBars(shelf, `${format.label} by genre`)}</div>
        <div><h5>The ones you have ${verb}</h5>${statsRank(finished, `Nothing ${verb} yet.`)}</div>
      </div>` : statsEmpty('No genres saved yet.'), category === 'video-games' ? 'stats-card--wide' : 'stats-card--stacked');
  }

  dataContainer.innerHTML = `
    <dl class="stats-tiles stats-tiles--format">${tiles}</dl>
    <div class="stats-meter" role="img" aria-label="${escapeHtml(`${statsPercent(watch.completion_percentage)} of your ${format.many} finished`)}"><span class="stats-meter__fill" data-stats-w="${Number(watch.completion_percentage) || 0}"></span></div>
    <div class="stats-cards">${cards}</div>`;
  applyStatsSizes(dataContainer);
}
