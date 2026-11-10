// Binge calculator (/binge-calculator) and its "how long" guides (/binge-calculator/<slug>).
// Everything is worked out in the browser from numbers already on the page. A guide's
// planner reads its parts from data-binge-plan; the hub's calculator builds one part from
// the fields a visitor types in. Members also get their own progress and time left
// (GET /api/binge-calculator/<slug>/progress, /api/binge-calculator/mine).
(function () {
  'use strict';

  const WEEK_DAYS = { 7: [0, 1, 2, 3, 4, 5, 6], 5: [1, 2, 3, 4, 5], 2: [0, 6], 3: [1, 3, 5] };
  const MAX_DAYS = 40000;
  const SLUG = /^[a-z0-9-]{1,80}$/;

  // ------------------------------------------------------------ dates and wording
  function todayIso(now) {
    const date = now || new Date();
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function parseIso(text) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text || '')) return null;
    const date = new Date(`${text}T12:00:00`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function allowedDays(daysPerWeek) {
    return WEEK_DAYS[daysPerWeek] || WEEK_DAYS[7];
  }

  // The date of the Nth day that falls on the chosen weekdays; the start day can be day one.
  function finishDate(startIso, activeDays, daysPerWeek) {
    const date = parseIso(startIso);
    if (!date || !(activeDays >= 1)) return null;
    const allowed = allowedDays(daysPerWeek);
    let counted = 0;
    for (let guard = 0; guard < MAX_DAYS; guard += 1) {
      if (allowed.includes(date.getDay())) {
        counted += 1;
        if (counted >= activeDays) return date;
      }
      date.setDate(date.getDate() + 1);
    }
    return null;
  }

  // How many of the chosen weekdays fall from the start date to the end date, both included.
  function activeDaysBetween(startIso, endIso, daysPerWeek) {
    const date = parseIso(startIso);
    const end = parseIso(endIso);
    if (!date || !end || end < date) return 0;
    const allowed = allowedDays(daysPerWeek);
    let counted = 0;
    for (let guard = 0; guard < MAX_DAYS && date <= end; guard += 1) {
      if (allowed.includes(date.getDay())) counted += 1;
      date.setDate(date.getDate() + 1);
    }
    return counted;
  }

  function formatHours(hours) {
    return hours < 10 ? hours.toFixed(1).replace(/\.0$/, '') : Math.round(hours).toLocaleString('en-US');
  }

  function clock(minutes) {
    const total = Math.round(minutes);
    const hours = Math.floor(total / 60);
    const rest = total % 60;
    if (!hours) return `${rest} min`;
    return rest ? `${hours} h ${rest} min` : `${hours} h`;
  }

  // "1 hour 5 minutes", for how long a day's share is.
  function spoken(minutes) {
    const total = Math.max(1, Math.round(minutes));
    const hours = Math.floor(total / 60);
    const rest = total % 60;
    const parts = [];
    if (hours) parts.push(`${hours} hour${hours === 1 ? '' : 's'}`);
    if (rest) parts.push(`${rest} minute${rest === 1 ? '' : 's'}`);
    return parts.join(' ');
  }

  function plural(count, word) {
    const shown = Number.isInteger(count) ? count.toLocaleString('en-US') : count.toFixed(1);
    return `${shown} ${word}${count === 1 ? '' : 's'}`;
  }

  function longDate(date) {
    return date.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  }

  // ------------------------------------------------------------ lengths
  // options: { alt, skip (minutes off an episode), how ('read' | 'listen'), pagesPerHour, speed }
  function partCount(part, options) {
    return options && options.alt && part.altN != null ? part.altN : part.n;
  }

  function partMinutes(part, options) {
    const opts = options || {};
    if (opts.how === 'listen' && part.audio) return part.audio / (opts.speed > 0 ? opts.speed : 1);
    if (part.pages && opts.how !== 'listen') return (part.pages / (opts.pagesPerHour > 0 ? opts.pagesPerHour : 40)) * 60;
    const count = partCount(part, opts);
    let minutes = opts.alt && part.altMin != null ? part.altMin : part.min;
    if (opts.skip > 0 && part.unit === 'episode') minutes = Math.max(count, minutes - opts.skip * count);
    return minutes;
  }

  // What is left of a plan: unticked parts are out, and `seen` episodes come off the ticked
  // episode parts in order. Returns the minutes, a count of what is left and each part's state.
  function remaining(plan, state) {
    const options = state || {};
    const checked = options.checked;
    let seenLeft = Math.max(0, Math.floor(options.seen || 0));
    let minutes = 0;
    let units = 0;
    let pages = 0;
    const byUnit = {};
    const parts = plan.parts.map(part => {
      const on = checked ? checked.has(part.id) : !part.optional;
      const full = partMinutes(part, options);
      const count = partCount(part, options);
      let share = on ? 1 : 0;
      if (on && part.unit === 'episode' && seenLeft > 0) {
        const taken = Math.min(count, seenLeft);
        seenLeft -= taken;
        share = count ? (count - taken) / count : 0;
      }
      minutes += full * share;
      units += count * share;
      if (part.unit) byUnit[part.unit] = (byUnit[part.unit] || 0) + count * share;
      if (part.pages) pages += part.pages * share;
      return { id: part.id, minutes: full, on, share };
    });
    Object.keys(byUnit).forEach(unit => { byUnit[unit] = Math.round(byUnit[unit]); });
    return { minutes, units: Math.round(units), pages: Math.round(pages), byUnit, parts };
  }

  function planByTime(minutes, hoursPerDay, daysPerWeek, startIso) {
    if (!(minutes > 0) || !(hoursPerDay > 0)) return null;
    const days = Math.ceil(minutes / (hoursPerDay * 60) - 1e-9);
    return { days, finish: finishDate(startIso, days, daysPerWeek) };
  }

  function planByDate(minutes, startIso, byIso, daysPerWeek) {
    if (!(minutes > 0)) return null;
    const start = parseIso(startIso);
    const end = parseIso(byIso);
    if (!start || !end) return { error: 'missing' };
    if (end < start) return { error: 'past' };
    const days = activeDaysBetween(startIso, byIso, daysPerWeek);
    if (!days) return { error: 'no-days' };
    const perDay = minutes / days;
    if (perDay > 24 * 60) return { error: 'too-much', days };
    return { days, perDay, finish: end };
  }

  // What a day's share looks like in the thing you are counting: episodes, pages or films.
  function perDayText(left, days, counting) {
    if (!days || !counting) return '';
    const amount = counting === 'page' ? left.pages : unitCount(left, counting);
    if (!amount) return '';
    const each = amount / days;
    if (counting === 'film' && each < 1) return '';
    const shown = each >= 10 || counting === 'page' ? Math.round(each) : Math.round(each * 10) / 10;
    if (!shown) return '';
    return `About ${plural(shown, counting)} a day.`;
  }

  function counting(plan, options) {
    if (plan.kind === 'book') return options.how === 'listen' ? '' : 'page';
    if (plan.kind === 'film') return 'film';
    if (plan.kind === 'tv' || plan.kind === 'anime') return 'episode';
    return '';
  }

  // A series can mix episodes with a film or a special, so each is counted under its own name.
  function unitCount(left, unit) {
    return left.byUnit && unit in left.byUnit ? left.byUnit[unit] : left.units;
  }

  function unitList(left, first) {
    const units = Object.keys(left.byUnit || {}).filter(unit => left.byUnit[unit] > 0);
    units.sort((a, b) => (a === first ? -1 : b === first ? 1 : 0));
    if (!units.length) return plural(left.units, first);
    return units.map(unit => plural(left.byUnit[unit], unit)).join(' and ');
  }

  function leftText(plan, left, options) {
    const what = counting(plan, options);
    if (what === 'page') return `${left.pages.toLocaleString('en-US')} pages at ${options.pagesPerHour} pages an hour.`;
    if (plan.kind === 'book') return `Audiobook at ${options.speed}x speed.`;
    if (!what) return '';
    if (plan.parts.length === 1 && left.units > 1) {
      // The hub's calculator has one part, so the length of each item is worth saying.
      const each = Math.round((left.minutes / left.units) * 10) / 10;
      return `${plural(left.units, what)} at ${each} minutes each.`;
    }
    return `${unitList(left, what)}.`;
  }

  // The two sentences under the big number.
  function describe(plan, left, inputs, options, today) {
    const doing = plan.kind === 'book' ? (options.how === 'listen' ? 'listening' : 'reading') : plan.kind === 'game' ? 'playing' : 'viewing';
    const detail = plan.detail || leftText(plan, left, options);
    const what = counting(plan, options);
    if (!(left.minutes > 0)) {
      return { finish: plan.parts.length > 1 ? 'Nothing left to plan. Tick a part to add it back.' : 'Fill in the length to get a plan.', detail: '' };
    }
    if (inputs.mode === 'date') {
      const result = planByDate(left.minutes, inputs.start, inputs.by, inputs.week);
      if (!result || result.error === 'missing') return { finish: 'Pick the date you want to be finished by.', detail };
      if (result.error === 'past') return { finish: 'Pick a finish date after the start date.', detail };
      if (result.error === 'no-days') return { finish: 'None of the days you chose fall before that date. Try a later date or more days a week.', detail };
      if (result.error === 'too-much') {
        return { finish: `That would take more than 24 hours a day across ${plural(result.days, 'day')}. Pick a later date.`, detail };
      }
      const days = inputs.week === 7 ? plural(result.days, 'day') : `${plural(result.days, `${doing} day`)}`;
      return {
        finish: `To finish by ${longDate(result.finish)}, you need about ${spoken(result.perDay)} a day for ${days}.`,
        detail: [detail, perDayText(left, result.days, what)].filter(Boolean).join(' '),
        date: result.finish,
      };
    }
    const result = planByTime(left.minutes, inputs.hours, inputs.week, inputs.start);
    if (!result) return { finish: 'Say how many hours a day you have.', detail };
    const pace = `${formatHours(inputs.hours)} hour${inputs.hours === 1 ? '' : 's'} a day`;
    const when = result.finish ? longDate(result.finish) : '';
    const finish = !when ? `At ${pace}, that is ${plural(result.days, 'day')}.`
      : inputs.week === 7
        ? `At ${pace}, that is ${plural(result.days, 'day')}. Start ${inputs.start === today ? 'today' : 'then'} and you would finish on ${when}.`
        : `At ${pace} on ${plural(result.days, `${doing} day`)}, you would finish on ${when}.`;
    return { finish, detail: [detail, perDayText(left, result.days, what)].filter(Boolean).join(' '), date: result.finish };
  }

  // ------------------------------------------------------------ calendar file and share link
  function icsEscape(text) {
    return String(text || '').replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/([,;])/g, '\\$1');
  }

  function icsDate(date) {
    return `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;
  }

  // An all-day event on the finish date.
  function calendarFile(name, finish, description, url, now) {
    const next = new Date(finish.getTime());
    next.setDate(next.getDate() + 1);
    const stamp = (now || new Date()).toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
    return [
      'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//OmniTrackr//Binge calculator//EN', 'BEGIN:VEVENT',
      `UID:binge-${icsDate(finish)}-${Math.abs(hash(name))}@omnitrackr.xyz`, `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${icsDate(finish)}`, `DTEND;VALUE=DATE:${icsDate(next)}`,
      `SUMMARY:${icsEscape(`Finish ${name}`)}`, `DESCRIPTION:${icsEscape(description)}`,
      url ? `URL:${icsEscape(url)}` : '', 'TRANSP:TRANSPARENT', 'END:VEVENT', 'END:VCALENDAR',
    ].filter(Boolean).join('\r\n');
  }

  function hash(text) {
    let value = 0;
    for (let index = 0; index < String(text).length; index += 1) value = (value * 31 + String(text).charCodeAt(index)) | 0;
    return value;
  }

  function report(event) {
    if (report.sent && report.sent.has(event)) return;
    report.sent = report.sent || new Set();
    report.sent.add(event);
    try {
      const sent = JSON.parse(sessionStorage.getItem('omnitrackr_funnel_sent') || '[]');
      if (Array.isArray(sent) && sent.includes(event)) return;
      sessionStorage.setItem('omnitrackr_funnel_sent', JSON.stringify([...(Array.isArray(sent) ? sent : []), event].slice(-20)));
    } catch (error) { /* storage blocked: once per page instead */ }
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* analytics only */ }
  }

  function authHeaders() {
    const headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  // ------------------------------------------------------------ a planner on the page
  // Works for both pages: `getPlan` returns the parts to plan and the name to show.
  function setup(tool, getPlan, extras) {
    const form = tool.querySelector('[data-binge-form]');
    const out = {
      name: tool.querySelector('[data-binge-name]'),
      hours: tool.querySelector('[data-binge-hours]'),
      unit: tool.querySelector('[data-binge-hours-unit]'),
      finish: tool.querySelector('[data-binge-finish]'),
      detail: tool.querySelector('[data-binge-detail]'),
      actions: tool.querySelector('[data-binge-actions]'),
      copied: tool.querySelector('[data-binge-copied]'),
    };
    const checks = Array.from(tool.querySelectorAll('[data-binge-check]'));
    const rows = Array.from(tool.querySelectorAll('[data-binge-part]'));
    let last = null;

    function field(name) {
      return form.elements[name] || null;
    }

    function number(name) {
      const input = field(name);
      const value = input ? Number(input.value) : 0;
      return Number.isFinite(value) && value > 0 ? value : 0;
    }

    function radio(name, fallback) {
      const input = field(name);
      return (input && input.value) || fallback;
    }

    function options(plan) {
      const how = radio('how', plan.how || 'read');
      return {
        alt: Boolean(field('alt') && field('alt').checked),
        skip: field('skip') && field('skip').checked ? plan.skip || 0 : 0,
        how,
        pagesPerHour: number('pace') || plan.pagesPerHour || 40,
        speed: field('speed') ? Number(field('speed').value) || 1 : 1,
        seen: number('seen'),
        checked: checks.length ? new Set(checks.filter(box => box.checked).map(box => box.dataset.bingeCheck)) : null,
      };
    }

    function inputs() {
      return {
        mode: radio('mode', 'time') === 'date' ? 'date' : 'time',
        hours: number('hours'),
        week: Number(field('week').value) || 7,
        start: field('start').value || todayIso(),
        by: field('by') ? field('by').value : '',
      };
    }

    function update() {
      const plan = getPlan();
      const opts = options(plan);
      const values = inputs();
      tool.querySelectorAll('[data-binge-when]').forEach(node => { node.hidden = node.dataset.bingeWhen !== values.mode; });
      tool.querySelectorAll('[data-binge-how]').forEach(node => { node.hidden = node.dataset.bingeHow !== opts.how; });
      const left = remaining(plan, opts);
      const text = describe(plan, left, values, opts, todayIso());
      const film = plan.kind === 'film';
      out.name.textContent = plan.name || 'Your plan';
      out.hours.textContent = film ? clock(left.minutes) : formatHours(left.minutes / 60);
      if (out.unit) out.unit.textContent = film ? '' : left.minutes / 60 === 1 ? 'hour' : 'hours';
      out.finish.textContent = text.finish;
      out.detail.textContent = text.detail;
      if (out.actions) out.actions.hidden = !(left.minutes > 0);
      const calendar = tool.querySelector('[data-binge-calendar]');
      if (calendar) calendar.hidden = !text.date;
      left.parts.forEach((part, index) => {
        const row = rows[index];
        if (!row) return;
        row.classList.toggle('is-off', !part.on);
        row.classList.toggle('is-done', part.on && part.share === 0);
        const time = row.querySelector('[data-binge-part-time]');
        if (time) time.textContent = film ? clock(part.minutes) : `${formatHours(part.minutes / 60)} h`;
      });
      last = { plan, left, text, values, opts };
      if (extras && extras.onUpdate) extras.onUpdate(last);
      return last;
    }

    // ---- share link: every field that differs from how the page loads
    function stateParams() {
      const params = new URLSearchParams();
      Array.from(form.elements).forEach(input => {
        if (!input.name) return;
        if (input.name === 'by' && radio('mode', 'time') !== 'date') return;
        if (input.type === 'radio') {
          if (input.checked && !input.defaultChecked) params.set(input.name, input.value);
        } else if (input.type === 'checkbox') {
          if (input.checked !== input.defaultChecked) params.set(input.name, input.checked ? '1' : '0');
        } else if (input.tagName === 'SELECT') {
          const option = input.options[input.selectedIndex];
          if (option && !option.defaultSelected && input.selectedIndex !== 0) params.set(input.name, input.value);
        } else if (input.name === 'start') {
          if (input.value && input.value !== todayIso()) params.set('start', input.value);
        } else if (input.value !== input.defaultValue && input.value !== '') {
          params.set(input.name, input.value);
        }
      });
      const flipped = checks.filter(box => box.checked !== box.defaultChecked).map(box => box.dataset.bingeCheck);
      if (flipped.length) params.set('x', flipped.join('.'));
      if (extras && extras.params) extras.params(params);
      return params;
    }

    function applyParams(params) {
      let used = false;
      Array.from(form.elements).forEach(input => {
        if (!input.name || !params.has(input.name)) return;
        const value = params.get(input.name);
        if (input.type === 'radio') input.checked = input.value === value;
        else if (input.type === 'checkbox') input.checked = value === '1';
        else if (input.tagName === 'SELECT') {
          if (Array.from(input.options).some(option => option.value === value)) input.value = value;
        } else if (input.type === 'date') {
          if (parseIso(value)) input.value = value;
        } else if (/^\d{1,6}(\.\d{1,2})?$/.test(value)) input.value = value;
        used = true;
      });
      const flipped = (params.get('x') || '').split('.').filter(Boolean);
      checks.forEach(box => {
        if (flipped.includes(box.dataset.bingeCheck)) { box.checked = !box.defaultChecked; used = true; }
      });
      return used;
    }

    function shareUrl() {
      const params = stateParams();
      const query = params.toString();
      return `${window.location.origin}${window.location.pathname}${query ? `?${query}` : ''}`;
    }

    function say(message) {
      if (out.copied) out.copied.textContent = message;
    }

    async function copyLink() {
      const url = shareUrl();
      try {
        await navigator.clipboard.writeText(url);
        say('Link copied. Anyone who opens it sees this plan.');
      } catch (error) {
        say(url);
      }
      report('share_clicked');
    }

    function saveCalendar() {
      if (!last || !last.text.date) return;
      const name = last.plan.name || 'my plan';
      const body = `${last.text.finish} ${last.text.detail}`.trim();
      const blob = new Blob([calendarFile(name, last.text.date, body, shareUrl())], { type: 'text/calendar' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `finish-${(name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'plan').slice(0, 60)}.ics`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      say('Calendar file saved. Open it to add the date to your calendar.');
    }

    // Ticking parts by hand starts the count again; typing a number of episodes leaves the ticks alone.
    checks.forEach(box => {
      box.hidden = false;
      box.addEventListener('change', () => {
        report('binge_planned');
        update();
      });
    });
    const hint = tool.querySelector('[data-binge-hint]');
    if (hint) hint.hidden = false;
    form.addEventListener('input', event => {
      report('binge_planned');
      if (extras && extras.onInput) extras.onInput(event);
      update();
    });
    form.addEventListener('change', update);
    form.addEventListener('submit', event => event.preventDefault());
    tool.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!target) return;
      if (target.hasAttribute('data-binge-copy')) copyLink();
      else if (target.hasAttribute('data-binge-calendar')) saveCalendar();
    });

    field('start').value = todayIso();
    if (field('by')) {
      // A month from today is a sensible first deadline.
      const month = new Date();
      month.setDate(month.getDate() + 30);
      field('by').value = todayIso(month);
    }
    let fromLink = false;
    try {
      fromLink = applyParams(new URLSearchParams(window.location.search));
    } catch (error) { /* a bad link just loads the defaults */ }
    update();
    return { update, field, checks, fromLink, say };
  }

  // ------------------------------------------------------------ a guide's planner
  function setupGuide(tool) {
    let plan;
    try {
      plan = JSON.parse(tool.dataset.bingePlan);
    } catch (error) {
      return null;
    }
    if (!plan || !Array.isArray(plan.parts)) return null;
    const planner = setup(tool, () => plan);
    setupTrack(plan, planner);
    setupGuestSave();
    return planner;
  }

  function trackText(plan, progress, left) {
    const single = progress.total === 1;
    const hours = `${formatHours(left.minutes / 60)} hours`;
    const doing = plan.kind === 'book' ? 'reading' : 'watching';
    if (progress.total && progress.done >= progress.total) {
      return { title: single ? `You have finished ${plan.name}` : `You have finished all ${progress.total}`, text: 'It is marked as finished in your library. Nicely done.' };
    }
    if (progress.watched) {
      return { title: `You are ${plural(progress.watched, 'episode')} in`,
        text: `Your library says you have seen ${plural(progress.watched, 'episode')}, so the planner starts from there: about ${hours} of ${doing} left.` };
    }
    if (!single && progress.done) {
      return { title: `You have finished ${progress.done} of ${progress.total}`,
        text: `The ones marked finished in your library are unticked below: about ${hours} of ${doing} left.` };
    }
    if (progress.tracked) {
      return { title: single ? `${plan.name} is in your library` : `${progress.tracked} of ${progress.total} are in your library`,
        text: single && (plan.kind === 'tv' || plan.kind === 'anime')
          ? 'Tick off episodes in your library and this page will start the plan from where you are.'
          : 'Mark them finished in your library as you go and this page will count only what is left.' };
    }
    return { title: 'Not in your library yet', text: `Add ${single ? 'it' : 'them'} and this page keeps count of what you have left.` };
  }

  function addLabel(plan, progress) {
    const missing = (progress.missing || []).length;
    if (!missing) return '';
    if (progress.total === 1) return 'Add it to my library';
    return missing === progress.total ? `Add all ${missing} to my library` : `Add the ${missing} you are missing to my library`;
  }

  function setupTrack(plan, planner) {
    const panel = document.querySelector('[data-binge-track]');
    if (!panel || !SLUG.test(panel.dataset.bingeTrack || '')) return;
    const slug = panel.dataset.bingeTrack;
    const title = panel.querySelector('[data-binge-track-title]');
    const text = panel.querySelector('[data-binge-track-text]');
    const button = panel.querySelector('[data-binge-add]');
    const status = panel.querySelector('[data-binge-track-status]');

    function show(progress, apply) {
      if (apply && !planner.fromLink) {
        const done = new Set(progress.done_parts || []);
        planner.checks.forEach(box => { if (done.has(box.dataset.bingeCheck)) box.checked = false; });
        const seen = planner.field('seen');
        if (seen && progress.watched > 0) seen.value = String(progress.watched);
      }
      const state = planner.update();
      const words = trackText(plan, progress, state.left);
      title.textContent = words.title;
      text.textContent = words.text;
      const label = addLabel(plan, progress);
      button.hidden = !label;
      button.textContent = label;
      panel.hidden = false;
    }

    fetch(`/api/binge-calculator/${slug}/progress`, { credentials: 'same-origin', headers: authHeaders() })
      .then(response => (response.ok ? response.json() : null))
      .then(progress => { if (progress && typeof progress.total === 'number') show(progress, true); })
      .catch(() => { /* the page works without it */ });

    button.addEventListener('click', async () => {
      button.disabled = true;
      status.textContent = '';
      try {
        const response = await fetch(`/api/binge-calculator/${slug}/add`, { method: 'POST', credentials: 'same-origin', headers: authHeaders() });
        if (!response.ok) throw new Error('failed');
        const result = await response.json();
        const added = (result.added || []).length;
        show(result.progress, false);
        status.textContent = added ? `Added ${added === 1 ? `“${result.added[0].title}”` : `${added} titles`} to your library. ` : 'Already in your library. ';
        const link = document.createElement('a');
        link.href = '/';
        link.textContent = 'Open my library';
        status.appendChild(link);
      } catch (error) {
        status.textContent = 'Could not add right now. Try again in a moment.';
      }
      button.disabled = false;
    });
  }

  function setupGuestSave() {
    const button = document.querySelector('[data-binge-guest-save]');
    const holder = document.querySelector('[data-binge-guest]');
    if (!button || !holder) return;
    const status = document.querySelector('[data-binge-track-status]');
    const tiles = Array.from(holder.querySelectorAll('[data-guest-kind]'));
    const label = button.textContent;
    const allSaved = () => {
      const list = window.OmniGuestList;
      if (!list) return false;
      const saved = list.read();
      return tiles.every(tile => saved.some(item => item.kind === tile.dataset.guestKind && item.slug === tile.dataset.guestSlug));
    };
    const refresh = () => { button.textContent = allSaved() ? 'Saved to your list ✓' : label; };
    button.addEventListener('click', () => {
      const list = window.OmniGuestList;
      if (!list) return;
      let saved = 0;
      let full = false;
      tiles.forEach(tile => {
        const result = list.add(tile.dataset.guestKind, tile.dataset.guestSlug, tile.dataset.guestTitle);
        if (result.added) saved += 1;
        if (result.full) full = true;
      });
      list.refreshTiles();
      if (saved) report('binge_saved');
      status.textContent = full ? `Saved ${saved}. Your list is full (${list.MAX} titles). `
        : saved ? `Saved ${saved === 1 ? 'it' : saved} to your list. It stays in this browser until you sign up. `
          : 'Already on your list. ';
      const link = document.createElement('a');
      link.href = '/#signup';
      link.textContent = 'Create a free account to keep it';
      status.appendChild(link);
      refresh();
    });
    refresh();
  }

  // ------------------------------------------------------------ the hub's calculator
  const KIND_FOR_LOOKUP = { tv: 'screen', anime: 'screen', book: 'book', movie: 'film', game: 'game' };

  function customPlan(values) {
    const kind = values.kind;
    if (values.override) {
      return { kind: 'time', name: values.override.name, detail: values.override.detail, skip: 0,
        parts: [{ id: '0', name: values.override.name, unit: 'item', n: 1, min: values.override.minutes }] };
    }
    if (kind === 'book') {
      return { kind: 'book', name: values.name || 'Your book', how: 'read', pagesPerHour: values.pace, skip: 0,
        parts: [{ id: '0', name: 'Book', unit: 'book', n: 1, min: 0, pages: values.pages }] };
    }
    if (kind === 'audio') {
      return { kind: 'book', name: values.name || 'Your audiobook', how: 'listen', skip: 0,
        parts: [{ id: '0', name: 'Audiobook', unit: 'book', n: 1, min: values.audioHours * 60, audio: values.audioHours * 60 }] };
    }
    if (kind === 'game') {
      return { kind: 'game', name: values.name || 'Your game', skip: 0,
        parts: [{ id: '0', name: 'Game', unit: 'game', n: 1, min: values.gameHours * 60 }] };
    }
    if (kind === 'film') {
      return { kind: 'film', name: values.name || 'Your films', skip: 0,
        parts: [{ id: '0', name: 'Films', unit: 'film', n: values.films, min: values.films * values.filmMinutes }] };
    }
    return { kind: 'tv', name: values.name || 'Your show', skip: 2,
      parts: [{ id: '0', name: 'Episodes', unit: 'episode', n: values.episodes, min: values.episodes * values.minutes }] };
  }

  function setupCustom(tool) {
    const form = tool.querySelector('[data-binge-form]');
    const searchInput = document.getElementById('bcSearch');
    const results = tool.querySelector('[data-binge-results]');
    const LENGTH_FIELDS = ['episodes', 'minutes', 'films', 'filmMinutes', 'pages', 'audioHours', 'gameHours'];
    let name = 'Breaking Bad';
    let override = null;
    let guide = null;

    function value(field) {
      const number = Number(form.elements[field].value);
      return Number.isFinite(number) && number > 0 ? number : 0;
    }

    function kind() {
      return form.elements.kind.value || 'screen';
    }

    function getPlan() {
      const current = kind();
      tool.querySelectorAll('[data-binge-kind]').forEach(node => { node.hidden = Boolean(override) || node.dataset.bingeKind !== current; });
      // The hub's "how" follows the kind, so the shared planner reads it from the plan.
      return customPlan({ kind: current, name, override, episodes: value('episodes'), minutes: value('minutes'), films: value('films'),
        filmMinutes: value('filmMinutes'), pages: value('pages'), pace: value('pace'), audioHours: value('audioHours'),
        gameHours: value('gameHours') });
    }

    const planner = setup(tool, getPlan, {
      onInput(event) {
        const field = event.target && event.target.name;
        if (LENGTH_FIELDS.includes(field) || field === 'kind') {
          name = '';
          override = null;
          guide = null;
        }
      },
      onUpdate() { showGuideLink(); },
      params(params) { if (name && name !== 'Breaking Bad' && !override) params.set('name', name.slice(0, 80)); },
    });

    function showGuideLink() {
      let link = tool.querySelector('[data-binge-guide-link]');
      if (!guide || !SLUG.test(guide)) {
        if (link) link.remove();
        return;
      }
      if (!link) {
        link = document.createElement('a');
        link.className = 'bc-result__guide';
        link.dataset.bingeGuideLink = '';
        tool.querySelector('[data-binge-result]').appendChild(link);
      }
      link.href = `/binge-calculator/${guide}`;
      link.textContent = 'See it broken down part by part →';
    }

    function load(values) {
      override = values.override || null;
      guide = values.guide || null;
      name = values.name || '';
      if (!override) {
        const target = values.kind || 'screen';
        Array.from(form.elements.kind).forEach(input => { input.checked = input.value === target; });
        ['episodes', 'minutes', 'films', 'filmMinutes', 'pages', 'audioHours', 'gameHours'].forEach(field => {
          if (values[field]) form.elements[field].value = values[field];
          else if ((values.blank || []).includes(field)) form.elements[field].value = '';
        });
      }
      planner.update();
    }

    document.querySelectorAll('[data-binge-example]').forEach(button => {
      button.addEventListener('click', () => {
        const data = button.dataset;
        const each = data.count > 0 ? Math.round((data.total / data.count) * 10) / 10 : 0;
        load({ kind: data.kind, name: data.name, pages: data.pages,
          episodes: data.kind === 'screen' ? data.count : 0, minutes: data.kind === 'screen' ? each : 0,
          films: data.kind === 'film' ? data.count : 0, filmMinutes: data.kind === 'film' ? each : 0,
          guide: (button.closest('[id]') || {}).id });
        tool.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    // ---- look up a title members track
    let searchTimer = null;
    let searchToken = 0;
    function closeResults() {
      results.hidden = true;
      results.textContent = '';
    }

    async function pick(entry) {
      closeResults();
      searchInput.value = entry.title;
      const params = new URLSearchParams({ kind: entry.kind, title: entry.title });
      if (entry.year) params.set('year', entry.year);
      const finish = tool.querySelector('[data-binge-finish]');
      finish.textContent = `Looking up ${entry.title}…`;
      try {
        const response = await fetch(`/api/binge-calculator/length?${params}`);
        const data = response.ok ? await response.json() : {};
        const label = entry.year ? `${entry.title} (${entry.year})` : entry.title;
        const target = KIND_FOR_LOOKUP[entry.kind] || 'screen';
        // Whatever the lookup could not find is left empty, so another title's numbers never sit under this name.
        const blank = { screen: ['episodes', 'minutes'], film: ['filmMinutes'], book: ['pages'], game: ['gameHours'] }[target] || [];
        load({ kind: target, name: label, guide: data.guide, episodes: data.episodes, pages: data.pages, gameHours: data.hours, blank,
          minutes: target === 'screen' ? data.minutes : 0, films: target === 'film' ? 1 : 0, filmMinutes: target === 'film' ? data.minutes : 0 });
        const missing = target === 'book' ? !data.pages : target === 'game' ? !data.hours : target === 'film' ? !data.minutes : !(data.episodes && data.minutes);
        if (missing) finish.textContent = `We do not have the full length of ${entry.title} yet. Fill in the empty boxes and the plan appears.`;
      } catch (error) {
        planner.update();
      }
    }

    async function search(text) {
      const token = ++searchToken;
      if (text.trim().length < 2) return closeResults();
      try {
        const response = await fetch(`/api/titles/search?q=${encodeURIComponent(text)}`);
        const data = response.ok ? await response.json() : { results: [] };
        if (token !== searchToken) return;
        const found = (data.results || []).filter(entry => KIND_FOR_LOOKUP[entry.kind]).slice(0, 6);
        results.textContent = '';
        if (!found.length) {
          const empty = document.createElement('p');
          empty.className = 'muted';
          empty.textContent = 'Nothing with that name yet. Type the numbers in instead.';
          results.append(empty);
        }
        found.forEach(entry => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'bc-search__result';
          const title = document.createElement('strong');
          title.textContent = entry.title;
          const meta = document.createElement('span');
          meta.textContent = [entry.label, entry.year].filter(Boolean).join(' · ');
          button.append(title, meta);
          button.addEventListener('click', () => pick(entry));
          results.append(button);
        });
        results.hidden = false;
      } catch (error) {
        closeResults();
      }
    }

    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => search(searchInput.value), 250);
    });
    searchInput.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeResults();
    });

    // A link from a title page (?kind=tv&title=Severance&year=2022) looks the title up on arrival.
    try {
      const params = new URLSearchParams(window.location.search);
      const title = (params.get('title') || '').slice(0, 200);
      const linkKind = params.get('lookup') || '';
      if (title && KIND_FOR_LOOKUP[linkKind]) {
        const year = /^\d{4}$/.test(params.get('year') || '') ? Number(params.get('year')) : null;
        pick({ kind: linkKind, title, year });
      } else if (params.get('name')) {
        name = params.get('name').slice(0, 80);
        planner.update();
      }
    } catch (error) { /* a bad link just loads the defaults */ }

    setupMine(load);
    return planner;
  }

  // ------------------------------------------------------------ the member's own unfinished titles
  function mineSummary(data) {
    if (!data.count) return 'Nothing unfinished in your library. Add something you plan to start and it shows up here.';
    const all = `${plural(data.count, 'unfinished title')} in your library, about ${formatHours(data.minutes / 60)} hours in all.`;
    if (!data.started) return `You have ${all}`;
    return `You have ${all} The ${data.started === 1 ? 'one' : data.started} you have started ${data.started === 1 ? 'needs' : 'need'} about ${formatHours(data.started_minutes / 60)} hours to finish.`;
  }

  function setupMine(load) {
    const panel = document.querySelector('[data-binge-mine]');
    if (!panel) return;
    const list = panel.querySelector('[data-binge-mine-list]');
    fetch('/api/binge-calculator/mine', { credentials: 'same-origin', headers: authHeaders() })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (!data || !Array.isArray(data.titles)) return;
        panel.querySelector('[data-binge-mine-summary]').textContent = mineSummary(data);
        data.titles.forEach(item => {
          if (typeof item.title !== 'string' || !(item.minutes > 0)) return;
          const row = document.createElement('li');
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'bc-mine__item';
          const title = document.createElement('strong');
          title.textContent = item.title;
          const meta = document.createElement('span');
          meta.textContent = `${item.label} · ${item.started ? `${item.percent}% done, ` : ''}${formatHours(item.minutes / 60)} h left`;
          button.append(title, meta);
          button.addEventListener('click', () => {
            load({ override: { name: item.title, minutes: item.minutes,
              detail: item.started ? `What you have left, from your library (${item.percent}% done).` : 'The whole thing, from your library.' },
            guide: item.guide });
            document.getElementById('bingeTool').scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
          row.appendChild(button);
          list.appendChild(row);
        });
        const note = panel.querySelector('[data-binge-mine-note]');
        note.textContent = data.typical
          ? `${data.typical === 1 ? 'One of these uses' : `${data.typical} of these use`} a typical length because nothing more exact is known yet. Tap a title to plan it.`
          : 'Tap a title to plan it.';
        if (!data.titles.length) note.textContent = '';
        panel.hidden = false;
      })
      .catch(() => { /* the calculator works without it */ });
  }

  function init() {
    const guide = document.querySelector('[data-binge-plan]');
    if (guide) setupGuide(guide);
    const custom = document.querySelector('[data-binge-custom]');
    if (custom) setupCustom(custom);
  }

  const api = { todayIso, parseIso, finishDate, activeDaysBetween, formatHours, clock, spoken, plural, partCount, partMinutes,
    remaining, planByTime, planByDate, perDayText, describe, calendarFile, customPlan, trackText, addLabel, mineSummary };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
}());
