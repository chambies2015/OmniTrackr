// Guide pages: a thin reading-progress line under the header, and the contents
// rail marks the section you are reading. Both are extras; the page works without them.
(() => {
  const article = document.querySelector('.trail-guide');
  const body = article && article.querySelector('.guide-body');
  if (!body) return;

  const bar = document.createElement('div');
  bar.className = 'guide-progress';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);

  let queued = false;
  const update = () => {
    queued = false;
    const box = body.getBoundingClientRect();
    const span = box.height - window.innerHeight * 0.6;
    const done = span > 0 ? Math.min(1, Math.max(0, -box.top / span)) : 1;
    bar.style.transform = `scaleX(${done})`;
    bar.classList.toggle('is-on', box.top < 0 && done < 1);
  };
  const queue = () => {
    if (!queued) { queued = true; window.requestAnimationFrame(update); }
  };
  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  update();

  const links = Array.from(article.querySelectorAll('.guide-toc a[href^="#"]'));
  if (!links.length || !('IntersectionObserver' in window)) return;
  const targets = links
    .map(link => {
      try { return [link, document.getElementById(decodeURIComponent(link.hash.slice(1)))]; } catch (e) { return [link, null]; }
    })
    .filter(([, target]) => target);
  const visible = new Set();
  const mark = () => {
    // The first section still on screen, or the last one passed when none is.
    let current = targets.find(([, target]) => visible.has(target));
    if (!current) {
      const passed = targets.filter(([, target]) => target.getBoundingClientRect().top < 120);
      current = passed[passed.length - 1];
    }
    links.forEach(link => link.removeAttribute('aria-current'));
    if (current) current[0].setAttribute('aria-current', 'location');
  };
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => (entry.isIntersecting ? visible.add(entry.target) : visible.delete(entry.target)));
    mark();
  }, { rootMargin: '-88px 0px -55% 0px' });
  targets.forEach(([, target]) => observer.observe(target));
})();
