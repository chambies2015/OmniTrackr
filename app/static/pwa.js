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
    const button = event.target.closest && event.target.closest('#installAppBtn');
    if (!button || !deferredPrompt) return;
    event.preventDefault();
    const prompt = deferredPrompt;
    deferredPrompt = null;
    button.hidden = true;
    try {
      await prompt.prompt();
      await prompt.userChoice;
    } catch (error) { /* the browser decides */ }
  });

  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register);
})();
