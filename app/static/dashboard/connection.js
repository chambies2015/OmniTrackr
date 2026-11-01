// Connection bar. Phones drop signal on trains and in lifts; without this the
// library just stops answering. While offline a thin bar says so (what is on
// screen stays usable to read), and when the connection returns the open
// library tab, the home cards and the notification count refresh by themselves.
(function () {
  'use strict';

  let bar = null;
  let hideTimer = null;
  let wentOffline = false;

  function ensureBar() {
    if (bar) return bar;
    bar = document.createElement('div');
    bar.id = 'connectionBar';
    bar.className = 'connection-bar';
    bar.setAttribute('role', 'status');
    bar.hidden = true;
    document.body.appendChild(bar);
    return bar;
  }

  function show(text, tone) {
    const node = ensureBar();
    clearTimeout(hideTimer);
    node.textContent = text;
    node.dataset.tone = tone;
    node.hidden = false;
  }

  function signedIn() {
    try { return typeof hasStoredAuth === 'function' && hasStoredAuth(); } catch (_) { return false; }
  }

  function goneOffline() {
    if (!signedIn()) return;
    wentOffline = true;
    show("You're offline. You can keep reading this page, but changes can't be saved until you reconnect.", 'offline');
  }

  function refreshAfterReconnect() {
    try {
      // Leave a half-finished edit alone; the member can press Refresh after saving.
      if (typeof editingRowId === 'undefined' || editingRowId === null) {
        const config = typeof libraryPageConfig === 'function' ? libraryPageConfig(currentTab) : null;
        if (config && typeof config[2] === 'function') Promise.resolve(config[2]()).catch(() => {});
      }
    } catch (_) { /* the Refresh button still works */ }
    try { if (typeof scheduleLibraryLaunchpadRefresh === 'function') scheduleLibraryLaunchpadRefresh(true); } catch (_) { /* optional */ }
    try { if (typeof updateNotificationCount === 'function') updateNotificationCount(); } catch (_) { /* optional */ }
  }

  function backOnline() {
    if (!wentOffline) return;
    wentOffline = false;
    show('Back online.', 'online');
    hideTimer = setTimeout(() => { if (bar) bar.hidden = true; }, 2500);
    refreshAfterReconnect();
  }

  if (typeof window.addEventListener !== 'function') return;
  window.addEventListener('offline', goneOffline);
  window.addEventListener('online', backOnline);
  // Opened with no signal (for example from the home screen icon on a train).
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', goneOffline, { once: true });
    else goneOffline();
  }
})();
