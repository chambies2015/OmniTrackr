// Dashboard welcome strip, library tab counts and the stat line under each library heading.
// Data comes from /statistics/home/ (the member's own library, read only). Every piece of
// server text is set with textContent.
(function () {
  'use strict';

  const TABS = {
    movies: 'Movies', 'tv-shows': 'TV Shows', anime: 'Anime', 'video-games': 'Games', music: 'Music',
    books: 'Books', manga: 'Manga', podcasts: 'Podcasts', audiobooks: 'Audiobooks',
  };
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December'];
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const COVER_LIMIT = 5;
  const state = { request: null, epoch: 0, timer: null, data: null };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const signedIn = () => (typeof hasStoredAuth === 'function' ? hasStoredAuth() : false);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function count(n, one, many) {
    return `${n.toLocaleString()} ${n === 1 ? one : many}`;
  }

  function greeting(now, name) {
    const hour = now.getHours();
    const who = name ? `, ${name}` : '';
    if (hour < 5) return `Still up${who}?`;
    if (hour < 12) return `Good morning${who}`;
    if (hour < 18) return `Good afternoon${who}`;
    return `Good evening${who}`;
  }

  function summaryText(data, now) {
    const month = MONTHS[now.getMonth()];
    const done = Number(data.finished_this_month) || 0;
    const waiting = Number(data.unfinished) || 0;
    const first = done
      ? `${count(done, 'title', 'titles')} finished in ${month} so far.`
      : `Nothing finished in ${month} yet.`;
    if (!waiting) return `${first} Everything you've saved is done. Time to add something new.`;
    return `${first} ${waiting.toLocaleString()} still waiting for you.`;
  }

  function stat(label, value) {
    const wrap = el('div', 'home-hero__stat');
    wrap.append(el('dt', '', label), el('dd', '', Number(value || 0).toLocaleString()));
    return wrap;
  }

  function renderStats(data) {
    const list = $('homeHeroStats');
    if (!list) return;
    list.replaceChildren(
      stat('In your library', data.total),
      stat('Finished', data.finished),
      stat('Rated', data.rated),
      stat('This month', data.finished_this_month),
    );
  }

  // A thin bar split by format, in the same colours as the library tabs.
  function renderMix(libraries) {
    const bar = $('homeHeroMix');
    if (!bar) return;
    bar.replaceChildren();
    const parts = libraries.filter(library => library.visible && library.total > 0 && TABS[library.key]);
    parts.forEach(library => {
      const part = el('span', 'home-hero__mix-part');
      part.dataset.format = library.key;
      part.style.setProperty('--share', String(library.total));
      part.title = `${TABS[library.key]}: ${library.total.toLocaleString()}`;
      bar.appendChild(part);
    });
    bar.setAttribute('aria-label', `Your library by format: ${parts.map(library => count(library.total, library.one, library.many)).join(', ')}`);
    bar.hidden = !parts.length;
  }

  function renderCovers(recent) {
    const wall = $('homeHeroCovers');
    if (!wall) return;
    wall.replaceChildren();
    recent.slice(0, COVER_LIMIT).forEach((item, index) => {
      const button = el('button', 'home-hero__cover');
      button.type = 'button';
      button.dataset.action = 'pulse-open-item';
      button.dataset.pulseTab = item.category;
      button.dataset.pulseItemId = String(item.id);
      button.dataset.pulseTitle = item.title;
      button.dataset.format = item.category;
      button.style.setProperty('--i', String(index));
      button.setAttribute('aria-label', `Open ${item.title}`);
      button.title = item.title;
      const img = el('img');
      img.src = item.image;
      img.alt = '';
      img.loading = index < 4 ? 'eager' : 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.width = 120;
      img.height = 180;
      // A cover that fails to load drops out instead of leaving a broken box.
      img.addEventListener('error', () => button.remove(), { once: true });
      button.appendChild(img);
      wall.appendChild(button);
    });
    wall.hidden = !wall.children.length;
    const section = $('homeHero');
    if (!section) return;
    section.classList.toggle('home-hero--covers', !wall.hidden);
    // The newest cover, blurred, tints the strip behind the text.
    let wash = section.querySelector(':scope > .home-hero__wash');
    const first = recent[0];
    if (!first) { wash?.remove(); return; }
    if (!wash) {
      wash = el('img', 'home-hero__wash');
      wash.alt = '';
      wash.setAttribute('aria-hidden', 'true');
      wash.decoding = 'async';
      wash.referrerPolicy = 'no-referrer';
      wash.addEventListener('error', () => wash.remove());
      section.prepend(wash);
    }
    if (wash.getAttribute('src') !== first.image) wash.src = first.image;
  }

  // Library tabs get a quiet count; the stat line sits under each library heading.
  function renderTabCounts(libraries) {
    libraries.forEach(library => {
      document.querySelectorAll(`.tabs .tab[data-switch-tab="${library.key}"]`).forEach(tab => {
        if (library.total > 0) tab.dataset.count = library.total > 999 ? '999+' : String(library.total);
        else delete tab.dataset.count;
      });
    });
  }

  function headingLine(library) {
    if (!library.total) return '';
    const parts = [count(library.total, library.one, library.many)];
    parts.push(`${library.finished.toLocaleString()} ${library.verb}`);
    if (library.rated) parts.push(`${library.rated.toLocaleString()} rated`);
    if (library.average_rating !== null && library.average_rating !== undefined) {
      parts.push(`average ${Number(library.average_rating).toFixed(1)}`);
    }
    return parts.join(' · ');
  }

  function renderHeadings(libraries) {
    libraries.forEach(library => {
      const heading = document.querySelector(`#${library.key}-tab .library-panel > .library-heading`);
      if (!heading) return;
      let line = heading.parentElement.querySelector(':scope > .library-heading__stats');
      const text = headingLine(library);
      if (!text) { line?.remove(); return; }
      if (!line) {
        line = el('p', 'library-heading__stats');
        heading.insertAdjacentElement('afterend', line);
      }
      line.textContent = text;
    });
  }

  function render(data, now = new Date()) {
    const section = $('homeHero');
    if (!section || !data) return;
    state.data = data;
    const libraries = Array.isArray(data.libraries) ? data.libraries : [];
    renderTabCounts(libraries);
    renderHeadings(libraries);
    if (!(Number(data.total) > 0)) {
      section.hidden = true;
      return;
    }
    const date = $('homeHeroDate');
    if (date) date.textContent = `${DAYS[now.getDay()]}, ${MONTHS[now.getMonth()]} ${now.getDate()}`;
    const title = $('homeHeroTitle');
    if (title) title.textContent = greeting(now, data.name);
    const summary = $('homeHeroSummary');
    if (summary) summary.textContent = summaryText(data, now);
    renderStats(data);
    renderMix(libraries);
    renderCovers(Array.isArray(data.recent) ? data.recent : []);
    section.hidden = false;
  }

  function refresh() {
    if (!signedIn()) return Promise.resolve();
    const epoch = state.epoch;
    const options = typeof authFetchOptions === 'function' ? authFetchOptions({}) : { credentials: 'same-origin' };
    const request = fetch(`${apiBase()}/statistics/home/`, options)
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data && epoch === state.epoch && signedIn()) render(data); })
      .catch(() => { /* The strip is optional; the dashboard works without it. */ });
    state.request = request;
    return request;
  }

  function refreshSoon() {
    window.clearTimeout(state.timer);
    state.timer = window.setTimeout(refresh, 600);
  }

  function reset() {
    state.epoch++;
    state.data = null;
    window.clearTimeout(state.timer);
    const section = $('homeHero');
    if (section) section.hidden = true;
    document.querySelectorAll('.tabs .tab[data-count]').forEach(tab => { delete tab.dataset.count; });
    document.querySelectorAll('.library-heading__stats').forEach(line => line.remove());
  }

  function init() {
    // A library count changes after an add, a delete or an import: fetch fresh numbers.
    const counts = document.querySelectorAll('.library-panel .library-count');
    if (counts.length && typeof MutationObserver === 'function') {
      const seen = new WeakMap();
      counts.forEach(node => seen.set(node, node.textContent));
      const observer = new MutationObserver(records => {
        let changed = false;
        records.forEach(record => {
          const node = record.target.nodeType === 1 ? record.target.closest('.library-count') : record.target.parentElement?.closest('.library-count');
          if (node && seen.get(node) !== node.textContent) { seen.set(node, node.textContent); changed = true; }
        });
        if (changed && state.data) refreshSoon();
      });
      counts.forEach(node => observer.observe(node, { childList: true, characterData: true, subtree: true }));
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && state.data) refreshSoon();
    });
  }

  window.OmniHomeHero = { refresh, reset, render };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { greeting, summaryText, headingLine, render, refresh, reset, state };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
