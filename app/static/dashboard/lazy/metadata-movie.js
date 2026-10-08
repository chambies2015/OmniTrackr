async function searchMovieMetadata() {
  const titleInput = document.getElementById('movieTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    alert('Please enter a movie title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchMovieBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
  try {
    const proxyUrl = `${API_BASE}/api/proxy/omdb?title=${encodeURIComponent(title)}`;
    
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
        alert('Failed to search for movie. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data.Error) {
      alert(`Movie not found: ${data.Error}`);
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    if (data && data.Title) {
      titleInput.value = data.Title;
      
      if (data.Director && data.Director !== 'N/A') {
        document.getElementById('movieDirector').value = data.Director;
      }
      
      if (data.Year && data.Year !== 'N/A') {
        const year = parseInt(data.Year.split('-')[0], 10);
        if (!isNaN(year)) {
          document.getElementById('movieYear').value = year;
        }
      }
      
      if (data.Poster && data.Poster !== 'N/A') {
        titleInput.dataset.posterUrl = data.Poster;
      }
      
      alert('Movie information loaded successfully!');
    } else {
      alert('No movie information found.');
    }
  } catch (err) {
    console.error('Error searching for movie:', err);
    alert('Failed to search for movie. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

