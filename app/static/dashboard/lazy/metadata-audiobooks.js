async function searchAudiobookMetadata() {
  const titleInput = document.getElementById('audiobookTitle');
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter an audiobook title or author to search.');
    return;
  }

  const searchBtn = document.getElementById('searchAudiobookBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await cachedProxyFetch(`${API_BASE}/api/proxy/itunes-audiobooks?query=${encodeURIComponent(title)}`, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      alert(res.status === 429 ? 'Audiobook search is busy. Please try again in a minute.'
        : res.status === 504 ? 'Search request timed out. Please try again.' : 'Failed to search for audiobooks. Please try again.');
      return;
    }
    const data = await res.json();
    const results = (data && data.results) || [];
    if (!results.length) {
      alert('No results found. Try just the title, or fill in the details yourself.');
    } else if (results.length === 1) {
      selectAudiobookResult(results[0]);
    } else {
      openAudiobookSearchModal(results);
    }
  } catch (error) {
    alert(error.name === 'AbortError' ? 'Search request timed out. Please try again.' : 'Error searching for audiobooks: ' + error.message);
  } finally {
    clearTimeout(timeoutId);
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

function openAudiobookSearchModal(results) {
  const modal = document.getElementById('audiobookSearchModal');
  const resultsContainer = document.getElementById('audiobookSearchResults');
  if (!modal || !resultsContainer) return;
  resultsContainer.innerHTML = '';

  results.forEach((audiobook) => {
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.onclick = () => {
      selectAudiobookResult(audiobook);
      closeAudiobookSearchModal();
    };
    item.innerHTML = `
      ${audiobook.cover_art_url ? `<img src="${escapeHtml(audiobook.cover_art_url)}" alt="${escapeHtml(audiobook.title)}" data-hide-on-error="true">` : '<div class="search-result-no-cover">No Cover</div>'}
      <h4>${escapeHtml(audiobook.title || 'Unknown title')}</h4>
      <p>${escapeHtml(audiobook.author || 'Unknown author')}</p>
      ${audiobook.year ? `<p class="search-result-meta-small">${escapeHtml(audiobook.year)}</p>` : ''}
      ${audiobook.genre ? `<p class="search-result-meta-primary">${escapeHtml(audiobook.genre)}</p>` : ''}
    `;
    resultsContainer.appendChild(item);
  });

  modal.style.display = 'flex';
  modal.onclick = (e) => {
    if (e.target === modal) closeAudiobookSearchModal();
  };
}

function closeAudiobookSearchModal() {
  const modal = document.getElementById('audiobookSearchModal');
  if (modal) modal.style.display = 'none';
}

function selectAudiobookResult(audiobook) {
  const titleInput = document.getElementById('audiobookTitle');
  titleInput.value = audiobook.title || titleInput.value;
  const fill = (id, value) => {
    const field = document.getElementById(id);
    if (field && value !== null && value !== undefined && value !== '') field.value = value;
  };
  fill('audiobookAuthor', audiobook.author);
  fill('audiobookYear', audiobook.year);
  fill('audiobookGenre', audiobook.genre);
  if (audiobook.cover_art_url) titleInput.dataset.coverArtUrl = audiobook.cover_art_url;
  else delete titleInput.dataset.coverArtUrl;
  // Apple doesn't list narrators or runtimes, so point the member at those two.
  const narrator = document.getElementById('audiobookNarrator');
  if (narrator && !narrator.value) narrator.focus();
}
