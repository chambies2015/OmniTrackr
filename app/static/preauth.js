try {
  if (localStorage.getItem('omnitrackr_user') || localStorage.getItem('omnitrackr_token')) {
    document.documentElement.classList.add('authenticated');
    // Reserve the library's space until the cards above it settle. home.js clears
    // this class once ready; the timer bounds the wait to three seconds.
    document.documentElement.classList.add('dashboard-settling');
    setTimeout(() => document.documentElement.classList.remove('dashboard-settling'), 3000);
  }
} catch (_) {
  // Authentication can recover the HttpOnly session without browser storage.
}
