// /supporters: count Ko-fi button presses (an anonymous daily counter, nothing about the visitor).
(function () {
  'use strict';

  document.querySelectorAll('[data-kofi]').forEach(link => {
    link.addEventListener('click', () => {
      try {
        if (navigator.sendBeacon) {
          navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event: 'supporters_kofi_clicked' })], { type: 'application/json' }));
        }
      } catch (error) { /* counting is optional */ }
    });
  });
})();
