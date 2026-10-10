// Dashboard: yearly goals ("Read 24 books in 2027") with progress rings.
// Everything is built with DOM APIs; server text is only ever set as textContent.
(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const RING_RADIUS = 20;
  const RING_LENGTH = 2 * Math.PI * RING_RADIUS;
  const state = { request: 0, year: null, data: null, editing: null, forced: false, busy: false };

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

  function dismissKey() {
    let name = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) name = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_goals_prompt_hidden_${name}`;
  }

  function promptDismissed() {
    try { return localStorage.getItem(dismissKey()) === '1'; } catch (error) { return false; }
  }

  function paceText(goal) {
    const pace = goal.pace || {};
    if (pace.status === 'done') return 'Goal reached';
    if (pace.status === 'ahead') return `${pace.difference} ahead of pace`;
    if (pace.status === 'behind') return `${pace.difference} behind pace`;
    if (pace.status === 'on_track') return 'On pace';
    if (pace.status === 'not_started') return 'Starts January 1';
    return '';
  }

  function ringOffset(percent) {
    const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
    return RING_LENGTH * (1 - clamped / 100);
  }

  function ring(goal) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 48 48');
    svg.setAttribute('class', 'year-goal__ring');
    svg.setAttribute('aria-hidden', 'true');
    const track = document.createElementNS(SVG_NS, 'circle');
    const fill = document.createElementNS(SVG_NS, 'circle');
    [track, fill].forEach(circle => {
      circle.setAttribute('cx', '24');
      circle.setAttribute('cy', '24');
      circle.setAttribute('r', String(RING_RADIUS));
    });
    track.setAttribute('class', 'year-goal__ring-track');
    fill.setAttribute('class', 'year-goal__ring-fill');
    fill.setAttribute('stroke-dasharray', RING_LENGTH.toFixed(2));
    fill.setAttribute('stroke-dashoffset', ringOffset(goal.percent).toFixed(2));
    const label = document.createElementNS(SVG_NS, 'text');
    label.setAttribute('x', '24');
    label.setAttribute('y', '28');
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('class', 'year-goal__ring-label');
    label.textContent = `${Math.max(0, Math.min(100, Number(goal.percent) || 0))}%`;
    svg.append(track, fill, label);
    return svg;
  }

  function openCategories(data, editing) {
    const taken = new Set((data.goals || []).map(goal => goal.category));
    return (data.categories || []).filter(category => category.key === editing || !taken.has(category.key));
  }

  function goalItem(goal) {
    const item = el('li', `year-goal year-goal--${goal.pace?.status || 'on_track'}`);
    const copy = el('div', 'year-goal__copy');
    copy.append(el('strong', 'year-goal__count', `${goal.done} of ${goal.target} ${goal.noun}`),
      el('span', 'year-goal__pace', paceText(goal)));
    const actions = el('div', 'year-goal__actions');
    const edit = el('button', 'year-goal__edit', 'Edit');
    edit.type = 'button';
    edit.dataset.goalAction = 'edit';
    edit.dataset.goalCategory = goal.category;
    edit.setAttribute('aria-label', `Edit your ${goal.noun} goal`);
    const remove = el('button', 'year-goal__remove', 'Remove');
    remove.type = 'button';
    remove.dataset.goalAction = 'remove';
    remove.dataset.goalCategory = goal.category;
    remove.setAttribute('aria-label', `Remove your ${goal.noun} goal`);
    actions.append(edit, remove);
    item.append(ring(goal), copy, actions);
    return item;
  }

  function goalForm(data) {
    const editing = state.editing === true ? null : state.editing;
    const current = (data.goals || []).find(goal => goal.category === editing);
    const form = el('form', 'year-goals__form');
    form.id = 'yearGoalsForm';
    const label = el('label', 'year-goals__field');
    label.append(el('span', '', 'Finish'));
    const target = el('input');
    target.type = 'number';
    target.name = 'target';
    target.min = '1';
    target.max = String(data.max_target || 1000);
    target.required = true;
    target.inputMode = 'numeric';
    target.value = current ? String(current.target) : '12';
    target.setAttribute('aria-label', 'How many to finish');
    label.appendChild(target);
    const select = el('select');
    select.name = 'category';
    select.setAttribute('aria-label', 'What to finish');
    openCategories(data, editing).forEach(category => {
      const option = el('option', '', category.key === 'all' ? 'titles (any kind)' : category.noun);
      option.value = category.key;
      option.selected = category.key === editing;
      select.appendChild(option);
    });
    select.disabled = Boolean(editing);
    label.append(select, el('span', '', `in ${data.year}`));
    const save = el('button', 'action-btn year-goals__save', current ? 'Save goal' : 'Set goal');
    save.type = 'submit';
    const cancel = el('button', 'year-goals__cancel', 'Cancel');
    cancel.type = 'button';
    cancel.dataset.goalAction = 'cancel';
    form.append(label, save, cancel);
    return form;
  }

  function render(data) {
    const section = $('yearGoals');
    if (!section) return;
    state.data = data;
    const goals = data.goals || [];
    const show = goals.length > 0 || state.forced || state.editing !== null || !promptDismissed();
    section.hidden = !show;
    if (!show) return;
    $('yearGoalsTitle').textContent = `Your ${data.year} goals`;
    const reached = goals.filter(goal => goal.pace?.status === 'done').length;
    $('yearGoalsSummary').textContent = goals.length
      ? `${reached} of ${goals.length} reached. Progress counts titles you mark finished this year.`
      : `Pick a number to finish this year, like 12 books or 30 movies. Goals stay private unless you share your Year in Review.`;
    const years = $('yearGoalsYears');
    years.replaceChildren();
    const month = new Date().getMonth();
    const offerNext = month >= 10;
    (data.years || []).filter((year, index) => index === 0 || offerNext || year === data.year).forEach(year => {
      const chip = el('button', 'year-goals__year', String(year));
      chip.type = 'button';
      chip.dataset.goalYear = String(year);
      chip.setAttribute('aria-pressed', String(year === data.year));
      years.appendChild(chip);
    });
    years.hidden = years.childElementCount < 2;
    const list = $('yearGoalsList');
    list.replaceChildren(...goals.map(goalItem));
    list.hidden = !goals.length;
    const formSlot = $('yearGoalsFormSlot');
    formSlot.replaceChildren();
    if (state.editing !== null) formSlot.appendChild(goalForm(data));
    const canAdd = openCategories(data, null).length > 0;
    $('yearGoalsAdd').hidden = state.editing !== null || !canAdd;
    $('yearGoalsAdd').textContent = goals.length ? 'Add a goal' : 'Set a goal';
    $('yearGoalsDismiss').hidden = goals.length > 0 || state.editing !== null;
  }

  function status(text) {
    const node = $('yearGoalsStatus');
    if (node) node.textContent = text || '';
  }

  async function refreshYearGoals() {
    const section = $('yearGoals');
    if (!section) return;
    const request = ++state.request;
    const year = state.year || new Date().getFullYear();
    try {
      const response = await fetch(`${apiBase()}/api/goals?year=${encodeURIComponent(year)}`, fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      state.year = data.year;
      // A background refresh never redraws an open form, so typing is never lost.
      if (state.editing !== null && state.data && state.data.year === data.year) return;
      render(data);
      openFromHash();
    } catch (error) {
      // Goals are optional; the dashboard works without them.
    }
  }

  function resetYearGoals() {
    state.request += 1;
    state.year = null;
    state.data = null;
    state.editing = null;
    state.forced = false;
    const section = $('yearGoals');
    if (section) section.hidden = true;
  }

  async function send(method, category, body) {
    if (state.busy) return;
    state.busy = true;
    status('');
    try {
      const response = await fetch(`${apiBase()}/api/goals/${encodeURIComponent(state.year)}/${encodeURIComponent(category)}`, fetchOptions({
        method,
        headers: body ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not save your goal.');
      state.editing = null;
      render(data);
      status(method === 'DELETE' ? 'Goal removed.' : 'Goal saved.');
    } catch (error) {
      status(error.message || 'Could not save your goal.');
    } finally {
      state.busy = false;
    }
  }

  function handleClick(event) {
    const target = event.target.closest && event.target.closest('#yearGoals [data-goal-action], #yearGoals [data-goal-year], #yearGoalsAdd, #yearGoalsDismiss');
    if (!target || !state.data) return;
    if (target.id === 'yearGoalsAdd') {
      state.editing = true;
      render(state.data);
      $('yearGoalsForm')?.querySelector('input')?.focus();
      return;
    }
    if (target.id === 'yearGoalsDismiss') {
      try { localStorage.setItem(dismissKey(), '1'); } catch (error) { /* session only */ }
      state.forced = false;
      render(state.data);
      return;
    }
    if (target.dataset.goalYear) {
      const year = Number(target.dataset.goalYear);
      if (year !== state.year) {
        state.year = year;
        state.editing = null;
        refreshYearGoals();
      }
      return;
    }
    const action = target.dataset.goalAction;
    if (action === 'edit') {
      state.editing = target.dataset.goalCategory;
      render(state.data);
      $('yearGoalsForm')?.querySelector('input')?.focus();
    } else if (action === 'remove') {
      send('DELETE', target.dataset.goalCategory);
    } else if (action === 'cancel') {
      state.editing = null;
      render(state.data);
    }
  }

  function handleSubmit(event) {
    if (!event.target || event.target.id !== 'yearGoalsForm') return;
    event.preventDefault();
    const form = event.target;
    const target = Number.parseInt(form.elements.target.value, 10);
    if (!Number.isInteger(target) || target < 1) {
      status('Pick a number from 1 up.');
      return;
    }
    send('PUT', form.elements.category.value, { target });
  }

  function openFromHash() {
    if (window.location.hash !== '#goals' || !state.data) return;
    state.forced = true;
    render(state.data);
    const section = $('yearGoals');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  function init() {
    document.addEventListener('click', handleClick);
    document.addEventListener('submit', handleSubmit);
    window.addEventListener('hashchange', openFromHash);
  }

  if (typeof window !== 'undefined') {
    window.refreshYearGoals = refreshYearGoals;
    window.resetYearGoals = resetYearGoals;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { paceText, ringOffset, openCategories, RING_LENGTH };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
