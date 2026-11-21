/* Shared behaviour for the public site header: close a menu after a choice,
   on an outside click, or with Escape (focus returns to its button), and keep
   only one menu open at a time. */
(function () {
  const MENUS = 'details.site-menu[open], details.site-dd[open]';

  function openMenus() {
    return document.querySelectorAll(MENUS);
  }

  document.addEventListener('click', function (event) {
    openMenus().forEach(function (menu) {
      if (!menu.contains(event.target) || event.target.closest('.site-menu__panel a, .site-dd__panel a')) menu.open = false;
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

  // "toggle" does not bubble, so listen in the capture phase.
  document.addEventListener('toggle', function (event) {
    const menu = event.target;
    if (!menu || !menu.matches || !menu.matches('details.site-menu, details.site-dd')) return;
    if (menu.open) {
      openMenus().forEach(function (other) { if (other !== menu) other.open = false; });
    }
    if (menu.matches('details.site-menu') && document.body) {
      document.body.classList.toggle('site-menu-open', menu.open);
    }
  }, true);
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

/* The header firms up once the page scrolls (site.css .site-header.is-scrolled). */
(function () {
  const header = document.querySelector('.site-header');
  if (!header) return;
  let queued = false;
  const update = function () {
    queued = false;
    header.classList.toggle('is-scrolled', window.scrollY > 8);
  };
  window.addEventListener('scroll', function () {
    if (!queued) { queued = true; window.requestAnimationFrame(update); }
  }, { passive: true });
  update();
})();

/* Phones: each footer column folds into its heading, which becomes a button that
   opens the links. Wider screens (and pages without scripts) show every column. */
(function () {
  const footer = document.querySelector('.site-footer');
  if (!footer || !window.matchMedia) return;
  const narrow = window.matchMedia('(max-width: 640px)');
  const columns = Array.from(footer.querySelectorAll('.site-footer__col'));

  const fold = function () {
    columns.forEach(function (column) {
      const heading = column.querySelector('h2');
      const links = column.querySelector('.site-footer__links');
      if (!heading || !links || heading.querySelector('button')) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'site-footer__toggle';
      button.setAttribute('aria-expanded', 'false');
      if (links.id) button.setAttribute('aria-controls', links.id);
      button.textContent = heading.textContent;
      heading.textContent = '';
      heading.appendChild(button);
      button.addEventListener('click', function () {
        const open = button.getAttribute('aria-expanded') !== 'true';
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        column.classList.toggle('is-open', open);
      });
    });
    footer.classList.add('is-folding');
  };

  const unfold = function () {
    columns.forEach(function (column) {
      const heading = column.querySelector('h2');
      const button = heading && heading.querySelector('button');
      if (!button) return;
      heading.textContent = button.textContent;
      column.classList.remove('is-open');
    });
    footer.classList.remove('is-folding');
  };

  const sync = function () { if (narrow.matches) fold(); else unfold(); };
  sync();
  if (narrow.addEventListener) narrow.addEventListener('change', sync);
})();
