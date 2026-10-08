/* Installable-app support: registers the offline-only service worker and,
 * on the dashboard, offers an "Install app" button when the browser allows it. */
(function () {
  'use strict';

  const isLocalhost = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
  const canRegister = 'serviceWorker' in navigator && (window.location.protocol === 'https:' || isLocalhost);

  if (canRegister) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
        /* The site works exactly as before without the worker. */
      });
    });
  }

  function isStandalone() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
      || window.navigator.standalone === true;
  }

  function isIosSafari() {
    const ua = window.navigator.userAgent || '';
    const iOS = /iPad|iPhone|iPod/.test(ua) || (ua.includes('Macintosh') && navigator.maxTouchPoints > 1);
    return iOS && !/CriOS|FxiOS|EdgiOS/.test(ua);
  }

  let deferredPrompt = null;

  function installButton() {
    return document.getElementById('installAppBtn');
  }

  function showButton() {
    const button = installButton();
    if (button && !isStandalone()) button.hidden = false;
  }

  function hideButton() {
    const button = installButton();
    if (button) button.hidden = true;
  }

  function showIosHelp() {
    const dialog = document.getElementById('installAppDialog');
    if (dialog && typeof dialog.showModal === 'function') {
      dialog.showModal();
    }
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;
    showButton();
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    hideButton();
  });

  function init() {
    const button = installButton();
    if (!button) return;
    if (isStandalone()) {
      document.documentElement.classList.add('is-installed-app');
      hideButton();
      return;
    }
    if (deferredPrompt || isIosSafari()) showButton();

    button.addEventListener('click', async () => {
      if (deferredPrompt) {
        const prompt = deferredPrompt;
        deferredPrompt = null;
        prompt.prompt();
        try {
          const choice = await prompt.userChoice;
          if (choice && choice.outcome === 'accepted') hideButton();
        } catch (error) {
          /* Ignore: the browser closed the prompt. */
        }
        return;
      }
      if (isIosSafari()) showIosHelp();
    });

    const close = document.getElementById('installAppDialogClose');
    if (close) {
      close.addEventListener('click', () => {
        const dialog = document.getElementById('installAppDialog');
        if (dialog) dialog.close();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
