// Registers the service worker and offers "Install app" where the browser supports it.
(function () {
  'use strict';

  let deferredPrompt = null;

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

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    deferredPrompt = event;
    const button = installButton();
    if (button && !standalone()) button.hidden = false;
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const button = installButton();
    if (button) button.hidden = true;
  });

  document.addEventListener('click', async event => {
    if (event.target.closest && event.target.closest('#installAppDialogClose')) {
      const dialog = document.getElementById('installAppDialog');
      if (dialog) dialog.close();
      return;
    }
    const button = event.target.closest && event.target.closest('#installAppBtn');
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
    try {
      await prompt.prompt();
      await prompt.userChoice;
    } catch (error) { /* the browser decides */ }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', offerIosInstall);
  else offerIosInstall();

  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register);
})();
