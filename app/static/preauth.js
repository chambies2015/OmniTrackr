if (localStorage.getItem('omnitrackr_user') || localStorage.getItem('omnitrackr_token')) {
  document.documentElement.classList.add('authenticated');
}
