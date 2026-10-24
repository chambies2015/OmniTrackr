async function searchTVShowMetadata() {
  const titleInput = document.getElementById('tvTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    alert('Please enter a TV show title to search.');
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
        alert('Search request timed out. Please try again.');
      } else {
        alert('Network error: ' + fetchError.message);
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (!res.ok) {
      if (res.status === 429) {
        alert('OMDB API rate limit reached. Please try again later.');
      } else if (res.status === 503) {
        alert('OMDB API not configured on server.');
      } else if (res.status === 504) {
        alert('Search request timed out. Please try again.');
      } else {
        alert('Failed to search for TV show. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data.Error) {
      alert(`TV show not found: ${data.Error}`);
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
      
      alert('TV show information loaded successfully!');
    } else {
      alert('No TV show information found.');
    }
  } catch (err) {
    console.error('Error searching for TV show:', err);
    alert('Failed to search for TV show. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

async function searchAnimeMetadata() {
  const titleInput = document.getElementById('animeTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    alert('Please enter an anime title to search.');
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
        alert('Search request timed out. Please try again.');
      } else {
        alert('Network error: ' + fetchError.message);
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (!res.ok) {
      if (res.status === 429) {
        alert('Jikan API rate limit reached. Please try again later.');
      } else if (res.status === 504) {
        alert('Search request timed out. Please try again.');
      } else {
        alert('Failed to search for anime. Please try again.');
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
      
      alert('Anime information loaded successfully!');
    } else {
      alert('No anime information found.');
    }
  } catch (err) {
    console.error('Error searching for anime:', err);
    alert('Failed to search for anime. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

async function searchVideoGameMetadata() {
  const titleInput = document.getElementById('videoGameTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    alert('Please enter a video game title to search.');
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
        alert('Search request timed out. Please try again.');
      } else {
        alert('Network error: ' + fetchError.message);
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (!res.ok) {
      if (res.status === 429) {
        alert('RAWG API rate limit reached. Please try again later.');
      } else if (res.status === 503) {
        alert('RAWG API not configured on server.');
      } else if (res.status === 504) {
        alert('Search request timed out. Please try again.');
      } else {
        alert('Failed to search for video game. Please try again.');
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
      
      alert('Video game information loaded successfully!');
    } else {
      alert('No video game information found.');
    }
  } catch (err) {
    console.error('Error searching for video game:', err);
    alert('Failed to search for video game. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

