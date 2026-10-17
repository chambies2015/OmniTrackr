// Dashboard: this month's opt-in challenge ("Finish one pick from the October edition").
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { request: 0, data: null, forced: false, busy: false };

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
    return item;
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

  async function refreshMonthlyChallenge() {
    if (!$('monthlyChallenge')) return;
    const request = ++state.request;
    try {
      const response = await fetch(`${apiBase()}/api/challenge`, fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      render(data);
      openFromHash();
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
  }

  if (typeof window !== 'undefined') {
    window.refreshMonthlyChallenge = refreshMonthlyChallenge;
    window.resetMonthlyChallenge = resetMonthlyChallenge;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { daysLeftText, summaryText, dismissKey };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
