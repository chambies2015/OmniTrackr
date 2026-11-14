// The December advent calendar: opening doors on /holidays/advent-calendar, saving picks,
// the morning reminder, and the dashboard card.
// Members' opened doors are kept on the server; visitors' stay in this browser until they sign up.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const TOTAL = 24;

  function guestKey(year) {
    return `omnitrackr_advent_${year}`;
  }

  function readStorage(key) {
    try { return window.localStorage.getItem(key); } catch (error) { return null; }
  }

  function writeStorage(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
    } catch (error) { /* storage blocked: the page still works for this visit */ }
  }

  // Doors a visitor opened, as a sorted list of valid day numbers.
  function cleanDays(values) {
    const days = new Set();
    (Array.isArray(values) ? values : []).forEach(value => {
      const day = Number(value);
      if (Number.isInteger(day) && day >= 1 && day <= TOTAL) days.add(day);
    });
    return Array.from(days).sort((a, b) => a - b);
  }

  function readGuest(year) {
    try { return cleanDays(JSON.parse(readStorage(guestKey(year)) || '[]')); } catch (error) { return []; }
  }

  function writeGuest(year, days) {
    writeStorage(guestKey(year), days.length ? JSON.stringify(cleanDays(days)) : null);
  }

  // YYYY-MM-DD in the reader's own time zone.
  function localDate(now) {
    const date = now || new Date();
    const pad = value => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function progressText(opened, unlocked) {
    if (!unlocked) return 'The first door opens on December 1.';
    if (opened >= TOTAL) return `All ${TOTAL} doors opened. That's the whole calendar.`;
    const waiting = unlocked - opened;
    const head = `${opened} of ${TOTAL} so far`;
    if (!waiting) return `${head}, and you're up to date. The next door opens at midnight.`;
    return `${head}. ${waiting} more ${waiting === 1 ? 'door is' : 'doors are'} open and waiting for you.`;
  }

  function beacon(event) {
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting is optional */ }
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data && typeof data.detail === 'string' ? data.detail : 'Something went wrong. Try again.');
    return data;
  }

  function reducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (error) { return false; }
  }

  // ---------------------------------------------------------------- the calendar page

  function initCalendar(root) {
    const year = Number(root.dataset.adventYear);
    if (!Number.isInteger(year)) return;
    const member = root.dataset.adventMember === '1';
    const single = root.dataset.adventSingle === '1';
    const today = localDate();
    const state = { opened: new Set(), library: {}, reminder: false, hasDevice: false, busy: false };

    // Doors whose date hasn't started where the reader is stay shut, even if it's that day somewhere else.
    const doors = Array.from(root.querySelectorAll('[data-advent-door]'));
    const ready = [];
    doors.forEach(link => {
      const day = Number(link.dataset.adventDoor);
      if ((link.dataset.adventDate || '') > today) {
        link.classList.remove('ad-door--ready');
        link.classList.add('ad-door--locked', 'ad-door--soon');
        link.removeAttribute('href');
        link.setAttribute('aria-disabled', 'true');
        const hint = link.querySelector('.ad-door__front');
        if (hint && !hint.querySelector('.ad-door__when')) {
          const when = document.createElement('span');
          when.className = 'ad-door__when';
          when.textContent = 'Opens at midnight';
          hint.appendChild(when);
        }
        const pick = root.querySelector(`[data-advent-pick="${day}"]`);
        if (pick && !single) pick.hidden = true;
      } else {
        ready.push(day);
      }
    });

    function render() {
      doors.forEach(link => {
        const day = Number(link.dataset.adventDoor);
        link.classList.toggle('ad-door--open', state.opened.has(day));
        if (state.opened.has(day)) link.setAttribute('aria-label', link.getAttribute('aria-label').replace(/ \(opened\)$/, '') + ' (opened)');
      });
      root.querySelectorAll('[data-advent-pick]').forEach(pick => {
        const day = Number(pick.dataset.adventPick);
        const opened = pick.querySelector('[data-advent-opened]');
        if (opened) opened.hidden = !state.opened.has(day);
        const owned = pick.querySelector('[data-advent-owned]');
        const match = state.library[String(day)];
        if (owned) {
          owned.hidden = !match;
          owned.textContent = match ? (match.state === 'done' ? 'Finished ✓' : 'In your library') : '';
        }
        const add = pick.querySelector('[data-advent-add]');
        if (add) add.hidden = Boolean(match);
        pick.classList.toggle('sn-pick--done', Boolean(match && match.state === 'done'));
      });
      const box = root.querySelector('[data-advent-progress]');
      if (box && !single) {
        const count = Array.from(state.opened).filter(day => ready.includes(day)).length;
        box.hidden = false;
        const meter = box.querySelector('[data-advent-meter]');
        const fill = box.querySelector('[data-advent-meter-fill]');
        if (meter) meter.setAttribute('aria-valuenow', String(count));
        if (fill) fill.style.width = `${Math.round((count / TOTAL) * 100)}%`;
        const title = box.querySelector('[data-advent-progress-title]');
        if (title) title.textContent = count ? `${count} ${count === 1 ? 'door' : 'doors'} opened` : 'Your calendar';
        const text = box.querySelector('[data-advent-progress-text]');
        if (text) text.textContent = progressText(count, ready.length);
        const remind = box.querySelector('[data-advent-remind]');
        if (remind) {
          remind.setAttribute('aria-pressed', state.reminder ? 'true' : 'false');
          remind.textContent = state.reminder ? 'Morning reminder on ✓' : 'Remind me each morning';
        }
      }
    }

    function applyState(data) {
      if (!data || !Array.isArray(data.opened)) return;
      state.opened = new Set(cleanDays(data.opened));
      state.library = data.library && typeof data.library === 'object' ? data.library : {};
      state.reminder = Boolean(data.reminder);
      state.hasDevice = Boolean(data.has_device);
      render();
    }

    async function openDoor(day) {
      if (!ready.includes(day) || state.opened.has(day)) return;
      state.opened.add(day);
      render();
      if (member) {
        try {
          applyState(await send('POST', `/api/advent-calendar/${year}/open`, { days: [day] }));
        } catch (error) { /* shown as opened for this visit; it is saved next time */ }
      } else {
        writeGuest(year, Array.from(state.opened));
        beacon('advent_guest_opened');
      }
    }

    doors.forEach(link => {
      link.addEventListener('click', event => {
        const day = Number(link.dataset.adventDoor);
        if (!ready.includes(day)) { event.preventDefault(); return; }
        event.preventDefault();
        const wasOpen = state.opened.has(day);
        openDoor(day);
        const target = root.querySelector(`#door-${day}`);
        if (!target) return;
        const go = () => {
          target.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
          try { history.replaceState(null, '', `#door-${day}`); } catch (error) { /* the hash is a nicety */ }
          target.classList.add('ad-pick--flash');
          setTimeout(() => target.classList.remove('ad-pick--flash'), 1600);
        };
        // Let the door swing before scrolling to what's behind it.
        if (wasOpen || reducedMotion()) go();
        else setTimeout(go, 700);
      });
    });

    // Members: add a pick to the library.
    root.addEventListener('click', async event => {
      const add = event.target.closest && event.target.closest('[data-advent-add]');
      if (add && member && !state.busy) {
        const day = Number(add.dataset.adventAdd);
        const pick = add.closest('[data-advent-pick]');
        const status = pick && pick.querySelector('[data-advent-status]');
        state.busy = true;
        add.disabled = true;
        try {
          const data = await send('POST', `/api/advent-calendar/${year}/doors/${day}/add`);
          if (status) status.textContent = data.state === 'created' ? `Added ${data.title} to your library, not started yet.` : `${data.title} is already in your library.`;
          applyState(data);
          openDoor(day);
        } catch (error) {
          if (status) status.textContent = error.message;
        } finally {
          add.disabled = false;
          state.busy = false;
        }
        return;
      }
      const share = event.target.closest && event.target.closest('[data-advent-share]');
      if (share) {
        const url = share.dataset.shareUrl;
        const title = share.dataset.shareTitle || document.title;
        const pick = share.closest('[data-advent-pick]');
        const status = pick && pick.querySelector('[data-advent-status]');
        beacon('advent_shared');
        if (navigator.share) {
          try { await navigator.share({ title, url }); return; } catch (error) { if (error && error.name === 'AbortError') return; }
        }
        try {
          await navigator.clipboard.writeText(url);
          if (status) status.textContent = 'Link copied. It shows this door and nothing from your library.';
        } catch (error) {
          if (status) status.textContent = `The link: ${url}`;
        }
        return;
      }
      const remind = event.target.closest && event.target.closest('[data-advent-remind]');
      if (remind && member && !state.busy) {
        const note = root.querySelector('[data-advent-remind-note]');
        state.busy = true;
        remind.disabled = true;
        try {
          const data = await send('PUT', `/api/advent-calendar/${year}/reminder`, { on: !state.reminder });
          applyState(data);
          if (note) {
            if (!state.reminder) note.textContent = 'Reminder off. The doors still open every day.';
            else if (state.hasDevice) note.textContent = 'You\'ll get one notification each morning when a new door opens. It never names the pick.';
            else {
              note.textContent = 'Saved. To get it on this phone or computer, turn on notifications from the bell on your dashboard. ';
              const link = document.createElement('a');
              link.href = '/#settings-notifications';
              link.textContent = 'Notification settings';
              note.appendChild(link);
            }
          }
        } catch (error) {
          if (note) note.textContent = error.message;
        } finally {
          remind.disabled = false;
          state.busy = false;
        }
        return;
      }
      const signup = event.target.closest && event.target.closest('[data-advent-signup]');
      if (signup) beacon('advent_signup_clicked');
    });

    if (member) {
      (async () => {
        try {
          let data = await send('GET', `/api/advent-calendar/${year}`);
          // Doors opened in this browser before signing up join the member's calendar once.
          const waiting = readGuest(year).filter(day => ready.includes(day) && !(data.opened || []).includes(day));
          if (waiting.length) {
            data = await send('POST', `/api/advent-calendar/${year}/open`, { days: waiting });
            writeGuest(year, []);
          }
          applyState(data);
        } catch (error) {
          render();
        }
      })();
    } else {
      state.opened = new Set(readGuest(year).filter(day => ready.includes(day)));
      render();
    }
  }

  // ---------------------------------------------------------------- dashboard card

  const card = { request: 0 };

  function cardDismissKey(data) {
    let who = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) who = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_advent_card_hidden_${who}_${data.year}`;
  }

  // Today's door is the newest one whose date has started where the member is.
  function cardView(data, today) {
    const doors = (Array.isArray(data.doors) ? data.doors : []).filter(door => door && (door.date || '') <= today);
    if (!doors.length) return null;
    const opened = cleanDays(data.opened_days);
    const newest = doors[doors.length - 1];
    return {
      newest: Number(newest.day), hint: String(newest.hint || ''), total: Number(data.total) || TOTAL,
      unlocked: doors.length, opened, newestOpened: opened.includes(Number(newest.day)),
      missed: doors.filter(door => !opened.includes(Number(door.day))).length,
    };
  }

  function cardCopy(view) {
    const left = view.total - view.newest;
    const when = left === 0 ? 'The last door is open.' : `${left} ${left === 1 ? 'door' : 'doors'} to go.`;
    const count = view.opened.length;
    if (count >= view.total) {
      return { title: 'Every door opened', summary: 'You opened the whole calendar. Merry Christmas.', action: 'See the calendar' };
    }
    if (view.newestOpened) {
      const others = view.missed;
      const missed = others ? ` ${others} earlier ${others === 1 ? 'door is' : 'doors are'} still shut.` : '';
      return { title: `Door ${view.newest} opened`, summary: `${count} of ${view.total} opened. ${when}${missed}`, action: others ? 'Catch up' : 'See the calendar' };
    }
    return { title: `Door ${view.newest} is open`, summary: `${view.hint}. ${count} of ${view.total} opened so far.`, action: 'Open today\'s door' };
  }

  function renderCard(data) {
    const section = $('adventCard');
    if (!section) return;
    const view = data && data.show ? cardView(data, localDate()) : null;
    if (!view || readStorage(cardDismissKey(data)) === '1') {
      section.hidden = true;
      return;
    }
    const copy = cardCopy(view);
    $('adventCardTitle').textContent = copy.title;
    $('adventCardSummary').textContent = copy.summary;
    const link = $('adventCardLink');
    link.textContent = copy.action;
    link.href = view.newestOpened ? '/holidays/advent-calendar#calendar' : `/holidays/advent-calendar#door-${view.newest}`;
    const strip = $('adventCardDoors');
    if (strip) {
      strip.replaceChildren();
      for (let day = 1; day <= view.total; day += 1) {
        const cell = document.createElement('li');
        if (day <= view.unlocked) cell.classList.add('is-ready');
        if (view.opened.includes(day)) cell.classList.add('is-opened');
        if (day === view.newest) cell.classList.add('is-today');
        strip.appendChild(cell);
      }
    }
    section.dataset.dismissKey = cardDismissKey(data);
    section.hidden = false;
  }

  // The calendar only runs in December (an earlier opening day can be set for testing in November).
  function cardSeason(now) {
    const month = (now || new Date()).getMonth();
    return month === 10 || month === 11;
  }

  async function refreshAdventCard() {
    const section = $('adventCard');
    if (!section) return;
    if (!cardSeason()) { section.hidden = true; return; }
    const request = ++card.request;
    try {
      const response = await fetch('/api/advent-calendar', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== card.request) return;
      renderCard(data);
    } catch (error) {
      // The card is optional; the dashboard works without it.
    }
  }

  function resetAdventCard() {
    card.request += 1;
    const section = $('adventCard');
    if (section) section.hidden = true;
  }

  function initCard() {
    const dismiss = $('adventCardDismiss');
    if (!dismiss) return;
    dismiss.addEventListener('click', () => {
      const section = $('adventCard');
      if (section && section.dataset.dismissKey) writeStorage(section.dataset.dismissKey, '1');
      if (section) section.hidden = true;
    });
  }

  function init() {
    const root = document.querySelector('[data-advent-year]');
    if (root) initCalendar(root);
    initCard();
  }

  if (typeof window !== 'undefined') {
    window.refreshAdventCard = refreshAdventCard;
    window.resetAdventCard = resetAdventCard;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { cleanDays, localDate, progressText, cardView, cardCopy, cardSeason };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
