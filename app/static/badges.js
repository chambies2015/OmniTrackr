// Dashboard: the member's trophy case. Badges have three tiers and fill in from the library.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { request: 0, data: null, forced: false, busy: false, expanded: false };

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

  function hideKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_badges_hidden_${name}`;
  }

  function hidden() {
    try { return localStorage.getItem(hideKey()) === '1'; } catch (error) { return false; }
  }

  const TIER_CLASSES = ['locked', 'bronze', 'silver', 'gold'];

  function tierClass(tier) {
    return TIER_CLASSES[Math.max(0, Math.min(3, Number(tier) || 0))];
  }

  function summaryText(data) {
    if (!data) return '';
    if (!data.earned_levels) return `${data.badges.length} badges to earn, each with bronze, silver and gold. Your first ones are close.`;
    const gold = data.gold ? `, ${data.gold} gold` : '';
    return `${data.earned_levels} of ${data.total_levels} badge tiers earned across ${data.earned_badges} badge${data.earned_badges === 1 ? '' : 's'}${gold}.`;
  }

  function progressText(badge) {
    if (!badge.next_target) return `${badge.count} ${badge.counts} · gold`;
    return `${badge.count} of ${badge.next_target} ${badge.counts}`;
  }

  function celebrationText(data) {
    const fresh = (data.celebrate || []).map(key => byKey(data, key)).filter(Boolean);
    if (!fresh.length) return '';
    if (fresh.length === 1) return `New badge: ${fresh[0].name}, ${String(fresh[0].tier_name).toLowerCase()}!`;
    if (fresh.length > 3) return `You earned ${fresh.length} badges. Nicely done!`;
    const names = fresh.map(badge => `${badge.name} (${String(badge.tier_name).toLowerCase()})`);
    return `New badges: ${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}!`;
  }

  function byKey(data, key) {
    return (data.badges || []).find(badge => badge.key === key) || null;
  }

  function medal(badge, size) {
    const node = el('span', `badge-medal badge-medal--${tierClass(badge.tier)}${size ? ` badge-medal--${size}` : ''}`);
    node.appendChild(el('span', 'badge-medal__glyph', badge.emoji));
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  function pips(tier) {
    const row = el('span', 'badge-pips');
    row.setAttribute('aria-hidden', 'true');
    for (let index = 1; index <= 3; index += 1) {
      row.appendChild(el('span', `badge-pip${index <= tier ? ` badge-pip--${tierClass(index)}` : ''}`));
    }
    return row;
  }

  function bar(percent) {
    const track = el('span', 'badge-bar');
    const fill = el('span', 'badge-bar__fill');
    fill.style.width = `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
    track.appendChild(fill);
    track.setAttribute('aria-hidden', 'true');
    return track;
  }

  function nextItem(badge) {
    const item = el('li', 'badge-next');
    item.appendChild(medal(badge));
    const copy = el('div', 'badge-next__copy');
    const head = el('div', 'badge-next__head');
    head.append(el('strong', '', badge.name), el('span', 'badge-next__tier', `${badge.next_tier_name} next`));
    copy.append(head, bar(badge.percent));
    const foot = el('div', 'badge-next__foot');
    foot.append(el('span', '', progressText(badge)));
    if (badge.link) {
      const link = el('a', 'badge-next__hint', badge.hint);
      link.href = badge.link;
      foot.appendChild(link);
    } else {
      foot.appendChild(el('span', 'badge-next__hint', badge.hint));
    }
    copy.appendChild(foot);
    item.appendChild(copy);
    return item;
  }

  function gridItem(badge) {
    const item = el('li', `badge-tile badge-tile--${tierClass(badge.tier)}${badge.new ? ' badge-tile--new' : ''}`);
    item.appendChild(medal(badge, 'lg'));
    item.appendChild(el('strong', 'badge-tile__name', badge.name));
    item.appendChild(el('span', 'badge-tile__tier', badge.tier ? badge.tier_name : 'Not yet'));
    item.appendChild(pips(badge.tier));
    item.appendChild(el('span', 'badge-tile__count', progressText(badge)));
    if (badge.next_target) item.appendChild(bar(badge.percent));
    const label = badge.tier ? `${badge.name}, ${badge.tier_name}. ` : `${badge.name}, not earned yet. `;
    item.appendChild(el('span', 'visually-hidden', `${label}${badge.next_target ? badge.hint : 'Top tier reached'}.`));
    return item;
  }

  function renderCelebration(data) {
    const box = $('badgeCaseCelebration');
    if (!box) return;
    const text = celebrationText(data);
    box.replaceChildren();
    box.hidden = !text;
    if (!text) return;
    const medals = el('div', 'badge-case__celebration-medals');
    (data.celebrate || []).slice(0, 4).map(key => byKey(data, key)).filter(Boolean)
      .forEach(badge => medals.appendChild(medal(badge)));
    const copy = el('div', 'badge-case__celebration-copy');
    copy.append(el('strong', '', text), el('span', '', 'Badges fill in from your library, so they always match it.'));
    const seen = el('button', 'badge-case__link', 'Dismiss');
    seen.type = 'button';
    seen.dataset.badgeAction = 'seen';
    box.append(medals, copy, seen);
  }

  function render(data) {
    const section = $('badgeCase');
    if (!section || !data || !Array.isArray(data.badges)) return;
    state.data = data;
    const show = state.forced || !hidden() || (data.celebrate || []).length > 0;
    section.hidden = !show;
    if (!show) return;
    $('badgeCaseSummary').textContent = summaryText(data);
    const shelf = $('badgeCaseShelf');
    const earned = data.badges.filter(badge => badge.tier > 0).sort((a, b) => b.tier - a.tier);
    shelf.replaceChildren(...earned.slice(0, 8).map(badge => {
      const node = medal(badge, 'sm');
      node.title = `${badge.name} · ${badge.tier_name}`;
      return node;
    }));
    if (earned.length > 8) shelf.appendChild(el('span', 'badge-case__more', `+${earned.length - 8}`));
    shelf.hidden = earned.length === 0;
    renderCelebration(data);
    const next = (data.next || []).map(key => byKey(data, key)).filter(Boolean);
    $('badgeCaseNextTitle').hidden = next.length === 0;
    $('badgeCaseNext').replaceChildren(...next.map(nextItem));
    const grid = $('badgeCaseGrid');
    grid.replaceChildren(...data.badges.map(gridItem));
    grid.hidden = !state.expanded;
    const toggle = $('badgeCaseToggle');
    toggle.textContent = state.expanded ? 'Show less' : `See all ${data.badges.length} badges`;
    toggle.setAttribute('aria-expanded', String(state.expanded));
  }

  async function refreshBadges() {
    if (!$('badgeCase')) return;
    const request = ++state.request;
    try {
      const response = await fetch(`${apiBase()}/api/badges`, fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      render(data);
      openFromHash();
    } catch (error) {
      // Badges are optional; the dashboard works without them.
    }
  }

  function resetBadges() {
    state.request += 1;
    state.data = null;
    state.forced = false;
    state.expanded = false;
    const section = $('badgeCase');
    if (section) section.hidden = true;
  }

  async function markSeen() {
    if (state.busy || !state.data) return;
    state.busy = true;
    try {
      const response = await fetch(`${apiBase()}/api/badges/seen`, fetchOptions({ method: 'POST', headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.data.celebrate = [];
      state.data.badges.forEach(badge => { badge.new = false; });
      render(state.data);
    } catch (error) {
      // Leave the celebration up; it can be dismissed again.
    } finally {
      state.busy = false;
    }
  }

  function handleClick(event) {
    const target = event.target.closest && event.target.closest('#badgeCase [data-badge-action]');
    if (!target || !state.data) return;
    const action = target.dataset.badgeAction;
    if (action === 'toggle') {
      state.expanded = !state.expanded;
      render(state.data);
    } else if (action === 'hide') {
      try { localStorage.setItem(hideKey(), '1'); } catch (error) { /* session only */ }
      state.forced = false;
      render(state.data);
    } else if (action === 'seen') {
      markSeen();
    }
  }

  function openFromHash() {
    if (window.location.hash !== '#badges' || !state.data) return;
    state.forced = true;
    state.expanded = true;
    try { localStorage.removeItem(hideKey()); } catch (error) { /* fine */ }
    render(state.data);
    const section = $('badgeCase');
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
    window.refreshBadges = refreshBadges;
    window.resetBadges = resetBadges;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { summaryText, progressText, celebrationText, tierClass, hideKey };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
