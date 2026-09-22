const REVIEW_CATEGORIES = {
  movie: 'Movies', tv_show: 'TV Shows', anime: 'Anime',
  video_game: 'Video Games', music: 'Music', book: 'Books',
};
const REVIEW_PAGE_SIZE = 20;
let reviewFeed = null;
let reviewRequest = null;
let reviewGeneration = 0;
let failedReviewRequest = null;

function reviewFilters() {
  const category = document.getElementById('categoryFilter').value;
  return {
    category: Object.hasOwn(REVIEW_CATEGORIES, category) ? category : '',
    q: document.getElementById('reviewSearch').value.trim().slice(0, 100),
  };
}

function describeReviewFilters(filters) {
  const category = REVIEW_CATEGORIES[filters.category] || 'all media';
  return filters.q ? `${category} matching “${filters.q}”` : category;
}

function updateReviewControls(message) {
  const status = document.getElementById('reviewFeedStatus');
  const more = document.getElementById('loadMoreReviews');
  const retry = document.getElementById('retryReviews');
  const busy = Boolean(reviewRequest);
  document.getElementById('reviewsContainer').setAttribute('aria-busy', String(busy));
  status.textContent = message || '';
  more.hidden = !reviewFeed.hasMore || Boolean(failedReviewRequest);
  more.disabled = busy;
  more.textContent = busy && !reviewRequest.reset ? 'Loading more…' : 'Load more reviews';
  retry.hidden = !failedReviewRequest;
  retry.disabled = busy;
}

function clearReplacedReviewSchema() {
  // The document's canonical, robots policy, and other server metadata stay intact.
  // An in-page filter must not leave structured reviews for cards it has replaced.
  document.querySelectorAll('script[type="application/ld+json"]').forEach((script) => {
    try {
      const data = JSON.parse(script.textContent);
      if (data['@type'] === 'CollectionPage' && data.mainEntity?.['@type'] === 'ItemList') {
        data.mainEntity.itemListElement = [];
        data.mainEntity.numberOfItems = 0;
        script.textContent = JSON.stringify(data);
      }
    } catch (_) { /* Leave unrelated or unrecognized server metadata alone. */ }
  });
}

