async function searchMusicMetadata() {
  const titleInput = document.getElementById('musicTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    showNotice('Please enter a music title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchMusicBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
  try {
    const proxyUrl = `${API_BASE}/api/proxy/itunes?query=${encodeURIComponent(title)}&entity=album`;
    
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
        showNotice('Search request timed out. Please try again.');
      } else {
        showNotice("Couldn't reach the search service. Check your connection and try again.");
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (!res.ok) {
      if (res.status === 429) {
        showNotice('Music search is busy. Please try again in a minute.');
      } else if (res.status === 503) {
        showNotice('Music search is unavailable right now. You can still fill in the details yourself.');
      } else if (res.status === 504) {
        showNotice('Search request timed out. Please try again.');
      } else {
        showNotice('Music search failed. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (!data || !data.results || data.results.length === 0) {
      showNotice('No results for that search. Try a different spelling, or fill in the details yourself.');
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const results = data.results;
    
    if (results.length === 1) {
      const album = results[0];
      selectMusicResult(album);
    } else {
      openMusicSearchModal(results);
    }
    
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  } catch (err) {
    console.error('Error searching music metadata:', err);
    showNotice('Music search failed. Please try again.');
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

function openMusicSearchModal(results) {
  const modal = document.getElementById('musicSearchModal');
  const resultsContainer = document.getElementById('musicSearchResults');
  
  if (!modal || !resultsContainer) return;
  
  resultsContainer.innerHTML = '';
  
  results.forEach((album) => {
    const coverArtUrl = album.artworkUrl100 || album.artworkUrl60 || null;
    const albumTitle = album.collectionName || album.trackName || 'Unknown Album';
    const albumArtist = album.artistName || 'Unknown Artist';
    const albumYear = album.releaseDate ? parseInt(album.releaseDate.split('-')[0]) : null;
    const albumGenre = album.primaryGenreName || '';
    
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.onclick = () => {
      selectMusicResult(album);
      closeMusicSearchModal();
    };
    
    item.innerHTML = `
      ${coverArtUrl ? `<img src="${coverArtUrl}" alt="${escapeHtml(albumTitle)}" data-hide-on-error="true">` : '<div class="search-result-no-cover">No Cover</div>'}
      <h4>${escapeHtml(albumTitle)}</h4>
      <p>${escapeHtml(albumArtist)}</p>
      ${albumYear ? `<p class="search-result-meta-small">${albumYear}</p>` : ''}
      ${albumGenre ? `<p class="search-result-meta-primary">${escapeHtml(albumGenre)}</p>` : ''}
    `;
    
    resultsContainer.appendChild(item);
  });
  
  modal.style.display = 'flex';
  
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeMusicSearchModal();
    }
  };
}

function closeMusicSearchModal() {
  const modal = document.getElementById('musicSearchModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function selectMusicResult(album) {
  const coverArtUrl = album.artworkUrl100 || album.artworkUrl60 || null;
  const albumTitle = album.collectionName || album.trackName || '';
  const albumArtist = album.artistName || '';
  const albumYear = album.releaseDate ? parseInt(album.releaseDate.split('-')[0]) : null;
  const albumGenre = album.primaryGenreName || '';
  
  document.getElementById('musicTitle').value = albumTitle;
  const titleInput = document.getElementById('musicTitle');
  if (coverArtUrl) titleInput.dataset.coverArtUrl = coverArtUrl;
  if (document.getElementById('musicArtist')) {
    document.getElementById('musicArtist').value = albumArtist;
  }
  if (albumYear && document.getElementById('musicYear')) {
    document.getElementById('musicYear').value = albumYear;
  }
  if (albumGenre && document.getElementById('musicGenre')) {
    document.getElementById('musicGenre').value = albumGenre;
  }
  
  const previewImg = document.getElementById('musicPreview');
  if (previewImg && coverArtUrl) {
    previewImg.src = coverArtUrl;
    previewImg.style.display = 'block';
  }
}

