// Title pages: click-to-play trailers (nothing loads from YouTube until asked)
// "Add to my library", "Write a review" and "Ask a friend" for signed-in members.
(function () {
  'use strict';

  function playTrailer(button) {
    const id = button.dataset.youtubeId || '';
    if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
    const frame = document.createElement('iframe');
    frame.className = 'title-trailer-frame';
    frame.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`;
    frame.title = button.getAttribute('aria-label') || 'Trailer';
    frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    button.replaceWith(frame);
  }

  function authHeaders() {
    const headers = { Accept: 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  async function addToLibrary(button) {
    const status = document.querySelector('.title-hero__status');
    button.disabled = true;
    const original = button.textContent;
    button.textContent = 'Adding…';
    try {
      const response = await fetch(`/api/titles/${encodeURIComponent(button.dataset.titleKind)}/${encodeURIComponent(button.dataset.titleSlug)}/add`, {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(),
      });
      if (response.status === 401) {
        window.location.href = '/#landing-auth';
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not add it');
      button.textContent = '✓ In your library';
      if (status) status.textContent = data.state === 'existing' ? 'Already in your library.' : 'Added to your library. Rate it or write a review from your dashboard.';
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      if (status) status.textContent = 'Could not add it right now. Please try again.';
    }
  }

  // ---------- Write a review (members) ----------
  const reviewForm = document.querySelector('[data-title-review]');

  function countWords(text) {
    const words = String(text || '').match(/[A-Za-z0-9\u00C0-\u024F'\u2019]+/g);
    return words ? words.length : 0;
  }

  // Mirrors evaluate_public_review in review_quality.py: 80 characters to be listed here;
  // 240 characters, 35 words and two sentences (or 55 words) for a page of its own.
  function reviewHint(text) {
    const value = String(text || '').trim();
    const words = countWords(value);
    if (!words) return '';
    const sentences = (value.match(/[.!?\u2026](?:\s|$)/g) || []).length;
    const label = `${words} word${words === 1 ? '' : 's'}`;
    if (value.length < 80) return `${label}: keep going, a couple of sentences is plenty`;
    if (value.length < 240 || words < 35 || (sentences < 2 && words < 55)) return `${label}: it will show here; a little more and it gets its own page`;
    if (words < 150) return `${label}: good, this gets its own review page`;
    return `${label}: a thorough review, thank you`;
  }

  function reviewStatus(message, link) {
    const status = reviewForm.querySelector('.title-write__status');
    status.replaceChildren(document.createTextNode(message));
    if (link && /^\/reviews\/\d+\?category=[a-z_]+$/.test(link)) {
      const anchor = document.createElement('a');
      anchor.href = link;
      anchor.textContent = 'See your review';
      status.append(' ', anchor);
    }
  }

  function signInUrl() {
    const take = new URLSearchParams(window.location.search).get('take');
    const query = take && /^[A-Za-z0-9_-]{16,64}$/.test(take) ? `?take=${take}` : '';
    return `/?next=${encodeURIComponent(`${window.location.pathname}${query}#write-review`)}#landing-auth`;
  }

  async function loadOwnReview() {
    const submit = reviewForm.querySelector('[type="submit"]');
    submit.disabled = true;
    reviewForm.dataset.expected = '';
    try {
      const response = await fetch(`/api/titles/${encodeURIComponent(reviewForm.dataset.titleKind)}/${encodeURIComponent(reviewForm.dataset.titleSlug)}/my-review`, {
        credentials: 'same-origin', headers: authHeaders(),
      });
      if (response.status === 401) {
        reviewStatus('Your session has ended. Sign in again to write a review.');
        const anchor = document.createElement('a');
        anchor.href = signInUrl();
        anchor.textContent = 'Sign in';
        reviewForm.querySelector('.title-write__status').append(' ', anchor);
        return;
      }
      if (!response.ok) throw new Error('load failed');
      const data = await response.json();
      if (data.in_library && data.review) {
        reviewForm.elements.review.value = data.review;
        reviewForm.dataset.expected = data.review;
        reviewForm.querySelector('[type="submit"]').textContent = 'Update review';
      }
      if (data.in_library && data.rating !== null && data.rating !== undefined) reviewForm.elements.rating.value = data.rating;
      if (data.in_library) reviewForm.elements.public.checked = data.review ? Boolean(data.public) : true;
      reviewForm.querySelector('.title-write__meter').textContent = reviewHint(reviewForm.elements.review.value);
      submit.disabled = false;
    } catch (error) {
      reviewStatus('Could not load your library entry. Reload the page to try again.');
    }
  }

  async function saveReview(event) {
    event.preventDefault();
    const review = reviewForm.elements.review.value.trim();
    const ratingText = reviewForm.elements.rating.value.trim();
    const rating = ratingText === '' ? null : Number(ratingText);
    if (!review) {
      reviewStatus('Write a few words first.');
      reviewForm.elements.review.focus();
      return;
    }
    if (rating !== null && !(Number.isFinite(rating) && rating >= 0 && rating <= 10)) {
      reviewStatus('Ratings go from 0 to 10.');
      reviewForm.elements.rating.focus();
      return;
    }
    const submit = reviewForm.querySelector('[type="submit"]');
    submit.disabled = true;
    reviewStatus('Saving…');
    try {
      const response = await fetch(`/api/titles/${encodeURIComponent(reviewForm.dataset.titleKind)}/${encodeURIComponent(reviewForm.dataset.titleSlug)}/review`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review, rating, public: reviewForm.elements.public.checked,
          expected_review: reviewForm.dataset.expected || '', take: reviewForm.dataset.take || null,
        }),
      });
      if (response.status === 401) {
        window.location.href = signInUrl();
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        reviewStatus(typeof data.detail === 'string' ? data.detail : 'Could not save your review. Your text is still here; please try again.');
        return;
      }
      reviewForm.dataset.expected = review;
      submit.textContent = 'Update review';
      const added = (data.state === 'created' ? ' It is in your library now too.' : '')
        + (data.asked_by ? ` We let ${data.asked_by} know.` : '');
      if (!data.public) reviewStatus(`Saved to your library. Only you can see it.${added}`);
      else if (data.standalone) reviewStatus(`Your review is live on OmniTrackr.${added}`, data.review_url);
      else if (data.listed) reviewStatus(`Your review will appear on this page.${added} Add a few more sentences any time and it gets its own page.`);
      else reviewStatus(`Saved.${added} It is a little short to show publicly yet; add a sentence or two and it will appear here.`);
    } catch (error) {
      reviewStatus('Could not save your review. Your text is still here; please try again.');
    } finally {
      submit.disabled = false;
    }
  }

  if (reviewForm) {
    reviewForm.addEventListener('submit', saveReview);
    reviewForm.elements.review.addEventListener('input', () => {
      reviewForm.querySelector('.title-write__meter').textContent = reviewHint(reviewForm.elements.review.value);
    });
    loadOwnReview();
  }

  // ---------- Ask a friend for their take (members) ----------
  async function askFriend(button) {
    const status = document.querySelector('.title-hero__status');
    button.disabled = true;
    try {
      const response = await fetch(`/api/titles/${encodeURIComponent(button.dataset.titleKind)}/${encodeURIComponent(button.dataset.titleSlug)}/ask`, {
        method: 'POST', credentials: 'same-origin', headers: authHeaders(),
      });
      if (response.status === 401) {
        window.location.href = signInUrl();
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok || typeof data.url !== 'string') throw new Error('ask failed');
      const note = "When a friend reviews it from your link, you'll get a notification.";
      if (navigator.share) {
        try {
          await navigator.share({ title: data.title, text: data.text, url: data.url });
          if (status) status.textContent = `Sent. ${note}`;
          return;
        } catch (error) {
          if (error && error.name === 'AbortError') return;
        }
      }
      try {
        await navigator.clipboard.writeText(`${data.text} ${data.url}`);
        if (status) status.textContent = `Link copied. Paste it to a friend. ${note}`;
      } catch (error) {
        window.prompt('Copy this link and send it to a friend:', data.url);
      }
    } catch (error) {
      if (status) status.textContent = 'Could not make a link right now. Please try again.';
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener('click', event => {
    const trailer = event.target.closest && event.target.closest('.title-trailer');
    if (trailer) {
      playTrailer(trailer);
      return;
    }
    const add = event.target.closest && event.target.closest('[data-title-add]');
    if (add) addToLibrary(add);
    const ask = event.target.closest && event.target.closest('[data-take-ask]');
    if (ask) askFriend(ask);
  });
})();
