try {
  if (localStorage.getItem('omnitrackr_user') || localStorage.getItem('omnitrackr_token')) {
    const root = document.documentElement;
    root.classList.add('authenticated');
    // Reserve the library's space until the cards above it settle. home.js clears
    // this class once they are ready. The cards are only asked for once the page has
    // parsed, so the three-second bound starts then: a phone that needs four seconds
    // for the scripts on a cold cache used to reveal the board before any card had
    // loaded, and the cards then pushed it down one by one. Ten seconds is the outer limit.
    root.classList.add('dashboard-settling');
    const reveal = () => root.classList.remove('dashboard-settling');
    document.addEventListener('DOMContentLoaded', () => setTimeout(reveal, 3000), { once: true });
    setTimeout(reveal, 10000);
  }
} catch (_) {
  // Authentication can recover the HttpOnly session without browser storage.
}
