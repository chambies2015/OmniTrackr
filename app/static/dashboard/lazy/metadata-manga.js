async function searchMangaMetadata() {
  const titleInput = document.getElementById('mangaTitle');
  const title = titleInput.value.trim();
  if (!title) {
    alert('Please enter a manga title to search.');
    return;
  }

  const searchBtn = document.getElementById('searchMangaBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await cachedProxyFetch(`${API_BASE}/api/proxy/jikan-manga?query=${encodeURIComponent(title)}`, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) {
      alert(res.status === 429 ? 'MyAnimeList search is busy. Please try again in a minute.'
        : res.status === 504 ? 'Search request timed out. Please try again.' : 'Failed to search for manga. Please try again.');
      return;
    }
    const data = await res.json();
    const results = (data && data.results) || [];
    if (!results.length) {
      alert('No results found. Try the original or English title, or fill in the details yourself.');
    } else if (results.length === 1) {
      selectMangaResult(results[0]);
    } else {
      openMangaSearchModal(results);
    }
  } catch (error) {
    alert(error.name === 'AbortError' ? 'Search request timed out. Please try again.' : 'Error searching for manga: ' + error.message);
  } finally {
    clearTimeout(timeoutId);
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

function openMangaSearchModal(results) {
  const modal = document.getElementById('mangaSearchModal');
  const resultsContainer = document.getElementById('mangaSearchResults');
  if (!modal || !resultsContainer) return;
  resultsContainer.innerHTML = '';

  results.forEach((manga) => {
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.onclick = () => {
      selectMangaResult(manga);
      closeMangaSearchModal();
    };
    const details = [manga.type, manga.year, manga.volumes ? `${manga.volumes} vol.` : ''].filter(Boolean).join(' · ');
    item.innerHTML = `
      ${manga.cover_art_url ? `<img src="${escapeHtml(manga.cover_art_url)}" alt="${escapeHtml(manga.title)}" data-hide-on-error="true">` : '<div class="search-result-no-cover">No Cover</div>'}
      <h4>${escapeHtml(manga.title || 'Unknown title')}</h4>
      <p>${escapeHtml(manga.author || 'Unknown mangaka')}</p>
      ${details ? `<p class="search-result-meta-small">${escapeHtml(details)}</p>` : ''}
      ${manga.genre ? `<p class="search-result-meta-primary">${escapeHtml(manga.genre)}</p>` : ''}
    `;
    resultsContainer.appendChild(item);
  });

  modal.style.display = 'flex';
  modal.onclick = (e) => {
    if (e.target === modal) closeMangaSearchModal();
  };
}

function closeMangaSearchModal() {
  const modal = document.getElementById('mangaSearchModal');
  if (modal) modal.style.display = 'none';
}

function selectMangaResult(manga) {
  const titleInput = document.getElementById('mangaTitle');
  titleInput.value = manga.title || titleInput.value;
  const fill = (id, value) => {
    const field = document.getElementById(id);
    if (field && value !== null && value !== undefined && value !== '') field.value = value;
  };
  fill('mangaAuthor', manga.author);
  fill('mangaYear', manga.year);
  fill('mangaGenre', manga.genre);
  fill('mangaVolumes', manga.volumes);
  fill('mangaChapters', manga.chapters);
  if (manga.cover_art_url) titleInput.dataset.coverArtUrl = manga.cover_art_url;
  else delete titleInput.dataset.coverArtUrl;
}
