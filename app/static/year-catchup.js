// The year's big ones on "Fill in your year" (app/year_catchup.py): tap a poster, pick the month, and the
// title is saved to the library and counted in the recap. The grid arrives drawn by the server as plain
// forms (the emailed page posts them as they are); here they save without a reload, one poster stays open
// at a time, and covers the site doesn't have yet are looked up as they scroll into view.
// Text from the server is only ever set as textContent.
(function () {
  'use strict';

  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];

  // The month numbers a poster offers: from the month it came out to the last month that can be picked.
  function monthsFrom(from, last) {
    const start = Math.max(1, Math.min(12, Number(from) || 1));
    const end = Math.max(0, Math.min(12, Number(last) || 0));
    const out = [];
    for (let month = start; month <= end; month += 1) out.push(month);
    return out;
  }

  // The line under an answered poster.
  function saidText(state, verb, month) {
    if (state === 'month') return month >= 1 && month <= 12 ? `${verb} in ${MONTHS[month - 1]}` : verb;
    if (state === 'want' || state === 'library_saved') return 'On your list';
    if (state === 'library_done') return 'In your library';
    if (state === 'no') return 'Not for me';
    return '';
  }

  // "month-7" -> {answer: "month", month: 7}; "want" / "no" / "undo" as they are; anything else null.
  function parseChoice(value) {
    const text = String(value || '');
    if (text === 'want' || text === 'no' || text === 'undo') return { answer: text, month: null };
    const match = /^month-(\d{1,2})$/.exec(text);
    if (!match) return null;
    const month = Number(match[1]);
    return month >= 1 && month <= 12 ? { answer: 'month', month } : null;
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { monthsFrom, saidText, parseChoice };
  if (typeof document === 'undefined') return;

  const root = document.querySelector('[data-yc]');
  if (!root || root.closest('.yf--emailed')) return;
  const year = Number(root.dataset.year);
  if (!Number.isInteger(year)) return;
  const api = `/api/year-in-review/${year}/big-ones`;
  const lastMonth = Number(root.dataset.monthsLast) || 0;
  const state = { busy: false, clicked: null };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function showError(message) {
    const box = root.querySelector('[data-yc-error]');
    if (!box) return;
    box.textContent = message || '';
    box.hidden = !message;
  }

  async function call(path, body) {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (response.status === 401) {
      window.location.href = '/#login';
      throw new Error('Please log in again.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0] && data.detail[0].msg : data.detail;
      if (response.status === 429) throw new Error('That was quick. Wait a moment and tap again.');
      throw new Error(String(detail || 'That didn’t save. Please try again.'));
    }
    return data;
  }

  // ------------------------------------------------------------ the two ways a poster looks

  function posterOf(item) {
    const poster = item.querySelector('.yc-poster');
    const copy = poster ? poster.cloneNode(true) : el('span', 'yc-poster');
    copy.querySelectorAll('.yc-badge').forEach(node => node.remove());
    return copy;
  }

  function nameOf(item) {
    const name = item.querySelector('.yc-name');
    const when = item.querySelector('.yc-when');
    return [el('span', 'yc-name', name ? name.textContent : ''), el('span', 'yc-when', when ? when.textContent : '')];
  }

  function hidden(name, value) {
    const input = el('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    return input;
  }

  function drawAnswered(item, answer, month) {
    const poster = posterOf(item);
    const badge = el('span', 'yc-badge', answer === 'month' || answer === 'library_done' ? '✓'
      : (answer === 'no' ? '–' : '+'));
    badge.setAttribute('aria-hidden', 'true');
    poster.appendChild(badge);
    const face = el('div', 'yc-face');
    face.append(poster, ...nameOf(item), el('span', 'yc-said', saidText(answer, item.dataset.verb || 'Finished', month)));
    const parts = [face];
    if (answer === 'month' || answer === 'want' || answer === 'no') {
      const form = el('form', 'yc-change');
      form.method = 'post';
      form.dataset.ycForm = '';
      const change = el('button', 'yf-link', 'Change');
      change.type = 'submit';
      change.name = 'choice';
      change.value = 'undo';
      change.setAttribute('aria-label', `Change your answer for ${nameOf(item)[0].textContent}`);
      form.append(hidden('pick', item.dataset.id), change);
      parts.push(form);
    }
    item.className = `yc-item is-answered is-${answer}`;
    item.dataset.state = answer;
    item.replaceChildren(...parts);
  }

  function drawOpen(item) {
    const [name, when] = nameOf(item);
    const details = el('details', 'yc-pick');
    const summary = el('summary', 'yc-face');
    summary.append(posterOf(item), name, when, el('span', 'yc-tap', 'I got to it'));
    const form = el('form', 'yc-ask');
    form.method = 'post';
    form.dataset.ycForm = '';
    const question = item.dataset.question || 'When did you get to it?';
    const row = el('div', 'yf-months yc-months');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', `${name.textContent}: ${question}`);
    const today = new Date();
    monthsFrom(item.dataset.from, lastMonth).forEach(month => {
      const current = year === today.getFullYear() && month === today.getMonth() + 1;
      const button = el('button', `yf-month${current ? ' yf-month--now' : ''}`, MONTHS[month - 1].slice(0, 3));
      button.type = 'submit';
      button.name = 'choice';
      button.value = `month-${month}`;
      button.setAttribute('aria-label', `${MONTHS[month - 1]} ${year}${current ? ' (this month)' : ''}`);
      row.appendChild(button);
    });
    const others = el('div', 'yf-others');
    [['want', item.dataset.want || 'Want to'], ['no', 'Not for me']].forEach(([value, label]) => {
      const button = el('button', 'yf-other', label);
      button.type = 'submit';
      button.name = 'choice';
      button.value = value;
      others.appendChild(button);
    });
    form.append(hidden('pick', item.dataset.id), el('p', 'yc-q', question), row, others);
    details.append(summary, form);
    item.className = 'yc-item';
    item.dataset.state = 'open';
    item.replaceChildren(details);
    watchArt(item);
    return details;
  }

  function setCounts(result) {
    const got = root.querySelector('[data-yc-got]');
    if (got && Number.isInteger(result.got)) got.textContent = String(result.got);
    const finished = Number(result.finished_total);
    if (Number.isInteger(finished)) {
      const count = document.querySelector('[data-yf-finished]');
      if (count) count.textContent = finished.toLocaleString('en-US');
      const label = document.querySelector('[data-yf-finished-label]');
      if (label) label.textContent = `${finished === 1 ? 'finish' : 'finishes'} in your ${year} recap`;
    }
    const filled = Number(result.filled);
    const filledNode = document.querySelector('[data-yf-filled]');
    if (filledNode && Number.isInteger(filled)) filledNode.textContent = filled.toLocaleString('en-US');
  }

  // ------------------------------------------------------------ saving

  async function submit(form, button) {
    const item = form.closest('.yc-item');
    const choice = parseChoice(button && button.value);
    if (!item || !choice || state.busy) return;
    state.busy = true;
    showError('');
    const buttons = form.querySelectorAll('button');
    buttons.forEach(node => { node.disabled = true; });
    try {
      if (choice.answer === 'undo') {
        const result = await call(`${api}/undo`, { id: item.dataset.id });
        setCounts(result);
        const details = drawOpen(item);
        const summary = details.querySelector('summary');
        if (summary) summary.focus();
        return;
      }
      const body = { id: item.dataset.id, answer: choice.answer };
      if (choice.answer === 'month') body.month = choice.month;
      const result = await call(api, body);
      setCounts(result);
      if (result.state === 'library') {
        drawAnswered(item, result.done ? 'library_done' : 'library_saved', null);
      } else if (result.state === 'already') {
        window.location.reload();
        return;
      } else {
        drawAnswered(item, result.state, result.month);
      }
      const change = item.querySelector('.yc-change button');
      if (change) change.focus({ preventScroll: true });
    } catch (error) {
      buttons.forEach(node => { node.disabled = false; });
      showError(error.message);
    } finally {
      state.busy = false;
    }
  }

  root.addEventListener('click', event => {
    const button = event.target instanceof Element ? event.target.closest('button[type="submit"]') : null;
    if (button && root.contains(button)) state.clicked = button;
  });

  root.addEventListener('submit', event => {
    const form = event.target instanceof Element ? event.target.closest('[data-yc-form]') : null;
    if (!form) return;
    event.preventDefault();
    const button = event.submitter || (state.clicked && form.contains(state.clicked) ? state.clicked : null);
    submit(form, button);
  });

  // One poster open at a time, scrolled into view; Escape closes it.
  root.addEventListener('toggle', event => {
    const details = event.target;
    if (!(details instanceof HTMLDetailsElement) || !details.open) return;
    root.querySelectorAll('details.yc-pick[open]').forEach(other => { if (other !== details) other.open = false; });
    const item = details.closest('.yc-item');
    if (item && typeof item.scrollIntoView === 'function') item.scrollIntoView({ block: 'nearest' });
  }, true);

  root.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const details = event.target instanceof Element ? event.target.closest('details.yc-pick[open]') : null;
    if (!details) return;
    details.open = false;
    const summary = details.querySelector('summary');
    if (summary) summary.focus();
  });

  // ------------------------------------------------------------ covers the site doesn't have yet

  const artQueue = [];
  let artRunning = 0;

  function nextArt() {
    while (artRunning < 3 && artQueue.length) {
      const item = artQueue.shift();
      const id = String(item.dataset.id || '');
      const slash = id.indexOf('/');
      if (slash < 1) continue;
      artRunning += 1;
      fetch(`${api}/art/${encodeURIComponent(id.slice(0, slash))}/${encodeURIComponent(id.slice(slash + 1))}`,
        { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(response => (response.ok ? response.json() : null))
        .then(data => {
          const image = data && typeof data.image === 'string' ? data.image : '';
          if (!/^https:\/\//.test(image)) return;
          item.querySelectorAll('.yc-poster').forEach(poster => {
            const initial = poster.querySelector('.yc-initial');
            if (!initial) return;
            const img = el('img');
            img.src = image;
            img.alt = '';
            img.width = 150;
            img.height = 225;
            img.loading = 'lazy';
            img.referrerPolicy = 'no-referrer';
            initial.replaceWith(img);
          });
        })
        .catch(() => {})
        .finally(() => { artRunning -= 1; nextArt(); });
    }
  }

  const observer = typeof IntersectionObserver === 'function'
    ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        artQueue.push(entry.target);
      });
      nextArt();
    }, { rootMargin: '200px 0px' })
    : null;

  function watchArt(item) {
    if (observer && item.querySelector('.yc-initial')) observer.observe(item);
  }

  // A cover that fails to load shows the title instead, the same as a poster with no cover. site.js gets
  // the first go at a Wikipedia thumbnail that fails (it swaps in the full-size poster), so only an image
  // that has finished loading and has nothing to show is replaced.
  function coverFailed(img) {
    if (!img.complete || img.naturalWidth > 0) return;
    const item = img.closest('.yc-item');
    const name = item && item.querySelector('.yc-name');
    const initial = el('span', 'yc-initial', name ? name.textContent : '');
    initial.setAttribute('aria-hidden', 'true');
    img.replaceWith(initial);
  }

  root.addEventListener('error', event => {
    const img = event.target;
    if (img instanceof HTMLImageElement && img.closest('.yc-poster')) coverFailed(img);
  }, true);
  root.querySelectorAll('.yc-poster img').forEach(img => {
    const thumb = /upload\.wikimedia\.org\/.*\/thumb\//.test(img.getAttribute('src') || '');
    if (!thumb || img.dataset.thumbFailed) coverFailed(img);
  });

  root.querySelectorAll('.yc-item').forEach(watchArt);

  // A link to one title (#yc-...) opens it.
  if (window.location.hash && window.location.hash.startsWith('#yc-')) {
    const target = document.getElementById(window.location.hash.slice(1));
    const details = target && target.querySelector('details.yc-pick');
    if (details) details.open = true;
  }
}());
