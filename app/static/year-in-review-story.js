// Year in Review story: full-screen slides you tap through, with a story image to share at the end.
(function () {
  'use strict';

  const story = document.querySelector('[data-recap-story]');
  if (!story) return;
  const slides = Array.from(story.querySelectorAll('.recap-slide'));
  const bars = story.querySelector('[data-story-bars]');
  const openers = Array.from(document.querySelectorAll('[data-story-open]'));
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SLIDE_MS = 6500;
  let index = 0;
  let timer = null;
  let started = 0;
  let remaining = SLIDE_MS;
  let lastFocus = null;

  function count(event) {
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting is optional */ }
  }

  bars.innerHTML = slides.map(() => '<span><i></i></span>').join('');
  const fills = Array.from(bars.querySelectorAll('i'));

  function stop() {
    if (timer) { clearTimeout(timer); timer = null; }
  }

  function schedule(ms) {
    stop();
    if (reduceMotion || index >= slides.length - 1) return;
    started = Date.now();
    remaining = ms;
    timer = setTimeout(() => show(index + 1), ms);
  }

  function show(next) {
    index = Math.max(0, Math.min(slides.length - 1, next));
    slides.forEach((slide, i) => {
      slide.classList.toggle('is-active', i === index);
      slide.setAttribute('aria-hidden', i === index ? 'false' : 'true');
    });
    fills.forEach((fill, i) => {
      fill.classList.remove('is-running');
      fill.style.animationDuration = '';
      fill.classList.toggle('is-done', i < index || (reduceMotion && i === index));
    });
    const fill = fills[index];
    if (fill && !reduceMotion && index < slides.length - 1) {
      void fill.offsetWidth; // restart the CSS animation
      fill.style.animationDuration = `${SLIDE_MS}ms`;
      fill.classList.add('is-running');
    } else if (fill) {
      fill.classList.add('is-done');
    }
    story.classList.toggle('is-last', index === slides.length - 1);
    schedule(SLIDE_MS);
  }

  function pause() {
    if (!timer) return;
    stop();
    remaining = Math.max(400, remaining - (Date.now() - started));
    story.classList.add('is-paused');
  }

  function resume() {
    if (!story.classList.contains('is-paused')) return;
    story.classList.remove('is-paused');
    schedule(remaining);
  }

  function open() {
    lastFocus = document.activeElement;
    story.hidden = false;
    document.documentElement.classList.add('recap-story-open');
    show(0);
    const close = story.querySelector('[data-story-close]');
    if (close) close.focus();
    count('recap_story_played');
  }

  function close() {
    stop();
    story.hidden = true;
    story.classList.remove('is-paused');
    document.documentElement.classList.remove('recap-story-open');
    if (window.location.hash === '#story') {
      try { history.replaceState(null, '', window.location.pathname + window.location.search); } catch (error) { /* fine */ }
    }
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  openers.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', open);
  });
  story.querySelectorAll('[data-story-close]').forEach(button => button.addEventListener('click', close));
  story.querySelector('[data-story-prev]').addEventListener('click', () => show(index - 1));
  story.querySelector('[data-story-next]').addEventListener('click', () => {
    if (index >= slides.length - 1) close(); else show(index + 1);
  });

  // Press and hold anywhere on the slide to pause, like other story viewers.
  const frame = story.querySelector('.recap-story__frame');
  frame.addEventListener('pointerdown', event => { if (!event.target.closest('a, button')) pause(); });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(name => frame.addEventListener(name, resume));
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); else resume(); });

  story.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    else if (event.key === 'ArrowRight') { event.preventDefault(); show(index + 1); }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); show(index - 1); }
    else if (event.key === 'Tab') {
      const focusable = Array.from(story.querySelectorAll('button, a[href]'))
        .filter(el => !el.closest('.recap-slide') || el.closest('.recap-slide').classList.contains('is-active'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  const status = story.querySelector('[data-story-status]');
  function say(text) { if (status) status.textContent = text; }

  story.querySelectorAll('[data-story-share-image]').forEach(button => {
    button.addEventListener('click', async () => {
      const src = button.dataset.src;
      const name = button.dataset.filename || 'omnitrackr-story.png';
      button.disabled = true;
      say('Getting your image ready…');
      try {
        const response = await fetch(src, { credentials: 'same-origin' });
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        const file = new File([blob], name, { type: 'image/png' });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          try {
            await navigator.share({ files: [file], title: 'My year in review' });
            say('Shared.');
            count('recap_story_shared');
          } catch (error) {
            say(error && error.name === 'AbortError' ? '' : 'Sharing did not open. Use Save image instead.');
          }
        } else {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = name;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 2000);
          say('Saved. Add it to your story from your photos or downloads.');
          count('recap_story_shared');
        }
      } catch (error) {
        say('That did not work. Please try again.');
      } finally {
        button.disabled = false;
      }
    });
  });
  story.querySelectorAll('a[download]').forEach(link => link.addEventListener('click', () => count('recap_story_shared')));

  if (window.location.hash === '#story') open();
}());
