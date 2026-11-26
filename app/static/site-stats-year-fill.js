// Site stats: the December Year in Review email card (app/year_fill.py). It reads its own endpoint,
// so the rest of the page never waits on it. Text from the server is only ever set as textContent.
(function () {
  'use strict';
  const card = document.getElementById('yearFillCard');
  if (!card) return;
  const $ = id => document.getElementById(id);
  const STATES = { draft: 'Not started', sending: 'On: checking every hour', paused: 'Paused' };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function number(value) {
    return Number(value || 0).toLocaleString('en-US');
  }

  function headers(json) {
    const out = { Accept: 'application/json' };
    if (json) out['Content-Type'] = 'application/json';
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) out.Authorization = `Bearer ${token}`;
    } catch (error) {
      // Cookie sessions work without storage.
    }
    return out;
  }

  function render(info) {
    if (!info || typeof info !== 'object') return;
    let status = STATES[info.status] || String(info.status || '');
    if (info.status === 'sending' && info.waiting_on_whats_new) status = 'On, waiting until the “What’s new” email finishes';
    else if (info.status === 'sending' && !info.window_open) status = `On, sends ${info.window}`;
    const rows = [
      ['Status', status],
      ['When it goes', `${info.window} (UTC), once per member`],
      ['Members due now', number(info.due_now)],
      ['Sent in the last 45 days', number(info.sent_recent)],
      [`Came back within ${info.came_back_window_days} days of one`, number(info.came_back)],
      ['Sent all time', number(info.sent_all_time)],
      ['Daily limit', `${number(info.daily_limit)} (shares the daily email budget, so sign-up and reset emails always go out)`],
    ];
    if (!info.mail_configured) rows.push(['Email', 'NOT configured on this server: nothing can be sent']);
    const list = $('yearFillList');
    list.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', value));
      list.appendChild(row);
    });
    const pageStats = info.page || {};
    const sources = Array.isArray(pageStats.by_source) ? pageStats.by_source : [];
    const wrap = el('div', 'stats-table-wrap');
    const table = el('table', 'stats-table');
    const head = el('tr');
    ['Fill-in pages, last 30 days', 'Opened', 'Dated', 'Before the year', 'Skipped', 'Ticked off', 'Answered all']
      .forEach((label, index) => head.appendChild(el('th', index ? 'num' : '', label)));
    const thead = el('thead');
    thead.appendChild(head);
    const body = el('tbody');
    sources.forEach(row => {
      const tr = el('tr');
      [row.source, row.opened, row.dated, row.before, row.skipped, row.ticked, row.all_done]
        .forEach((value, index) => tr.appendChild(el('td', index ? 'num' : '', index ? number(value) : value)));
      body.appendChild(tr);
    });
    table.append(thead, body);
    wrap.appendChild(table);
    $('yearFillPage').replaceChildren(wrap);
    $('yearFillStart').hidden = info.status === 'sending';
    $('yearFillStart').textContent = info.status === 'paused' ? 'Resume sending' : 'Start sending';
    $('yearFillPause').hidden = info.status !== 'sending';
    card.hidden = false;
  }

  async function load() {
    try {
      const response = await fetch('/api/site-stats/year-fill', { credentials: 'same-origin', headers: headers(false) });
      if (!response.ok) return;
      render(await response.json());
    } catch (error) {
      // The card stays hidden.
    }
  }

  async function act(action) {
    const status = $('yearFillStatus');
    if (action === 'start' && !window.confirm('Turn on the Year in Review email? From December 1 to 14, each member with a library gets one email about their recap and the titles it is missing, up to 30 a day. You can pause any time.')) return;
    const buttons = card.querySelectorAll('[data-year-fill]');
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = action === 'test' ? 'Sending a test to your email…' : 'Saving…';
    try {
      const response = await fetch('/api/site-stats/year-fill', {
        method: 'POST', credentials: 'same-origin', headers: headers(true), body: JSON.stringify({ action }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      render(result);
      status.textContent = result.message || (action === 'start'
        ? 'On. Emails go out within the hour from December 1 to 14.'
        : 'Paused. Nothing more will be sent until you resume.');
    } catch (error) {
      status.textContent = `Couldn't do that: ${error.message}`;
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  card.querySelectorAll('[data-year-fill]').forEach(button => {
    button.addEventListener('click', () => act(button.dataset.yearFill));
  });
  load();
}());
