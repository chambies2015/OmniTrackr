async function searchBookMetadata() {
  const titleInput = document.getElementById('bookTitle');
  const title = titleInput.value.trim();
  
  if (!title) {
    alert('Please enter a book title to search.');
    return;
  }
  
  const searchBtn = document.getElementById('searchBookBtn');
  const originalText = searchBtn.textContent;
  searchBtn.disabled = true;
  searchBtn.textContent = 'Searching...';
  
  try {
    const proxyUrl = `${API_BASE}/api/proxy/openlibrary?query=${encodeURIComponent(title)}`;
    
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
        alert('Open Library API rate limit reached. Please try again later.');
      } else if (res.status === 504) {
        alert('Search request timed out. Please try again.');
      } else {
        alert('Failed to search for book. Please try again.');
      }
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const data = await res.json();
    
    if (!data || !data.docs || data.docs.length === 0) {
      alert('No results found. Please try a different search term.');
      searchBtn.disabled = false;
      searchBtn.textContent = originalText;
      return;
    }
    
    const results = data.docs;
    
    if (results.length === 1) {
      const book = results[0];
      selectBookResult(book);
    } else {
      openBookSearchModal(results);
    }
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  } catch (error) {
    console.error('Error searching for book:', error);
    alert('Error searching for book: ' + error.message);
    searchBtn.disabled = false;
    searchBtn.textContent = originalText;
  }
}

function openBookSearchModal(results) {
  const modal = document.getElementById('bookSearchModal');
  const resultsContainer = document.getElementById('bookSearchResults');
  
  if (!modal || !resultsContainer) return;
  
  resultsContainer.innerHTML = '';
  
  results.forEach((book) => {
    const bookTitle = book.title || 'Unknown Title';
    const bookAuthor = book.author_name && book.author_name.length > 0 ? book.author_name[0] : 'Unknown Author';
    const bookYear = book.first_publish_year || (book.publish_year && book.publish_year.length > 0 ? book.publish_year[0] : null);
    const bookGenre = book.subject ? book.subject.slice(0, 2).join(', ') : '';
    const coverId = book.cover_i || (book.isbn && book.isbn.length > 0 ? book.isbn[0] : null);
    const coverArtUrl = coverId ? `https://covers.openlibrary.org/b/id/${coverId}-L.jpg` : null;
    
    const item = document.createElement('div');
    item.className = 'search-result-item';
    item.onclick = () => {
      selectBookResult(book);
      closeBookSearchModal();
    };
    
    item.innerHTML = `
      ${coverArtUrl ? `<img src="${coverArtUrl}" alt="${escapeHtml(bookTitle)}" data-hide-on-error="true">` : '<div class="search-result-no-cover">No Cover</div>'}
      <h4>${escapeHtml(bookTitle)}</h4>
      <p>${escapeHtml(bookAuthor)}</p>
      ${bookYear ? `<p class="search-result-meta-small">${bookYear}</p>` : ''}
      ${bookGenre ? `<p class="search-result-meta-primary">${escapeHtml(bookGenre)}</p>` : ''}
    `;
    
    resultsContainer.appendChild(item);
  });
  
  modal.style.display = 'flex';
  
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeBookSearchModal();
    }
  };
}

function closeBookSearchModal() {
  const modal = document.getElementById('bookSearchModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function selectBookResult(book) {
  const titleInput = document.getElementById('bookTitle');
  const bookTitle = book.title || '';
  const bookAuthor = book.author_name && book.author_name.length > 0 ? book.author_name[0] : '';
  const bookYear = book.first_publish_year || (book.publish_year && book.publish_year.length > 0 ? book.publish_year[0] : '');
  const bookGenre = book.subject ? book.subject.slice(0, 3).join(', ') : '';
  const coverId = book.cover_i || (book.isbn && book.isbn.length > 0 ? book.isbn[0] : null);
  
  titleInput.value = bookTitle;
  if (document.getElementById('bookAuthor')) {
    document.getElementById('bookAuthor').value = bookAuthor;
  }
  if (bookYear && document.getElementById('bookYear')) {
    document.getElementById('bookYear').value = bookYear;
  }
  if (bookGenre && document.getElementById('bookGenre')) {
    document.getElementById('bookGenre').value = bookGenre;
  }
  if (coverId) {
    titleInput.dataset.coverArtUrl = `https://covers.openlibrary.org/b/id/${coverId}-L.jpg`;
  }
}

