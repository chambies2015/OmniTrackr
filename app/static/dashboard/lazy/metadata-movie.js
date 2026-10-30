async function searchMovieMetadata() {
  const titleInput = document.getElementById('movieTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    showNotice('Please enter a movie title to search.');
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
        showNotice('Movie search failed. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (data.Error) {
      showNotice('No movie matched that title. Check the spelling, or fill in the details yourself.');
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
      
      showNotice('Movie details filled in.', 'success');
    } else {
      showNotice('No movie matched that title. Check the spelling, or fill in the details yourself.');
    }
  } catch (err) {
    console.error('Error searching for movie:', err);
    showNotice('Movie search failed. Please try again.');
  } finally {
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

