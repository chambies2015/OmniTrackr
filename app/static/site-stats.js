// Owner-only Site stats page. Everything is built with DOM APIs and textContent;
// no server string is ever inserted as HTML.
(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const COLORS = { views: '#8b5cf6', visitors: '#0d9488' };
  const DEVICE_COLORS = { desktop: '#8b5cf6', mobile: '#0d9488', tablet: '#d97706' };
  const AUDIENCE_COLORS = { guest: '#8b5cf6', member: '#0d9488' };
  const state = { days: 30, data: null, loading: false };

  const $ = id => document.getElementById(id);
  const number = value => Number(value || 0).toLocaleString('en-US');
  const percent = (part, whole) => (whole ? Math.round((part / whole) * 1000) / 10 : 0);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function svg(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function shortDate(iso) {
    const date = new Date(`${iso}T12:00:00Z`);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  }

  function dateTime(iso) {
    if (!iso) return '—';
    const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  function dayOnly(iso) {
    if (!iso) return '—';
    const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function niceMax(value) {
    if (value <= 4) return 4;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const step = [1, 2, 2.5, 5, 10].find(candidate => candidate * magnitude >= value / 4) * magnitude;
    return Math.ceil(value / step) * step;
  }

  function delta(current, previous) {
    if (!previous) return current ? { text: 'new', up: true } : null;
    const change = Math.round(((current - previous) / previous) * 100);
    return { text: `${change > 0 ? '+' : ''}${change}%`, up: change >= 0 };
  }

  // ---------------------------------------------------------------- tooltip
  const tooltip = () => $('statsTooltip');

  function showTooltip(x, y, title, rows) {
    const tip = tooltip();
    tip.replaceChildren();
    tip.appendChild(el('span', 'tt-date', title));
    rows.forEach(row => {
      const line = el('div', 'tt-row');
      const label = el('span');
      if (row.color) {
        const key = el('i');
        key.style.background = row.color;
        label.appendChild(key);
      }
      label.appendChild(document.createTextNode(row.label));
      line.append(el('strong', '', number(row.value)), label);
      tip.appendChild(line);
    });
    tip.hidden = false;
    const width = tip.offsetWidth;
    const left = Math.min(window.innerWidth - width - 12, Math.max(12, x + 14));
    tip.style.left = `${left}px`;
    tip.style.top = `${Math.max(12, y - tip.offsetHeight - 12)}px`;
  }

  function hideTooltip() {
    tooltip().hidden = true;
  }

  // ---------------------------------------------------------------- charts
  function emptyChart(container, message) {
    container.replaceChildren(el('div', 'stats-empty', message));
  }

  function lineChart(container, dates, series, emptyMessage, { partialLast = false } = {}) {
    const total = series.reduce((sum, item) => sum + item.values.reduce((a, b) => a + b, 0), 0);
    if (!dates.length || !total) {
      emptyChart(container, emptyMessage);
      return;
    }
    const width = Math.max(280, container.clientWidth);
    const height = Math.max(140, container.clientHeight);
    const pad = { top: 12, right: 92, bottom: 26, left: 40 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const max = niceMax(Math.max(...series.flatMap(item => item.values)));
    const x = index => pad.left + (dates.length === 1 ? plotW / 2 : (index / (dates.length - 1)) * plotW);
    const y = value => pad.top + plotH - (value / max) * plotH;
    const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': series.map(item => item.label).join(' and ') + ' per day' });

    for (let step = 0; step <= 4; step += 1) {
      const value = (max / 4) * step;
      root.appendChild(svg('line', { class: 'grid-line', x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value) }));
      const label = svg('text', { class: 'axis-label', x: pad.left - 8, y: y(value) + 4, 'text-anchor': 'end' });
      label.textContent = number(value);
      root.appendChild(label);
    }
    [0, Math.floor((dates.length - 1) / 2), dates.length - 1].filter((v, i, list) => list.indexOf(v) === i).forEach((index, position, list) => {
      const anchor = position === 0 ? 'start' : position === list.length - 1 ? 'end' : 'middle';
      const label = svg('text', { class: 'axis-label', x: x(index), y: height - 6, 'text-anchor': anchor });
      label.textContent = shortDate(dates[index]);
      root.appendChild(label);
    });

    // Today is still in progress: draw its segment dashed so a partial day does not read as a crash.
    const dashed = partialLast && dates.length > 1;
    const lastFull = dashed ? dates.length - 2 : dates.length - 1;
    series.forEach((item, seriesIndex) => {
      const points = item.values.map((value, index) => `${x(index)},${y(value)}`);
      const solid = points.slice(0, lastFull + 1);
      if (seriesIndex === 0) {
        const area = svg('path', { class: 'series-area', fill: item.color, d: `M${x(0)},${y(0)} L${solid.join(' L')} L${x(lastFull)},${y(0)} Z` });
        root.appendChild(area);
      }
      root.appendChild(svg('path', { class: 'series-line', stroke: item.color, d: `M${solid.join(' L')}` }));
      if (dashed) {
        root.appendChild(svg('path', { class: 'series-line series-line--partial', stroke: item.color, d: `M${points[lastFull]} L${points[lastFull + 1]}` }));
      }
    });
    // Direct labels (last complete day) at the line ends, nudged apart when they would collide.
    const ends = series.map(item => ({ item, y: y(item.values[lastFull]) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i += 1) {
      if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    }
    ends.forEach(({ item, y: labelY }) => {
      const label = svg('text', { class: 'end-label', x: width - pad.right + 8, y: labelY + 4 });
      label.textContent = `${item.shortLabel || item.label} ${number(item.values[lastFull])}`;
      root.appendChild(label);
    });

    const crosshair = svg('line', { class: 'crosshair', y1: pad.top, y2: pad.top + plotH, visibility: 'hidden' });
    root.appendChild(crosshair);
    const dots = series.map(item => {
      const dot = svg('circle', { class: 'dot', r: 4, fill: item.color, visibility: 'hidden' });
      root.appendChild(dot);
      return dot;
    });
    const hit = svg('rect', { class: 'hit', x: pad.left - 6, y: pad.top, width: plotW + 12, height: plotH });
    root.appendChild(hit);

    const focusIndex = (index, clientX, clientY) => {
      crosshair.setAttribute('x1', x(index));
      crosshair.setAttribute('x2', x(index));
      crosshair.setAttribute('visibility', 'visible');
      dots.forEach((dot, i) => {
        dot.setAttribute('cx', x(index));
        dot.setAttribute('cy', y(series[i].values[index]));
        dot.setAttribute('visibility', 'visible');
      });
      showTooltip(clientX, clientY, `${shortDate(dates[index])}${dashed && index === dates.length - 1 ? ' (today so far)' : ''}`, series.map(item => ({ label: item.label, value: item.values[index], color: item.color })));
    };
    const clear = () => {
      crosshair.setAttribute('visibility', 'hidden');
      dots.forEach(dot => dot.setAttribute('visibility', 'hidden'));
      hideTooltip();
    };
    hit.addEventListener('pointermove', event => {
      const box = root.getBoundingClientRect();
      const localX = ((event.clientX - box.left) / box.width) * width;
      const index = Math.round(((localX - pad.left) / plotW) * (dates.length - 1));
      focusIndex(Math.max(0, Math.min(dates.length - 1, index)), event.clientX, event.clientY);
    });
    hit.addEventListener('pointerleave', clear);

    container.replaceChildren(root);
    container.tabIndex = 0;
    let keyboardIndex = dates.length - 1;
    container.onkeydown = event => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      keyboardIndex = Math.max(0, Math.min(dates.length - 1, keyboardIndex + (event.key === 'ArrowRight' ? 1 : -1)));
      const box = root.getBoundingClientRect();
      focusIndex(keyboardIndex, box.left + (x(keyboardIndex) / width) * box.width, box.top + pad.top);
    };
    container.onblur = clear;
  }

  function barChart(container, dates, values, label, emptyMessage) {
    if (!values.some(Boolean)) {
      emptyChart(container, emptyMessage);
      return;
    }
    const width = Math.max(240, container.clientWidth);
    const height = Math.max(120, container.clientHeight);
    const pad = { top: 10, right: 6, bottom: 24, left: 32 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const max = niceMax(Math.max(...values));
    const slot = plotW / values.length;
    const barW = Math.max(2, slot - 2);
    const y = value => pad.top + plotH - (value / max) * plotH;
    const root = svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `${label} per day` });
    [0, max / 2, max].forEach(value => {
      root.appendChild(svg('line', { class: 'grid-line', x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value) }));
      const text = svg('text', { class: 'axis-label', x: pad.left - 6, y: y(value) + 4, 'text-anchor': 'end' });
      text.textContent = number(value);
      root.appendChild(text);
    });
    [0, values.length - 1].forEach((index, position) => {
      const text = svg('text', { class: 'axis-label', x: position ? width - pad.right : pad.left, y: height - 6, 'text-anchor': position ? 'end' : 'start' });
      text.textContent = shortDate(dates[index]);
      root.appendChild(text);
    });
    values.forEach((value, index) => {
      const barX = pad.left + index * slot + 1;
      if (value > 0) {
        const barH = Math.max(2, plotH - (y(value) - pad.top));
        root.appendChild(svg('rect', { class: 'bar', x: barX, y: pad.top + plotH - barH, width: barW, height: barH, rx: Math.min(2, barW / 2) }));
      }
      const hit = svg('rect', { class: 'hit', x: pad.left + index * slot, y: pad.top, width: slot, height: plotH });
      hit.addEventListener('pointermove', event => {
        root.querySelectorAll('.bar.is-hover').forEach(bar => bar.classList.remove('is-hover'));
        const bar = hit.previousSibling;
        if (bar && bar.classList && bar.classList.contains('bar')) bar.classList.add('is-hover');
        showTooltip(event.clientX, event.clientY, shortDate(dates[index]), [{ label, value }]);
      });
      hit.addEventListener('pointerleave', () => {
        root.querySelectorAll('.bar.is-hover').forEach(bar => bar.classList.remove('is-hover'));
        hideTooltip();
      });
      root.appendChild(hit);
    });
    container.replaceChildren(root);
  }

  function table(headers, rows, numericFrom = 1) {
    const wrap = el('div', 'stats-table-wrap');
    const tableEl = el('table', 'stats-table');
    const head = el('tr');
    headers.forEach((header, index) => head.appendChild(el('th', index >= numericFrom ? 'num' : '', header)));
    const thead = el('thead');
    thead.appendChild(head);
    const tbody = el('tbody');
    rows.forEach(row => {
      const tr = el('tr');
      row.forEach((cell, index) => tr.appendChild(el('td', index >= numericFrom ? 'num' : '', cell)));
      tbody.appendChild(tr);
    });
    tableEl.append(thead, tbody);
    wrap.appendChild(tableEl);
    return wrap;
  }

  function bars(container, items, emptyMessage, formatLabel = value => value) {
    container.replaceChildren();
    if (!items.length) {
      container.appendChild(el('p', 'stats-empty', emptyMessage));
      return;
    }
    const max = Math.max(...items.map(item => item.count));
    items.forEach(item => {
      const row = el('div', 'stats-bar');
      const top = el('div', 'stats-bar__top');
      const label = el('span', 'stats-bar__label', formatLabel(item.key));
      label.title = item.key;
      top.append(label, el('span', 'stats-bar__value', number(item.count)));
      const track = el('div', 'stats-bar__track');
      const fill = el('div', 'stats-bar__fill');
      fill.style.width = `${percent(item.count, max)}%`;
      track.appendChild(fill);
      row.append(top, track);
      container.appendChild(row);
    });
  }

  function split(container, items, colors, labels, emptyMessage) {
    container.replaceChildren();
    const total = items.reduce((sum, item) => sum + item.count, 0);
    if (!total) {
      container.appendChild(el('p', 'stats-empty', emptyMessage));
      return;
    }
    const barEl = el('div', 'stats-split');
    barEl.setAttribute('role', 'img');
    barEl.setAttribute('aria-label', items.map(item => `${labels[item.key] || item.key} ${percent(item.count, total)}%`).join(', '));
    const legend = el('div', 'stats-split-legend');
    items.forEach(item => {
      const color = colors[item.key] || '#64748b';
      const part = el('span');
      part.style.width = `${percent(item.count, total)}%`;
      part.style.background = color;
      barEl.appendChild(part);
      const row = el('div');
      const key = el('i');
      key.style.background = color;
      row.append(key, el('span', '', labels[item.key] || item.key), el('b', '', number(item.count)), el('em', '', `${percent(item.count, total)}%`));
      legend.appendChild(row);
    });
    container.append(barEl, legend);
  }

  // ---------------------------------------------------------------- sections
  function kpi(label, value, meta, change) {
    const card = el('article', 'stats-kpi');
    card.append(el('p', 'stats-kpi__label', label), el('p', 'stats-kpi__value', value));
    const metaEl = el('p', 'stats-kpi__meta');
    if (change) {
      metaEl.appendChild(el('span', `stats-delta ${change.up ? 'stats-delta--up' : 'stats-delta--down'}`, change.text));
      metaEl.appendChild(document.createTextNode(' '));
    }
    metaEl.appendChild(document.createTextNode(meta));
    card.appendChild(metaEl);
    return card;
  }

  function renderKpis(data) {
    const { traffic, members, insights, days } = data;
    const range = `vs previous ${days} days`;
    $('statsKpis').replaceChildren(
      kpi('Visitors', number(traffic.totals.visitors), traffic.tracking_since ? range : 'counting starts after deploy', traffic.tracking_since ? delta(traffic.totals.visitors, traffic.previous_totals.visitors) : null),
      kpi('Page views', number(traffic.totals.views), `${number(traffic.today.views)} today`, traffic.tracking_since ? delta(traffic.totals.views, traffic.previous_totals.views) : null),
      kpi('New members', number(members.new_in_range), range, delta(members.new_in_range, members.new_previous_range)),
      kpi('Total members', number(insights.users.total), `${number(insights.users.verified)} verified · ${number(members.new_today)} joined today`),
      kpi('Active members', number(members.active_7_days), `logged in this week · ${number(members.active_24_hours)} today · ${number(members.active_30_days)} this month`),
      kpi('Titles tracked', number(insights.content.total_items), `${number(insights.content.public_reviews)} public reviews`),
    );
  }

  function renderTraffic(data) {
    const { traffic } = data;
    const dates = traffic.series.map(day => day.date);
    const since = traffic.tracking_since ? `Counting since ${dayOnly(traffic.tracking_since)}.` : 'Counting starts once this update is deployed.';
    $('trafficNote').textContent = `Human page views and estimated unique visitors per day. ${since}`;
    lineChart($('trafficChart'), dates, [
      { key: 'views', label: 'Page views', shortLabel: 'Views', color: COLORS.views, values: traffic.series.map(day => day.views) },
      { key: 'visitors', label: 'Visitors', color: COLORS.visitors, values: traffic.series.map(day => day.visitors) },
    ], traffic.enabled ? 'No visits recorded in this range yet. Numbers appear within a minute of the first visit.' : 'Traffic counting is turned off (SITE_TRAFFIC_TRACKING).', { partialLast: true });
    $('trafficTable').replaceChildren(table(['Day', 'Page views', 'Visitors'], traffic.series.slice().reverse().map(day => [shortDate(day.date), number(day.views), number(day.visitors)])));
    bars($('topPages'), traffic.top_pages, 'No page views recorded yet.');
    bars($('trafficSources'), traffic.sources, 'No outside visits recorded yet.', key => (key === '(direct)' ? 'Direct / bookmarks / apps' : key));
    split($('deviceSplit'), traffic.devices, DEVICE_COLORS, { desktop: 'Desktop', mobile: 'Mobile', tablet: 'Tablet' }, 'No page views recorded yet.');
    split($('audienceSplit'), traffic.audience, AUDIENCE_COLORS, { guest: 'Guests', member: 'Signed-in members' }, 'No page views recorded yet.');
  }

  function renderGrowth(data) {
    const signupDates = data.signups.map(day => day.date);
    $('signupNote').textContent = `Accounts created per day · ${number(data.members.new_in_range)} in the last ${data.days} days.`;
    barChart($('signupChart'), signupDates, data.signups.map(day => day.signups), 'New members', 'No new accounts in this range.');
    $('signupTable').replaceChildren(table(['Day', 'New members'], data.signups.slice().reverse().map(day => [shortDate(day.date), number(day.signups)])));
    const journalDates = data.journal_activity.map(day => day.date);
    barChart($('journalChart'), journalDates, data.journal_activity.map(day => day.entries), 'Journal entries', 'No journal entries in this range.');
    $('journalTable').replaceChildren(table(['Day', 'Entries'], data.journal_activity.slice().reverse().map(day => [shortDate(day.date), number(day.entries)])));
  }

  function renderFunnel(data) {
    const container = $('activationFunnel');
    container.replaceChildren();
    const first = data.insights.activation[0]?.count || 0;
    data.insights.activation.forEach((stage, index) => {
      const row = el('div', 'stats-step');
      const track = el('div', 'stats-step__track');
      const fill = el('div', 'stats-step__fill');
      fill.style.width = `${percent(stage.count, first)}%`;
      track.appendChild(fill);
      const value = el('div', 'stats-step__value');
      value.append(el('b', '', number(stage.count)), el('span', '', index ? `${stage.step_rate}%` : '100%'));
      row.append(el('div', 'stats-step__label', stage.label), track, value);
      container.appendChild(row);
    });
  }

  function renderSignupFunnel(data) {
    const container = $('signupFunnel');
    if (!container || !data.funnel) return;
    container.replaceChildren();
    // Ranges from before the visitor step existed fall back to all "/" page views.
    const counted = data.funnel.steps.some(step => step.event === 'landing_viewed' && step.count > 0);
    const homeViews = (data.traffic.top_pages.find(page => page.key === '/') || {}).count || 0;
    const steps = counted ? data.funnel.steps.slice()
      : [{ label: 'Homepage views (all, incl. members)', count: homeViews }, ...data.funnel.steps.filter(step => step.event !== 'landing_viewed')];
    const first = Math.max(...steps.map(step => step.count), 1);
    steps.forEach((step, index) => {
      const row = el('div', 'stats-step');
      const track = el('div', 'stats-step__track');
      const fill = el('div', 'stats-step__fill');
      fill.style.width = `${percent(step.count, first)}%`;
      track.appendChild(fill);
      const previous = index ? steps[index - 1].count : 0;
      const rate = index && previous ? `${Math.round((step.count / previous) * 100)}%` : '';
      const value = el('div', 'stats-step__value');
      value.append(el('b', '', number(step.count)), el('span', '', rate));
      row.append(el('div', 'stats-step__label', step.label), track, value);
      container.appendChild(row);
    });
    const fillList = (id, items) => {
      const list = $(id);
      list.replaceChildren();
      items.forEach(item => {
        const row = el('div');
        row.append(el('dt', '', item.label), el('dd', '', number(item.count)));
        list.appendChild(row);
      });
    };
    fillList('signupIssues', data.funnel.issues);
    const retention = data.retention || {};
    fillList('guestList', [
      ...data.funnel.guest,
      { label: 'Weekly email subscribers (now)', count: retention.weekly_email_subscribers || 0 },
      { label: 'Public profiles switched on (now)', count: retention.public_profiles || 0 },
    ]);
  }

  function renderLibraries(data) {
    const content = data.insights.content;
    const rows = content.categories.map(category => [category.label, number(category.total), number(category.completed), number(category.rated), number(category.reviewed)]);
    rows.push(['All', number(content.total_items), number(content.completed_items), number(content.rated_items), number(content.reviewed_items)]);
    rows.push(['Custom tabs', number(content.custom_items), '—', '—', '—']);
    $('categoryTable').replaceChildren(table(['Category', 'Titles', 'Finished', 'Rated', 'Reviewed'], rows));
  }

  function renderCommunity(data) {
    const { moderation, engagement } = data.insights;
    const items = [
      ['Public reviews', data.insights.content.public_reviews],
      ['Public collections (listed)', `${number(moderation.approved)} of ${number(moderation.public)}`],
      ['Collection views', moderation.views],
      ['Helpful votes', moderation.helpful],
      ['Friendships', engagement.friendships],
      ['Recommendation requests', engagement.recommendation_requests],
      ['Recommendations received', engagement.recommendation_submissions],
      ['Journal entries (30 days)', engagement.activity_entries_30_days],
      ['Next Up items', engagement.next_up_items],
      ['Open reports (collections / reviews)', `${number(moderation.reports)} / ${number(moderation.review_reports)}`],
      ['Unlisted by reports', number(moderation.collection_unlistings + moderation.review_unlistings)],
    ];
    const list = $('communityList');
    list.replaceChildren();
    items.forEach(([label, value]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', typeof value === 'number' ? number(value) : value));
      list.appendChild(row);
    });
  }

  function renderTitles(data) {
    const list = $('popularTitles');
    list.replaceChildren();
    if (!data.popular_titles.length) {
      list.appendChild(el('li', 'stats-empty stats-titles__empty', 'No title is in two or more libraries yet.'));
      return;
    }
    data.popular_titles.forEach(item => {
      const row = el('li');
      row.append(el('span', 'title', item.title), el('span', 'chip', item.category), el('span', 'count', `${number(item.members)} members`));
      list.appendChild(row);
    });
  }

  function renderHealth(data) {
    const list = $('healthList');
    list.replaceChildren();
    const system = data.system;
    const dbRow = el('li');
    dbRow.append(el('span', '', `Database: ${system.database}`), el('span', 'stats-status stats-status--ok', '✓ Connected'));
    list.appendChild(dbRow);
    if (system.title_details) {
      const details = system.title_details;
      const row = el('li');
      row.append(el('span', '', `Title pages: details found for ${number(details.found)} (${number(details.not_found)} not found, ${number(details.errors)} errors)`),
        el('span', `stats-status ${details.errors > details.found ? 'stats-status--warn' : 'stats-status--ok'}`, details.errors > details.found ? '! Check' : '✓ OK'));
      list.appendChild(row);
    }
    system.integrations.forEach(item => {
      const row = el('li');
      row.append(el('span', '', item.name), el('span', `stats-status ${item.configured ? 'stats-status--ok' : 'stats-status--warn'}`, item.configured ? '✓ Set up' : '! Not set'));
      list.appendChild(row);
    });
    $('radarTable').replaceChildren(table(['Release Radar', 'Titles', 'Updated'], system.release_radar.map(entry => [
      `${entry.category} · ${entry.window || '—'}`,
      number(entry.items),
      entry.error ? `error (${entry.error})` : entry.age_hours === null ? 'not loaded yet' : entry.age_hours < 1 ? 'under 1h ago' : `${entry.age_hours}h ago`,
    ])));
  }

  function renderMembers(data) {
    const rows = data.insights.recent_users.map(user => [
      user.username,
      dayOnly(user.joined_at),
      user.is_verified ? 'Yes' : 'No',
      number(user.library_items),
      number(user.activity_entries),
      dayOnly(user.last_activity_at),
    ]);
    $('recentMembers').replaceChildren(rows.length ? table(['Member', 'Joined', 'Verified', 'Titles', 'Journal', 'Last journal entry'], rows, 3) : el('p', 'stats-empty', 'No members yet.'));
  }

  function renderEditor(data) {
    const info = data.editor_collections;
    const card = $('editorCard');
    if (!card || !info) return;
    const list = $('editorList');
    list.replaceChildren();
    const published = new Set(info.published_names || []);
    info.names.forEach(name => {
      const row = el('li');
      const done = info.published >= info.available || published.has(name);
      row.append(el('span', '', name), el('span', `stats-status ${done ? 'stats-status--ok' : 'stats-status--warn'}`, done ? '✓ Published' : 'Not yet'));
      list.appendChild(row);
    });
    const all = info.published >= info.available;
    $('editorPublish').hidden = all;
    $('editorSummary').textContent = all
      ? `All ${info.available} starter collections are live on the public Collections page. Edit or unpublish them like any other collection.`
      : `${info.published} of ${info.available} starter collections published. Publishing adds them to the public Collections page under an editors account (not your library).`;
  }

  async function publishEditor() {
    const button = $('editorPublish');
    const status = $('editorStatus');
    button.disabled = true;
    button.textContent = 'Publishing… (looking up cover art)';
    try {
      const response = await fetch('/api/site-stats/editor-collections', { method: 'POST', credentials: 'same-origin', headers: authHeaders() });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      const listed = result.created.filter(item => item.listed).length;
      const art = result.created.reduce((sum, item) => sum + item.with_artwork, 0);
      const items = result.created.reduce((sum, item) => sum + item.items, 0);
      status.textContent = result.created.length
        ? `Published ${result.created.length} collection${result.created.length === 1 ? '' : 's'} (${listed} listed publicly, cover art found for ${art} of ${items} titles).`
        : 'Everything was already published.';
      if (state.data) {
        state.data.editor_collections = result.status;
        renderEditor(state.data);
      }
    } catch (error) {
      status.textContent = `Could not publish: ${error.message}`;
    } finally {
      button.disabled = false;
      button.textContent = 'Publish collections';
    }
  }

  const ANNOUNCEMENT_STATES = {
    draft: 'Not started',
    sending: 'Sending (about 30 a day)',
    paused: 'Paused',
    done: 'Finished',
  };

  function renderAnnouncement(data) {
    const info = data.announcement;
    const card = $('announcementCard');
    if (!card) return;
    card.hidden = !info;
    if (!info) return;
    const rows = [
      ['Status', ANNOUNCEMENT_STATES[info.status] || info.status],
      ['Sent', number(info.sent)],
      ['Still to send', number(info.remaining)],
      ['Failed', number(info.failed)],
      ['Unsubscribed from updates', number(info.opted_out)],
      ['Daily limit', `${number(info.daily_limit)} (keeps room for sign-up and reset emails on the free Mailgun plan)`],
    ];
    if (info.status !== 'done' && info.days_to_finish) rows.push(['Time to reach everyone', `about ${info.days_to_finish} day${info.days_to_finish === 1 ? '' : 's'}`]);
    if (!info.mail_configured) rows.push(['Email', 'NOT configured on this server: nothing can be sent']);
    const list = $('announcementList');
    list.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', String(value)));
      list.appendChild(row);
    });
    $('announcementStart').hidden = info.status === 'sending' || info.status === 'done';
    $('announcementStart').textContent = info.status === 'paused' ? 'Resume sending' : 'Start sending';
    $('announcementPause').hidden = info.status !== 'sending';
  }

  async function announcementAction(action) {
    const status = $('announcementStatus');
    if (action === 'start' && !window.confirm('Start sending the “What’s new” email to verified members? About 30 go out per day, and you can pause any time.')) return;
    const buttons = document.querySelectorAll('[data-announcement]');
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = action === 'test' ? 'Sending a test to your email…' : 'Saving…';
    try {
      const response = await fetch('/api/site-stats/announcement', {
        method: 'POST', credentials: 'same-origin',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      if (state.data) {
        state.data.announcement = result;
        renderAnnouncement(state.data);
      }
      status.textContent = result.message || (action === 'start' ? 'Started. The first batch goes out within the hour.' : 'Paused. Nothing more will be sent until you resume.');
    } catch (error) {
      status.textContent = `Couldn't do that: ${error.message}`;
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  function render(data) {
    state.data = data;
    $('statsUpdated').textContent = `Updated ${dateTime(data.generated_at)} · last ${data.days} days · signed in as ${data.viewer}`;
    $('statsPrivacy').textContent = `${data.insights.privacy_note} Traffic counts are anonymous daily totals: no cookies, IP addresses, or per-visitor records are stored; visitors are estimated per day.`;
    renderKpis(data);
    renderTraffic(data);
    renderGrowth(data);
    renderFunnel(data);
    renderSignupFunnel(data);
    renderLibraries(data);
    renderCommunity(data);
    renderTitles(data);
    renderHealth(data);
    renderMembers(data);
    renderEditor(data);
    renderAnnouncement(data);
  }

  // ---------------------------------------------------------------- report
  function buildReport(data) {
    const { traffic, members, insights, days } = data;
    const list = items => items.map(item => `${item.key} (${number(item.count)})`).join(', ') || 'none yet';
    const lines = [
      `OmniTrackr site stats — last ${days} days (generated ${dateTime(data.generated_at)})`,
      '',
      `Traffic: ${number(traffic.totals.visitors)} visitors, ${number(traffic.totals.views)} page views (previous ${days} days: ${number(traffic.previous_totals.visitors)} visitors, ${number(traffic.previous_totals.views)} views). Counting since ${traffic.tracking_since || 'not started'}.`,
      `Top pages: ${list(traffic.top_pages.slice(0, 10))}`,
      `Sources: ${list(traffic.sources.slice(0, 10))}`,
      `Devices: ${list(traffic.devices)} · Audience: ${list(traffic.audience)}`,
      '',
      `Members: ${number(insights.users.total)} total, ${number(insights.users.verified)} verified, ${number(members.new_in_range)} new (previous ${days} days: ${number(members.new_previous_range)}).`,
      `Active (logged in): ${number(members.active_24_hours)} in 24h, ${number(members.active_7_days)} in 7 days, ${number(members.active_30_days)} in 30 days.`,
      `Journey: ${insights.activation.map(stage => `${stage.label} ${number(stage.count)}`).join(' → ')}`,
      data.funnel ? `Sign-up funnel: ${data.funnel.steps.map(step => `${step.label} ${number(step.count)}`).join(' → ')}` : '',
      data.funnel ? `Sign-up issues: ${data.funnel.issues.filter(item => item.count).map(item => `${item.label} ${number(item.count)}`).join('; ') || 'none'}` : '',
      data.funnel ? `Guest lists: ${data.funnel.guest.map(item => `${item.label} ${number(item.count)}`).join('; ')}` : '',
      data.retention ? `Return features: ${number(data.retention.weekly_email_subscribers)} weekly email subscribers, ${number(data.retention.public_profiles)} public profiles on.` : '',
      '',
      `Libraries: ${number(insights.content.total_items)} titles (${insights.content.categories.map(category => `${category.label} ${number(category.total)}`).join(', ')}), ${number(insights.content.public_reviews)} public reviews, ${number(insights.content.custom_items)} custom-tab items.`,
      `Community: ${number(insights.moderation.approved)} listed public collections, ${number(insights.moderation.views)} collection views, ${number(insights.engagement.friendships)} friendships, ${number(insights.engagement.activity_entries_30_days)} journal entries in 30 days, reports ${number(insights.moderation.reports)}/${number(insights.moderation.review_reports)}.`,
      `Most tracked: ${data.popular_titles.slice(0, 8).map(item => `${item.title} [${item.category}] ${item.members}`).join('; ') || 'none yet'}`,
      '',
      `Health: ${data.system.database}; ${data.system.integrations.map(item => `${item.name}: ${item.configured ? 'ok' : 'NOT SET'}`).join('; ')}.`,
      `Release Radar: ${data.system.release_radar.map(entry => `${entry.category} ${entry.items} titles${entry.error ? ` (${entry.error})` : ''}`).join(', ')}.`,
      data.system.title_details ? `Title pages: details for ${number(data.system.title_details.found)}, not found ${number(data.system.title_details.not_found)}, errors ${number(data.system.title_details.errors)}.` : '',
    ];
    return lines.filter((line, index) => line !== '' || (index > 0 && lines[index - 1] !== '')).join('\n');
  }

  async function copyReport() {
    if (!state.data) return;
    const text = buildReport(state.data);
    const toast = $('statsToast');
    try {
      await navigator.clipboard.writeText(text);
      toast.textContent = 'Report copied. Paste it into your chat with Claude.';
    } catch (error) {
      const area = el('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.className = 'stats-copy-fallback';
      document.body.appendChild(area);
      area.select();
      const copied = document.execCommand && document.execCommand('copy');
      area.remove();
      toast.textContent = copied ? 'Report copied. Paste it into your chat with Claude.' : 'Copy was blocked by the browser. Try again after clicking the page.';
    }
  }

  // ---------------------------------------------------------------- loading
  function gate(title, text, action) {
    $('statsBody').hidden = true;
    $('statsGate').hidden = false;
    $('statsGateTitle').textContent = title;
    $('statsGateText').textContent = text;
    const link = $('statsGateAction');
    link.textContent = action.label;
    link.href = action.href;
    document.querySelector('.stats-controls').hidden = true;
    $('statsUpdated').textContent = '';
  }

  function authHeaders() {
    const headers = { Accept: 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) {
      // Cookie sessions work without storage.
    }
    return headers;
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    $('statsBody').setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(`/api/site-stats/overview?days=${state.days}`, { credentials: 'same-origin', headers: authHeaders() });
      if (response.status === 401) {
        gate('Log in to see site stats', 'This page shows live numbers for the site owner. Log in with the owner account first.', { label: 'Log in', href: '/#landing-auth' });
        return;
      }
      if (response.status === 403) {
        gate('This page is for the site owner', 'Only the site owner can see these numbers. (Owner: add your username to the ADMIN_USERNAMES environment variable on Render, then redeploy.)', { label: 'Back to my library', href: '/' });
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
      $('statsToast').textContent = '';
    } catch (error) {
      $('statsToast').textContent = 'Could not load the latest numbers. Check your connection and press Refresh.';
    } finally {
      state.loading = false;
      $('statsBody').setAttribute('aria-busy', 'false');
    }
  }

  function init() {
    document.querySelectorAll('[data-range]').forEach(button => {
      button.addEventListener('click', () => {
        state.days = Number(button.dataset.range);
        document.querySelectorAll('[data-range]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        load();
      });
    });
    $('statsRefresh').addEventListener('click', load);
    $('statsCopy').addEventListener('click', copyReport);
    $('editorPublish')?.addEventListener('click', publishEditor);
    document.querySelectorAll('[data-announcement]').forEach(button => {
      button.addEventListener('click', () => announcementAction(button.dataset.announcement));
    });
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (!state.data) return;
        renderTraffic(state.data);
        renderGrowth(state.data);
      }, 150);
    });
    load();
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { buildReport, niceMax, delta, percent };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
