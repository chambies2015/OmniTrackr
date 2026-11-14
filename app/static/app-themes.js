// Signed-in app: remembers light or night mode on this device, and applies a supporter's app
// theme before the first paint. Loaded right after <body> opens, so it must stay small and
// must never throw. supporter.js keeps the saved theme in step with the server.
(function () {
  'use strict';

  const MODE_KEY = 'ot-color-mode';
  const THEME_KEY = 'ot-app-theme';
  const NAME = /^[a-z]{1,16}$/;
  const body = document.body;
  if (!body) return;

  function read(storage, key) {
    try { return window[storage].getItem(key); } catch (error) { return null; }
  }

  function write(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
    } catch (error) { /* private mode: this page still switches */ }
  }

  // Who is signed in on this device, from the copy auth.js keeps. The theme belongs to one member.
  function memberKey() {
    try {
      const user = JSON.parse(read('sessionStorage', 'omnitrackr_session_user') || read('localStorage', 'omnitrackr_user') || 'null');
      if (!user || typeof user !== 'object') return null;
      if (user.id !== undefined && user.id !== null) return `id:${user.id}`;
      return typeof user.username === 'string' && user.username ? `name:${user.username}` : null;
    } catch (error) { return null; }
  }

  function saved() {
    try {
      const value = JSON.parse(read('localStorage', THEME_KEY) || 'null');
      return value && typeof value === 'object' ? value : null;
    } catch (error) { return null; }
  }

  function show(theme) {
    if (theme && NAME.test(theme)) body.setAttribute('data-app-theme', theme);
    else body.removeAttribute('data-app-theme');
  }

  if (read('localStorage', MODE_KEY) === 'light') body.classList.remove('dark-mode');
  const record = saved();
  const who = memberKey();
  if (record && who && record.member === who) show(record.theme);

  function syncModeButton() {
    const button = document.getElementById('toggleMode');
    if (button) button.textContent = body.classList.contains('dark-mode') ? 'Light Mode' : 'Night Mode';
  }

  document.addEventListener('DOMContentLoaded', () => {
    syncModeButton();
    const button = document.getElementById('toggleMode');
    // library.js flips the class on click; store the result once it has.
    if (button) button.addEventListener('click', () => setTimeout(() => write(MODE_KEY, body.classList.contains('dark-mode') ? 'dark' : 'light'), 0));
  });

  window.OmniAppTheme = {
    // The server's answer: the theme this member may show right now (null for none).
    remember(theme) {
      const key = memberKey();
      // A member without a theme is stored too, so their next visit doesn't ask the server again.
      if (key) write(THEME_KEY, JSON.stringify({ member: key, theme: theme && NAME.test(theme) ? theme : null }));
      else write(THEME_KEY, null);
      show(theme);
    },
    // Try a theme on this page only. A reload goes back to the saved one.
    preview(theme) { show(theme); },
    restore() {
      const current = saved();
      show(current && current.member === memberKey() ? current.theme : null);
    },
    known() {
      const current = saved();
      return Boolean(current && current.member === memberKey());
    },
  };
})();
