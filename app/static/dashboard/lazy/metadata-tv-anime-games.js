async function searchTVShowMetadata() {
  const titleInput = document.getElementById('tvTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    showNotice('Please enter a TV show title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchTVShowBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
  try {
    const proxyUrl = `${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}&type=series`;
    
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
        showNotice('Title search is busy. Please try again in a minute.');
      } else if (res.status === 503) {
        showNotice('Title search is switched off right now. You can still fill in the details yourself.');
      } else if (res.status === 504) {
        showNotice('Search request timed out. Please try again.');
      } else {
        showNotice('TV show search failed. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data.Error) {
      showNotice('No TV show matched that title. Check the spelling, or fill in the details yourself.');
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (data && data.Title) {
      titleInput.value = data.Title;
      
      if (data.Year && data.Year !== 'N/A') {
        const year = parseInt(data.Year.split('-')[0], 10);
        if (!isNaN(year)) {
          document.getElementById('tvYear').value = year;
        }
      }
      
      if (data.totalSeasons && data.totalSeasons !== 'N/A') {
        const seasons = parseInt(data.totalSeasons, 10);
        if (!isNaN(seasons)) {
          document.getElementById('tvSeasons').value = seasons;
        }
      }
      
      if (data.Poster && data.Poster !== 'N/A') {
        titleInput.dataset.posterUrl = data.Poster;
      }
      
      showNotice('TV show details filled in.', 'success');
    } else {
      showNotice('No TV show matched that title. Check the spelling, or fill in the details yourself.');
    }
  } catch (err) {
    console.error('Error searching for TV show:', err);
    showNotice('TV show search failed. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

async function searchAnimeMetadata() {
  const titleInput = document.getElementById('animeTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    showNotice('Please enter an anime title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchAnimeBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
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
        showNotice('Anime search is busy. Please try again in a minute.');
      } else if (res.status === 504) {
        showNotice('Search request timed out. Please try again.');
      } else {
        showNotice('Anime search failed. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data && data.data && data.data.length > 0) {
      const anime = data.data[0];
      
      if (anime.title_english || anime.title) {
        titleInput.value = anime.title_english || anime.title;
      }
      
      if (anime.year) {
        document.getElementById('animeYear').value = anime.year;
      }
      
      if (anime.seasons) {
        document.getElementById('animeSeasons').value = anime.seasons;
      }
      
      if (anime.episodes) {
        document.getElementById('animeEpisodes').value = anime.episodes;
      }
      
      const posterUrl = anime.images?.jpg?.large_image_url || anime.images?.jpg?.image_url;
      if (posterUrl) {
        titleInput.dataset.posterUrl = posterUrl;
      }
      
      showNotice('Anime details filled in.', 'success');
    } else {
      showNotice('No anime matched that title. Check the spelling, or fill in the details yourself.');
    }
  } catch (err) {
    console.error('Error searching for anime:', err);
    showNotice('Anime search failed. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

async function searchVideoGameMetadata() {
  const titleInput = document.getElementById('videoGameTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    showNotice('Please enter a video game title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchVideoGameBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
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
        showNotice('Game search is busy. Please try again in a minute.');
      } else if (res.status === 503) {
        showNotice('Game search is switched off right now. You can still fill in the details yourself.');
      } else if (res.status === 504) {
        showNotice('Search request timed out. Please try again.');
      } else {
        showNotice('Game search failed. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data && data.results && data.results.length > 0) {
      const game = data.results[0];
      
      if (game.name) {
        titleInput.value = game.name;
      }
      
      if (game.genres && game.genres.length > 0) {
        document.getElementById('videoGameGenres').value = game.genres.map(g => g.name).join(', ');
      }
      
      if (game.released) {
        titleInput.dataset.releaseDate = game.released;
      }
      
      if (game.background_image) {
        titleInput.dataset.coverArtUrl = game.background_image;
      }
      
      if (game.slug) {
        titleInput.dataset.rawgLink = `https://rawg.io/games/${game.slug}`;
      }
      
      showNotice('Game details filled in.', 'success');
    } else {
      showNotice('No game matched that title. Check the spelling, or fill in the details yourself.');
    }
  } catch (err) {
    console.error('Error searching for video game:', err);
    showNotice('Game search failed. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

