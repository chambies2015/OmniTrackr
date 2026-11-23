// Break planner (/break): the sample plan for visitors, and the member's own plan (set up, the day-by-day
// board, ticks, moves, swaps, sharing). The plan itself is built on the server (app/break_plan.py).
// Everything from the server or the member's library is put on the page with textContent, never as HTML.
(function () {
  'use strict';

  const DAY_MS = 86400000;

  // ------------------------------------------------------------------ pure helpers (also used by tests)

  function pad(n) { return String(n).padStart(2, '0'); }

  function isoDay(when) {
    return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`;
  }

  function parseDay(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    if (!match) return null;
    const when = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return Number.isNaN(when.getTime()) ? null : when;
  }

  function daysBetween(startIso, endIso, max = 16) {
    const start = parseDay(startIso);
    const end = parseDay(endIso);
    if (!start || !end || end < start) return [];
    const found = [];
    for (let when = new Date(start.getTime()); when <= end && found.length < max; when.setDate(when.getDate() + 1)) {
      found.push(isoDay(when));
    }
    return found;
  }

  function hoursWords(minutes) {
    const value = Math.max(0, Math.round(Number(minutes) || 0));
    if (value === 0) return 'Busy';
    if (value < 60) return `${value} min`;
    const hours = Math.round(value / 30) / 2;
    return `${hours} hour${hours === 1 ? '' : 's'}`;
  }

  function lengthWords(minutes) {
    const value = Math.max(0, Math.round(Number(minutes) || 0));
    if (value < 60) return `${value} min`;
    const hours = Math.floor(value / 60);
    const rest = value % 60;
    return rest ? `${hours}h ${pad(rest)}m` : `${hours}h`;
  }

  // Minutes for each day: the daily amount, and a light hour on Thanksgiving Day or Christmas Day.
  function dayDefaults(days, daily, light, lightMinutes = 60) {
    const lightSet = new Set(light || []);
    const found = {};
    days.forEach(day => { found[day] = lightSet.has(day) ? Math.min(daily, lightMinutes) : daily; });
    return found;
  }

  function fillShare(planned, budget) {
    if (!(budget > 0)) return planned > 0 ? 100 : 0;
    return Math.max(0, Math.min(100, Math.round(planned / budget * 100)));
  }

  function phaseLine(plan) {
    if (!plan) return '';
    if (plan.phase === 'upcoming') {
      const start = parseDay(plan.starts_on);
      const today = parseDay(plan.today);
      const away = start && today ? Math.round((start - today) / DAY_MS) : null;
      if (away === 1) return 'Starts tomorrow';
      if (away !== null && away < 7 && start) return `Starts ${start.toLocaleDateString(undefined, { weekday: 'long' })}`;
      return `Starts ${start ? start.toLocaleDateString(undefined, { month: 'long', day: 'numeric' }) : ''}`;
    }
    if (plan.phase === 'during') return `Day ${plan.day_number} of ${plan.day_count}`;
    return 'All done';
  }

  const helpers = { isoDay, parseDay, daysBetween, hoursWords, lengthWords, dayDefaults, fillShare, phaseLine };
  if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------ page helpers

  const todayIso = () => isoDay(new Date());
  const tz = () => -new Date().getTimezoneOffset();

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(text, className, onClick) {
    const node = el('button', className || 'bp-pill', text);
    node.type = 'button';
    if (onClick) node.addEventListener('click', onClick);
    return node;
  }

  const reported = new Set();
  function report(event) {
    if (reported.has(event)) return;
    reported.add(event);
    try {
      navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
    } catch (error) { /* analytics only */ }
  }
  document.addEventListener('click', event => {
    if (event.target.closest && event.target.closest('[data-break-signup]')) report('break_signup_clicked');
  });

  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', credentials: 'same-origin', headers: { Accept: 'application/json' } };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify({ today: todayIso(), ...options.body });
    }
    const joiner = path.includes('?') ? '&' : '?';
    const url = init.method === 'GET' || init.method === 'DELETE' ? `${path}${joiner}today=${todayIso()}` : path;
    const response = await fetch(url, init);
    if (response.status === 401 && !options.guest) {
      window.location.href = `/?next=${encodeURIComponent('/break')}#login`;
      throw new Error('Please log in again.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail[0] && data.detail[0].msg : data.detail;
      if (response.status === 429 && !detail) throw new Error('Slow down a little and try again in a minute.');
      throw new Error(String(detail || 'Something went wrong. Please try again.').replace(/^Value error, /, ''));
    }
    return data;
  }

  function art(item) {
    const frame = el('span', 'bp-art');
    const letter = () => {
      const empty = el('span', 'bp-art__empty', (String(item.title || '?').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase());
      empty.setAttribute('aria-hidden', 'true');
      frame.replaceChildren(empty);
    };
    if (typeof item.image === 'string' && /^https:\/\//.test(item.image)) {
      const image = el('img');
      image.src = item.image;
      image.alt = '';
      image.loading = 'lazy';
      image.referrerPolicy = 'no-referrer';
      image.width = 36;
      image.height = 54;
      image.addEventListener('error', letter, { once: true });
      frame.appendChild(image);
    } else {
      letter();
    }
    return frame;
  }

  function dayColumn(day, options = {}) {
    const column = el('li', 'bp-col');
    if (day.today) column.dataset.today = 'true';
    if (day.past) column.dataset.past = 'true';
    const head = el('p', 'bp-col__day', day.label);
    if (day.today) head.appendChild(el('span', 'bp-col__today', 'Today'));
    column.appendChild(head);
    const time = el('p', 'bp-col__time');
    const over = day.planned > day.budget + 10;
    if (over) time.dataset.over = 'true';
    if (day.budget) {
      time.append(el('strong', null, lengthWords(day.planned)), document.createTextNode(` planned of ${hoursWords(day.budget)}`));
    } else {
      time.textContent = day.planned ? `Busy day, ${lengthWords(day.planned)} planned` : 'Busy day';
    }
    column.appendChild(time);
    const bar = el('div', 'bp-bar');
    bar.setAttribute('aria-hidden', 'true');
    if (over) bar.dataset.over = 'true';
    bar.style.setProperty('--bp-fill', `${fillShare(day.planned, day.budget)}%`);
    column.appendChild(bar);
    const list = el('ul', 'bp-col__items');
    (day.items || []).forEach(item => list.appendChild(options.item ? options.item(item, day) : demoChip(item)));
    if (!list.children.length) column.appendChild(el('p', 'bp-col__empty', day.budget ? 'Nothing planned yet.' : 'A rest day.'));
    else column.appendChild(list);
    if (options.footer) {
      const footer = options.footer(day);
      if (footer) column.appendChild(footer);
    }
    return column;
  }

  function demoChip(item) {
    const chip = el('li', 'bp-chip');
    chip.dataset.category = item.category || '';
    chip.append(el('span', 'bp-chip__kind', item.kind_label), el('strong', null, item.title),
      el('span', 'bp-chip__what', item.unit === 'block' ? item.label : `${item.label} · ${item.length}`));
    return chip;
  }

  // ------------------------------------------------------------------ the sample plan for visitors

  const demo = document.getElementById('breakDemo');
  if (demo) {
    let presets = [];
    try { presets = JSON.parse(demo.dataset.presets || '[]'); } catch (error) { presets = []; }
    const controls = demo.querySelector('[data-break-demo-controls]');
    const board = demo.querySelector('[data-break-demo-board]');
    const spanLine = demo.querySelector('[data-break-demo-span]');
    const pick = { key: demo.dataset.preset, daily: 180 };
    const presetRow = el('div');
    presetRow.setAttribute('role', 'group');
    presetRow.setAttribute('aria-label', 'Which days');
    const dailyRow = el('div');
    dailyRow.setAttribute('role', 'group');
    dailyRow.setAttribute('aria-label', 'Time on most days');
    const note = el('p', 'bp-muted');
    note.setAttribute('role', 'status');
    let timer = 0;
    const draw = async () => {
      const preset = presets.find(entry => entry.key === pick.key) || presets[0];
      if (!preset) return;
      const days = daysBetween(preset.starts_on, preset.ends_on);
      try {
        const data = await api('/api/break/demo', { method: 'POST', guest: true,
          body: { starts_on: preset.starts_on, ends_on: preset.ends_on, minutes: dayDefaults(days, pick.daily, preset.light) } });
        const list = el('ol', 'bp-board bp-board--demo');
        (data.days || []).forEach(day => list.appendChild(dayColumn(day)));
        board.replaceChildren(list);
        if (spanLine) spanLine.textContent = `This is ${preset.name}, ${preset.span || ''}, with ${hoursWords(pick.daily)} a day.`;
        note.textContent = '';
      } catch (error) {
        note.textContent = error.message;
      }
    };
    const choose = (key, value) => {
      pick[key] = value;
      presetRow.querySelectorAll('button').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.key === pick.key)));
      dailyRow.querySelectorAll('button').forEach(node => node.setAttribute('aria-pressed', String(Number(node.dataset.minutes) === pick.daily)));
      clearTimeout(timer);
      timer = setTimeout(draw, 120);
    };
    presets.forEach(entry => {
      const chip = button(entry.name, 'bp-pill', () => choose('key', entry.key));
      chip.dataset.key = entry.key;
      chip.setAttribute('aria-pressed', String(entry.key === pick.key));
      presetRow.appendChild(chip);
    });
    [60, 120, 180, 240, 360].forEach(minutes => {
      const chip = button(`${hoursWords(minutes)} a day`, 'bp-pill', () => choose('daily', minutes));
      chip.dataset.minutes = String(minutes);
      chip.setAttribute('aria-pressed', String(minutes === pick.daily));
      dailyRow.appendChild(chip);
    });
    if (controls && presets.length) {
      controls.append(presetRow, dailyRow, note);
      controls.hidden = false;
    }
  }

  const root = document.getElementById('breakApp');
  if (!root) return;

  // ------------------------------------------------------------------ the member's plan

  const state = { data: null, busy: false, panel: '', asks: new Map(), status: '', tone: '', setup: null };

  function setStatus(text, tone) {
    state.status = text || '';
    state.tone = tone || '';
    const node = root.querySelector('[data-break-status]');
    if (node) {
      node.textContent = state.status;
      node.dataset.tone = state.tone;
    }
  }

  async function act(path, options, success) {
    if (state.busy) return null;
    state.busy = true;
    root.querySelectorAll('button').forEach(node => { if (!node.dataset.free) node.disabled = true; });
    try {
      const data = await api(path, options);
      if (data && 'plan' in data) state.data = data;
      render();
      if (success) setStatus(typeof success === 'function' ? success(data) : success);
      return data;
    } catch (error) {
      render();
      setStatus(error.message, 'error');
      return null;
    } finally {
      state.busy = false;
      root.querySelectorAll('button').forEach(node => { node.disabled = false; });
    }
  }

  async function load() {
    try {
      state.data = await api('/api/break');
      render();
      const plan = state.data.plan;
      if (plan && plan.phase === 'during') api('/api/break/seen', { method: 'POST', body: {} }).catch(() => {});
    } catch (error) {
      root.replaceChildren(el('p', 'bp-status', error.message));
      root.firstChild.dataset.tone = 'error';
    }
  }

  function render() {
    const data = state.data;
    if (!data) return;
    const status = el('p', 'bp-status');
    status.dataset.breakStatus = '';
    status.setAttribute('role', 'status');
    status.textContent = state.status;
    status.dataset.tone = state.tone;
    if (!data.plan) {
      root.replaceChildren(setupForm(data), status);
      return;
    }
    root.replaceChildren(planView(data.plan, data), status);
  }

  // ------------------------------------------------------------------ setting up

  function presetFromQuery(presets) {
    const wanted = new URLSearchParams(window.location.search).get('preset');
    return presets.find(entry => entry.key === wanted) || null;
  }

  function setupForm(data) {
    const presets = data.presets || [];
    if (!state.setup) {
      const first = presetFromQuery(presets) || presets[0] || null;
      const start = first ? first.starts_on : data.today;
      const end = first ? first.ends_on : data.today;
      state.setup = { key: first ? first.key : 'custom', starts_on: start, ends_on: end, daily: data.default_minutes,
        light: first ? first.light : [], minutes: {}, games: true, emails: Boolean(data.email_offer) };
      state.setup.minutes = dayDefaults(daysBetween(start, end, data.max_days), data.default_minutes, state.setup.light, data.light_minutes);
    }
    const setup = state.setup;
    const form = el('form', 'bp-setup');
    form.noValidate = true;
    form.appendChild(el('h2', null, data.plan === null && presets.length ? 'Plan a break' : 'Plan a break'));

    const refreshDays = () => {
      const days = daysBetween(setup.starts_on, setup.ends_on, data.max_days);
      const next = dayDefaults(days, setup.daily, setup.light, data.light_minutes);
      days.forEach(day => { if (setup.touched && setup.touched[day] !== undefined) next[day] = setup.touched[day]; });
      setup.minutes = next;
    };

    // Which days
    const which = el('fieldset', 'bp-step');
    which.appendChild(el('legend', null, 'Which days?'));
    which.appendChild(el('p', 'bp-step__hint', 'Thanksgiving Day and Christmas Day start with one hour, since most of those days go to family.'));
    const grid = el('div', 'bp-presets');
    const choices = [...presets.map(entry => ({ ...entry, sub: entry.span })),
      { key: 'custom', name: 'Pick my own dates', sub: `Up to ${data.max_days} days` }];
    choices.forEach(entry => {
      const chip = button('', 'bp-preset', () => {
        setup.key = entry.key;
        if (entry.key !== 'custom') {
          setup.starts_on = entry.starts_on;
          setup.ends_on = entry.ends_on;
          setup.light = entry.light || [];
        } else {
          setup.light = [];
        }
        setup.touched = {};
        refreshDays();
        render();
      });
      chip.dataset.free = '';
      chip.setAttribute('aria-pressed', String(setup.key === entry.key));
      chip.append(el('strong', null, entry.name), el('span', null, entry.sub));
      grid.appendChild(chip);
    });
    which.appendChild(grid);
    if (setup.key === 'custom') {
      const dates = el('div', 'bp-dates');
      const today = parseDay(data.today);
      const latest = new Date(today.getTime());
      latest.setDate(latest.getDate() + data.start_within_days + data.max_days);
      [['starts_on', 'First day'], ['ends_on', 'Last day']].forEach(([key, label]) => {
        const wrap = el('label', null, label);
        const input = el('input');
        input.type = 'date';
        input.min = data.today;
        input.max = isoDay(latest);
        input.value = setup[key];
        input.addEventListener('change', () => {
          setup[key] = input.value;
          if (key === 'starts_on' && (!setup.ends_on || setup.ends_on < input.value)) setup.ends_on = input.value;
          refreshDays();
          render();
        });
        wrap.appendChild(input);
        dates.appendChild(wrap);
      });
      which.appendChild(dates);
    }
    form.appendChild(which);

    // How much time
    const time = el('fieldset', 'bp-step');
    time.appendChild(el('legend', null, 'About how much time on most days?'));
    time.appendChild(el('p', 'bp-step__hint', 'Count it honestly: meals, errands and other people take a lot of a day off. Change any day below.'));
    const daily = el('div', 'bp-daily');
    [60, 120, 180, 240, 360, 480].forEach(minutes => {
      const chip = button(hoursWords(minutes), 'bp-pill', () => {
        setup.daily = minutes;
        setup.touched = {};
        refreshDays();
        render();
      });
      chip.dataset.free = '';
      chip.setAttribute('aria-pressed', String(setup.daily === minutes));
      daily.appendChild(chip);
    });
    time.appendChild(daily);
    const days = el('div', 'bp-days');
    Object.keys(setup.minutes).forEach(day => {
      const when = parseDay(day);
      const label = el('label', null, when.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }));
      label.appendChild(minutesSelect(data.choices, setup.minutes[day], value => {
        setup.touched = setup.touched || {};
        setup.touched[day] = value;
        setup.minutes[day] = value;
      }));
      days.appendChild(label);
    });
    time.appendChild(days);
    form.appendChild(time);

    // Switches
    const extras = el('fieldset', 'bp-step');
    extras.appendChild(el('legend', null, 'A couple of choices'));
    extras.appendChild(checkbox('Include a game (one at most, and only on a break of six hours or more)', setup.games, value => { setup.games = value; }));
    if (data.email_offer) {
      extras.appendChild(checkbox('Email me the morning it starts and the morning after it ends', setup.emails, value => { setup.emails = value; }));
    }
    form.appendChild(extras);

    const go = el('div', 'bp-go');
    const submit = el('button', 'bp-pill bp-pill--primary', 'Fill my break from my list');
    submit.type = 'submit';
    go.appendChild(submit);
    go.appendChild(el('span', 'bp-muted', 'You can change anything after.'));
    form.appendChild(go);
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (!setup.starts_on || !setup.ends_on) {
        setStatus('Pick the first and last day.', 'error');
        return;
      }
      act('/api/break', { method: 'POST', body: {
        starts_on: setup.starts_on, ends_on: setup.ends_on, minutes: setup.minutes,
        preset: setup.key === 'custom' ? null : setup.key, games: setup.games, emails: setup.emails, tz: tz(),
      } }, data => {
        const plan = data && data.plan;
        if (!plan) return '';
        state.setup = null;
        return plan.totals.titles ? `Planned: ${plan.totals.titles} titles, about ${plan.totals.hours}.`
          : 'Nothing on your list fits yet. Add something to your library, or put a title on a day by hand.';
      });
    });
    return form;
  }

  function minutesSelect(choices, value, onChange) {
    const select = el('select');
    (choices || []).forEach(minutes => {
      const option = el('option', null, hoursWords(minutes));
      option.value = String(minutes);
      if (Number(minutes) === Number(value)) option.selected = true;
      select.appendChild(option);
    });
    select.addEventListener('change', () => onChange(Number(select.value)));
    return select;
  }

  function checkbox(label, checked, onChange) {
    const wrap = el('label', 'bp-check');
    const input = el('input');
    input.type = 'checkbox';
    input.checked = Boolean(checked);
    input.addEventListener('change', () => onChange(input.checked));
    wrap.append(input, document.createTextNode(label));
    return wrap;
  }

  // ------------------------------------------------------------------ the plan

  function planView(plan, data) {
    const wrap = el('div', 'bp-plan');
    const head = el('div', 'bp-head');
    const copy = el('div');
    copy.append(el('p', 'bp-head__eyebrow', `${phaseLine(plan)} · ${plan.span}`), el('h2', null, plan.name));
    const totals = plan.totals;
    copy.appendChild(el('p', 'bp-head__line', totals.titles
      ? `${totals.titles} ${totals.titles === 1 ? 'title' : 'titles'} over ${plan.day_count} days, about ${totals.hours}.`
      : 'Nothing planned yet.'));
    head.appendChild(copy);
    if (totals.stretches) {
      const progress = el('div', 'bp-progress');
      const ring = el('div', 'bp-ring');
      ring.style.setProperty('--bp-done', String(Math.round(totals.done / totals.stretches * 100)));
      ring.setAttribute('aria-hidden', 'true');
      ring.appendChild(el('span', null, `${totals.done}/${totals.stretches}`));
      progress.append(ring, el('p', null, totals.done
        ? `${totals.done} of ${totals.stretches} ticked off. ${totals.finished} ${totals.finished === 1 ? 'title' : 'titles'} finished.`
        : 'Tick things off as you go. Your library moves along with you.'));
      head.appendChild(progress);
    }
    wrap.appendChild(head);
    if (plan.phase === 'after') wrap.appendChild(wrapUp(plan));
    wrap.appendChild(tools(plan, data));
    if (state.panel) {
      const panel = panelFor(state.panel, plan, data);
      if (panel) wrap.appendChild(panel);
    }
    const board = el('ol', 'bp-board');
    plan.days.forEach(day => board.appendChild(dayColumn(day, { item: (item, onDay) => itemCard(item, onDay, plan),
      footer: onDay => dayFooter(onDay, plan) })));
    wrap.appendChild(board);
    return wrap;
  }

  function tools(plan) {
    const row = el('div', 'bp-tools');
    const open = name => () => { state.panel = state.panel === name ? '' : name; setStatus(''); render(); };
    if (plan.phase !== 'after') {
      row.appendChild(button('Fill free time', 'bp-pill', () => act(`/api/break/${plan.id}/fill`, { method: 'POST', body: {} },
        result => (result.added ? 'Filled the free time.' : 'Nothing else on your list fits the time that\'s left.'))));
      row.appendChild(button('Try another mix', 'bp-pill', () => act(`/api/break/${plan.id}/shuffle`, { method: 'POST', body: {} },
        'Here\'s another mix. Anything you ticked or added yourself stayed put.')));
      const add = button('Add a title', 'bp-pill', open('add'));
      add.setAttribute('aria-expanded', String(state.panel === 'add'));
      row.appendChild(add);
      const times = button('Change days or times', 'bp-pill', open('times'));
      times.setAttribute('aria-expanded', String(state.panel === 'times'));
      row.appendChild(times);
    }
    const share = button(plan.share ? 'Share link' : 'Share it', 'bp-pill', open('share'));
    share.setAttribute('aria-expanded', String(state.panel === 'share'));
    row.appendChild(share);
    const calendar = el('a', 'bp-pill bp-pill--quiet', 'Add to calendar');
    calendar.href = `/api/break/${plan.id}/calendar.ics`;
    calendar.setAttribute('download', 'omnitrackr-break-plan.ics');
    row.appendChild(calendar);
    const more = button('More', 'bp-pill bp-pill--quiet', open('more'));
    more.setAttribute('aria-expanded', String(state.panel === 'more'));
    row.appendChild(more);
    return row;
  }

  function panelFor(name, plan, data) {
    if (name === 'add') return addPanel(plan);
    if (name === 'times') return timesPanel(plan, data);
    if (name === 'share') return sharePanel(plan);
    if (name === 'more') return morePanel(plan, data);
    return null;
  }

  function openDays(plan) {
    return plan.days.filter(day => !day.past);
  }

  function addPanel(plan) {
    const panel = el('section', 'bp-panel');
    panel.setAttribute('aria-label', 'Add a title');
    panel.appendChild(el('h3', null, 'Put something from your list on a day'));
    const row = el('div', 'bp-panel__row');
    const search = el('input');
    search.type = 'search';
    search.placeholder = 'Search your unfinished titles';
    search.setAttribute('aria-label', 'Search your unfinished titles');
    const days = el('select');
    days.setAttribute('aria-label', 'Day');
    openDays(plan).forEach(day => {
      const option = el('option', null, day.label);
      option.value = day.day;
      days.appendChild(option);
    });
    row.append(search, days);
    panel.appendChild(row);
    const list = el('ul', 'bp-titles');
    list.appendChild(el('li', 'bp-muted', 'Loading your list…'));
    panel.appendChild(list);
    // The first list has a share of every format; typing searches the whole library on the server, so a
    // title past the first couple of hundred can still be found.
    let titles = [];
    let found = null;
    let asked = '';
    let timer = 0;
    const draw = () => {
      const query = search.value.trim().replace(/\s+/g, ' ').toLowerCase();
      const pool = query && found ? found : titles;
      const shown = pool.filter(entry => !query || entry.title.toLowerCase().includes(query)).slice(0, 48);
      list.replaceChildren(...shown.map(entry => {
        const item = el('li');
        const pick = button('', null, () => act(`/api/break/${plan.id}/items`, { method: 'POST',
          body: { category: entry.category, item_id: entry.id, day: days.value } }, `Added ${entry.title}.`));
        pick.append(el('span', null, entry.title), el('small', null, entry.label));
        item.appendChild(pick);
        return item;
      }));
      if (!shown.length) list.appendChild(el('li', 'bp-muted', titles.length ? 'Nothing on your list matches.' : 'Everything on your list is on the plan or finished.'));
    };
    const lookUp = () => {
      const query = search.value.trim();
      if (!query) { found = null; asked = ''; draw(); return; }
      if (query === asked) return;
      asked = query;
      api(`/api/break/${plan.id}/titles?q=${encodeURIComponent(query.slice(0, 80))}`)
        .then(result => { if (asked === query) { found = result.titles || []; draw(); } })
        .catch(() => {});
    };
    search.addEventListener('input', () => {
      draw();
      clearTimeout(timer);
      timer = setTimeout(lookUp, 300);
    });
    api(`/api/break/${plan.id}/titles`).then(result => { titles = result.titles || []; draw(); })
      .catch(error => { list.replaceChildren(el('li', 'bp-muted', error.message)); });
    setTimeout(() => search.focus(), 0);
    return panel;
  }

  function timesPanel(plan, data) {
    const panel = el('section', 'bp-panel');
    panel.setAttribute('aria-label', 'Change days or times');
    panel.appendChild(el('h3', null, 'Change days or times'));
    panel.appendChild(el('p', 'bp-muted', 'Less time keeps what\'s planned, so you can move or remove things yourself. More time gets filled.'));
    const minutes = {};
    const grid = el('div', 'bp-days');
    plan.days.filter(day => !day.past).forEach(day => {
      minutes[day.day] = day.budget;
      const label = el('label', null, day.label);
      label.appendChild(minutesSelect(data.choices, day.budget, value => { minutes[day.day] = value; }));
      grid.appendChild(label);
    });
    panel.appendChild(grid);
    const row = el('div', 'bp-panel__row');
    const endLabel = el('label', 'bp-dates');
    const end = el('input');
    end.type = 'date';
    end.value = plan.ends_on;
    end.min = plan.today > plan.starts_on ? plan.today : plan.starts_on;
    const latest = parseDay(plan.starts_on);
    latest.setDate(latest.getDate() + plan.max_days - 1);
    end.max = isoDay(latest);
    endLabel.append(document.createTextNode('Last day '), end);
    row.appendChild(endLabel);
    row.appendChild(button('Save', 'bp-pill bp-pill--primary', () => {
      const body = { minutes };
      if (end.value && end.value !== plan.ends_on) body.ends_on = end.value;
      state.panel = '';
      act(`/api/break/${plan.id}`, { method: 'PATCH', body }, 'Saved.');
    }));
    panel.appendChild(row);
    return panel;
  }

  function sharePanel(plan) {
    const panel = el('section', 'bp-panel');
    panel.setAttribute('aria-label', 'Share your plan');
    panel.appendChild(el('h3', null, 'Share your plan'));
    if (!plan.share) {
      panel.appendChild(el('p', 'bp-muted', 'A link anyone can open. It shows titles from the shelves you share on your profile, what you\'ve ticked off, and nothing else. You can turn it off any time.'));
      panel.appendChild(button('Make a link', 'bp-pill bp-pill--primary', () => act(`/api/break/${plan.id}/share`, { method: 'POST', body: {} }, 'Link made.')));
      return panel;
    }
    panel.appendChild(el('p', 'bp-share-url', plan.share));
    const row = el('div', 'bp-share-row');
    const text = `My plan for ${plan.name}`;
    if (navigator.share) {
      row.appendChild(button('Send it', 'bp-pill bp-pill--primary', async () => {
        try { await navigator.share({ title: text, text, url: plan.share }); } catch (error) { /* closed */ }
      }));
    }
    const copy = button('Copy link', 'bp-pill', async () => {
      try {
        await navigator.clipboard.writeText(plan.share);
        copy.textContent = 'Link copied ✓';
        setTimeout(() => { copy.textContent = 'Copy link'; }, 2200);
      } catch (error) {
        setStatus(`Copy this link: ${plan.share}`);
      }
    });
    copy.dataset.free = '';
    row.appendChild(copy);
    row.appendChild(button('Turn the link off', 'bp-link bp-link--danger', () => act(`/api/break/${plan.id}/share`, { method: 'DELETE' }, 'The link is off.')));
    panel.appendChild(row);
    return panel;
  }

  function morePanel(plan, data) {
    const panel = el('section', 'bp-panel');
    panel.setAttribute('aria-label', 'More choices');
    panel.appendChild(el('h3', null, 'More'));
    if (plan.phase !== 'after') {
      panel.appendChild(checkbox('Fill with a game too', plan.games, value => act(`/api/break/${plan.id}`, { method: 'PATCH', body: { games: value } }, 'Saved.')));
      if (data.email_offer) {
        panel.appendChild(checkbox('Email me the morning it starts and the morning after it ends', plan.emails,
          value => act(`/api/break/${plan.id}`, { method: 'PATCH', body: { emails: value } }, value ? 'You\'ll get two emails for this break.' : 'No emails for this break.')));
      }
    }
    const row = el('div', 'bp-panel__row');
    const confirmBox = el('div', 'bp-row');
    const start = button(plan.phase === 'after' ? 'Plan another break' : 'Start over', 'bp-link bp-link--danger', () => {
      confirmBox.replaceChildren(el('span', 'bp-muted', plan.phase === 'after' ? 'This one goes away (your library keeps everything you ticked).' : 'This deletes the plan. Your library keeps everything you ticked.'),
        button('Yes, start over', 'bp-pill', () => {
          state.panel = '';
          act(`/api/break/${plan.id}`, { method: 'DELETE' }, 'Plan deleted. Make a new one whenever you like.');
        }));
    });
    row.append(start, confirmBox);
    panel.appendChild(row);
    return panel;
  }

  function wrapUp(plan) {
    const box = el('section', 'bp-wrap');
    box.setAttribute('aria-label', 'How it went');
    const totals = plan.totals;
    box.appendChild(el('h3', null, totals.done ? 'How it went' : 'The break is over'));
    box.appendChild(el('p', 'bp-muted', totals.done
      ? 'Give the ones you finished a score while they\'re fresh, and share how it went if you like.'
      : 'Nothing got ticked off this time. If you did watch or read something, tick it on its day.'));
    const stats = el('ul', 'bp-wrap__stats');
    [[totals.done, 'ticked off'], [totals.finished, totals.finished === 1 ? 'title finished' : 'titles finished'], [totals.done_hours, 'of watching, reading and playing']]
      .forEach(([value, label]) => {
        const item = el('li');
        item.append(el('strong', null, value), document.createTextNode(label));
        stats.appendChild(item);
      });
    box.appendChild(stats);
    if (plan.finished && plan.finished.length) {
      const list = el('ul', 'bp-wrap__list');
      plan.finished.forEach(item => {
        const row = el('li', 'bp-chip bp-chip--art bp-chip--done');
        row.dataset.category = item.category;
        const body = el('span', 'bp-chip__body');
        body.append(el('span', 'bp-chip__kind', item.kind_label), el('strong', null, item.title));
        body.appendChild(scoreRow(plan, item));
        row.append(art(item), body);
        list.appendChild(row);
      });
      box.appendChild(list);
    }
    return box;
  }

  function scoreRow(plan, item) {
    const row = el('div', 'bp-scores');
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', `Score ${item.title} out of 10`);
    for (let score = 1; score <= 10; score += 1) {
      const pick = button(String(score), null, () => act(`/api/break/${plan.id}/items/${item.id}/rate`, { method: 'POST', body: { rating: score } },
        `Saved: ${item.title}, ${score} out of 10.`));
      pick.setAttribute('aria-pressed', String(item.rating === score));
      pick.setAttribute('aria-label', `${score} out of 10`);
      row.appendChild(pick);
    }
    return row;
  }

  function itemCard(item, day, plan) {
    const card = el('li', `bp-chip${item.done ? ' bp-chip--done' : ''}`);
    card.dataset.category = item.category;
    const row = el('div', 'bp-item');
    const tick = button(item.done ? '✓' : '✓', 'bp-tick', () => {
      if (item.done) {
        act(`/api/break/${plan.id}/items/${item.id}/undo`, { method: 'POST', body: {} }, `Unticked ${item.title}.`);
        return;
      }
      act(`/api/break/${plan.id}/items/${item.id}/done`, { method: 'POST', body: {} }, result => {
        const ticked = result && result.ticked;
        if (ticked && ticked.finished) {
          state.asks.set(item.id, 'score');
          render();
          return `Finished ${item.title}. Nice.`;
        }
        if (ticked && ticked.ask_finish) {
          state.asks.set(item.id, 'finish');
          render();
          return '';
        }
        return `Ticked off: ${item.title}, ${item.label.charAt(0).toLowerCase()}${item.label.slice(1)}.`;
      });
    });
    tick.setAttribute('aria-pressed', String(item.done));
    tick.setAttribute('aria-label', item.done ? `Untick ${item.title}, ${item.label}` : `Tick off ${item.title}, ${item.label}`);
    const body = el('div', 'bp-chip__body');
    body.appendChild(el('span', 'bp-chip__kind', item.kind_label));
    if (item.url && /^\/titles\//.test(item.url)) {
      const link = el('a', 'bp-item__title');
      link.href = item.url;
      link.appendChild(el('strong', null, item.title));
      body.appendChild(link);
    } else {
      body.appendChild(el('strong', null, item.title));
    }
    body.appendChild(el('span', 'bp-chip__what', item.unit === 'block' ? item.label : `${item.label} · ${item.length}`));
    const ask = state.asks.get(item.id);
    if (ask === 'score' && item.finished_title) {
      const box = el('div', 'bp-ask');
      box.appendChild(el('p', null, 'Finished. Give it a score?'));
      box.appendChild(scoreRow(plan, item));
      body.appendChild(box);
    } else if (ask === 'finish' && !item.finished_title) {
      const box = el('div', 'bp-ask');
      box.appendChild(el('p', null, 'Did you finish it?'));
      const answers = el('div', 'bp-row');
      answers.append(
        button('Yes, finished', 'bp-pill', () => {
          state.asks.set(item.id, 'score');
          act(`/api/break/${plan.id}/items/${item.id}/finish`, { method: 'POST', body: {} }, `Finished ${item.title}.`);
        }),
        button('Not yet', 'bp-link', () => { state.asks.delete(item.id); render(); }));
      box.appendChild(answers);
      body.appendChild(box);
    } else if (item.confirm_finish) {
      // Its last part is ticked, but a game or a length we guessed doesn't finish the title on its own.
      body.appendChild(button('Mark it finished', 'bp-link', () => {
        state.asks.set(item.id, 'score');
        act(`/api/break/${plan.id}/items/${item.id}/finish`, { method: 'POST', body: {} }, `Finished ${item.title}.`);
      }));
    }
    if (!item.done && !day.past) body.appendChild(itemMenu(item, plan));
    row.append(tick, body);
    card.appendChild(row);
    return card;
  }

  function itemMenu(item, plan) {
    const menu = el('details', 'bp-more');
    const summary = el('summary', null, 'Change');
    summary.setAttribute('aria-label', `Change ${item.title}`);
    menu.appendChild(summary);
    const inner = el('div', 'bp-more__menu');
    const move = el('div', 'bp-more__move');
    const select = el('select');
    select.setAttribute('aria-label', `Move ${item.title} to`);
    const placeholder = el('option', null, 'Move to…');
    placeholder.value = '';
    select.appendChild(placeholder);
    plan.days.filter(day => !day.past && !day.items.some(entry => entry.id === item.id)).forEach(day => {
      const option = el('option', null, day.label);
      option.value = day.day;
      select.appendChild(option);
    });
    select.addEventListener('change', () => {
      if (select.value) act(`/api/break/${plan.id}/items/${item.id}`, { method: 'PATCH', body: { day: select.value } }, `Moved ${item.title}.`);
    });
    if (select.options.length > 1) {
      move.appendChild(select);
      inner.appendChild(move);
    }
    inner.appendChild(button('Swap for something else', 'bp-link', () => act(`/api/break/${plan.id}/items/${item.id}?swap=true`, { method: 'DELETE' },
      result => (result.added ? `Swapped ${item.title} for something else.` : `Took ${item.title} off. Nothing else on your list fits that time.`))));
    inner.appendChild(button('Finished the whole thing', 'bp-link', () => {
      state.asks.set(item.id, 'score');
      act(`/api/break/${plan.id}/items/${item.id}/finish`, { method: 'POST', body: {} }, `Finished ${item.title}.`);
    }));
    inner.appendChild(button('Take it off the plan', 'bp-link bp-link--danger', () => act(`/api/break/${plan.id}/items/${item.id}`, { method: 'DELETE' }, `Took ${item.title} off the plan.`)));
    menu.appendChild(inner);
    return menu;
  }

  function dayFooter(day, plan) {
    if (day.past || plan.phase === 'after' || day.free < 30 || !day.budget) return null;
    const footer = el('div', 'bp-col__fill');
    footer.appendChild(button(`Fill ${lengthWords(day.free)} free`, 'bp-link', () => act(`/api/break/${plan.id}/fill`, { method: 'POST', body: { day: day.day } },
      result => (result.added ? `Filled ${day.label}.` : 'Nothing else on your list fits that time.'))));
    return footer;
  }

  load();
})();
