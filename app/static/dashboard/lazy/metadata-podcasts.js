async function searchPodcastMetadata() {
  const titleInput = document.getElementById('podcastTitle');
  const title = titleInput.value.trim();
  if (!title) {
    showNotice('Please enter a podcast name to search.');
    return;
  }

  const searchBtn = document.getElementById('searchPodcastBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await cachedProxyFetch(`${API_BASE}/api/proxy/itunes-podcasts?query=${encodeURIComponent(title)}`, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      showNotice(res.status === 429 ? 'Podcast search is busy. Please try again in a minute.'
        : res.status === 504 ? 'Search request timed out. Please try again.' : 'Failed to search for podcasts. Please try again.');
      return;
    }
    const data = await res.json();
    const results = (data && data.results) || [];
    if (!results.length) {
      showNotice('No results found. Try the show name without "podcast", or fill in the details yourself.');
    } else if (results.length === 1) {
      selectPodcastResult(results[0]);
    } else {
      openPodcastSearchModal(results);
    }
  } catch (error) {
    showNotice(error.name === 'AbortError' ? 'Search request timed out. Please try again.' : 'Error searching for podcasts: ' + error.message);
  } finally {
    clearTimeout(timeoutId);
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

function openPodcastSearchModal(results) {
  const modal = document.getElementById('podcastSearchModal');
  const resultsContainer = document.getElementById('podcastSearchResults');
  if (!modal || !resultsContainer) return;
  resultsContainer.innerHTML = '';

  results.forEach((podcast) => {
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.onclick = () => {
      selectPodcastResult(podcast);
      closePodcastSearchModal();
    };
    const details = [podcast.episodes ? `${podcast.episodes} episodes` : '',
      podcast.latest_episode ? `latest ${podcast.latest_episode.slice(0, 4)}` : ''].filter(Boolean).join(' · ');
    item.innerHTML = `
      ${podcast.cover_art_url ? `<img src="${escapeHtml(podcast.cover_art_url)}" alt="${escapeHtml(podcast.title)}" data-hide-on-error="true">` : '<div class="search-result-no-cover">No Cover</div>'}
      <h4>${escapeHtml(podcast.title || 'Unknown title')}</h4>
      <p>${escapeHtml(podcast.host || 'Unknown host')}</p>
      ${details ? `<p class="search-result-meta-small">${escapeHtml(details)}</p>` : ''}
      ${podcast.genre ? `<p class="search-result-meta-primary">${escapeHtml(podcast.genre)}</p>` : ''}
    `;
    resultsContainer.appendChild(item);
  });

  modal.style.display = 'flex';
  modal.onclick = (e) => {
    if (e.target === modal) closePodcastSearchModal();
  };
}

function closePodcastSearchModal() {
  const modal = document.getElementById('podcastSearchModal');
  if (modal) modal.style.display = 'none';
}

function selectPodcastResult(podcast) {
  const titleInput = document.getElementById('podcastTitle');
  titleInput.value = podcast.title || titleInput.value;
  const fill = (id, value) => {
    const field = document.getElementById(id);
    if (field && value !== null && value !== undefined && value !== '') field.value = value;
  };
  fill('podcastHost', podcast.host);
  fill('podcastGenre', podcast.genre);
  fill('podcastEpisodes', podcast.episodes);
  if (podcast.cover_art_url) titleInput.dataset.coverArtUrl = podcast.cover_art_url;
  else delete titleInput.dataset.coverArtUrl;
}
