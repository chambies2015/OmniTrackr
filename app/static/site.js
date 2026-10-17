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

/* Long-form guides: a reading-time line under the title, a reading progress
   bar, and on wide screens a sticky "On this page" rail that marks the
   section being read. Pages read the same without it. */
(function () {
  const main = document.querySelector('body.public-reader .reader-main');
  if (!main) return;
  const header = main.querySelector(':scope > header');
  const words = (main.innerText || '').split(/\s+/).filter(Boolean).length;

  if (header && words >= 500 && !main.querySelector('.reader-meta, .guide-updated, .reader-byline, .last-updated')) {
    const parts = [`${Math.max(2, Math.round(words / 230))} min read`];
    try {
      const data = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
        .map(node => JSON.parse(node.textContent))
        .find(item => item && item.dateModified);
      const date = data && new Date(`${data.dateModified}T12:00:00Z`);
      if (date && !Number.isNaN(date.getTime())) {
        parts.push(`Updated ${date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}`);
      }
    } catch (_) { /* the reading time alone is fine */ }
    const meta = document.createElement('p');
    meta.className = 'reader-meta';
    meta.textContent = parts.join(' · ');
    header.appendChild(meta);
  }

  if (words >= 500) {
    const bar = document.createElement('div');
    bar.className = 'reader-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    let queued = false;
    const update = () => {
      queued = false;
      const end = main.offsetTop + main.offsetHeight - window.innerHeight;
      const share = end > 0 ? Math.min(1, Math.max(0, window.scrollY / end)) : 1;
      bar.style.transform = `scaleX(${share})`;
    };
    window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
    window.addEventListener('resize', update, { passive: true });
    update();
  }

  const contents = main.querySelector(':scope > .reader-contents');
  if (!contents) return;
  const wide = window.matchMedia('(min-width: 1100px)');
  const sync = () => { if (wide.matches) contents.open = true; };
  sync();
  if (wide.addEventListener) wide.addEventListener('change', sync);

  const links = Array.from(contents.querySelectorAll('nav a[href^="#"]'));
  const targets = links.map(link => document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean);
  if (!targets.length || !('IntersectionObserver' in window)) return;
  const mark = id => links.forEach(link => {
    if (link.hash.slice(1) === id) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  const visible = new Set();
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) visible.add(entry.target); else visible.delete(entry.target); });
    const first = targets.find(target => visible.has(target));
    if (first) mark(first.id);
  }, { rootMargin: '-90px 0px -55% 0px' });
  targets.forEach(target => observer.observe(target));
})();
