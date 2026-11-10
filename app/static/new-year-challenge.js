// The New Year challenge: the pledge form on /new-year-challenge/<year> and the dashboard card.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const SAMPLES = {
    light: { books: 6, movies: 12, music: 12, 'video-games': 3 },
    busy: { books: 24, movies: 52, 'tv-shows': 6, anime: 4, 'video-games': 8, music: 30, podcasts: 2, audiobooks: 4 },
  };
  const FLASH_KEY = 'omnitrackr_pledge_flash';

  const $ = id => document.getElementById(id);

  function draftKey(year) {
    return `omnitrackr_pledge_draft_${year}`;
  }

  function readStorage(store, key) {
    try { return window[store].getItem(key); } catch (error) { return null; }
  }

  function writeStorage(store, key, value) {
    try {
      if (value === null) window[store].removeItem(key);
      else window[store].setItem(key, value);
    } catch (error) { /* storage blocked: the form still works */ }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  // Same wording as new_year_challenge.hours_label on the server.
  function hoursLabel(hours) {
    if (!(hours > 0)) return '';
    if (hours < 1) {
      const minutes = Math.max(5, Math.round((hours * 60) / 5) * 5);
      return `about ${minutes} minutes a week`;
    }
    const whole = Math.round(hours * 2) / 2;
    return `about ${whole} hour${whole === 1 ? '' : 's'} a week`;
  }

  function weeklyHours(rows) {
    let total = 0;
    rows.forEach(row => {
      const value = Number.parseInt(row.querySelector('input').value, 10);
      const hours = Number(row.dataset.hours) || 0;
      if (Number.isInteger(value) && value > 0) total += hours * value;
    });
    return Math.round((total / 52) * 10) / 10;
  }

  function totalText(hours) {
    const label = hoursLabel(hours);
    if (!label) return 'Fill in a number or two to see roughly how much time it adds up to.';
    return `At typical lengths that comes to ${label}, not counting the any-kind goal.`;
  }

  function collect(form) {
    const values = {};
    let count = 0;
    let invalid = false;
    const max = Number(form.dataset.max) || 1000;
    form.querySelectorAll('.nyc-row').forEach(row => {
      const input = row.querySelector('input');
      const raw = input.value.trim();
      if (!raw) { values[row.dataset.category] = null; return; }
      const value = Number(raw);
      if (!Number.isInteger(value) || value < 1 || value > max) { invalid = true; return; }
      values[row.dataset.category] = value;
      count += 1;
    });
    return { values, count, invalid };
  }

  function fill(form, numbers) {
    form.querySelectorAll('.nyc-row').forEach(row => {
      const value = numbers[row.dataset.category];
      row.querySelector('input').value = Number.isInteger(value) && value > 0 ? String(value) : '';
    });
  }

  function apiErrorText(body, fallback) {
    if (body && typeof body.detail === 'string') return body.detail;
    if (body && Array.isArray(body.detail) && body.detail[0] && body.detail[0].msg) return 'Check the numbers and try again.';
    return fallback;
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiErrorText(data, 'Something went wrong. Try again.'));
    return data;
  }

  function beacon(event) {
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
      }
    } catch (error) { /* counting is optional */ }
  }

  // Opens the share sheet, or copies the link. Returns a line for the status text.
  async function shareLink(url, year) {
    const text = `My ${year} challenge on OmniTrackr`;
    if (navigator.share) {
      try {
        await navigator.share({ title: text, text, url });
        return '';
      } catch (error) {
        if (error && error.name === 'AbortError') return '';
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      return 'Link copied. It shows your numbers, never your titles.';
    } catch (error) {
      return `Your link: ${url}`;
    }
  }

  function reloadWith(message) {
    writeStorage('sessionStorage', FLASH_KEY, message);
    window.location.hash = 'pledge';
    window.location.reload();
  }

  // ---------------------------------------------------------------- the guide page

  function initForm(form) {
    const year = form.dataset.year;
    const member = form.dataset.member === '1';
    const rows = Array.from(form.querySelectorAll('.nyc-row'));
    const total = form.querySelector('[data-pledge-total]');
    const statusNode = form.querySelector('[data-pledge-status]');
    const status = text => { if (statusNode) statusNode.textContent = text || ''; };
    const section = form.closest('section') || document;
    let busy = false;
    let leaveArmed = false;

    const update = () => { if (total) total.textContent = totalText(weeklyHours(rows)); };

    const flash = readStorage('sessionStorage', FLASH_KEY);
    if (flash) {
      writeStorage('sessionStorage', FLASH_KEY, null);
      status(flash);
    }

    const draft = readStorage('localStorage', draftKey(year));
    if (draft) {
      try {
        const numbers = JSON.parse(draft);
        if (member && form.dataset.pledged !== '1') {
          fill(form, numbers);
          status('These are the numbers you picked before signing up. Press "Make my pledge" to save them.');
        } else if (!member) {
          fill(form, numbers);
        }
      } catch (error) { /* a broken draft is ignored */ }
      if (member && form.dataset.pledged === '1') writeStorage('localStorage', draftKey(year), null);
    }
    update();

    form.addEventListener('input', update);
    form.addEventListener('click', event => {
      const button = event.target.closest('button[data-preset], button[data-sample]');
      if (!button) return;
      if (button.dataset.sample) {
        fill(form, SAMPLES[button.dataset.sample] || {});
      } else if (button.dataset.preset === 'clear') {
        fill(form, {});
      } else {
        const preset = button.dataset.preset;
        const numbers = {};
        rows.forEach(row => {
          const value = Number(row.dataset[preset]);
          if (Number.isInteger(value) && value > 0) numbers[row.dataset.category] = value;
        });
        fill(form, numbers);
      }
      update();
      status('');
    });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      const { values, count, invalid } = collect(form);
      if (invalid) { status(`Use whole numbers from 1 to ${form.dataset.max || 1000}.`); return; }
      if (!member) {
        if (!count) { status('Fill in at least one number first.'); return; }
        const numbers = {};
        Object.keys(values).forEach(key => { if (values[key]) numbers[key] = values[key]; });
        writeStorage('localStorage', draftKey(year), JSON.stringify(numbers));
        beacon('pledge_signup_clicked');
        window.location.assign(form.dataset.signup);
        return;
      }
      if (!count && form.dataset.pledged !== '1') { status('Fill in at least one number first.'); return; }
      busy = true;
      status('Saving…');
      try {
        await send('PUT', `/api/new-year-challenge/${encodeURIComponent(year)}/pledge`, { goals: values });
        writeStorage('localStorage', draftKey(year), null);
        reloadWith(form.dataset.pledged === '1' ? 'Pledge updated.' : `You're in. Your ${year} goals are on your dashboard.`);
      } catch (error) {
        status(error.message);
        busy = false;
      }
    });

    section.addEventListener('click', async event => {
      const button = event.target.closest('[data-pledge-action]');
      if (!button || busy) return;
      const action = button.dataset.pledgeAction;
      if (action === 'leave' && !leaveArmed) {
        leaveArmed = true;
        button.textContent = 'Press again to leave (your goals stay)';
        return;
      }
      busy = true;
      try {
        if (action === 'share') {
          const data = await send('PUT', `/api/new-year-challenge/${encodeURIComponent(year)}/share`);
          const message = data.url ? await shareLink(data.url, year) : '';
          if (form.dataset.shared !== '1') {
            reloadWith(message || 'Your pledge card is live.');
            return;
          }
          status(message);
        } else if (action === 'unshare') {
          await send('DELETE', `/api/new-year-challenge/${encodeURIComponent(year)}/share`);
          reloadWith('Sharing stopped. The old link no longer works.');
        } else if (action === 'leave') {
          await send('DELETE', `/api/new-year-challenge/${encodeURIComponent(year)}/pledge`);
          reloadWith('You left the challenge. Your goals are still on your dashboard.');
        }
      } catch (error) {
        status(error.message);
      } finally {
        busy = false;
      }
    });
  }

  // ---------------------------------------------------------------- dashboard card

  const card = { request: 0 };

  function cardDismissKey(year) {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_pledge_card_hidden_${name}_${year}`;
  }

  function cardCopy(data) {
    if (!data.pledged) {
      return {
        eyebrow: `The ${data.year} challenge`,
        title: `Pick what you'll finish in ${data.year}`,
        summary: data.started
          ? 'Pledge a number of books, films, games or albums for the year. It counts what you already track, and you can join any time.'
          : 'Pledge a number of books, films, games or albums for next year. Your numbers from this year are there to start from.',
        action: 'Make your pledge',
      };
    }
    const goalsText = `${data.goals} goal${data.goals === 1 ? '' : 's'}`;
    return {
      eyebrow: `The ${data.year} challenge`,
      title: data.started ? `You're in with ${goalsText}` : `You're in. ${data.days_until_start} day${data.days_until_start === 1 ? '' : 's'} to go`,
      summary: data.started
        ? 'Your goals card below shows where you stand. Your pledge card updates as you go.'
        : `${goalsText} pledged. Share your pledge card so friends can join you.`,
      action: data.shared ? 'See your pledge' : 'Share your pledge card',
    };
  }

  function renderCard(data) {
    const section = $('newYearPledge');
    if (!section) return;
    if (!data || !data.show || readStorage('localStorage', cardDismissKey(data.year)) === '1') {
      section.hidden = true;
      return;
    }
    const copy = cardCopy(data);
    $('newYearPledgeEyebrow').textContent = copy.eyebrow;
    $('newYearPledgeTitle').textContent = copy.title;
    $('newYearPledgeSummary').textContent = copy.summary;
    const link = $('newYearPledgeLink');
    link.textContent = copy.action;
    link.href = data.shared && data.url ? data.url : `${data.page}#pledge`;
    section.dataset.year = String(data.year);
    section.hidden = false;
  }

  async function refreshNewYearPledge() {
    const section = $('newYearPledge');
    if (!section) return;
    const request = ++card.request;
    try {
      const response = await fetch('/api/new-year-challenge', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== card.request) return;
      renderCard(data);
    } catch (error) {
      // The card is optional; the dashboard works without it.
    }
  }

  function resetNewYearPledge() {
    card.request += 1;
    const section = $('newYearPledge');
    if (section) section.hidden = true;
  }

  function initCard() {
    const dismiss = $('newYearPledgeDismiss');
    if (!dismiss) return;
    dismiss.addEventListener('click', () => {
      const section = $('newYearPledge');
      const year = section && section.dataset.year;
      if (year) writeStorage('localStorage', cardDismissKey(year), '1');
      if (section) section.hidden = true;
    });
  }

  function init() {
    const form = $('pledgeForm');
    if (form) initForm(form);
    initCard();
  }

  if (typeof window !== 'undefined') {
    window.refreshNewYearPledge = refreshNewYearPledge;
    window.resetNewYearPledge = resetNewYearPledge;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { hoursLabel, weeklyHours, totalText, collect, cardCopy, SAMPLES };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
