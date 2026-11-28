// The occasional "support OmniTrackr" note on the home screen, and its on/off switch in Settings → Supporter.
// The server decides whether there's a note at all (a goal reached, a library milestone, an anniversary,
// perks that just ended) and keeps it to one every couple of months. Server text is only set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const state = { ask: null, request: 0, seen: '', observer: null };

  function options(extra = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(extra);
    return { credentials: 'same-origin', ...extra };
  }

  async function send(method, url, body) {
    const response = await fetch(url, options({
      method,
      headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data && typeof data.detail === 'string' ? data.detail : 'Something went wrong. Try again.');
    return data;
  }

  // Only ko-fi.com links, so a bad value can never send someone elsewhere.
  function safeKofi(url) {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' && (parsed.hostname === 'ko-fi.com' || parsed.hostname.endsWith('.ko-fi.com')) ? parsed.href : null;
    } catch (error) {
      return null;
    }
  }

  function meterWidth(percent) {
    const value = Number(percent);
    if (!Number.isFinite(value)) return 0;
    return Math.max(0, Math.min(100, Math.round(value)));
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text || '';
  }

  function render(ask) {
    const card = $('supportAsk');
    if (!card) return;
    state.ask = ask || null;
    if (!ask) {
      card.hidden = true;
      return;
    }
    card.classList.toggle('support-ask--ended', ask.moment === 'ended');
    card.classList.toggle('support-ask--founding', ask.moment === 'founding');
    card.classList.remove('is-thanked');
    setText('supportAskEyebrow', ask.eyebrow);
    setText('supportAskTitle', ask.title);
    setText('supportAskBody', ask.body);
    setText('supportAskNote', ask.email_note);
    setText('supportAskStatus', '');
    const kofi = $('supportAskKofi');
    if (kofi) {
      kofi.textContent = `${ask.action || 'Support on Ko-fi'} ↗`;
      const url = safeKofi(ask.kofi_url);
      if (url) kofi.href = url;
    }
    const goal = $('supportAskGoal');
    if (goal) {
      goal.hidden = !ask.goal;
      if (ask.goal) {
        const fill = $('supportAskFill');
        if (fill) fill.style.width = `${Math.max(4, meterWidth(ask.goal.percent))}%`;
        setText('supportAskGoalText', ask.goal.text);
      }
    }
    card.querySelectorAll('.support-ask__actions, .support-ask__foot').forEach(node => { node.hidden = false; });
    card.hidden = false;
    watchSeen(card);
  }

  // Counted as shown once at least half the card is on screen, so a note nobody saw doesn't use up the moment.
  function watchSeen(card) {
    if (state.observer) state.observer.disconnect();
    const key = state.ask && state.ask.key;
    if (!key || state.seen === key) return;
    const report = () => {
      if (state.seen === key || !state.ask || state.ask.key !== key) return;
      state.seen = key;
      send('POST', '/api/support-ask/seen', { key }).catch(() => { state.seen = ''; });
    };
    if (typeof IntersectionObserver !== 'function') {
      report();
      return;
    }
    state.observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.5 && !document.hidden)) {
        state.observer.disconnect();
        report();
      }
    }, { threshold: [0.5] });
    state.observer.observe(card);
  }

  async function answer(reply) {
    const ask = state.ask;
    if (!ask) return null;
    try {
      return await send('POST', '/api/support-ask/answer', { key: ask.key, answer: reply });
    } catch (error) {
      return null;  // the note is a nicety; never bother the member with an error about it
    }
  }

  function settle(card, message) {
    card.querySelectorAll('.support-ask__actions, .support-ask__foot').forEach(node => { node.hidden = true; });
    setText('supportAskStatus', message);
  }

  function bindCard() {
    const card = $('supportAsk');
    if (!card || card.dataset.bound) return;
    card.dataset.bound = '1';
    $('supportAskKofi')?.addEventListener('click', () => {
      answer('kofi');
      card.classList.add('is-thanked');
      setText('supportAskTitle', 'Thank you!');
      setText('supportAskBody', 'Ko-fi opened in a new tab. Use the same email there as here and your supporter perks switch on by themselves, usually within a minute.');
      settle(card, '');
      const goal = $('supportAskGoal');
      if (goal) goal.hidden = true;
    });
    $('supportAskPerks')?.addEventListener('click', () => { answer('perks'); });
    $('supportAskLater')?.addEventListener('click', () => {
      answer('later');
      card.hidden = true;
    });
    $('supportAskStop')?.addEventListener('click', async () => {
      settle(card, 'Okay, no more notes like this. You can turn them back on in Settings → Supporter.');
      const result = await answer('stop');
      if (result) syncSetting(result.asks_off);
    });
  }

  function syncSetting(off) {
    const box = $('supportAskOn');
    if (box) box.checked = !off;
  }

  function bindSetting() {
    const box = $('supportAskOn');
    if (!box || box.dataset.bound) return;
    box.dataset.bound = '1';
    box.addEventListener('change', async () => {
      const wanted = box.checked;
      box.disabled = true;
      try {
        const result = await send('PUT', '/api/support-ask/settings', { on: wanted });
        syncSetting(result.asks_off);
        if (typeof showNotice === 'function') {
          showNotice(result.asks_off ? 'Support notes are off.' : 'Support notes are on. You\'ll see one at most every two months.', 'success');
        }
        if (result.asks_off) render(null);
      } catch (error) {
        box.checked = !wanted;
        if (typeof showNotice === 'function') showNotice(error.message, 'error');
      } finally {
        box.disabled = false;
      }
    });
  }

  async function refreshSupportAsk() {
    const card = $('supportAsk');
    if (!card) return;
    bindCard();
    bindSetting();
    const request = ++state.request;
    try {
      const data = await send('GET', '/api/support-ask');
      if (request !== state.request) return;
      syncSetting(data.asks_off);
      render(data.ask);
    } catch (error) {
      // Optional card: the dashboard works without it.
    }
  }

  function resetSupportAsk() {
    state.request += 1;
    state.ask = null;
    state.seen = '';
    if (state.observer) state.observer.disconnect();
    const card = $('supportAsk');
    if (card) card.hidden = true;
  }

  if (typeof window !== 'undefined') {
    window.refreshSupportAsk = refreshSupportAsk;
    window.resetSupportAsk = resetSupportAsk;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { safeKofi, meterWidth };
  }
})();
