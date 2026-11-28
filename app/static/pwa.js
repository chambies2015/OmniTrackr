// Registers the service worker and offers "Install app" where the browser allows it.
// Returning members see a dismissible install card on the dashboard; on phones a short
// note slides up at the bottom on a return visit instead. Browsers without an install
// button (Safari, Chrome on iPhone, Firefox on Android, in-app browsers) get their own
// Add to Home Screen steps. The installed app's icon shows the unread notification count
// where the system allows. Each step is counted for Site stats through POST /api/app/event
// (whitelisted names in app/app_install.py; nothing about the member is sent).
(function () {
  'use strict';

  const DAY_MS = 24 * 60 * 60 * 1000;
  const CARD_MIN_VISIT_DAYS = 3; // never on a first visit: only once someone keeps coming back
  const SHEET_MIN_VISIT_DAYS = 2; // phones: coming back on a second day is the moment to ask
  const SHEET_DELAY_MS = 4000; // let the home screen settle before anything slides up
  const SHEET_REST_DAYS = 7; // an unanswered note waits a week before it can show again
  const SHEET_MAX_SHOWS = 3;
  const CARD_SNOOZE_DAYS = 30;
  const CARD_MAX_DISMISSALS = 2; // after the second "Not now" the card stays away for good
  const OPENED_KEY = 'omnitrackr_app_opened';

  let deferredPrompt = null;
  let cardActive = false;
  let sheetActive = false;
  let sheetTimer = null;
  let serverCheck = null;

  const $ = id => document.getElementById(id);

  function installButton() {
    return $('installAppBtn');
  }

  function userAgent() {
    return (window.navigator && window.navigator.userAgent) || '';
  }

  function matches(query) {
    try {
      return Boolean(window.matchMedia && window.matchMedia(query).matches);
    } catch (error) {
      return false;
    }
  }

  function standalone() {
    return matches('(display-mode: standalone)') || matches('(display-mode: fullscreen)')
      || window.navigator.standalone === true;
  }

  // iPhone and iPad. iPadOS reports a Mac user agent, so touch support tells them apart.
  function appleMobile() {
    const ua = userAgent();
    return /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && window.navigator.maxTouchPoints > 1);
  }

  function android() {
    return /Android/.test(userAgent());
  }

  // Facebook, Instagram, TikTok and the like open links in their own browser, which can't install.
  function inAppBrowser() {
    const ua = userAgent();
    return /FBAN|FBAV|FB_IAB|Instagram|musical_ly|Bytedance|TikTok|Snapchat|LinkedInApp|Pinterest|Line\/|GSA\//.test(ua)
      || (android() && /; wv\)/.test(ua));
  }

  // Safari 17 and later on a Mac can add a site to the Dock.
  function macSafari() {
    const ua = userAgent();
    if (!/Macintosh/.test(ua) || appleMobile() || /Chrome|Chromium|Edg\/|Firefox|OPR\//.test(ua)) return false;
    const version = /Version\/(\d+)/.exec(ua);
    return Boolean(version) && Number(version[1]) >= 17;
  }

  // How this browser installs: "prompt" (its own dialog), the name of the steps to show, or "".
  function installRoute() {
    if (standalone()) return '';
    if (deferredPrompt) return 'prompt';
    if (appleMobile()) {
      if (inAppBrowser()) return 'in_app';
      return /CriOS|FxiOS|EdgiOS/.test(userAgent()) ? 'ios_other' : 'ios_safari';
    }
    if (android()) {
      if (inAppBrowser()) return 'in_app';
      // Chrome, Samsung Internet, Edge and Opera offer their own dialog whenever the app isn't
      // installed yet, so no dialog there usually means it already is.
      return /Firefox\//.test(userAgent()) ? 'android_other' : '';
    }
    return macSafari() ? 'desktop_other' : '';
  }

  // Kept for the iPhone check other scripts used before the routes above.
  function iosSafari() {
    return installRoute() === 'ios_safari';
  }

  function touchDevice() {
    return matches('(pointer: coarse)');
  }

  function phone() {
    return touchDevice() && (Number(window.innerWidth) || 1024) <= 760;
  }

  function platform() {
    if (appleMobile()) return 'ios';
    return android() ? 'android' : 'desktop';
  }

  // ------------------------------------------------------------ counting

  function send(event, extra) {
    try {
      const body = JSON.stringify({ event, platform: platform(), ...(extra || {}) });
      const nav = window.navigator;
      if (nav && typeof nav.sendBeacon === 'function' && typeof Blob === 'function'
          && nav.sendBeacon('/api/app/event', new Blob([body], { type: 'application/json' }))) return;
      if (typeof fetch === 'function') {
        fetch('/api/app/event', {
          method: 'POST', body, keepalive: true, credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
        }).catch(() => {});
      }
    } catch (error) { /* counting is optional */ }
  }

  function track(name, event) {
    try {
      if (typeof window.gtag === 'function') window.gtag('event', name, { event_category: 'install_app' });
    } catch (error) { /* analytics is optional */ }
    if (event) send(event);
  }

  // ------------------------------------------------------------ Add to Home Screen steps

  function each(selector, fn) {
    try {
      if (typeof document.querySelectorAll !== 'function') return;
      Array.prototype.forEach.call(document.querySelectorAll(selector), fn);
    } catch (error) { /* older browsers */ }
  }

  function showSteps(route) {
    const dialog = $('installAppDialog');
    if (!dialog || typeof dialog.showModal !== 'function') return false;
    const steps = route || installRoute();
    const shown = steps && steps !== 'prompt' ? steps : 'ios_safari';
    let title = '';
    each('[data-install-steps]', block => {
      const match = block.getAttribute('data-install-steps') === shown;
      block.hidden = !match;
      if (match) title = block.getAttribute('data-install-title') || '';
    });
    const heading = $('installAppDialogTitle');
    if (heading && title) heading.textContent = title;
    if (!dialog.open) dialog.showModal();
    track(shown === 'ios_safari' ? 'install_ios_steps' : `install_steps_${shown}`, `steps_${shown}`);
    return true;
  }

  async function copyLink(button) {
    try {
      await window.navigator.clipboard.writeText(window.location.href);
      button.textContent = 'Link copied. Paste it in your browser.';
    } catch (error) {
      button.textContent = window.location.href;
    }
  }

  // The browser's own install dialog. Resolves to "accepted", "dismissed" or "".
  async function promptInstall() {
    const prompt = deferredPrompt;
    if (!prompt) return '';
    deferredPrompt = null;
    const button = installButton();
    if (button) button.hidden = true;
    let outcome = '';
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      outcome = choice && choice.outcome === 'accepted' ? 'accepted' : 'dismissed';
    } catch (error) { /* the browser decides */ }
    if (outcome) send(outcome === 'accepted' ? 'prompt_accepted' : 'prompt_dismissed');
    if (outcome === 'accepted' && signedIn()) writeCardState({ ...readCardState(), installed: true });
    return outcome;
  }

  // "Install" pressed anywhere: the browser's dialog where there is one, otherwise the steps.
  async function installFrom(place) {
    send(`install_${place}`);
    if (deferredPrompt) return promptInstall();
    const route = installRoute();
    if (route) showSteps(route);
    return route ? 'steps' : '';
  }

  function updateInstallButton() {
    const route = installRoute();
    const button = installButton();
    if (button) button.hidden = !route;
    // The Get the app page: its button where something can install, a note inside the app.
    each('[data-install-app]', node => { node.hidden = !route; });
    each('[data-app-installed]', node => { node.hidden = !standalone(); });
  }

  function register() {
    if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => { /* optional */ });
  }

  // ------------------------------------------------------------ install card and phone note

  function signedIn() {
    try { return typeof isAuthenticated === 'function' && isAuthenticated(); } catch (error) { return false; }
  }

  function cardKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_install_card_${name}`;
  }

  function readCardState() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(cardKey()) || '{}');
      return saved && typeof saved === 'object' ? saved : {};
    } catch (error) {
      return {};
    }
  }

  function writeCardState(state) {
    try { window.localStorage.setItem(cardKey(), JSON.stringify(state)); } catch (error) { /* this visit only */ }
  }

  function localDay(now) {
    const date = new Date(now);
    return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
  }

  // Counts the distinct days a member opened their dashboard on this device.
  function recordVisit(state, now) {
    const today = localDay(now);
    if (state.lastDay === today) return state;
    return { ...state, lastDay: today, days: (Number(state.days) || 0) + 1 };
  }

  // In-app browsers can't install, so they only get the steps from the menu, never an offer.
  function canInstall() {
    const route = installRoute();
    return Boolean(route) && route !== 'in_app';
  }

  function resting(state, now) {
    if (state.installed || !canInstall()) return true;
    if ((Number(state.dismissals) || 0) >= CARD_MAX_DISMISSALS) return true;
    const snoozedAt = Number(state.snoozedAt) || 0;
    return Boolean(snoozedAt) && now - snoozedAt < CARD_SNOOZE_DAYS * DAY_MS;
  }

  function cardDue(state, now) {
    if (resting(state, now)) return false;
    return (Number(state.days) || 0) >= CARD_MIN_VISIT_DAYS;
  }

  function sheetDue(state, now) {
    if (resting(state, now)) return false;
    if ((Number(state.days) || 0) < SHEET_MIN_VISIT_DAYS) return false;
    if ((Number(state.sheetShows) || 0) >= SHEET_MAX_SHOWS) return false;
    const shownAt = Number(state.sheetAt) || 0;
    return !shownAt || now - shownAt >= SHEET_REST_DAYS * DAY_MS;
  }

  function cardCopy() {
    // Android lists the installed app in the share sheet; iPhone and iPad don't offer that to web apps.
    if (touchDevice() && android()) {
      return {
        title: 'Keep your library on your home screen',
        summary: 'Add OmniTrackr as an app. It opens full screen from its own icon, and OmniTrackr shows up '
          + 'when you tap Share in IMDb, Spotify, Goodreads or YouTube, so saving a title takes one tap.',
      };
    }
    if (appleMobile() || touchDevice()) {
      return {
        title: 'Keep your library on your home screen',
        summary: 'Add OmniTrackr as an app. It opens full screen from its own icon, starts faster, '
          + 'and can show the release-day and friend alerts you turn on from the bell.',
      };
    }
    return {
      title: 'Open OmniTrackr in its own window',
      summary: 'Install OmniTrackr on this computer. It gets its own icon and window, starts faster, '
        + 'and can show the release-day and friend alerts you turn on from the bell.',
    };
  }

  function sheetCopy() {
    if (deferredPrompt) {
      return {
        summary: android()
          ? 'One tap opens your library full screen, and OmniTrackr shows up when you share a link from IMDb, Spotify or YouTube.'
          : 'One tap opens your library full screen, without the browser around it.',
        action: 'Install app',
      };
    }
    return {
      summary: appleMobile()
        ? 'One tap opens your library full screen, and on iPhone it can show the alerts you turn on from the bell.'
        : 'One tap opens your library full screen, without the browser around it.',
      action: 'Show me how',
    };
  }

  // iPhone and iPad keep the installed app's storage apart from Safari's, so Safari can't tell the
  // app is already there. Ask the server once a day whether this member opened it on this kind of device.
  function alreadyUsesApp() {
    if (deferredPrompt || typeof fetch !== 'function') return Promise.resolve(false);
    const state = readCardState();
    const today = localDay(Date.now());
    if (state.checkedDay === today) return Promise.resolve(Boolean(state.usesApp));
    if (!serverCheck) {
      const options = typeof authFetchOptions === 'function'
        ? authFetchOptions({ headers: { Accept: 'application/json' } })
        : { credentials: 'same-origin', headers: { Accept: 'application/json' } };
      serverCheck = fetch('/api/app/status', options)
        .then(response => (response.ok ? response.json() : {}))
        .then(data => {
          const uses = Boolean(data && Array.isArray(data.platforms) && data.platforms.includes(platform()));
          const next = { ...readCardState(), checkedDay: today, usesApp: uses };
          if (uses) next.installed = true;
          writeCardState(next);
          return uses;
        })
        .catch(() => false)
        .finally(() => { serverCheck = null; });
    }
    return serverCheck;
  }

  function hideCard() {
    const card = $('installAppCard');
    if (card) card.hidden = true;
    cardActive = false;
  }

  function hideSheet() {
    if (sheetTimer !== null && typeof clearTimeout === 'function') clearTimeout(sheetTimer);
    sheetTimer = null;
    const sheet = $('installAppSheet');
    if (sheet) sheet.hidden = true;
    sheetActive = false;
  }

  function somethingOpen() {
    try {
      if (typeof document.querySelector !== 'function') return false;
      return Boolean(document.querySelector('dialog[open], .quick-capture.is-open, .app-notice'));
    } catch (error) {
      return false;
    }
  }

  async function showSheet(attempt) {
    sheetTimer = null;
    const sheet = $('installAppSheet');
    if (!sheet || !signedIn() || !phone() || !sheetDue(readCardState(), Date.now())) return;
    if (document.visibilityState === 'hidden' || somethingOpen()) {
      // Something else has the member's attention; try once more a little later.
      if (attempt < 1 && typeof setTimeout === 'function') sheetTimer = setTimeout(() => showSheet(attempt + 1), SHEET_DELAY_MS * 2);
      return;
    }
    if (await alreadyUsesApp()) return;
    const copy = sheetCopy();
    const summary = $('installAppSheetSummary');
    const action = $('installAppSheetInstall');
    if (summary) summary.textContent = copy.summary;
    if (action) action.textContent = copy.action;
    const state = readCardState();
    writeCardState({ ...state, sheetAt: Date.now(), sheetShows: (Number(state.sheetShows) || 0) + 1 });
    hideCard();
    sheet.hidden = false;
    sheetActive = true;
    track('install_sheet_shown', 'offer_sheet');
  }

  function renderCard() {
    const card = $('installAppCard');
    if (!signedIn()) {
      hideCard();
      hideSheet();
      return;
    }
    const state = readCardState();
    const now = Date.now();
    // Phones get the note at the bottom instead of a card in the middle of the home screen.
    if (phone() && $('installAppSheet')) {
      hideCard();
      if (!sheetActive && sheetTimer === null && sheetDue(state, now) && typeof setTimeout === 'function') {
        sheetTimer = setTimeout(() => showSheet(0), SHEET_DELAY_MS);
      }
      return;
    }
    if (!card) return;
    if (!cardDue(state, now)) {
      hideCard();
      return;
    }
    if (card.hidden && !deferredPrompt) {
      // Usually answered from today's saved check; otherwise the card goes away again once the server says so.
      alreadyUsesApp().then(uses => { if (uses) hideCard(); });
    }
    const copy = cardCopy();
    const title = $('installAppCardTitle');
    const summary = $('installAppCardSummary');
    if (title) title.textContent = copy.title;
    if (summary) summary.textContent = copy.summary;
    if (card.hidden) track('install_card_shown', 'offer_card');
    card.hidden = false;
    cardActive = true;
  }

  function refreshInstallCard() {
    noteAppOpen();
    if (!signedIn()) {
      hideCard();
      hideSheet();
      return;
    }
    let state = recordVisit(readCardState(), Date.now());
    // Opened from the installed app: this device already has it, so the card never returns here.
    if (standalone()) state = { ...state, installed: true };
    writeCardState(state);
    renderCard();
  }

  function snoozeCard(countAsDismissal) {
    const state = readCardState();
    writeCardState({
      ...state,
      snoozedAt: Date.now(),
      dismissals: (Number(state.dismissals) || 0) + (countAsDismissal ? 1 : 0),
    });
    hideCard();
    hideSheet();
  }

  async function installFromOffer(place) {
    if (deferredPrompt) {
      track(`install_${place}_accepted`);
      const outcome = await installFrom(place);
      if (outcome === 'accepted') {
        hideCard();
        hideSheet();
        return;
      }
      // The browser's own dialog was closed without installing: rest for a while,
      // but don't count it against the two "Not now" answers.
      snoozeCard(false);
      return;
    }
    if (canInstall()) {
      await installFrom(place);
      snoozeCard(false);
    }
  }

  // ------------------------------------------------------------ opens from the home screen

  // Once a day per device, the installed app reports that it was opened, so Site stats can count
  // members who keep it. A guest open that later signs in reports once more, without counting twice.
  function noteAppOpen() {
    if (!standalone()) return;
    const member = signedIn();
    const today = localDay(Date.now());
    let saved = '';
    try { saved = window.localStorage.getItem(OPENED_KEY) || ''; } catch (error) { return; }
    const [day, who] = saved.split('|');
    if (day === today && (who === 'member' || !member)) return;
    try { window.localStorage.setItem(OPENED_KEY, `${today}|${member ? 'member' : 'guest'}`); } catch (error) { return; }
    send('opened', day === today ? { repeat: true } : undefined);
  }

  // ------------------------------------------------------------ app icon badge

  // Unread notifications on the installed app's icon. Browsers without the
  // Badging API, or a page that is not installed, simply ignore it.
  function setAppIconBadge(count) {
    try {
      const nav = window.navigator;
      const value = Math.max(0, Math.floor(Number(count) || 0));
      if (value > 0 && typeof nav.setAppBadge === 'function') {
        nav.setAppBadge(value).catch(() => {});
      } else if (value === 0 && typeof nav.clearAppBadge === 'function') {
        nav.clearAppBadge().catch(() => {});
      }
    } catch (error) { /* optional */ }
  }

  // ------------------------------------------------------------ events

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    deferredPrompt = event;
    updateInstallButton();
    // The browser often decides the app is installable after the dashboard has drawn.
    if (signedIn()) renderCard();
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    updateInstallButton();
    if (signedIn()) writeCardState({ ...readCardState(), installed: true });
    hideCard();
    hideSheet();
    track('app_installed', 'installed');
  });

  document.addEventListener('click', async event => {
    const target = event.target;
    if (!target || !target.closest) return;
    if (target.closest('#installAppDialogClose')) {
      const dialog = $('installAppDialog');
      if (dialog) dialog.close();
      return;
    }
    const copy = target.closest('[data-install-copy-link]');
    if (copy) {
      event.preventDefault();
      await copyLink(copy);
      return;
    }
    if (target.closest('#installAppCardInstall')) {
      event.preventDefault();
      await installFromOffer('card');
      return;
    }
    if (target.closest('#installAppCardDismiss')) {
      event.preventDefault();
      track('install_card_dismissed', 'later_card');
      snoozeCard(true);
      return;
    }
    if (target.closest('#installAppSheetInstall')) {
      event.preventDefault();
      await installFromOffer('sheet');
      return;
    }
    if (target.closest('#installAppSheetDismiss')) {
      event.preventDefault();
      track('install_sheet_dismissed', 'later_sheet');
      snoozeCard(true);
      return;
    }
    const pageButton = target.closest('[data-install-app]');
    if (pageButton) {
      event.preventDefault();
      const place = pageButton.getAttribute('data-install-app') === 'page' ? 'page' : 'menu';
      await installFrom(place);
      return;
    }
    const button = target.closest('#installAppBtn');
    if (!button) return;
    if (!installRoute()) return;
    event.preventDefault();
    if (cardActive) hideCard();
    hideSheet();
    await installFrom('menu');
  });

  window.refreshInstallCard = refreshInstallCard;
  window.resetInstallCard = () => { hideCard(); hideSheet(); };
  window.setAppIconBadge = setAppIconBadge;
  // The notification bell on iPhone sends people here: notifications need the app there.
  window.showInstallSteps = place => {
    send(`install_${place === 'bell' ? 'bell' : 'menu'}`);
    return showSteps(installRoute() || (appleMobile() ? 'ios_safari' : ''));
  };
  window.omniInstall = { route: installRoute, iosSafari, platform };

  function start() {
    updateInstallButton();
    noteAppOpen();
    // In case the dashboard was drawn before this deferred script ran.
    if ($('installAppCard') && signedIn()) refreshInstallCard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();

  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register);
})();
