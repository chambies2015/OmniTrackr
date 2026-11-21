// Dashboard: this month's opt-in challenge ("Finish one pick from the October edition").
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { request: 0, data: null, forced: false, busy: false, crediting: null };

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function dismissKey(month) {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_challenge_hidden_${name}_${month}`;
  }

  function dismissed(month) {
    try { return localStorage.getItem(dismissKey(month)) === '1'; } catch (error) { return false; }
  }

  function daysLeftText(days) {
    if (days <= 0) return 'Ends today';
    if (days === 1) return 'Last day';
    return `${days} days left`;
  }

  function summaryText(data) {
    const steps = data.steps || [];
    if (data.completion) return `Challenge complete. ${daysLeftText(data.days_left)} in ${data.month_name}.`;
    if (!data.joined) {
      const start = data.done_steps
        ? ` You're already ${data.done_steps} of ${steps.length} steps in from what you've finished this month.`
        : ' Progress fills in from what you mark finished this month.';
      return `${steps.length} small steps for ${data.month_name}.${start}`;
    }
    return `${data.done_steps} of ${steps.length} steps done · ${daysLeftText(data.days_left)}`;
  }

  function stepItem(step) {
    const item = el('li', `month-challenge__step${step.done ? ' month-challenge__step--done' : ''}`);
    const mark = el('span', 'month-challenge__mark', step.done ? '✓' : '');
    mark.setAttribute('aria-hidden', 'true');
    const copy = el('span', 'month-challenge__label', step.label);
    item.append(mark, copy);
    if (step.target > 1) item.appendChild(el('span', 'month-challenge__count', `${step.count} of ${step.target}`));
    const status = el('span', 'visually-hidden', step.done ? ' (done)' : ' (not done yet)');
    item.appendChild(status);
    if (step.kind === 'revisit' && !step.done) {
      // A revisit is logged in the Journal, which members rarely open from the home screen.
      const log = el('button', 'month-challenge__link', 'Log a revisit');
      log.type = 'button';
      log.dataset.challengeAction = 'log-revisit';
      item.appendChild(log);
    }
    const hint = stretchHint(step) || birthdayHint(step);
    if (hint) copy.appendChild(el('span', 'month-challenge__hint', hint));
    if (step.kind === 'recommended' && !step.done) {
      copy.appendChild(creditRow(step) || el('span', 'month-challenge__hint', 'Name them under "Why I added it" on the title'));
    }
    return item;
  }

  // Under a step about recommendations: this month's finishes that don't say where they came
  // from yet, each a button that opens the title's "Why I added it" editor.
  function creditRow(step) {
    const titles = (Array.isArray(step.unsaid) ? step.unsaid : [])
      .filter(title => title && Number.isInteger(title.id) && title.id > 0 && typeof title.category === 'string')
      .slice(0, 3);
    if (!titles.length) return null;
    const row = el('span', 'month-challenge__credits');
    row.appendChild(el('span', 'month-challenge__hint', titles.length === 1 ? 'Did someone recommend it?' : 'Did someone recommend one of these?'));
    for (const title of titles) {
      const name = String(title.title || 'Untitled');
      const button = el('button', 'month-challenge__link', name);
      button.type = 'button';
      button.dataset.challengeAction = 'credit';
      button.dataset.category = title.category;
      button.dataset.itemId = String(title.id);
      button.dataset.title = name;
      button.setAttribute('aria-label', `Say who recommended ${name}`);
      row.appendChild(button);
    }
    return row;
  }

  function creditTitle(button) {
    const origins = typeof window !== 'undefined' ? window.OmniTitleOrigins : null;
    const opened = origins && typeof origins.open === 'function'
      && origins.open(button.dataset.category, Number(button.dataset.itemId), button.dataset.title, button);
    state.crediting = opened ? { category: button.dataset.category, id: Number(button.dataset.itemId) } : null;
    if (!opened) status('Open the title in your library and choose Why I added it.');
  }

  // After a save from the card: its button is gone once the card redraws, so the keyboard would
  // drop to the top of the page. Move to the next title to credit (or the card's heading) and say
  // whether the save finished the step.
  function afterCredit() {
    const step = ((state.data && state.data.steps) || []).find(item => item.kind === 'recommended');
    status(step && step.done ? 'Saved. That counts for this step.' : 'Saved.');
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    const next = document.querySelector('#monthlyChallenge [data-challenge-action="credit"]');
    const title = $('monthlyChallengeTitle');
    const target = next || title;
    if (!target || typeof target.focus !== 'function') return;
    if (target === title && !title.hasAttribute('tabindex')) title.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
  }

  // "Counts for you: manga, podcasts or audiobooks" under a step about a format you rarely finish.
  function stretchHint(step) {
    if (step.kind !== 'stretch' || step.done || !Array.isArray(step.formats) || !step.formats.length) return '';
    if (step.formats.length >= 9) return 'Any format counts for you';
    const names = step.formats.map(String);
    const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}`;
    return `Counts for you: ${list}`;
  }

  // Under a step about titles turning a round number this year: up to three from the member's own
  // library ("In your library: Star Wars turns 50, Portal turns 20"), or the years that count.
  function birthdayHint(step) {
    if (step.kind !== 'birthday' || step.done) return '';
    const turning = (Array.isArray(step.turning) ? step.turning : [])
      .filter(title => title && typeof title.title === 'string' && title.title.trim() && Number.isInteger(title.age) && title.age > 0)
      .slice(0, 3);
    if (turning.length) {
      return `In your library: ${turning.map(title => `${title.title.trim()} turns ${title.age}`).join(', ')}`;
    }
    const years = (Array.isArray(step.years) ? step.years : []).filter(year => Number.isInteger(year) && year > 0).slice(0, 4);
    if (!years.length) return '';
    return `Counts if it came out in ${years.join(', ')} or an earlier year ending in ${years[0] % 10}`;
  }

  // Open the Journal's "Add a moment" form with "Revisited" already chosen.
  async function openRevisitForm() {
    const opened = typeof navigateLibraryTab === 'function' ? await navigateLibraryTab('activity') : false;
    if (!opened) {
      status('Open your Journal, choose a title and pick Revisited as the moment.');
      return;
    }
    const action = $('activityAction');
    if (action) action.value = 'revisited';
    const form = $('activityForm');
    if (form && form.scrollIntoView) form.scrollIntoView({ block: 'center' });
    const category = $('activityCategory');
    if (category && category.focus) category.focus({ preventScroll: true });
  }

  function renderCelebration(data) {
    const box = $('monthlyChallengeCelebration');
    if (!box) return;
    const completion = data.completion;
    box.replaceChildren();
    box.hidden = !completion;
    if (!completion) return;
    const copy = el('div', 'month-challenge__celebration-copy');
    copy.append(el('strong', '', completion.celebrate ? `You completed the ${data.month_name} challenge!` : `${data.month_name} challenge complete`),
      el('span', '', completion.shared ? 'Your share link shows the challenge and its steps, never your titles.'
        : 'Share a card with the challenge and its steps. Your titles stay private.'));
    const actions = el('div', 'month-challenge__celebration-actions');
    const share = el('button', 'action-btn', completion.shared ? 'Copy link' : 'Share it');
    share.type = 'button';
    share.dataset.challengeAction = 'share';
    actions.appendChild(share);
    if (completion.shared) {
      const stop = el('button', 'month-challenge__link', 'Stop sharing');
      stop.type = 'button';
      stop.dataset.challengeAction = 'unshare';
      actions.appendChild(stop);
    }
    if (completion.celebrate) {
      const seen = el('button', 'month-challenge__link', 'Dismiss');
      seen.type = 'button';
      seen.dataset.challengeAction = 'seen';
      actions.appendChild(seen);
    }
    box.append(copy, actions);
  }

  function render(data) {
    const section = $('monthlyChallenge');
    if (!section) return;
    state.data = data;
    const show = data.joined || state.forced || !dismissed(data.month);
    section.hidden = !show;
    if (!show) return;
    $('monthlyChallengeEyebrow').textContent = `${data.month_name} challenge`;
    $('monthlyChallengeTitle').textContent = data.name;
    $('monthlyChallengeSummary').textContent = summaryText(data);
    renderCelebration(data);
    $('monthlyChallengeSteps').replaceChildren(...(data.steps || []).map(stepItem));
    const guide = $('monthlyChallengeGuide');
    guide.hidden = !data.url;
    if (data.url) guide.href = data.url;
    $('monthlyChallengeJoin').hidden = Boolean(data.joined);
    $('monthlyChallengeDismiss').hidden = Boolean(data.joined);
    $('monthlyChallengeLeave').hidden = !data.joined || Boolean(data.completion);
  }

  function status(text) {
    const node = $('monthlyChallengeStatus');
    if (node) node.textContent = text || '';
  }

  async function refreshMonthlyChallenge(options) {
    if (!$('monthlyChallenge')) return;
    const credited = Boolean(options && options.credited === true);
    const request = ++state.request;
    try {
      const response = await fetch(`${apiBase()}/api/challenge`, fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      render(data);
      openFromHash();
      if (credited) afterCredit();
    } catch (error) {
      // The challenge is optional; the dashboard works without it.
    }
  }

  function resetMonthlyChallenge() {
    state.request += 1;
    state.data = null;
    state.forced = false;
    const section = $('monthlyChallenge');
    if (section) section.hidden = true;
  }

  async function call(method, path) {
    if (state.busy) return null;
    state.busy = true;
    status('');
    try {
      const response = await fetch(`${apiBase()}/api/challenge/${path}`, fetchOptions({ method, headers: { Accept: 'application/json' } }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Try again.');
      return data;
    } catch (error) {
      status(error.message || 'Something went wrong. Try again.');
      return null;
    } finally {
      state.busy = false;
    }
  }

  async function updateCompletion(method, path) {
    // Name the month on screen so a completion stays reachable after the month turns over.
    const month = state.data && state.data.month;
    const completion = await call(method, month ? `${path}?month=${encodeURIComponent(month)}` : path);
    if (completion && state.data) {
      state.data.completion = completion;
      render(state.data);
    }
    return completion;
  }

  async function shareCompletion() {
    const completion = await updateCompletion('PUT', 'share');
    if (!completion || !completion.url) return;
    const text = `I completed the ${state.data.month_name} challenge on OmniTrackr: ${state.data.name}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: text, text, url: completion.url });
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(completion.url);
      status('Link copied. It shows the challenge, never your titles.');
    } catch (error) {
      status(completion.url);
    }
  }

  async function handleClick(event) {
    const target = event.target.closest && event.target.closest('#monthlyChallenge [data-challenge-action]');
    if (!target || !state.data) return;
    const action = target.dataset.challengeAction;
    if (action === 'join') {
      const data = await call('POST', 'join');
      if (data) { render(data); status('You\'re in. Progress updates as you finish things this month.'); }
    } else if (action === 'leave') {
      const data = await call('DELETE', 'join');
      if (data) { render(data); status('You left the challenge. Your library is unchanged.'); }
    } else if (action === 'dismiss') {
      try { localStorage.setItem(dismissKey(state.data.month), '1'); } catch (error) { /* session only */ }
      state.forced = false;
      render(state.data);
    } else if (action === 'share') {
      shareCompletion();
    } else if (action === 'unshare') {
      if (await updateCompletion('DELETE', 'share')) status('Sharing stopped. The old link no longer works.');
    } else if (action === 'seen') {
      updateCompletion('POST', 'seen');
    } else if (action === 'log-revisit') {
      openRevisitForm();
    } else if (action === 'credit') {
      creditTitle(target);
    }
  }

  function openFromHash() {
    if (window.location.hash !== '#challenge' || !state.data) return;
    state.forced = true;
    render(state.data);
    const section = $('monthlyChallenge');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  function init() {
    document.addEventListener('click', handleClick);
    window.addEventListener('hashchange', openFromHash);
    // Saying who recommended a title can finish a step, wherever it was said.
    window.addEventListener('omnitrackr:title-origin-saved', event => {
      if (!state.data) return;
      const saved = event && event.detail;
      const fromCard = Boolean(state.crediting && saved && saved.category === state.crediting.category
        && Number(saved.id) === state.crediting.id);
      if (fromCard) state.crediting = null;
      refreshMonthlyChallenge({ credited: fromCard });
    });
  }

  if (typeof window !== 'undefined') {
    window.refreshMonthlyChallenge = refreshMonthlyChallenge;
    window.resetMonthlyChallenge = resetMonthlyChallenge;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { daysLeftText, summaryText, dismissKey, stepItem, stretchHint, creditRow, afterCredit, state, birthdayHint };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