async function loadReviews(reset = true, retryFilters = null) {
  if (!reviewFeed || (!reset && (reviewRequest || !reviewFeed.hasMore))) return;
  const filters = retryFilters || (reset ? reviewFilters() : reviewFeed.filters);
  const offset = reset ? 0 : reviewFeed.offset;
  if (reviewRequest) reviewRequest.controller.abort();
  const request = { generation: ++reviewGeneration, controller: new AbortController(), reset, filters, offset };
  reviewRequest = request;
  failedReviewRequest = null;
  updateReviewControls(`${reset ? 'Finding' : 'Loading more'} reviews for ${describeReviewFilters(filters)}…`);

  let onAbort;
  try {
    const params = new URLSearchParams({ category: filters.category, q: filters.q, limit: REVIEW_PAGE_SIZE, offset });
    const responseWork = (async () => {
      const response = await fetch(`/api/public/review-feed?${params}`, { signal: request.controller.signal });
      if (!response.ok) throw new Error('Reviews could not be loaded.');
      return response.json();
    })();
    const payload = await Promise.race([
      responseWork,
      new Promise((_, reject) => {
        onAbort = () => reject(new Error('The request was cancelled.'));
        request.controller.signal.addEventListener('abort', onAbort, { once: true });
      }),
      new Promise((_, reject) => {
        request.timeout = setTimeout(() => {
          request.controller.abort();
          reject(new Error('The request took too long.'));
        }, 15000);
      }),
    ]);
    if (request.generation !== reviewGeneration || request.controller.signal.aborted) return;
    if (!Array.isArray(payload.reviews) || typeof payload.has_more !== 'boolean'
        || !Number.isSafeInteger(payload.next_offset) || payload.next_offset < offset
        || (payload.has_more && payload.next_offset <= offset)) {
      throw new Error('The review response was incomplete.');
    }
    const container = document.getElementById('reviewsContainer');
    // Build offscreen first, so an invalid response cannot remove usable cards.
    const keys = reset ? new Set() : new Set(reviewFeed.keys);
    const cards = [];
    payload.reviews.forEach((review) => {
      if (!review || !Object.hasOwn(REVIEW_CATEGORIES, review.category)
          || !Number.isSafeInteger(review.id) || review.id < 1 || typeof review.title !== 'string'
          || typeof review.review !== 'string') throw new Error('A review was incomplete.');
      const key = `${review.category}:${review.id}`;
      if (keys.has(key)) return;
      keys.add(key);
      cards.push(createReviewCard(review));
    });
    if (reset) {
      container.replaceChildren();
      clearReplacedReviewSchema();
    }
    cards.forEach(card => container.appendChild(card));
    reviewFeed = { filters, offset: payload.next_offset, hasMore: payload.has_more, keys };
    container.dataset.category = filters.category;
    container.dataset.query = filters.q;
    container.dataset.nextOffset = String(payload.next_offset);
    container.dataset.hasMore = String(payload.has_more);
    if (!keys.size) {
      const empty = document.createElement('section');
      empty.className = 'no-reviews';
      const heading = document.createElement('h2');
      heading.textContent = 'No reviews found yet';
      const explanation = document.createElement('p');
      explanation.textContent = 'Try another title or choose All media. New public reviews appear here as members share them.';
      empty.append(heading, explanation);
      container.appendChild(empty);
    }
    reviewRequest = null;
    updateReviewControls(`${keys.size} ${keys.size === 1 ? 'review' : 'reviews'} shown for ${describeReviewFilters(filters)}.${payload.has_more ? '' : ' You’re all caught up.'}`);
  } catch (_) {
    if (request.generation !== reviewGeneration) return;
    reviewRequest = null;
    failedReviewRequest = { reset, filters };
    const retained = reviewFeed.keys.size ? ` Your ${reviewFeed.keys.size} displayed reviews are still here.` : '';
    updateReviewControls(`Couldn’t load ${reset ? 'reviews' : 'more reviews'} for ${describeReviewFilters(filters)}.${retained} Please try again.`);
  } finally {
    clearTimeout(request.timeout);
    if (onAbort) request.controller.signal.removeEventListener('abort', onAbort);
  }
}

function reviewText(tag, className, value) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = value == null ? '' : String(value);
  return element;
}

function reviewImageUrl(value) {
  if (typeof value !== 'string') return '/static/default-avatar.svg';
  if (value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')) return value;
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' || url.protocol === 'http:') return url.href;
  } catch (_) { /* Use a local fallback for missing or unsupported artwork. */ }
  return '/static/default-avatar.svg';
}

function reviewItemMetadata(review) {
  const year = review.year || (review.release_date || '').slice(0, 4);
  const parts = [];
  if (review.category === 'movie' && review.director) parts.push(review.director);
  if (review.category === 'music' && review.artist) parts.push(review.artist);
  if (review.category === 'book' && review.author) parts.push(review.author);
  if (review.category === 'video_game' && review.genres) parts.push(review.genres);
  if (year) parts.push(year);
  if (review.seasons) parts.push(`${review.seasons} season${review.seasons === 1 ? '' : 's'}`);
  if (review.episodes) parts.push(`${review.episodes} episode${review.episodes === 1 ? '' : 's'}`);
  return parts.join(' · ');
}

function isStandaloneReview(review) {
  return review.search_ready === true;
}

