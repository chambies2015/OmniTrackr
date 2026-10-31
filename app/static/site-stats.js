// Owner-only Site stats page. Everything is built with DOM APIs and textContent;
// no server string is ever inserted as HTML.
(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const COLORS = { views: '#8b5cf6', visitors: '#0d9488' };
  const DEVICE_COLORS = { desktop: '#8b5cf6', mobile: '#0d9488', tablet: '#d97706' };
  const AUDIENCE_COLORS = { guest: '#8b5cf6', member: '#0d9488' };
  const state = { days: 30, data: null, loading: false, trafficView: null };

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

  // "Likely people" once those counts exist; before that, every request.
  function peopleCounted(traffic) {
    return Boolean(traffic.human && traffic.human.tracking_since);
  }

  function trafficView(traffic) {
    if (state.trafficView) return state.trafficView;
    return peopleCounted(traffic) ? 'human' : 'all';
  }

  function trafficSet(traffic, view = trafficView(traffic)) {
    return view === 'human' && traffic.human ? traffic.human : traffic;
  }

  function renderKpis(data) {
    const { traffic, members, insights, days } = data;
    const range = `vs previous ${days} days`;
    const people = peopleCounted(traffic);
    const shown = people ? traffic.human : traffic;
    const since = shown.tracking_since;
    // Only compare with the previous range when it was counted the same way.
    const comparable = since && shown.previous_totals.views > 0;
    $('statsKpis').replaceChildren(
      kpi(people ? 'Visitors (people)' : 'Visitors', number(shown.totals.visitors),
        people ? `${number(traffic.totals.visitors)} in all requests` : (since ? range : 'counting starts after deploy'),
        comparable ? delta(shown.totals.visitors, shown.previous_totals.visitors) : null),
      kpi(people ? 'Page views (people)' : 'Page views', number(shown.totals.views),
        people ? `${number(traffic.totals.views)} in all requests · ${number(shown.today.views)} today` : `${number(shown.today.views)} today`,
        comparable ? delta(shown.totals.views, shown.previous_totals.views) : null),
      kpi('New members', number(members.new_in_range), range, delta(members.new_in_range, members.new_previous_range)),
      kpi('Total members', number(insights.users.total), `${number(insights.users.verified)} verified · ${number(members.new_today)} joined today`),
      kpi('Active members', number(members.active_7_days), `logged in this week · ${number(members.active_24_hours)} today · ${number(members.active_30_days)} this month`),
      kpi('Titles tracked', number(insights.content.total_items), `${number(insights.content.public_reviews)} public reviews`),
    );
  }

  function renderTraffic(data) {
    const view = trafficView(data.traffic);
    const traffic = trafficSet(data.traffic, view);
    const enabled = data.traffic.enabled;
    document.querySelectorAll('[data-traffic-view]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.trafficView === view));
    });
    const dates = traffic.series.map(day => day.date);
    const since = traffic.tracking_since ? `Counting since ${dayOnly(traffic.tracking_since)}.` : 'Counting starts once this update is deployed.';
    $('trafficNote').textContent = view === 'human'
      ? `Pages a person opened in a real browser tab, and estimated people per day. Bots, scanners, crawlers and repeat reloads are left out. ${since}`
      : `Every page the server sent to something that doesn't call itself a bot, scanners and scripts included. ${since}`;
    lineChart($('trafficChart'), dates, [
      { key: 'views', label: 'Page views', shortLabel: 'Views', color: COLORS.views, values: traffic.series.map(day => day.views) },
      { key: 'visitors', label: 'Visitors', color: COLORS.visitors, values: traffic.series.map(day => day.visitors) },
    ], enabled ? 'No visits recorded in this range yet. Numbers appear within a minute of the first visit.' : 'Traffic counting is turned off (SITE_TRAFFIC_TRACKING).', { partialLast: true });
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

  // Ranges from before people were counted start from every homepage load instead.
  function funnelSteps(funnel) {
    const steps = funnel.steps.slice();
    const seen = steps.find(step => step.event === 'landing_seen');
    const loads = (funnel.raw || []).find(item => item.event === 'landing_viewed');
    if (seen && !seen.count && loads && loads.count) {
      steps[steps.indexOf(seen)] = { event: 'landing_viewed', label: 'Homepage loads, all requests', count: loads.count,
        detail: 'People were not counted separately yet in this range' };
    }
    return steps;
  }

  function drawSteps(container, steps) {
    container.replaceChildren();
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
      const label = el('div', 'stats-step__label', step.label);
      if (step.detail) label.appendChild(el('small', '', step.detail));
      row.append(label, track, value);
      container.appendChild(row);
    });
  }

  function renderSignupFunnel(data) {
    const container = $('signupFunnel');
    if (!container || !data.funnel) return;
    drawSteps(container, funnelSteps(data.funnel));
    if ($('homepageFunnel') && data.funnel.homepage) drawSteps($('homepageFunnel'), data.funnel.homepage);
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
    if ($('googleSignin')) fillList('googleSignin', data.funnel.google || []);
    if ($('startFunnel') && data.funnel.start) drawSteps($('startFunnel'), data.funnel.start);
    if ($('startPaths') && data.funnel.start_paths) fillList('startPaths', data.funnel.start_paths);
    const retention = data.retention || {};
    fillList('guestList', [
      ...data.funnel.guest,
      { label: 'Weekly email subscribers (now)', count: retention.weekly_email_subscribers || 0 },
      { label: 'Public profiles switched on (now)', count: retention.public_profiles || 0 },
    ]);
  }

  function growthRows(growth) {
    const { invites, supporters, weekly_email: email, takes } = growth;
    const calendar = growth.calendar || {};
    const push = growth.push || {};
    return {
      growthInvites: [
        { label: 'Sign-ups through an invite', count: invites.signups },
        { label: 'Friendships made by invites', count: invites.friends_made },
        { label: 'Invited, waiting to verify email (now)', count: invites.awaiting_verification },
        { label: 'Invite links created', count: invites.new_links },
        { label: 'Members with a link (all time)', count: invites.links },
      ],
      growthSupporters: [
        { label: 'Active supporters (now)', count: supporters.active },
        { label: 'Monthly members (now)', count: supporters.monthly },
        { label: 'New supporters', count: supporters.new },
        { label: 'Ko-fi payments received', count: supporters.payments },
        { label: 'Payments waiting to be linked (now)', count: supporters.unlinked_payments },
        { label: 'Supporters (all time)', count: supporters.all_time },
      ],
      growthEmail: [
        { label: 'Subscribers (now)', count: email.subscribers },
        { label: 'New opt-ins', count: email.new },
        ...(email.opted_in_by_place || []).filter(item => item.count).map(item => ({ label: `Turned on from ${item.place}`, count: item.count })),
        { label: 'Turned off', count: email.opted_out || 0 },
        ...(email.opted_out_by_place || []).filter(item => item.count).map(item => ({ label: `Turned off from ${item.place}`, count: item.count })),
        { label: 'Members sent one', count: email.emailed || 0 },
        { label: 'Members sent one in the last 7 days (now)', count: email.emailed_7d || 0 },
      ],
      growthCalendar: [
        { label: 'Members with a private calendar (now)', count: calendar.feeds || 0 },
        { label: 'Calendars refreshed in the last 7 days (now)', count: calendar.refreshed_7d || 0 },
        { label: 'New private calendars', count: calendar.new || 0 },
      ],
      growthTakes: [
        { label: 'Links shared', count: takes.asked },
        { label: 'Friends who answered', count: takes.answered },
      ],
      growthPush: [
        { label: 'Members with notifications on (now)', count: push.members || 0 },
        { label: 'Devices turned on (now)', count: push.devices || 0 },
        { label: 'New devices', count: push.new_devices || 0 },
        { label: 'Members reached in the last 7 days (now)', count: push.reached_7d || 0 },
        { label: 'Notifications sent', count: push.sent || 0 },
        ...(push.sent_by_kind || []).map(item => ({ label: `Sent: ${item.kind}`, count: item.count })),
        { label: 'Away reminders sent', count: push.away_reminders || 0 },
      ],
    };
  }

  const GROWTH_HEADINGS = {
    growthInvites: 'Friend invite links',
    growthSupporters: 'Ko-fi supporters',
    growthEmail: 'Weekly email',
    growthCalendar: 'Release calendar',
    growthTakes: 'Ask a friend for their take',
    growthPush: 'Phone and browser notifications',
  };

  function growthReport(data) {
    if (!data.growth) return [];
    return [
      `Growth features (last ${data.days} days; "now" rows are current totals):`,
      ...Object.entries(growthRows(data.growth)).map(([id, items]) =>
        `- ${GROWTH_HEADINGS[id]}: ${items.map(item => `${item.label} ${number(item.count)}`).join('; ')}`),
    ];
  }

  function renderGrowthFeatures(data) {
    const card = $('growthCard');
    if (!card) return;
    card.hidden = !data.growth;
    if (!data.growth) return;
    $('growthNote').textContent = `Invite links, Ko-fi supporters, the weekly email, release calendars, "ask a friend" and phone notifications in the last ${data.days} days. Rows marked "now" are current totals.`;
    Object.entries(growthRows(data.growth)).forEach(([id, items]) => {
      const list = $(id);
      list.replaceChildren();
      items.forEach(item => {
        const row = el('div');
        row.append(el('dt', '', item.label), el('dd', '', number(item.count)));
        list.appendChild(row);
      });
    });
  }

  function paymentLabel(payment) {
    const amount = [payment.amount, payment.currency].filter(Boolean).join(' ');
    const kind = payment.monthly ? `${payment.kind || 'Payment'} (monthly)` : (payment.kind || 'Payment');
    return {
      name: payment.from_name || 'Name not given',
      detail: [amount, kind, payment.received_at ? `received ${dayOnly(payment.received_at)}` : ''].filter(Boolean).join(' · '),
    };
  }

  const kofi = { email: '' };

  function kofiSummary(payments, waiting, tests = 0) {
    const testNote = tests ? ` ${number(tests)} Ko-fi test payment${tests === 1 ? '' : 's'} left out.` : '';
    return kofiSummaryText(payments, waiting) + testNote;
  }

  function kofiSummaryText(payments, waiting) {
    if (kofi.email) {
      return payments.length
        ? `${payments.length} waiting payment${payments.length === 1 ? '' : 's'} came from ${kofi.email}.`
        : `No waiting payment came from ${kofi.email}. Ko-fi test pings and linked payments aren't listed.`;
    }
    if (!payments.length) return 'Every Ko-fi payment is linked to a member. Payments without a supporter code or matching email will show up here.';
    const shown = waiting > payments.length ? ` The newest ${payments.length} are shown.` : '';
    return `${number(waiting)} payment${waiting === 1 ? '' : 's'} came in without a supporter code or a matching verified email.${shown} ` +
      'Press a suggested member to link in one click, or type a username or email. Perks count from the day you link, so nobody loses days.';
  }

  function kofiButton(text, className, onClick) {
    const button = el('button', className, text);
    button.type = 'button';
    button.addEventListener('click', onClick);
    return button;
  }

  function renderKofiPayments(payments, extra = {}) {
    const list = $('kofiList');
    if (!list) return;
    list.replaceChildren();
    $('kofiSummary').textContent = kofiSummary(payments, extra.waiting ?? payments.length, extra.tests || 0);
    renderKofiMembers(extra.members);
    if (!payments.length) {
      list.appendChild(el('li', 'stats-kofi__empty', 'Nothing to link.'));
      return;
    }
    payments.forEach(payment => {
      const label = paymentLabel(payment);
      const row = el('li');
      const info = el('div', 'stats-kofi__info');
      const name = el('b', '', label.name);
      if (payment.looks_like_test) name.appendChild(el('span', 'stats-kofi__tag', 'Looks like a Ko-fi test'));
      if (payment.claimed) name.appendChild(el('span', 'stats-kofi__tag stats-kofi__tag--claim', 'Claimed by a member'));
      info.append(name, el('span', '', label.detail));
      const suggestions = Array.isArray(payment.suggestions) ? payment.suggestions : [];
      if (suggestions.length) {
        const picks = el('div', 'stats-kofi__picks');
        suggestions.forEach(member => {
          const pick = kofiButton(`Link to @${member.username}`, 'site-btn site-btn--primary site-btn--sm',
            () => linkPayment(payment.message_id, member.username, label.name, pick));
          pick.title = member.reason || '';
          picks.append(pick, el('small', '', member.reason || ''));
        });
        info.appendChild(picks);
      }
      const form = el('form', 'stats-kofi__form');
      const input = el('input');
      input.type = 'text';
      input.name = 'username';
      input.placeholder = 'Username or email';
      input.autocomplete = 'off';
      input.spellcheck = false;
      input.maxLength = 254;
      input.required = true;
      input.setAttribute('aria-label', `Username or email to link the payment from ${label.name} to`);
      const button = el('button', 'site-btn site-btn--ghost site-btn--sm', 'Link');
      button.type = 'submit';
      const aside = kofiButton('Set aside', 'stats-kofi__aside', () => setAside(payment.message_id, label.name, true, aside));
      aside.title = 'For a refund, a duplicate or a test. It stays recorded but leaves this list.';
      form.append(input, button, aside);
      form.addEventListener('submit', event => {
        event.preventDefault();
        const who = input.value.trim();
        if (who) linkPayment(payment.message_id, who, label.name, button);
      });
      row.append(info, form);
      list.appendChild(row);
    });
  }

  function renderKofiMembers(members) {
    const box = $('kofiMembers');
    if (!box) return;
    box.replaceChildren();
    box.hidden = !kofi.email;
    if (!kofi.email) return;
    if (!Array.isArray(members) || !members.length) {
      box.textContent = `No member account uses ${kofi.email} (case, Gmail dots and "+tags" aside).`;
      return;
    }
    box.append(`Member${members.length === 1 ? '' : 's'} with this email: `);
    members.forEach((member, index) => {
      if (index) box.append(', ');
      box.append(el('b', '', `@${member.username}`), member.verified ? '' : ' (not verified)');
    });
  }

  async function loadKofiPayments() {
    if (!$('kofiList')) return;
    const query = kofi.email ? `?email=${encodeURIComponent(kofi.email)}` : '';
    try {
      const response = await fetch(`/api/supporters/unmatched${query}`, { credentials: 'same-origin', headers: authHeaders() });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `HTTP ${response.status}`);
      renderKofiPayments(result.payments || [], result);
    } catch (error) {
      $('kofiStatus').textContent = kofi.email
        ? `Could not search: ${error.message}`
        : 'Could not load Ko-fi payments. Press Refresh to try again.';
    }
  }

  function searchKofi(email) {
    kofi.email = (email || '').trim();
    $('kofiSearchClear').hidden = !kofi.email;
    $('kofiStatus').textContent = '';
    loadKofiPayments();
  }

  async function postKofi(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `HTTP ${response.status}`);
    return result;
  }

  async function linkPayment(messageId, who, name, button) {
    const status = $('kofiStatus');
    const target = who.includes('@') && !who.startsWith('@') ? who : `@${who.replace(/^@/, '')}`;
    if (!window.confirm(`Link the Ko-fi payment from ${name} to ${target}? Their supporter perks switch on right away and they get a note saying so.`)) return;
    button.disabled = true;
    try {
      const result = await postKofi('/api/supporters/link', { message_id: messageId, username: who });
      status.textContent = `Linked to @${result.username}. Their supporter perks are on.`;
      await load();
    } catch (error) {
      status.textContent = `Could not link: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  }

  async function setAside(messageId, name, setIt, button) {
    const status = $('kofiStatus');
    if (button) button.disabled = true;
    try {
      await postKofi('/api/supporters/set-aside', { message_id: messageId, set_aside: setIt });
      status.replaceChildren(setIt ? `Set aside the payment from ${name}. ` : `Put the payment from ${name} back on the list.`);
      if (setIt) status.appendChild(kofiButton('Undo', 'stats-kofi__aside', () => setAside(messageId, name, false)));
      await load();
    } catch (error) {
      status.textContent = `Could not change it: ${error.message}`;
    } finally {
      if (button) button.disabled = false;
    }
  }

  function bindKofiSearch() {
    const form = $('kofiSearch');
    if (!form) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      searchKofi($('kofiSearchEmail').value);
    });
    $('kofiSearchClear').addEventListener('click', () => {
      $('kofiSearchEmail').value = '';
      searchKofi('');
    });
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
    const outdated = (info.outdated_names || []).length;
    $('editorPublish').hidden = all && !outdated;
    $('editorPublish').textContent = all ? 'Update wording' : 'Publish collections';
    $('editorSummary').textContent = all
      ? (outdated
        ? `All ${info.available} starter collections are live. ${outdated} still use${outdated === 1 ? 's' : ''} older wording; updating changes only text nobody has edited since.`
        : `All ${info.available} starter collections are live on the public Collections page. Edit or unpublish them like any other collection.`)
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
      const updated = (result.updated || []).length;
      const wording = updated ? ` Updated the wording on ${updated} collection${updated === 1 ? '' : 's'}.` : '';
      status.textContent = result.created.length
        ? `Published ${result.created.length} collection${result.created.length === 1 ? '' : 's'} (${listed} listed publicly, cover art found for ${art} of ${items} titles).${wording}`
        : (updated ? wording.trim() : 'Everything was already published.');
      if (state.data) {
        state.data.editor_collections = result.status;
        renderEditor(state.data);
      }
    } catch (error) {
      status.textContent = `Could not publish: ${error.message}`;
    } finally {
      button.disabled = false;
      if (state.data) renderEditor(state.data);
      else button.textContent = 'Publish collections';
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

  const COMEBACK_STATES = {
    draft: 'Not started',
    sending: 'On: checking every hour',
    paused: 'Paused',
  };

  function renderComeback(data) {
    const info = data.comeback;
    const card = $('comebackCard');
    if (!card) return;
    card.hidden = !info;
    if (!info) return;
    let statusLabel = COMEBACK_STATES[info.status] || info.status;
    if (info.status === 'sending' && info.waiting_on_whats_new) statusLabel = 'On, waiting until the “What’s new” email finishes';
    const rows = [
      ['Status', statusLabel],
      ['Members due now', `${number(info.due_now)} (away ${info.away_days}+ days)`],
      ['Sent in the last 30 days', number(info.sent_30d)],
      [`Came back within ${info.came_back_window_days} days of one`, number(info.came_back)],
      ['Sent all time', number(info.sent_all_time)],
      ['Daily limit', `${number(info.daily_limit)} (shares the daily email budget, so sign-up and reset emails always go out)`],
    ];
    if (!info.mail_configured) rows.push(['Email', 'NOT configured on this server: nothing can be sent']);
    const list = $('comebackList');
    list.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', String(value)));
      list.appendChild(row);
    });
    $('comebackStart').hidden = info.status === 'sending';
    $('comebackStart').textContent = info.status === 'paused' ? 'Resume sending' : 'Start sending';
    $('comebackPause').hidden = info.status !== 'sending';
  }

  async function comebackAction(action) {
    const status = $('comebackStatus');
    if (action === 'start' && !window.confirm('Turn on the come-back email? Members away 30+ days get one personal check-in, at most every 60 days, up to 20 a day. You can pause any time.')) return;
    const buttons = document.querySelectorAll('[data-comeback]');
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = action === 'test' ? 'Sending a test to your email…' : 'Saving…';
    try {
      const response = await fetch('/api/site-stats/comeback', {
        method: 'POST', credentials: 'same-origin',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      if (state.data) {
        state.data.comeback = result;
        renderComeback(state.data);
      }
      status.textContent = result.message || (action === 'start' ? 'On. The first emails go out within the hour.' : 'Paused. Nothing more will be sent until you resume.');
    } catch (error) {
      status.textContent = `Couldn't do that: ${error.message}`;
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  }

  function renderWelcome(data) {
    const info = data.welcome;
    const card = $('welcomeCard');
    if (!card) return;
    card.hidden = !info;
    if (!info) return;
    const rows = [
      ['Status', COMEBACK_STATES[info.status] || info.status],
      ['Started', info.started_at ? `${dateTime(info.started_at)} (${number(info.joined_since_start)} members joined since)` : 'Not yet'],
      ['Members due now', number(info.due_now)],
      ...info.steps.map(step => [`${step.label}, last 30 days`, number(step.sent_30d)]),
      [`Came back within ${info.came_back_window_days} days of one`, `${number(info.came_back)} of ${number(info.sent_30d)}`],
      ['Daily limit', `${number(info.daily_limit)} (shares the daily email budget, so sign-up and reset emails always go out)`],
    ];
    if (!info.mail_configured) rows.push(['Email', 'NOT configured on this server: nothing can be sent']);
    const list = $('welcomeList');
    list.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = el('div');
      row.append(el('dt', '', label), el('dd', '', String(value)));
      list.appendChild(row);
    });
    $('welcomeStart').hidden = info.status === 'sending';
    $('welcomeStart').textContent = info.status === 'paused' ? 'Resume sending' : 'Start sending';
    $('welcomePause').hidden = info.status !== 'sending';
  }

  async function welcomeAction(action) {
    const status = $('welcomeStatus');
    if (action === 'start' && !window.confirm('Turn on the welcome emails? Members who sign up from now on get three short emails in their first week, up to 20 a day. Nobody who already has an account gets them. You can pause any time.')) return;
    const buttons = document.querySelectorAll('[data-welcome]');
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = action === 'test' ? 'Sending all three to your email…' : 'Saving…';
    try {
      const response = await fetch('/api/site-stats/welcome', {
        method: 'POST', credentials: 'same-origin',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
      if (state.data) {
        state.data.welcome = result;
        renderWelcome(state.data);
      }
      status.textContent = result.message || (action === 'start' ? 'On. Members who join from now on get the first one a day after signing up.' : 'Paused. Nothing more will be sent until you resume.');
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
    renderGrowthFeatures(data);
    renderLibraries(data);
    renderCommunity(data);
    renderTitles(data);
    renderHealth(data);
    renderMembers(data);
    renderEditor(data);
    renderAnnouncement(data);
    renderComeback(data);
    renderWelcome(data);
  }

  // ---------------------------------------------------------------- report
  function buildReport(data) {
    const { traffic, members, insights, days } = data;
    const list = items => items.map(item => `${item.key} (${number(item.count)})`).join(', ') || 'none yet';
    const people = traffic.human;
    const peopleLines = people && people.tracking_since ? [
      `Traffic, likely people (pages opened in a real browser tab; bots, scanners and reloads left out): ${number(people.totals.visitors)} visitors, ${number(people.totals.views)} page views (previous ${days} days: ${number(people.previous_totals.visitors)} visitors, ${number(people.previous_totals.views)} views). Counting since ${people.tracking_since}.`,
      `People, top pages: ${list(people.top_pages.slice(0, 10))}`,
      `People, sources: ${list(people.sources.slice(0, 10))}`,
      `People, devices: ${list(people.devices)} · Audience: ${list(people.audience)}`,
      '',
    ] : [];
    const lines = [
      `OmniTrackr site stats — last ${days} days (generated ${dateTime(data.generated_at)})`,
      '',
      ...peopleLines,
      `Traffic${peopleLines.length ? ', all requests (bots and scanners included)' : ''}: ${number(traffic.totals.visitors)} visitors, ${number(traffic.totals.views)} page views (previous ${days} days: ${number(traffic.previous_totals.visitors)} visitors, ${number(traffic.previous_totals.views)} views). Counting since ${traffic.tracking_since || 'not started'}.`,
      `Top pages: ${list(traffic.top_pages.slice(0, 10))}`,
      `Sources: ${list(traffic.sources.slice(0, 10))}`,
      `Devices: ${list(traffic.devices)} · Audience: ${list(traffic.audience)}`,
      '',
      `Members: ${number(insights.users.total)} total, ${number(insights.users.verified)} verified, ${number(members.new_in_range)} new (previous ${days} days: ${number(members.new_previous_range)}).`,
      `Active (logged in or visited): ${number(members.active_24_hours)} in 24h, ${number(members.active_7_days)} in 7 days, ${number(members.active_30_days)} in 30 days.`,
      `Journey: ${insights.activation.map(stage => `${stage.label} ${number(stage.count)}`).join(' → ')}`,
      data.funnel ? `Sign-up funnel: ${funnelSteps(data.funnel).map(step => `${step.label} ${number(step.count)}${step.detail ? ` (${step.detail})` : ''}`).join(' → ')}` : '',
      data.funnel && data.funnel.homepage ? `Homepage path: ${data.funnel.homepage.map(step => `${step.label} ${number(step.count)}`).join(' → ')}` : '',
      data.funnel ? `Sign-up issues: ${data.funnel.issues.filter(item => item.count).map(item => `${item.label} ${number(item.count)}`).join('; ') || 'none'}` : '',
      data.funnel ? `Guest lists: ${data.funnel.guest.map(item => `${item.label} ${number(item.count)}`).join('; ')}` : '',
      data.funnel && data.funnel.google ? `Google sign-in: ${data.funnel.google.map(item => `${item.label} ${number(item.count)}`).join('; ')}` : '',
      data.funnel && data.funnel.start ? `Start page: ${data.funnel.start.map(step => `${step.label} ${number(step.count)}`).join(' → ')}; ${(data.funnel.start_paths || []).map(item => `${item.label} ${number(item.count)}`).join('; ')}` : '',
      ...growthReport(data),
      data.announcement ? `What's new email: ${data.announcement.status}, ${number(data.announcement.sent)} sent, ${number(data.announcement.remaining)} still to send, ${number(data.announcement.opted_out)} unsubscribed from updates.` : '',
      data.comeback ? `Come-back email: ${data.comeback.status}, ${number(data.comeback.due_now)} members due now, ${number(data.comeback.sent_30d)} sent in 30 days, ${number(data.comeback.came_back)} came back within ${data.comeback.came_back_window_days} days of one.` : '',
      data.welcome ? `Welcome emails: ${data.welcome.status}, ${number(data.welcome.sent_30d)} sent in 30 days, ${number(data.welcome.came_back)} came back within ${data.welcome.came_back_window_days} days of one.` : '',
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
      loadKofiPayments();
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
    document.querySelectorAll('[data-traffic-view]').forEach(button => {
      button.addEventListener('click', () => {
        state.trafficView = button.dataset.trafficView;
        if (state.data) renderTraffic(state.data);
      });
    });
    $('statsRefresh').addEventListener('click', load);
    $('statsCopy').addEventListener('click', copyReport);
    $('editorPublish')?.addEventListener('click', publishEditor);
    bindKofiSearch();
    document.querySelectorAll('[data-announcement]').forEach(button => {
      button.addEventListener('click', () => announcementAction(button.dataset.announcement));
    });
    document.querySelectorAll('[data-comeback]').forEach(button => {
      button.addEventListener('click', () => comebackAction(button.dataset.comeback));
    });
    document.querySelectorAll('[data-welcome]').forEach(button => {
      button.addEventListener('click', () => welcomeAction(button.dataset.welcome));
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
    module.exports = { buildReport, growthRows, paymentLabel, kofiSummary, niceMax, delta, percent, funnelSteps, trafficSet };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
