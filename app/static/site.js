/* Shared behaviour for the public site header: close the compact menu after a
   choice, on an outside click, or with Escape (focus returns to its button). */
(function () {
  function openMenus() {
    return document.querySelectorAll('details.site-menu[open]');
  }

  document.addEventListener('click', function (event) {
    openMenus().forEach(function (menu) {
      if (!menu.contains(event.target) || event.target.closest('.site-menu__panel a')) menu.open = false;
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    openMenus().forEach(function (menu) {
      menu.open = false;
      const summary = menu.querySelector('summary');
      if (summary) summary.focus();
    });
  });
})();
