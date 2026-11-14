// Drag to reorder the Next Up queue on the home page, with the arrow keys as the
// keyboard version. The rows and their handles are drawn by renderNextUpQueue
// (dashboard/home.js); this file only listens, then hands the new position to
// moveNextUp, which saves it and redraws the queue.
(function () {
  'use strict';

  const THRESHOLD = 6;
  const EDGE = 64;
  let drag = null;

  function list() { return document.getElementById('nextUpQueueItems'); }
  function busy() {
    return typeof dailyDashboardState !== 'undefined' && dailyDashboardState.mutationPending;
  }
  function total() {
    return typeof dailyDashboardState !== 'undefined' ? dailyDashboardState.items.length : 0;
  }
  function announce(text) {
    const status = document.getElementById('nextUpQueueStatus');
    if (status) status.textContent = text;
  }
  function save(handle, position) {
    if (typeof moveNextUp !== 'function') return;
    const id = Number(handle.dataset.nextUpId);
    announce(`Moved ${handle.dataset.nextUpTitle || 'that title'} to number ${position + 1} of ${total()}.`);
    moveNextUp(id, position);
  }

  function reset() {
    if (!drag) return;
    drag.rows.forEach(row => { row.style.transform = ''; row.classList.remove('is-dragging'); });
    list()?.classList.remove('is-sorting');
    document.documentElement.classList.remove('next-up-dragging');
  }

  document.addEventListener('pointerdown', event => {
    const handle = event.target.closest && event.target.closest('[data-next-up-handle]');
    const container = list();
    if (!handle || !container || !container.contains(handle) || event.button > 0 || busy()) return;
    const row = handle.closest('[data-next-up-row-id]');
    const rows = Array.from(container.querySelectorAll('[data-next-up-row-id]'));
    if (!row || rows.length < 2) return;
    event.preventDefault();
    try { handle.setPointerCapture(event.pointerId); } catch (error) { /* older browsers */ }
    const scroll = window.scrollY;
    const tops = rows.map(item => { const rect = item.getBoundingClientRect(); return { top: rect.top + scroll, height: rect.height }; });
    const gap = tops.length > 1 ? Math.max(tops[1].top - (tops[0].top + tops[0].height), 0) : 8;
    const from = rows.indexOf(row);
    drag = { handle, row, rows, tops, gap, from, to: from, startY: event.clientY + scroll, pointerId: event.pointerId, moved: false };
  });

  document.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (event.clientY < EDGE) window.scrollBy(0, -12);
    else if (event.clientY > window.innerHeight - EDGE) window.scrollBy(0, 12);
    const dy = event.clientY + window.scrollY - drag.startY;
    if (!drag.moved && Math.abs(dy) < THRESHOLD) return;
    if (!drag.moved) {
      drag.moved = true;
      drag.row.classList.add('is-dragging');
      list()?.classList.add('is-sorting');
      document.documentElement.classList.add('next-up-dragging');
    }
    drag.row.style.transform = `translateY(${dy}px)`;
    const own = drag.tops[drag.from];
    const middle = own.top + own.height / 2 + dy;
    // The new index is how many of the other rows now sit above the dragged one.
    drag.to = drag.tops.filter((rect, index) => index !== drag.from && rect.top + rect.height / 2 < middle).length;
    const shift = own.height + drag.gap;
    drag.rows.forEach((row, index) => {
      if (index === drag.from) return;
      let offset = 0;
      if (drag.from < drag.to && index > drag.from && index <= drag.to) offset = -shift;
      if (drag.to < drag.from && index >= drag.to && index < drag.from) offset = shift;
      row.style.transform = offset ? `translateY(${offset}px)` : '';
    });
  });

  function end(event, cancelled) {
    if (!drag || (event && event.pointerId !== drag.pointerId)) return;
    const { handle, from, to, moved } = drag;
    reset();
    drag = null;
    if (!cancelled && moved && to !== from) save(handle, to);
  }
  document.addEventListener('pointerup', event => end(event, false));
  document.addEventListener('pointercancel', event => end(event, true));

  document.addEventListener('keydown', event => {
    if (drag && event.key === 'Escape') { reset(); drag = null; return; }
    const handle = event.target.closest && event.target.closest('[data-next-up-handle]');
    if (!handle || !list()?.contains(handle)) return;
    const index = Number(handle.dataset.nextUpIndex);
    const last = total() - 1;
    const target = { ArrowUp: index - 1, ArrowDown: index + 1, Home: 0, End: last }[event.key];
    if (target === undefined) return;
    event.preventDefault();
    if (busy() || target < 0 || target > last || target === index) return;
    save(handle, target);
  });
})();
