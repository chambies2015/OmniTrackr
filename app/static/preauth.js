if (localStorage.getItem('omnitrackr_user') || localStorage.getItem('omnitrackr_token')) {
  document.documentElement.classList.add('authenticated');
  // The home cards above the library arrive a moment after the library itself.
  // Keep the library invisible (its space stays reserved) until they settle, so
  // it does not jump down the page. dashboard/home.js clears this once the cards
  // are in; the timer makes sure it never waits longer than three seconds.
  document.documentElement.classList.add('dashboard-settling');
  setTimeout(() => document.documentElement.classList.remove('dashboard-settling'), 3000);
}
