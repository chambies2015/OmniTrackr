// Public profiles (/u/<username>): section tabs, the phone join bar for visitors, sign-up clicks.
(function () {
  'use strict';

  function report(event) {
    try {
      if (navigator.sendBeacon && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  // ---------- "On this page" tabs: sit under the sticky header, mark the section in view ----------
  function setupTabs() {
    const tabs = document.querySelector('.profile-tabs');
    if (!tabs) return;
    const header = document.querySelector('.site-header');
    const place = () => {
      const height = header ? Math.round(header.getBoundingClientRect().height) : 0;
      document.documentElement.style.setProperty('--title-tabs-top', `${height}px`);
    };
    place();
    window.addEventListener('resize', place);
    if (typeof IntersectionObserver !== 'function') return;
    const links = new Map();
    tabs.querySelectorAll('a[href^="#"]').forEach(link => {
      const heading = document.getElementById(link.getAttribute('href').slice(1));
      const section = heading && (heading.closest('section') || heading);
      if (section) links.set(section, link);
    });
    const visible = new Set();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => (entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target)));
      let current = null;
      links.forEach((link, section) => { if (!current && visible.has(section)) current = link; });
      links.forEach(link => {
        if (link === current) {
          link.setAttribute('aria-current', 'true');
          const strip = link.parentElement;
          if (strip.scrollWidth > strip.clientWidth) strip.scrollTo({ left: link.offsetLeft - 16, behavior: 'smooth' });
        } else {
          link.removeAttribute('aria-current');
        }
      });
    }, { rootMargin: '-35% 0px -55% 0px' });
    links.forEach((link, section) => observer.observe(section));
  }

  // ---------- Phone join bar: shows once the header buttons scroll away, hides at the closing card ----------
  function setupJoinbar() {
    const bar = document.querySelector('[data-profile-joinbar]');
    if (!bar || typeof IntersectionObserver !== 'function') return;
    const actions = document.querySelector('.profile-hero__actions');
    const closing = document.querySelector('.profile-cta');
    const seen = new Map();
    const update = () => {
      const show = seen.get(actions) === false && seen.get(closing) !== true;
      bar.classList.toggle('is-shown', show);
      document.body.classList.toggle('profile-page--joinbar', show);
    };
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => seen.set(entry.target, entry.isIntersecting));
      update();
    });
    [actions, closing].forEach(node => { if (node) observer.observe(node); });
  }

  if (typeof document === 'undefined') return;
  document.addEventListener('click', event => {
    const link = event.target.closest && event.target.closest('[data-profile-join]');
    if (link) report('profile_signup_clicked');
  });
  const start = () => { setupTabs(); setupJoinbar(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
