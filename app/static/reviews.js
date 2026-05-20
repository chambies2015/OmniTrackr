let currentOffset = 0;
let hasMore = true;
let isLoading = false;
const pageSize = 20;
let infiniteObserver = null;

function updateScrollStatus(message) {
  const sentinel = document.getElementById('scrollSentinel');
  if (sentinel) sentinel.textContent = message || '';
}

function setupInfiniteScroll() {
  const sentinel = document.getElementById('scrollSentinel');
  if (!sentinel) return;
  if (infiniteObserver) {
    infiniteObserver.disconnect();
  }
  infiniteObserver = new IntersectionObserver((entries) => {
    const entry = entries[0];
    if (!entry.isIntersecting || !hasMore || isLoading) return;
    loadReviews(false);
  }, { rootMargin: '300px 0px' });
  infiniteObserver.observe(sentinel);
}

async function loadReviews(reset = true) {
  if (isLoading) return;
  if (!hasMore && !reset) return;

  const reviewsContainer = document.getElementById('reviewsContainer');
  if (!reviewsContainer) return;

  if (reset) {
    currentOffset = 0;
    hasMore = true;
    reviewsContainer.innerHTML = '<div class="loading">Loading reviews...</div>';
    updateScrollStatus('Loading reviews...');
  } else {
    updateScrollStatus('Loading more reviews...');
  }

  const categoryFilter = document.getElementById('categoryFilter');
  const category = categoryFilter ? categoryFilter.value : '';
  const url = `/api/public/reviews?category=${encodeURIComponent(category)}&limit=${pageSize}&offset=${currentOffset}`;

  try {
    isLoading = true;
    const response = await fetch(url);
    const reviews = await response.json();

    if (reset) {
      reviewsContainer.innerHTML = '';
    }

    if (reviews.length === 0 && currentOffset === 0) {
      reviewsContainer.innerHTML = '<div class="no-reviews">No reviews found. Check back later for new reviews!</div>';
      hasMore = false;
      updateScrollStatus('No reviews to display.');
      return;
    }

    if (reviews.length < pageSize) {
      hasMore = false;
    }

    reviews.forEach((review) => {
      const card = createReviewCard(review);
      reviewsContainer.appendChild(card);
    });

    updateItemListJsonLd(reviews);
    updatePageMetadata(category);
    currentOffset += reviews.length;
    updateScrollStatus(hasMore ? 'Scroll to load more reviews...' : 'You reached the end.');
  } catch (error) {
    console.error('Error loading reviews:', error);
    reviewsContainer.innerHTML = '<div class="no-reviews">Error loading reviews. Please try again later.</div>';
    hasMore = false;
    updateScrollStatus('');
  } finally {
    isLoading = false;
  }
}

function createReviewCard(review) {
  const card = document.createElement('div');
  card.className = 'review-card';
  card.tabIndex = 0;
  card.setAttribute('role', 'link');
  card.addEventListener('click', () => {
    window.location.href = `/reviews/${encodeURIComponent(review.id)}?category=${encodeURIComponent(review.category)}`;
  });
  card.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      card.click();
    }
  });

  const posterUrl = review.poster_url || review.cover_art_url || '/static/default-avatar.svg';
  const categoryLabel = review.category === 'tv_show' ? 'TV Show' :
                       review.category === 'video_game' ? 'Video Game' :
                       review.category.charAt(0).toUpperCase() + review.category.slice(1);

  let metaInfo = review.year || 'N/A';
  if (review.category === 'movie') {
    metaInfo = `${review.director || 'Unknown'} - ${review.year || 'N/A'}`;
  } else if (review.category === 'video_game') {
    metaInfo = `${review.genres || 'Various'} - ${review.release_date ? new Date(review.release_date).getFullYear() : 'N/A'}`;
  } else if (review.category === 'music') {
    metaInfo = `${review.artist || 'Unknown'} - ${review.year || 'N/A'}`;
  } else if (review.category === 'book') {
    metaInfo = `${review.author || 'Unknown'} - ${review.year || 'N/A'}`;
  } else if (review.seasons) {
    metaInfo += ` - ${review.seasons} season${review.seasons > 1 ? 's' : ''}`;
  }

  card.innerHTML = `
    <span class="review-category">${escapeHtml(categoryLabel)}</span>
    <div class="review-card-header">
      <img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(review.title)}" class="review-poster" data-fallback-src="/static/default-avatar.svg">
      <div class="review-card-title">
        <h3>${escapeHtml(review.title)}</h3>
        <p>${escapeHtml(metaInfo)}</p>
      </div>
    </div>
    <div class="review-preview">${escapeHtml(review.review)}</div>
    <div class="review-meta">
      <span>By ${escapeHtml(review.username)}</span>
      ${review.rating ? `<span class="review-rating">Rating: ${review.rating}/10</span>` : ''}
    </div>
  `;

  return card;
}

