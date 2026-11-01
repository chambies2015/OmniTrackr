/* Phone navigation for the signed-in dashboard: a bottom bar (Home, Library,
   Add, Feed, More) and a "More" sheet that lists every tab, the public
   sections and the account controls.

   The bar reuses the dashboard's own delegated handlers (core.js): buttons
   carry data-switch-tab, data-action or data-click-target, so switching tabs,
   opening Quick Capture or pressing a toolbar button behaves exactly as it
   does from the desktop controls. The sheet mirrors the tab strip each time it
   opens, so hidden tabs stay hidden and custom tabs appear without extra code. */
(function () {
  'use strict';

  // The header's Explore menu is a <details>: close it on a click elsewhere or Escape.
  const explore = document.querySelector('.app-explore');
  if (explore) {
    document.addEventListener('click', (event) => {
      if (explore.open && !explore.contains(event.target)) explore.open = false;
    });
    explore.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && explore.open) {
        explore.open = false;
        explore.querySelector('summary').focus();
      }
    });
  }

  const dock = document.getElementById('appDock');
  const sheet = document.getElementById('appMoreSheet');
  const main = document.getElementById('mainContainer');
  if (!dock || !sheet || !main) return;

  const MEDIA_TABS = new Set(['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books', 'manga', 'podcasts', 'audiobooks']);
  const libraryButton = dock.querySelector('[data-dock="library"]');
  const homeButton = dock.querySelector('[data-dock="home"]');
  const moreButton = dock.querySelector('[data-dock="more"]');
  let lastMediaTab = 'movies';

  function visibleTabs(group) {
    return Array.from(document.querySelectorAll(`.tabs ${group} .tab[data-switch-tab]`))
      .filter((tab) => tab.style.display !== 'none' && !tab.hidden);
  }

  // The bar only belongs to the signed-in view; auth.js shows and hides #mainContainer.
  function syncVisibility() {
    const shown = getComputedStyle(main).display !== 'none';
    document.body.classList.toggle('has-app-dock', shown);
    document.body.classList.toggle('app-dock-off', !shown);
    dock.hidden = !shown;
  }

  // Library opens the media tab used last, skipping any the member hid.
  function syncLibraryTarget() {
    const media = visibleTabs('.library-nav__group:not(.library-nav__group--tools)')
      .map((tab) => tab.dataset.switchTab);
    if (!media.includes(lastMediaTab)) lastMediaTab = media[0] || 'movies';
    libraryButton.dataset.switchTab = lastMediaTab;
  }

  function markCurrent() {
    const active = document.body.dataset.activeTab || 'movies';
    if (MEDIA_TABS.has(active)) lastMediaTab = active;
    syncLibraryTarget();
    const tabs = document.querySelector('.tabs');
    const nearTop = !tabs || window.scrollY < tabs.offsetTop - 80;
    let current = 'more';
    if (sheet.open) current = 'more';
    else if (nearTop) current = 'home';
    else if (MEDIA_TABS.has(active)) current = 'library';
    else if (active === 'friends-feed') current = 'feed';
    dock.querySelectorAll('.app-dock__item').forEach((item) => {
      if (item.dataset.dock === current) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
  }

  function mirrorFeedDot() {
    const source = document.getElementById('friendsFeedDot');
    const dot = dock.querySelector('.app-dock__dot');
    if (source && dot) dot.hidden = source.hidden || source.style.display === 'none';
  }

  function sheetButton(tab) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'app-sheet__tab';
    button.dataset.switchTab = tab.dataset.switchTab;
    // Text only: tab labels include the hidden "(new updates)" note for screen readers.
    const label = Array.from(tab.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent).join('').trim() || tab.textContent.trim();
    button.textContent = label;
    if (tab.classList.contains('active')) button.setAttribute('aria-current', 'page');
    return button;
  }

  function fillSheet() {
    const libraries = sheet.querySelector('[data-sheet="libraries"]');
    const space = sheet.querySelector('[data-sheet="space"]');
    libraries.replaceChildren(...visibleTabs('.library-nav__group:not(.library-nav__group--tools)').map(sheetButton));
    space.replaceChildren(...visibleTabs('.library-nav__group--tools').map(sheetButton));
    space.closest('section').hidden = !space.children.length;

    // Account rows follow the real toolbar: hidden there means hidden here.
    sheet.querySelectorAll('[data-click-target]').forEach((row) => {
      const source = document.getElementById(row.dataset.clickTarget);
      const shown = source && !source.hidden && source.style.display !== 'none';
      row.hidden = !shown;
    });
    const mode = document.getElementById('toggleMode');
    const modeRow = sheet.querySelector('[data-click-target="toggleMode"] span');
    if (mode && modeRow) modeRow.textContent = mode.textContent.trim() || 'Switch theme';
    const name = document.getElementById('userDisplayText');
    const nameRow = sheet.querySelector('.app-sheet__name');
    if (nameRow) nameRow.textContent = (name && name.textContent.trim()) || 'Your account';
    const avatar = document.getElementById('userProfilePicture');
    const avatarRow = sheet.querySelector('.app-sheet__avatar');
    if (avatar && avatarRow && avatar.src) avatarRow.src = avatar.src;
  }

  function openSheet() {
    fillSheet();
    sheet.showModal();
    moreButton.setAttribute('aria-expanded', 'true');
    markCurrent();
  }

  function closeSheet() {
    if (sheet.open) sheet.close();
  }

  homeButton.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
  libraryButton.addEventListener('click', syncLibraryTarget, true);
  moreButton.addEventListener('click', () => (sheet.open ? closeSheet() : openSheet()));

  // Any choice in the sheet closes it; core.js has already acted on the click.
  sheet.addEventListener('click', (event) => {
    if (event.target === sheet || event.target.closest('button, a')) setTimeout(closeSheet, 0);
  });
  sheet.addEventListener('close', () => {
    moreButton.setAttribute('aria-expanded', 'false');
    markCurrent();
  });

  let queued = false;
  window.addEventListener('scroll', () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; markCurrent(); });
  }, { passive: true });

  new MutationObserver(syncVisibility).observe(main, { attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
  new MutationObserver(markCurrent).observe(document.body, { attributes: true, attributeFilter: ['data-active-tab'] });
  const dot = document.getElementById('friendsFeedDot');
  if (dot) new MutationObserver(mirrorFeedDot).observe(dot, { attributes: true, attributeFilter: ['hidden', 'style'] });

  syncVisibility();
  mirrorFeedDot();
  markCurrent();
})();
