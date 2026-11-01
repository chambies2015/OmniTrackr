// Registers the service worker and offers "Install app" where the browser supports it.
// Returning members also see a dismissible install card on the dashboard, and the
// installed app's icon shows the unread notification count where the system allows.
(function () {
  'use strict';

  const DAY_MS = 24 * 60 * 60 * 1000;
  const CARD_MIN_VISIT_DAYS = 3; // never on a first visit: only once someone keeps coming back
  const CARD_SNOOZE_DAYS = 30;
  const CARD_MAX_DISMISSALS = 2; // after the second "Not now" the card stays away for good

  let deferredPrompt = null;
  let cardActive = false;

  function installButton() {
    return document.getElementById('installAppBtn');
  }

  function standalone() {
    try {
      return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    } catch (error) {
      return false;
    }
  }

  // iPhone and iPad Safari never fire beforeinstallprompt, so the button opens
  // short Add to Home Screen steps there instead. iPadOS reports a Mac user agent.
  function iosSafari() {
    const ua = window.navigator.userAgent || '';
    const iOS = /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && window.navigator.maxTouchPoints > 1);
    return iOS && !/CriOS|FxiOS|EdgiOS/.test(ua);
  }

  function touchDevice() {
    try {
      return window.matchMedia('(pointer: coarse)').matches;
    } catch (error) {
      return false;
    }
  }

  function track(name) {
    try {
      if (typeof window.gtag === 'function') window.gtag('event', name, { event_category: 'install_app' });
    } catch (error) { /* analytics is optional */ }
  }

  function showIosHelp() {
    const dialog = document.getElementById('installAppDialog');
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  }

  function offerIosInstall() {
    const button = installButton();
    if (button && iosSafari() && !standalone()) button.hidden = false;
  }

  function register() {
    if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => { /* optional */ });
  }

  // ------------------------------------------------------------ install card

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

  function canInstall() {
    return !standalone() && (deferredPrompt !== null || iosSafari());
  }

  function cardDue(state, now) {
    if (state.installed || !canInstall()) return false;
    if ((Number(state.days) || 0) < CARD_MIN_VISIT_DAYS) return false;
    if ((Number(state.dismissals) || 0) >= CARD_MAX_DISMISSALS) return false;
    const snoozedAt = Number(state.snoozedAt) || 0;
    return !snoozedAt || now - snoozedAt >= CARD_SNOOZE_DAYS * DAY_MS;
  }

  function cardCopy() {
    if (iosSafari() || touchDevice()) {
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

  function hideCard() {
    const card = document.getElementById('installAppCard');
    if (card) card.hidden = true;
    cardActive = false;
  }

  function renderCard() {
    const card = document.getElementById('installAppCard');
    if (!card) return;
    if (!signedIn() || !cardDue(readCardState(), Date.now())) {
      hideCard();
      return;
    }
    const copy = cardCopy();
    const title = document.getElementById('installAppCardTitle');
    const summary = document.getElementById('installAppCardSummary');
    if (title) title.textContent = copy.title;
    if (summary) summary.textContent = copy.summary;
    if (card.hidden) track('install_card_shown');
    card.hidden = false;
    cardActive = true;
  }

  function refreshInstallCard() {
    if (!signedIn()) {
      hideCard();
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
  }

  async function installFromCard() {
    if (deferredPrompt) {
      const prompt = deferredPrompt;
      deferredPrompt = null;
      const button = installButton();
      if (button) button.hidden = true;
      track('install_card_accepted');
      try {
        await prompt.prompt();
        const choice = await prompt.userChoice;
        if (choice && choice.outcome === 'accepted') {
          writeCardState({ ...readCardState(), installed: true });
          hideCard();
          return;
        }
      } catch (error) { /* the browser decides */ }
      // The browser's own dialog was closed without installing: rest for a while,
      // but don't count it against the two "Not now" answers.
      snoozeCard(false);
      return;
    }
    if (iosSafari() && !standalone()) {
      track('install_card_ios_steps');
      showIosHelp();
      snoozeCard(false);
    }
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
    const button = installButton();
    if (button && !standalone()) button.hidden = false;
    // The browser often decides the app is installable after the dashboard has drawn.
    if (signedIn()) renderCard();
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const button = installButton();
    if (button) button.hidden = true;
    if (signedIn()) writeCardState({ ...readCardState(), installed: true });
    hideCard();
    track('app_installed');
  });

  document.addEventListener('click', async event => {
    const target = event.target;
    if (!target || !target.closest) return;
    if (target.closest('#installAppDialogClose')) {
      const dialog = document.getElementById('installAppDialog');
      if (dialog) dialog.close();
      return;
    }
    if (target.closest('#installAppCardInstall')) {
      event.preventDefault();
      await installFromCard();
      return;
    }
    if (target.closest('#installAppCardDismiss')) {
      event.preventDefault();
      track('install_card_dismissed');
      snoozeCard(true);
      return;
    }
    const button = target.closest('#installAppBtn');
    if (!button) return;
    if (!deferredPrompt) {
      if (iosSafari() && !standalone()) {
        event.preventDefault();
        showIosHelp();
      }
      return;
    }
    event.preventDefault();
    const prompt = deferredPrompt;
    deferredPrompt = null;
    button.hidden = true;
    if (cardActive) hideCard();
    try {
      await prompt.prompt();
      await prompt.userChoice;
    } catch (error) { /* the browser decides */ }
  });

  window.refreshInstallCard = refreshInstallCard;
  window.resetInstallCard = hideCard;
  window.setAppIconBadge = setAppIconBadge;

  function start() {
    offerIosInstall();
    // In case the dashboard was drawn before this deferred script ran.
    if (document.getElementById('installAppCard') && signedIn()) refreshInstallCard();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();

  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register);
})();