function createReviewCard(review) {
  const card = document.createElement('article');
  card.className = 'review-card';
  card.dataset.reviewKey = `${review.category}:${review.id}`;
  const reviewUrl = `/reviews/${encodeURIComponent(review.id)}?category=${encodeURIComponent(review.category)}`;
  const isStandalone = isStandaloneReview(review);
  if (!isStandalone) card.classList.add('review-card--summary');
  const categoryLabel = { movie: 'Movie', tv_show: 'TV Show', anime: 'Anime', video_game: 'Video Game', music: 'Music', book: 'Book' }[review.category];
  card.appendChild(reviewText('span', 'review-category', categoryLabel));
  const header = reviewText('div', 'review-card-header', '');
  const poster = document.createElement('img');
  poster.src = reviewImageUrl(review.poster_url || review.cover_art_url);
  poster.alt = '';
  poster.className = 'review-poster';
  poster.loading = 'lazy';
  poster.width = 64;
  poster.height = 88;
  poster.dataset.fallbackSrc = '/static/default-avatar.svg';
  const titleBlock = reviewText('div', 'review-card-title', '');
  const title = document.createElement('h3');
  if (isStandalone) {
    const link = reviewText('a', 'review-title-link', review.title);
    link.href = reviewUrl;
    title.appendChild(link);
  } else title.textContent = review.title;
  titleBlock.append(title, reviewText('p', 'review-item-meta', reviewItemMetadata(review)));
  header.append(poster, titleBlock);
  card.appendChild(header);
  const fullText = review.review.trim();
  const long = fullText.length > 420;
  card.appendChild(reviewText('p', 'review-preview', long ? `${fullText.slice(0, 417).trimEnd()}…` : fullText));
  if (long && !isStandalone) {
    const details = reviewText('details', 'review-full-text', '');
    details.append(reviewText('summary', '', 'Read full review'), reviewText('p', '', fullText));
    card.appendChild(details);
  }
  const meta = reviewText('div', 'review-meta', '');
  meta.appendChild(reviewText('span', 'review-author', `By ${review.username || 'Community member'}`));
  if (review.rating !== null && review.rating !== undefined) {
    meta.appendChild(reviewText('span', 'review-rating', `Rating: ${review.rating}/10`));
  }
  card.appendChild(meta);
  const actions = reviewText('div', 'review-card-actions', '');
  const save = reviewText('a', 'review-save-link', 'Save to my library');
  save.href = `/reviews/${encodeURIComponent(review.id)}/save?category=${encodeURIComponent(review.category)}`;
  save.setAttribute('aria-label', `Save ${review.title} to my library`);
  actions.appendChild(save);
  if (isStandalone) {
    const read = reviewText('a', 'review-detail-link', 'Read full review');
    read.href = reviewUrl;
    read.setAttribute('aria-label', `Read the full review of ${review.title}`);
    actions.appendChild(read);
  }
  card.appendChild(actions);
  if (!isStandalone && window.createReviewReportControls) {
    card.appendChild(window.createReviewReportControls(review.category, review.id));
  }
  return card;
}

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.dataset.fallbackSrc) return;
  if (image.src.endsWith(image.dataset.fallbackSrc)) return;
  image.src = image.dataset.fallbackSrc;
}, true);

window.addEventListener('pagehide', () => {
  if (!reviewRequest) return;
  const pending = reviewRequest;
  ++reviewGeneration;
  pending.controller.abort();
  clearTimeout(pending.timeout);
  reviewRequest = null;
  failedReviewRequest = { reset: pending.reset, filters: pending.filters };
  // A page restored from the browser's back/forward cache stays usable.
  updateReviewControls('Loading paused. Your displayed reviews are still here. Choose Try again to continue.');
});

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('reviewsContainer');
  const form = document.getElementById('reviewFilters');
  if (!container || !form) return;
  reviewFeed = {
    filters: { category: container.dataset.category || '', q: container.dataset.query || '' },
    offset: Number(container.dataset.nextOffset) || 0,
    hasMore: container.dataset.hasMore === 'true',
    keys: new Set(Array.from(container.querySelectorAll('[data-review-key]'), card => card.dataset.reviewKey)),
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    loadReviews();
  });
  document.getElementById('categoryFilter').addEventListener('change', () => loadReviews());
  document.getElementById('loadMoreReviews').addEventListener('click', () => loadReviews(false));
  document.getElementById('retryReviews').addEventListener('click', () => {
    if (failedReviewRequest) loadReviews(failedReviewRequest.reset, failedReviewRequest.filters);
  });
  updateReviewControls(reviewFeed.keys.size ? `${reviewFeed.keys.size} ${reviewFeed.keys.size === 1 ? 'review' : 'reviews'} to explore.` : 'Explore another title or media type, or check back for new reviews.');
  // Server-rendered cards and their order remain usable immediately, without a second request.
});
