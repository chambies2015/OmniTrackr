// Title pages: click-to-play trailers (nothing loads from YouTube until asked), poster rails,
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

  // A member who already tracks this title shouldn't be offered "Add to my library".
  function markInLibrary() {
    const add = document.querySelector('[data-title-add]');
    if (!add) return;
    add.textContent = '✓ In your library';
    add.disabled = true;
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
      if (data.in_library) markInLibrary();
      if (data.in_library && data.review) {
        reviewForm.elements.review.value = data.review;
        reviewForm.dataset.expected = data.review;
        reviewForm.querySelector('[type="submit"]').textContent = 'Update review';
      }
      if (data.in_library && data.rating !== null && data.rating !== undefined) reviewForm.elements.rating.value = data.rating;
      if (data.in_library) reviewForm.elements.public.checked = data.review ? Boolean(data.public) : true;
      if (reviewForm.elements.spoilers) reviewForm.elements.spoilers.checked = Boolean(data.spoilers);
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
          ...(reviewForm.elements.spoilers ? { spoilers: reviewForm.elements.spoilers.checked } : {}),
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

  // Funnel counts for the title page's own buttons (once per visit, like guest-list.js).
  function report(event) {
    // Guest counts only: members' pages have no guest save button.
    if (!document.querySelector('[data-guest-save]')) return;
    if (typeof window.reportFunnelEvent === 'function') { window.reportFunnelEvent(event); return; }
    try {
      const sent = JSON.parse(sessionStorage.getItem('omnitrackr_funnel_sent') || '[]');
      if (Array.isArray(sent) && sent.includes(event)) return;
      sessionStorage.setItem('omnitrackr_funnel_sent', JSON.stringify([...(Array.isArray(sent) ? sent : []), event].slice(-20)));
    } catch (error) { /* storage blocked: count it anyway */ }
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  document.addEventListener('click', event => {
    const trailer = event.target.closest && event.target.closest('.title-trailer');
    if (trailer) {
      report('title_trailer_played');
      playTrailer(trailer);
      return;
    }
    // The hero's "Trailer" button: go to the trailer and start it, in one tap.
    const jump = event.target.closest && event.target.closest('[data-trailer-jump]');
    if (jump) {
      const target = document.querySelector('.title-trailer');
      if (target) {
        event.preventDefault();
        report('title_trailer_played');
        const section = target.closest('section') || target;
        const smooth = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
        section.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'center' });
        playTrailer(target);
      }
      return;
    }
    if (event.target.closest && event.target.closest('[data-title-signup]')) report('title_signup_clicked');
    // "Save it first" in the join band presses the hero's save button, which owns saving.
    const joinSave = event.target.closest && event.target.closest('[data-join-save]');
    if (joinSave) {
      const source = document.querySelector('.title-hero [data-guest-save]');
      if (source && source.getAttribute('aria-pressed') !== 'true') source.click();
      syncJoinSave();
      return;
    }
    const add = event.target.closest && event.target.closest('[data-title-add]');
    if (add) addToLibrary(add);
    const ask = event.target.closest && event.target.closest('[data-take-ask]');
    if (ask) askFriend(ask);
  });

  // ---------- Members' share menu: closes on a pick, a tap elsewhere, or Escape ----------
  document.addEventListener('click', event => {
    document.querySelectorAll('details.title-more[open]').forEach(menu => {
      const inside = event.target.closest && event.target.closest('details.title-more') === menu;
      const picked = event.target.closest && event.target.closest('.title-more__item');
      if (!inside || picked) menu.removeAttribute('open');
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('details.title-more[open]').forEach(menu => {
      menu.removeAttribute('open');
      const summary = menu.querySelector('summary');
      if (summary) summary.focus();
    });
  });

  // ---------- "On this page" tabs: sit under the sticky header, mark the section in view ----------
  function setupTabs() {
    const tabs = document.querySelector('.title-tabs');
    if (!tabs || typeof tabs.querySelectorAll !== 'function') return;
    const header = document.querySelector('.site-header');
    const place = () => {
      const height = header ? Math.round(header.getBoundingClientRect().height) : 0;
      document.documentElement.style.setProperty('--title-tabs-top', `${height}px`);
    };
    place();
    window.addEventListener('resize', place);
    if (typeof IntersectionObserver !== 'function') return;
    const links = new Map();
    tabs.querySelectorAll('a[href^="#"]').forEach(link => {
      const heading = document.getElementById(link.getAttribute('href').slice(1));
      const section = heading && (heading.closest('section') || heading);
      if (section) links.set(section, link);
    });
    const visible = new Set();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => (entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target)));
      let current = null;
      links.forEach((link, section) => { if (!current && visible.has(section)) current = link; });
      links.forEach(link => {
        if (link === current) {
          link.setAttribute('aria-current', 'true');
          const strip = link.parentElement;
          if (strip.scrollWidth > strip.clientWidth) strip.scrollTo({ left: link.offsetLeft - 16, behavior: 'smooth' });
        } else {
          link.removeAttribute('aria-current');
        }
      });
    }, { rootMargin: '-35% 0px -55% 0px' });
    links.forEach((link, section) => observer.observe(section));
    // Back up in the hero, above the first section, the strip starts from its first tab again
    // instead of staying scrolled to the last tab that was marked further down.
    const first = links.keys().next().value;
    const strip = tabs.querySelector('.title-tabs__inner');
    let queued = false;
    if (first && strip) {
      window.addEventListener('scroll', () => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          if (strip.scrollLeft > 0 && first.getBoundingClientRect().top > window.innerHeight * 0.45) {
            strip.scrollTo({ left: 0, behavior: 'auto' });
          }
        });
      }, { passive: true });
    }
  }
  // ---------- Save button in the sticky bar once the hero's own button scrolls away ----------
  // It presses the hero button, so guest-list.js and addToLibrary stay the only code that saves.
  function setupDock() {
    const dock = document.querySelector('[data-title-dock]');
    const source = document.querySelector('.title-hero [data-guest-save], .title-hero [data-title-add]');
    const bar = document.querySelector('.title-tabs');
    if (!dock || !source || !bar || typeof IntersectionObserver !== 'function') return;
    const button = dock.querySelector('[data-dock-save]');
    const join = dock.querySelector('[data-dock-join]');
    const sync = () => {
      const pressed = source.getAttribute('aria-pressed');
      // Once a guest has saved, the bar's job is the sign-up: a short "Saved" and a join link.
      const saved = pressed === 'true' && Boolean(join);
      button.textContent = saved ? 'Saved' : source.textContent;
      button.disabled = source.disabled;
      if (pressed !== null) button.setAttribute('aria-pressed', pressed);
      if (join) join.hidden = !saved;
    };
    button.addEventListener('click', () => {
      source.click();
      setTimeout(sync, 0);
    });
    if (typeof MutationObserver === 'function') {
      new MutationObserver(sync).observe(source, { attributes: true, childList: true, characterData: true, subtree: true });
    }
    sync();
    dock.hidden = false;
    new IntersectionObserver(([entry]) => {
      const gone = !entry.isIntersecting && entry.boundingClientRect.top < 0;
      bar.classList.toggle('title-tabs--docked', gone);
      dock.setAttribute('aria-hidden', String(!gone));
      button.tabIndex = gone ? 0 : -1;
    }).observe(source);
  }

  // ---------- The join band's save button mirrors the hero's ----------
  function syncJoinSave() {
    const button = document.querySelector('[data-join-save]');
    const source = document.querySelector('.title-hero [data-guest-save]');
    if (!button || !source) return;
    const saved = source.getAttribute('aria-pressed') === 'true';
    if (!button.dataset.label) button.dataset.label = button.textContent;
    button.textContent = saved ? 'Saved to your list ✓' : button.dataset.label;
    button.disabled = saved;
  }

  function setupJoinSave() {
    const source = document.querySelector('.title-hero [data-guest-save]');
    const button = document.querySelector('[data-join-save]');
    if (!button) return;
    if (!source) { button.hidden = true; return; }
    if (typeof MutationObserver === 'function') {
      new MutationObserver(syncJoinSave).observe(source, { attributes: true, attributeFilter: ['aria-pressed'] });
    }
    syncJoinSave();
  }

  // ---------- Poster rails: arrow buttons on wide screens, swipe everywhere ----------
  function setupRails() {
    document.querySelectorAll('[data-title-rail]').forEach(rail => {
      const strip = rail.querySelector('.title-related-grid');
      if (!strip) return;
      const make = (direction, label) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `title-rail__arrow title-rail__arrow--${direction}`;
        button.setAttribute('aria-label', label);
        button.tabIndex = -1; // keyboard users scroll the strip itself; its links are all reachable
        button.addEventListener('click', () => {
          const step = Math.max(strip.clientWidth * 0.85, 200);
          strip.scrollBy({ left: direction === 'next' ? step : -step, behavior: 'smooth' });
        });
        rail.appendChild(button);
        return button;
      };
      const prev = make('prev', 'Scroll back');
      const next = make('next', 'Scroll on');
      const update = () => {
        const max = strip.scrollWidth - strip.clientWidth;
        rail.classList.toggle('title-rail--overflow', max > 4);
        prev.disabled = strip.scrollLeft <= 4;
        next.disabled = strip.scrollLeft >= max - 4;
      };
      strip.addEventListener('scroll', update, { passive: true });
      window.addEventListener('resize', update);
      update();
    });
  }

  if (typeof document.getElementById === 'function') {
    setupTabs();
    setupDock();
    setupJoinSave();
    setupRails();
  }
})();
