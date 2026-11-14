// /supporters: count Ko-fi button presses (an anonymous daily counter, nothing about the visitor),
// and the "Try it on" preview, which only changes classes on this page.
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

  const NAME = /^[a-z_]{1,16}$/;
  const profile = document.querySelector('[data-try-profile]');
  const banner = document.querySelector('[data-try-banner]');
  const frame = document.querySelector('[data-try-frame]');
  const app = document.querySelector('[data-try-app]');
  const night = document.querySelector('[data-try-night]');
  const stage = document.querySelector('.support-try__stage');
  if (!profile || !banner || !frame || !app || !stage) return;

  const picked = { theme: 'default', accent: 'violet', banner: 'aurora', frame: 'halo' };

  function swapClass(node, prefix, value) {
    Array.from(node.classList).filter(name => name.startsWith(prefix)).forEach(name => node.classList.remove(name));
    if (value) node.classList.add(prefix + value);
  }

  function render() {
    swapClass(profile, 'support-try__profile--', picked.accent);
    swapClass(app, 'support-try__app--', picked.theme);
    app.classList.toggle('support-try__app--light', !!night && !night.checked);
    banner.hidden = picked.banner === 'none';
    if (picked.banner !== 'none') swapClass(banner, 'profile-banner--', picked.banner);
    swapClass(frame, 'avatar-frame--', picked.frame === 'none' ? '' : picked.frame);
    const art = frame.querySelector('.avatar-frame__art');
    if (art) art.hidden = picked.frame === 'none';
  }

  document.querySelectorAll('[data-try]').forEach(button => {
    button.addEventListener('click', () => {
      const kind = button.getAttribute('data-try');
      const value = button.getAttribute('data-value');
      if (!Object.prototype.hasOwnProperty.call(picked, kind) || !NAME.test(value || '')) return;
      picked[kind] = value;
      document.querySelectorAll(`[data-try="${kind}"]`).forEach(other => other.setAttribute('aria-pressed', other === button ? 'true' : 'false'));
      render();
    });
  });
  if (night) night.addEventListener('change', render);
  stage.classList.add('is-ready');
  render();
})();