function updateItemListJsonLd(reviews) {
  const itemListElement = reviews.map((review, index) => ({
    "@type": "ListItem",
    "position": currentOffset - reviews.length + index + 1,
    "item": {
      "@type": "Review",
      "name": review.title,
      "url": `https://omnitrackr.xyz/reviews/${review.id}?category=${review.category}`,
      "author": {
        "@type": "Person",
        "name": review.username
      },
      "reviewRating": review.rating ? {
        "@type": "Rating",
        "ratingValue": review.rating,
        "bestRating": 10
      } : undefined
    }
  }));

  const collectionPage = document.querySelector('script[type="application/ld+json"]');
  if (collectionPage) {
    try {
      const data = JSON.parse(collectionPage.textContent);
      if (data.mainEntity && data.mainEntity.itemListElement) {
        data.mainEntity.itemListElement = data.mainEntity.itemListElement.concat(itemListElement);
      } else if (data.mainEntity) {
        data.mainEntity.itemListElement = itemListElement;
      }
      collectionPage.textContent = JSON.stringify(data);
    } catch (error) {
      console.error('Error updating JSON-LD:', error);
    }
  }
}

function updatePageMetadata(category) {
  if (!category) return;

  const categoryLabels = {
    movie: 'Movies',
    tv_show: 'TV Shows',
    anime: 'Anime',
    video_game: 'Video Games',
    music: 'Music',
    book: 'Books'
  };

  const categoryLabel = categoryLabels[category] || category;
  const title = `${categoryLabel} Reviews - OmniTrackr`;
  const description = `Discover thoughtful ${categoryLabel.toLowerCase()} reviews and insights from the OmniTrackr community.`;

  document.title = title;

  const metaDesc = document.querySelector('meta[name="description"]');
  if (metaDesc) {
    metaDesc.setAttribute('content', description);
  }

  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) {
    ogTitle.setAttribute('content', title);
  }

  const ogDesc = document.querySelector('meta[property="og:description"]');
  if (ogDesc) {
    ogDesc.setAttribute('content', description);
  }

  const twitterTitle = document.querySelector('meta[name="twitter:title"]');
  if (twitterTitle) {
    twitterTitle.setAttribute('content', title);
  }

  const twitterDesc = document.querySelector('meta[name="twitter:description"]');
  if (twitterDesc) {
    twitterDesc.setAttribute('content', description);
  }

  const canonicalUrl = `https://omnitrackr.xyz/reviews${category ? `?category=${encodeURIComponent(category)}` : ''}`;
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    canonical.setAttribute('href', canonicalUrl);
  }

  const ogUrl = document.querySelector('meta[property="og:url"]');
  if (ogUrl) {
    ogUrl.setAttribute('content', canonicalUrl);
  }

  const twitterUrl = document.querySelector('meta[name="twitter:url"]');
  if (twitterUrl) {
    twitterUrl.setAttribute('content', canonicalUrl);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.dataset.fallbackSrc) return;
  if (image.src.endsWith(image.dataset.fallbackSrc)) return;
  image.src = image.dataset.fallbackSrc;
}, true);

document.addEventListener('DOMContentLoaded', () => {
  const filterButton = document.getElementById('filterReviewsButton');
  if (filterButton) {
    filterButton.addEventListener('click', () => loadReviews());
  }

  const categoryFilter = document.getElementById('categoryFilter');
  if (categoryFilter) {
    categoryFilter.addEventListener('change', () => loadReviews());
  }

  setupInfiniteScroll();
  loadReviews();
});
