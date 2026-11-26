// "Fill in your year" (/year-in-review/<year>/fill): one tap dates a title, and the recap counts it.
// The page arrives with its cards drawn by the server; this saves answers, keeps the tallies right,
// offers an undo for the last answer and loads more cards when the deck runs out.
// Text from the server and from the library is only ever set as textContent.
(function () {
  'use strict';

  function plural(count, one, many) {
    return `${Number(count).toLocaleString('en-US')} ${count === 1 ? one : (many || `${one}s`)}`;
  }

  // How many titles are still waiting in each list, from the server's last word (the page's own
  // data attributes until the first answer). The page only ever shows the first few of them.
  function waiting(kind, counts, shown) {
    const left = counts ? Number(kind === 'open' ? counts.open_left : counts.undated_left) : NaN;
    return Number.isInteger(left) && left >= 0 ? left : shown;
  }

  // "The rest were all before" and "None of these yet" answer every title waiting in that list, not
  // only the cards on screen, so the question names them all.
  function restQuestion(kind, count, year) {
    return kind === 'undated'
      ? `Mark the ${plural(count, 'title')} left as finished before ${year}? They stay ticked off, just out of this recap.`
      : `Leave all ${plural(count, 'title')} on your list as not finished yet?`;
  }

  // A list whose cards have all been answered loads the next ones while the server says more are waiting.
  function needsMore(shownUndated, shownOpen, counts) {
    if (!counts) return false;
    return (!shownUndated && Number(counts.undated_left) > 0) || (!shownOpen && Number(counts.open_left) > 0);
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { waiting, restQuestion, needsMore };
  if (typeof document === 'undefined') return;

  const root = document.querySelector('[data-yf]');
  if (!root) return;
  const year = Number(root.dataset.year);
  if (!Number.isInteger(year)) return;
  const api = `/api/year-in-review/${year}/fill`;
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];
  const UNDO_MS = 9000;
  const state = { months: [], last: null, undoTimer: 0, busy: false, counts: null };

  const $ = selector => root.querySelector(selector);
  const lists = { undated: $('[data-yf-list="undated"]'), open: $('[data-yf-list="open"]') };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  async function call(path, body) {
    const init = { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json' } };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    const response = await fetch(path, init);
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

  function showError(message) {
    const box = $('[data-yf-error]');
    if (!box) return;
    box.textContent = message || '';
    box.hidden = !message;
  }

  // ------------------------------------------------------------ the deck

  function cards(kind) {
    const list = lists[kind];
    return list ? Array.from(list.querySelectorAll('.yf-card')) : [];
  }

  function markCurrent() {
    const deck = cards('undated');
    deck.forEach((card, index) => card.classList.toggle('is-current', index === 0));
    if (lists.undated) lists.undated.classList.add('is-deck');
  }

  function focusNext(kind) {
    const next = cards(kind)[0];
    const title = next && next.querySelector('.yf-title');
    if (title) {
      title.setAttribute('tabindex', '-1');
      title.focus({ preventScroll: kind === 'open' });
    }
  }

  function setCounts(counts) {
    if (!counts) return;
    state.counts = counts;
    const finished = Number(counts.finished_total) || 0;
    const set = (selector, text) => { const node = $(selector); if (node) node.textContent = text; };
    set('[data-yf-finished]', finished.toLocaleString('en-US'));
    set('[data-yf-finished-label]', `${finished === 1 ? 'finish' : 'finishes'} in your ${year} recap`);
    set('[data-yf-filled]', (Number(counts.filled) || 0).toLocaleString('en-US'));
    set('[data-yf-finished-done]', plural(finished, 'finish', 'finishes'));
    set('[data-yf-undated-left]', `${plural(Number(counts.undated_left) || 0, 'title')} to go`);
    set('[data-yf-open-left]', plural(Number(counts.open_left) || 0, 'title'));
  }

  function refreshSections() {
    const counts = state.counts || {};
    const deckSection = $('[data-yf-deck]');
    const openSection = $('[data-yf-open]');
    const undatedLeft = cards('undated').length;
    const openLeft = cards('open').length;
    if (deckSection) deckSection.hidden = !undatedLeft;
    if (openSection) openSection.hidden = !openLeft;
    const done = $('[data-yf-done]');
    if (done) done.hidden = Boolean(undatedLeft || openLeft || counts.undated_left || counts.open_left);
    markCurrent();
  }

  function said(card, result, answer, month) {
    const title = card.querySelector('.yf-title');
    const name = title ? title.textContent : 'It';
    if (answer === 'month') {
      const today = new Date();
      if (month === today.getMonth() + 1 && year === today.getFullYear()) return `${name}: ticked off today.`;
      return `${name}: finished in ${MONTHS[month - 1]}.`;
    }
    if (answer === 'before') return card.dataset.kind === 'open' ? `${name}: ticked off, finished before ${year}.` : `${name}: before ${year}.`;
    return card.dataset.kind === 'open' ? `${name}: not yet.` : `${name}: skipped.`;
  }

  function showUndo(text) {
    const bar = $('[data-yf-undo]');
    if (!bar) return;
    const label = bar.querySelector('[data-yf-undo-text]');
    if (label) label.textContent = text;
    bar.hidden = false;
    window.clearTimeout(state.undoTimer);
    state.undoTimer = window.setTimeout(() => { bar.hidden = true; state.last = null; }, UNDO_MS);
  }

  async function answer(card, choice, month) {
    if (state.busy) return;
    state.busy = true;
    showError('');
    const buttons = card.querySelectorAll('button');
    buttons.forEach(button => { button.disabled = true; });
    const kind = card.dataset.kind === 'open' ? 'open' : 'undated';
    try {
      const body = { category: card.dataset.category, id: Number(card.dataset.id), answer: choice };
      if (choice === 'month') body.month = month;
      const result = await call(api, body);
      const parent = card.parentNode;
      const next = card.nextSibling;
      card.remove();
      buttons.forEach(button => { button.disabled = false; });
      state.last = { card, parent, next, kind };
      setCounts(result);
      if (result.state === 'already' || result.state === 'dated') {
        state.last = null;
        showUndo(result.state === 'dated' ? 'That one already has a date.' : 'That one was already answered.');
      } else {
        showUndo(said(card, result, choice, month));
      }
      if (needsMore(cards('undated').length, cards('open').length, result)) await loadMore();
      refreshSections();
      focusNext(kind);
    } catch (error) {
      buttons.forEach(button => { button.disabled = false; });
      showError(error.message);
    } finally {
      state.busy = false;
    }
  }

  async function undo() {
    const last = state.last;
    if (!last || state.busy) return;
    state.busy = true;
    try {
      const result = await call(`${api}/undo`, { category: last.card.dataset.category, id: Number(last.card.dataset.id) });
      if (result.undone) {
        if (last.next && last.next.parentNode === last.parent) last.parent.insertBefore(last.card, last.next);
        else last.parent.insertBefore(last.card, last.parent.firstChild);
      }
      setCounts(result);
      state.last = null;
      const bar = $('[data-yf-undo]');
      if (bar) bar.hidden = true;
      refreshSections();
      const title = last.card.querySelector('.yf-title');
      if (title) { title.setAttribute('tabindex', '-1'); title.focus(); }
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
    }
  }

  // ------------------------------------------------------------ cards drawn here (more of the deck, brought back)

  function cardNode(card, months) {
    const item = el('li', 'yf-card');
    item.dataset.category = card.category;
    item.dataset.id = String(card.id);
    item.dataset.kind = card.kind === 'open' ? 'open' : 'undated';
    const cover = el('div', 'yf-cover');
    if (typeof card.image === 'string' && /^https:\/\//.test(card.image)) {
      const img = el('img');
      img.src = card.image;
      img.alt = '';
      img.width = 120;
      img.height = 180;
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      cover.appendChild(img);
    } else {
      const initial = el('span', 'yf-cover__initial', String(card.title || '?').charAt(0).toUpperCase());
      initial.setAttribute('aria-hidden', 'true');
      cover.appendChild(initial);
    }
    const body = el('div', 'yf-body');
    body.appendChild(el('p', 'yf-label', card.year ? `${card.label} · ${card.year}` : card.label));
    body.appendChild(el('h3', 'yf-title', card.title));
    const questionId = `yf-q-${card.category}-${card.id}`;
    const question = el('p', 'yf-q', card.question);
    question.id = questionId;
    body.appendChild(question);
    const row = el('div', 'yf-months');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-labelledby', questionId);
    months.forEach(month => {
      const button = el('button', `yf-month${month.current ? ' yf-month--now' : ''}`, month.short);
      button.type = 'button';
      button.dataset.answer = 'month';
      button.dataset.month = String(month.n);
      button.setAttribute('aria-label', `${month.name} ${year}${month.current ? ' (this month)' : ''}`);
      row.appendChild(button);
    });
    body.appendChild(row);
    const others = el('div', 'yf-others');
    const before = el('button', 'yf-other', item.dataset.kind === 'open' ? `Finished before ${year}` : `Before ${year}`);
    before.type = 'button';
    before.dataset.answer = 'before';
    const skip = el('button', 'yf-other', item.dataset.kind === 'open' ? 'Not yet' : 'Not sure');
    skip.type = 'button';
    skip.dataset.answer = 'skip';
    others.append(before, skip);
    body.appendChild(others);
    item.append(cover, body);
    return item;
  }

  function draw(data) {
    if (!data) return;
    const months = Array.isArray(data.months) ? data.months : state.months;
    state.months = months;
    ['undated', 'open'].forEach(kind => {
      const list = lists[kind];
      if (!list) return;
      const shown = new Set(cards(kind).map(card => `${card.dataset.category}-${card.dataset.id}`));
      (Array.isArray(data[kind]) ? data[kind] : []).forEach(card => {
        if (!shown.has(`${card.category}-${card.id}`)) list.appendChild(cardNode(card, months));
      });
    });
    setCounts({ finished_total: data.finished_total, filled: data.filled,
      undated_left: data.undated_total, open_left: data.open_total });
  }

  async function loadMore() {
    try {
      draw(await call(api));
    } catch (error) {
      showError(error.message);
    }
  }

  // ------------------------------------------------------------ everything else at once

  function confirmInPlace(button, question, yes, action) {
    const wrap = button.parentNode;
    const saved = Array.from(wrap.childNodes);
    const ask = el('p', 'yf-confirm', question);
    const go = el('button', 'yf-other yf-other--strong', yes);
    go.type = 'button';
    const cancel = el('button', 'yf-link', 'Cancel');
    cancel.type = 'button';
    const restore = () => { wrap.replaceChildren(...saved); button.focus(); };
    cancel.addEventListener('click', restore);
    go.addEventListener('click', async () => {
      go.disabled = true;
      cancel.disabled = true;
      try {
        await action();
        wrap.replaceChildren(...saved);
      } catch (error) {
        showError(error.message);
        restore();
      }
    });
    wrap.replaceChildren(ask, go, cancel);
    go.focus();
  }

  function rest(kind, button) {
    const question = restQuestion(kind, waiting(kind, state.counts, cards(kind).length), year);
    confirmInPlace(button, question, kind === 'undated' ? `Yes, all before ${year}` : 'Yes, none yet', async () => {
      const result = await call(`${api}/rest`, { kind });
      cards(kind).forEach(card => card.remove());
      state.last = null;
      const bar = $('[data-yf-undo]');
      if (bar) bar.hidden = true;
      setCounts(result);
      if (needsMore(cards('undated').length, cards('open').length, result)) await loadMore();
      refreshSections();
    });
  }

  async function bringBack(button) {
    button.disabled = true;
    try {
      const result = await call(`${api}/bring-back`, {});
      setCounts(result);
      await loadMore();
      refreshSections();
      button.remove();
    } catch (error) {
      button.disabled = false;
      showError(error.message);
    }
  }

  root.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target.closest('button') : null;
    if (!target || !root.contains(target)) return;
    if (target.matches('[data-yf-undo-button]')) { undo(); return; }
    if (target.matches('[data-yf-rest]')) { rest(target.dataset.yfRest === 'open' ? 'open' : 'undated', target); return; }
    if (target.matches('[data-yf-bring-back]')) { bringBack(target); return; }
    const card = target.closest('.yf-card');
    const choice = target.dataset.answer;
    if (!card || !['month', 'before', 'skip'].includes(choice)) return;
    const month = Number(target.dataset.month);
    if (choice === 'month' && !(Number.isInteger(month) && month >= 1 && month <= 12)) return;
    answer(card, choice, month);
  });

  // The totals the server drew the page with, so the first "the rest" question counts every title.
  const start = root.dataset;
  state.counts = {
    finished_total: Number(start.finishedTotal) || 0, filled: Number(start.filled) || 0,
    undated_left: Number(start.undatedTotal) || 0, open_left: Number(start.openTotal) || 0,
  };
  markCurrent();
}());
