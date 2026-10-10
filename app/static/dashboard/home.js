let collectionsCache = [];
let collectionLoadSequence = 0;
let collectionPickerTarget = null;

function consumeLibraryNavigationTarget() {
  const url = new URL(window.location.href);
  const categories = url.searchParams.getAll('library_category');
  const ids = url.searchParams.getAll('library_item');
  if (!categories.length && !ids.length) return null;
  url.searchParams.delete('library_category');
  url.searchParams.delete('library_item');
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  if (categories.length !== 1 || ids.length !== 1) return null;
  if (!LIBRARY_SEARCH_SOURCES.some(source => source.tab === categories[0])) return null;
  const id = Number(ids[0]);
  if (!Number.isInteger(id) || id < 1 || id > 2147483647 || String(id) !== ids[0]) return null;
  return { category: categories[0], id };
}

async function openLibraryItemFromLocation() {
  const status = document.getElementById('libraryNavigationStatus');
  if (!status || !hasStoredAuth()) return false;
  const params = new URL(window.location.href).searchParams;
  if (!params.has('library_category') && !params.has('library_item')) return false;
  const target = consumeLibraryNavigationTarget();
  status.hidden = false;
  if (!target) {
    status.textContent = 'This library link is invalid. Find the title using your library search.';
    return false;
  }
  if (editingRowId !== null) {
    status.textContent = 'Save or cancel your current edit before opening another title.';
    return false;
  }
  let interrupted = false;
  const stopAutoFocus = () => { interrupted = true; };
  const events = ['pointerdown', 'keydown', 'wheel', 'touchstart', 'popstate', 'hashchange'];
  for (const event of events) {
    (event === 'popstate' || event === 'hashchange' ? window : document).addEventListener(event, stopAutoFocus, true);
  }
  const canContinue = () => !interrupted && hasStoredAuth() && editingRowId === null;
  try {
    status.textContent = 'Opening your saved title…';
    // Honor category visibility before resolving the owner's title.
    await dashboardTabVisibilityReady;
    if (!canContinue()) return false;
    if (getTabButton(target.category)?.style.display === 'none') {
      status.textContent = 'Enable this media category in your settings to open this title.';
      return false;
    }
    const startingTab = currentTab;
    const response = await authenticatedFetch(`${API_BASE}/library/item/${target.category}/${target.id}`);
    if (currentTab !== startingTab) interrupted = true;
    if (!canContinue()) return false;
    if (!response.ok) {
      status.textContent = response.status === 404
        ? 'That title is unavailable in this account. It may have been removed.'
        : 'Could not open this title. Try finding it using your library search.';
      return false;
    }
    // The owner-scoped response supplies the title; never trust a title from the URL.
    const item = await response.json();
    if (currentTab !== startingTab) interrupted = true;
    if (!canContinue()) return false;
    if (item?.id !== target.id || typeof item.title !== 'string' || !item.title.trim()) {
      status.textContent = 'That title is unavailable in this account.';
      return false;
    }
    const opened = await openLibraryItem({ ...target, title: item.title }, {
      button: null, reasonElement: status, shouldContinue: (expectedTab = currentTab) => {
        if (currentTab !== expectedTab) interrupted = true;
        return canContinue();
      },
      focusReady: dashboardStartupLayoutReady,
    });
    if (opened) status.textContent = `Opened “${item.title}” in your library.`;
    return opened;
  } catch (error) {
    if (canContinue()) status.textContent = 'Could not open this title. Try finding it using your library search.';
    return false;
  } finally {
    if (!canContinue()) {
      status.hidden = true;
      status.textContent = '';
    }
    for (const event of events) {
      (event === 'popstate' || event === 'hashchange' ? window : document).removeEventListener(event, stopAutoFocus, true);
    }
  }
}

function openDashboardTargetFromLocation() {
  if (!hasStoredAuth()) return false;
  const params = new URL(window.location.href).searchParams;
  if (params.has('library_category') || params.has('library_item')) {
    // Ambiguous mixed handoffs must never race each other or choose a different title.
    if (params.has('collection')) {
      consumeCollectionNavigationTarget();
      consumeLibraryNavigationTarget();
      const status = document.getElementById('libraryNavigationStatus');
      if (status) {
        status.hidden = false;
        status.textContent = 'This library link has conflicting destinations. Find the title using your library search.';
      }
      return false;
    }
    return openLibraryItemFromLocation();
  }
  return openCollectionFromLocation();
}

function consumeCollectionNavigationTarget() {
  const url = new URL(window.location.href);
  const values = url.searchParams.getAll('collection');
  if (!values.length) return null;
  url.searchParams.delete('collection');
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  // Collection IDs use positive PostgreSQL integers. Reject ambiguous or coerced values.
  if (values.length !== 1 || !/^[1-9]\d{0,9}$/.test(values[0])) return null;
  const id = Number(values[0]);
  return id <= 2147483647 ? id : null;
}

async function openCollectionFromLocation() {
  const container = document.getElementById('collectionsList');
  if (!container || !hasStoredAuth()) return false;
  const collectionId = consumeCollectionNavigationTarget();
  if (collectionId === null) return false;

  let interrupted = false;
  const stopAutoFocus = () => { interrupted = true; };
  document.addEventListener('pointerdown', stopAutoFocus, true);
  document.addEventListener('keydown', stopAutoFocus, true);
  document.addEventListener('wheel', stopAutoFocus, true);
  document.addEventListener('touchstart', stopAutoFocus, true);
  try {
    container.textContent = 'Opening your saved collection…';
    const collections = await switchTab('collections');
    if (interrupted || currentTab !== 'collections' || !hasStoredAuth()) return false;
    // Initial guidance above the tabs can finish after the collection request.
    // Wait for those existing renders before scrolling once to the saved card.
    await dashboardStartupLayoutReady;
    // A late response must not pull someone away from their next action.
    if (interrupted || currentTab !== 'collections' || !hasStoredAuth()) return false;
    if (!Array.isArray(collections)) {
      container.tabIndex = -1;
      container.focus({ preventScroll: true });
      container.scrollIntoView({ block: 'start', behavior: 'auto' });
      return false;
    }
    // Only the authenticated owner's collection list can resolve this target.
    const collection = collections.find(item => item.id === collectionId);
    const card = collection && document.getElementById(`collection-${collectionId}`);
    if (!card) {
      const message = document.createElement('p');
      message.className = 'collections-empty';
      message.setAttribute('role', 'status');
      message.textContent = 'That collection is unavailable in this account.';
      container.prepend(message);
      message.tabIndex = -1;
      message.focus({ preventScroll: true });
      message.scrollIntoView({ block: 'start', behavior: 'auto' });
      return false;
    }
    card.tabIndex = -1;
    card.focus({ preventScroll: true });
    card.scrollIntoView({ block: 'start', behavior: 'auto' });
    return true;
  } finally {
    document.removeEventListener('pointerdown', stopAutoFocus, true);
    document.removeEventListener('keydown', stopAutoFocus, true);
    document.removeEventListener('wheel', stopAutoFocus, true);
    document.removeEventListener('touchstart', stopAutoFocus, true);
  }
}

// @lazy-chunk lazy/collections.js
// The owner-only Site stats link appears only when the server says this account is an admin.
let siteStatsAccessRequest = null;
window.resetSiteStatsLink = function () {
  siteStatsAccessRequest = null;
  const link = document.getElementById('siteStatsLink');
  if (link) link.hidden = true;
};
window.refreshSiteStatsLink = function () {
  const link = document.getElementById('siteStatsLink');
  if (!link || siteStatsAccessRequest) return siteStatsAccessRequest;
  siteStatsAccessRequest = fetch(`${API_BASE}/api/site-stats/access`, authFetchOptions())
    .then(response => (response.ok ? response.json() : { admin: false }))
    .then(result => { link.hidden = !result?.admin; })
    .catch(() => { link.hidden = true; });
  return siteStatsAccessRequest;
};

// @lazy-chunk lazy/collection-studio.js
// First-library guidance
// ============================================================================

const LAUNCHPAD_DISMISS_KEY = 'omnitrackr_library_launchpad_dismissed';
let demoStartGuidance = false;
let launchpadRefreshTimer = null;
let todaysPickOffset = 0;
let todaysPickCandidateCount = 0;
let todaysPickRequest = 0;
let todaysPickSelection = null;
let returnDeckActive = false;
let returnDeckPending = false;
let returnDeckBootstrapComplete = false;
let returnDeckEngagementToken = null;
let returnDeckItems = [];
let decisionCardsRefreshPromise = null;
let launchpadDecisionRefreshRequested = false;
let initialMovieLibraryLoad = true;

function captureDemoStartGuidance() {
  const params = new URLSearchParams(window.location.search);
  if (!params.has('start')) return;
  const values = params.getAll('start');
  demoStartGuidance = window.location.pathname === '/' && values.length === 1 && values[0] === 'demo'
    && !['next', 'collection', 'library_category', 'library_item', 'token', 'reset_token',
      'email_verified', 'password_reset', 'email_change_token', 'email_change'].some(key => params.has(key));
  params.delete('start');
  const query = params.toString();
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
}

function getReturnPromptContext() {
  try {
    const context = JSON.parse(sessionStorage.getItem('omnitrackr_return_prompt') || 'null');
    const daysAway = Number(context?.days_away);
    const createdAt = Number(context?.created_at);
    const engagementToken = context?.engagement_token;
    if (
      !context
      || !Number.isFinite(daysAway)
      || daysAway < 3
      || daysAway > 90
      || !Number.isFinite(createdAt)
      || createdAt > Date.now() + 60000
      || Date.now() - createdAt > 86400000
      || typeof engagementToken !== 'string'
      || engagementToken.length < 32
      || engagementToken.length > 512
    ) {
      sessionStorage.removeItem('omnitrackr_return_prompt');
      return null;
    }
    return context;
  } catch (error) {
    try {
      sessionStorage.removeItem('omnitrackr_return_prompt');
    } catch (storageError) {
      // The optional prompt remains disabled when storage is unavailable.
    }
    return null;
  }
}

function saveReturnPromptContext(context) {
  try {
    sessionStorage.setItem('omnitrackr_return_prompt', JSON.stringify(context));
  } catch (error) {
    // The deck can still be used without session storage.
  }
}

function clearReturnPromptContext() {
  try {
    sessionStorage.removeItem('omnitrackr_return_prompt');
  } catch (error) {
    // Nothing else is required to dismiss an optional prompt.
  }
}

async function recordReturnDeckEngagement(action, engagementToken = returnDeckEngagementToken) {
  if (!engagementToken) return false;
  try {
    const response = await authenticatedFetch(`${API_BASE}/statistics/return-deck/engagement`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, engagement_token: engagementToken }),
    });
    return response.ok;
  } catch (error) {
    // Anonymous product-health totals must never interrupt the dashboard.
    return false;
  }
}

function makeReturnDeckItem(item, label, detail, primary = false) {
  const index = returnDeckItems.push(item) - 1;
  const card = document.createElement('article');
  card.className = `return-deck__item${primary ? ' return-deck__item--primary' : ''}`;
  const eyebrow = document.createElement('span');
  eyebrow.className = 'return-deck__item-label';
  eyebrow.textContent = label;
  const title = document.createElement('strong');
  title.textContent = item.title;
  const meta = document.createElement('span');
  meta.className = 'return-deck__item-meta';
  meta.textContent = `${item.category_label} · ${detail}`;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'return-deck__open';
  button.dataset.action = 'open-return-deck-item';
  button.dataset.returnDeckIndex = String(index);
  button.textContent = label === 'Add context' ? 'Open item' : 'Open it';
  card.append(eyebrow, title, meta, button);
  if (typeof window !== 'undefined' && window.OmniProgress) {
    window.OmniProgress.appendSummary(card, item);
    window.OmniProgress.appendAction(card, item);
  }
  return card;
}

// "Out now": Release Radar titles tied to the member's library that came out while they were away.
function renderReturnDeckReleased(items) {
  const box = document.getElementById('returnDeckReleased');
  if (!box) return;
  box.replaceChildren();
  const safe = (Array.isArray(items) ? items : []).filter(item => item && typeof item.url === 'string' && item.url.startsWith('/release-radar'));
  box.hidden = safe.length === 0;
  if (!safe.length) return;
  const heading = document.createElement('p');
  heading.className = 'return-deck__released-title';
  heading.textContent = 'Out now from your library';
  const list = document.createElement('ul');
  safe.slice(0, 3).forEach(item => {
    const row = document.createElement('li');
    const link = document.createElement('a');
    link.href = item.url;
    link.textContent = item.title;
    const meta = document.createElement('span');
    meta.textContent = [item.label, item.reason].filter(Boolean).join(' · ');
    row.append(link, meta);
    list.appendChild(row);
  });
  box.append(heading, list);
}

function renderReturnDeck(payload, context) {
  const deck = document.getElementById('returnDeck');
  const actions = document.getElementById('returnDeckActions');
  const recapElement = document.getElementById('returnDeckRecap');
  if (!deck || !actions || !payload?.eligible) return false;

  returnDeckItems = [];
  actions.replaceChildren();
  if (payload.primary) {
    actions.appendChild(makeReturnDeckItem(payload.primary, 'Start here', payload.primary.reason, true));
  }
  if (payload.alternative) {
    actions.appendChild(makeReturnDeckItem(payload.alternative, 'Another option', payload.alternative.status_label));
  }
  if (payload.reflection) {
    const prompts = Array.isArray(payload.reflection.prompts) ? payload.reflection.prompts.join(' · ') : 'Add a personal note';
    actions.appendChild(makeReturnDeckItem(payload.reflection, 'Add context', prompts));
  }

  renderReturnDeckReleased(payload.released_while_away);
  const days = Number(payload.days_away) || Number(context.days_away);
  document.getElementById('returnDeckSummary').textContent =
    `It has been ${days} or more days since your previous visit. Here are a few useful ways back in—nothing new to manage.`;
  const recap = payload.recap || {};
  const recapParts = [];
  if (recap.entry_count) recapParts.push(`${recap.entry_count} journal moment${recap.entry_count === 1 ? '' : 's'}`);
  if (recap.completed_count) recapParts.push(`${recap.completed_count} finished`);
  if (recap.reflection_count) recapParts.push(`${recap.reflection_count} with a reflection`);
  if (recap.top_category_label) recapParts.push(`${recap.top_category_label} was most active`);
  recapElement.textContent = recapParts.length
    ? `Since your previous visit: ${recapParts.join(' · ')}.`
    : 'Your private library is ready when you are; no activity or streak is required.';

  returnDeckActive = true;
  returnDeckEngagementToken = context.engagement_token;
  document.getElementById('todaysPick')?.setAttribute('hidden', '');
  document.getElementById('libraryPulse')?.setAttribute('hidden', '');
  deck.removeAttribute('hidden');
  if (!context.shown) {
    context.shown = true;
    saveReturnPromptContext(context);
    recordReturnDeckEngagement('shown', context.engagement_token);
  }
  return true;
}

async function refreshReturnDeck() {
  const context = getReturnPromptContext();
  if (!context || !hasStoredAuth()) return false;
  returnDeckPending = true;
  try {
    const params = new URLSearchParams({
      days_away: String(context.days_away),
    });
    const response = await authenticatedFetch(`${API_BASE}/statistics/return-deck/?${params}`, {
      headers: { 'X-Return-Prompt': context.engagement_token },
    });
    if (!response.ok) throw new Error('Could not load return deck');
    const rendered = renderReturnDeck(await response.json(), context);
    if (!rendered) clearReturnPromptContext();
    return rendered;
  } catch (error) {
    // The established dashboard remains available if this optional layer fails.
    clearReturnPromptContext();
    return false;
  } finally {
    returnDeckPending = false;
  }
}

async function refreshDashboardDecisionCards() {
  if (!returnDeckBootstrapComplete || returnDeckActive || returnDeckPending) return false;
  if (decisionCardsRefreshPromise) return decisionCardsRefreshPromise;
  decisionCardsRefreshPromise = Promise.all([
    refreshLibraryPulse(),
    refreshTodaysPick(),
  ]).then(() => true).finally(() => {
    decisionCardsRefreshPromise = null;
  });
  return decisionCardsRefreshPromise;
}

async function bootstrapReturnDeck() {
  try {
    return await refreshReturnDeck();
  } finally {
    returnDeckBootstrapComplete = true;
    scheduleLibraryLaunchpadRefresh(true);
  }
}

function resolveReturnDeck(action) {
  if (!returnDeckActive || !returnDeckEngagementToken) return;
  const engagementToken = returnDeckEngagementToken;
  returnDeckEngagementToken = null;
  returnDeckActive = false;
  recordReturnDeckEngagement(action, engagementToken);
  clearReturnPromptContext();
  returnDeckItems = [];
  document.getElementById('returnDeck')?.setAttribute('hidden', '');
  scheduleLibraryLaunchpadRefresh(true);
}

function dismissReturnDeck() {
  resolveReturnDeck('dismissed');
}

async function openReturnDeckItem(index) {
  const item = returnDeckItems[index];
  if (!item) return;
  const button = document.querySelector(`[data-action="open-return-deck-item"][data-return-deck-index="${index}"]`);
  const opened = await openLibraryItem(item, {
    button,
    reasonElement: document.getElementById('returnDeckSummary'),
  });
  if (opened) resolveReturnDeck('opened');
}

function isLibraryLaunchpadDismissed() {
  try {
    return localStorage.getItem(LAUNCHPAD_DISMISS_KEY) === 'true';
  } catch (error) {
    return false;
  }
}

function dismissLibraryLaunchpad() {
  try {
    localStorage.setItem(LAUNCHPAD_DISMISS_KEY, 'true');
  } catch (error) {
    // The launchpad remains functional when browser storage is unavailable.
  }
  document.getElementById('libraryLaunchpad')?.setAttribute('hidden', '');
}

function openLaunchpadQuickCapture(category) {
  if (QUICK_CAPTURE_CATEGORIES[category]) selectQuickCaptureCategory(category);
  openQuickCapture();
}

function openLaunchpadAddItem(category = 'movies') {
  const destinations = {
    movies: { form: 'movieForm', input: 'movieTitle' },
    'tv-shows': { form: 'tvForm', input: 'tvTitle' },
    anime: { form: 'animeForm', input: 'animeTitle' },
    'video-games': { form: 'videoGameForm', input: 'videoGameTitle' },
    music: { form: 'musicForm', input: 'musicTitle' },
    books: { form: 'bookForm', input: 'bookTitle' },
  };
  const destination = destinations[category] || destinations.movies;
  switchTab(category in destinations ? category : 'movies');
  const formContent = document.getElementById(`${destination.form}Content`);
  if (formContent && (formContent.hidden || !formContent.classList.contains('expanded'))) {
    toggleCollapsible(destination.form);
  }
  window.setTimeout(() => document.getElementById(destination.input)?.focus(), 0);
}

function openLaunchpadInsights() {
  switchTab('statistics');
  const insights = document.getElementById('libraryInsightsStatsContent');
  if (insights && !isElementShown(insights)) {
    toggleCategoryAccordion('library-insights');
  }
}

function openLaunchpadImport() {
  // Reuse the existing preview-first importer; opening it performs no import.
  window.openAccountModal();
  document.getElementById('importStudio')?.scrollIntoView({ block: 'start' });
  document.getElementById('importStudioSource')?.focus({ preventScroll: true });
}

function renderLibraryLaunchpad(insights, firstWeek = null) {
  const launchpad = document.getElementById('libraryLaunchpad');
  const summary = document.getElementById('libraryLaunchpadSummary');
  const steps = document.getElementById('libraryLaunchpadSteps');
  const categories = document.getElementById('libraryLaunchpadCategories');
  if (!launchpad || !summary || !steps || !categories) return;
  if (isLibraryLaunchpadDismissed()) {
    launchpad.hidden = true;
    return;
  }

  const total = Number(insights?.total_items || 0);
  const rated = Number(insights?.rated_items || 0);
  const reviewed = Number(insights?.reviewed_items || 0);
  const completed = Number(insights?.completed_items || 0);
  if (total > 0) demoStartGuidance = false;
  const libraryDone = total > 0 && rated > 0 && reviewed > 0;
  // New members also get a few social steps once they have a title saved.
  const socialSteps = total > 0 ? firstWeekSteps(firstWeek) : [];
  // Let the existing dashboard take over when these introductory steps are done.
  if (libraryDone && socialSteps.every((step) => step.complete)) {
    launchpad.hidden = true;
    return;
  }
  const starterPaths = document.getElementById('libraryLaunchpadStarterPaths');
  const insightsAction = document.getElementById('libraryLaunchpadInsights');
  if (starterPaths) starterPaths.hidden = total > 0;
  if (insightsAction) insightsAction.hidden = total === 0;
  const launchpadSteps = [
    { complete: total > 0, label: total ? `${total} item${total === 1 ? '' : 's'} saved` : 'Save your first title' },
    { complete: rated > 0, label: rated ? `${rated} item${rated === 1 ? '' : 's'} rated` : 'Give one item a rating' },
    { complete: reviewed > 0, label: reviewed ? `${reviewed} note${reviewed === 1 ? '' : 's'} written` : 'Leave a note for future you' },
  ];

  if (libraryDone) {
    summary.textContent = 'Your library is set up. OmniTrackr gets better with people in it: add a friend, share a review, and let the weekly email tell you what\'s coming.';
  } else if (!total) {
    summary.textContent = demoStartGuidance
      ? 'Make it yours: use Add Anything to search for your first real title. Your demo practice stays separate from this private library.'
      : 'Start with one title you love, bring an existing list, or browse Discover for an idea. You only need one title to begin.';
  } else if (total === 1) {
    summary.textContent = 'Your first title is saved. Add a rating or private note using Edit in your library, or use Next up to put it on your shortlist.';
  } else if (completed) {
    summary.textContent = `${completed} finished so far. Add a rating or note when you want your library to tell a clearer story.`;
  } else {
    summary.textContent = 'Your library is taking shape. Mark progress, add a rating, or leave a note when a detail is worth remembering.';
  }

  categories.replaceChildren();
  categories.hidden = total > 0;
  if (!total) {
    const choices = [
      ['movies', 'a movie'], ['tv-shows', 'a TV show'], ['anime', 'an anime'],
      ['video-games', 'a game'], ['music', 'an album'], ['books', 'a book'],
    ];
    choices.forEach(([category, label]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'library-launchpad__category';
      button.dataset.action = 'launchpad-choose-category';
      button.dataset.launchpadCategory = category;
      button.textContent = `Add ${label}`;
      categories.appendChild(button);
    });
  }

  steps.replaceChildren();
  launchpadSteps.concat(socialSteps).forEach((step) => {
    const item = document.createElement('div');
    item.className = `library-launchpad__step${step.complete ? ' is-complete' : ''}`;
    const icon = document.createElement('span');
    icon.className = 'library-launchpad__step-icon';
    icon.textContent = step.complete ? '✓' : '○';
    const label = document.createElement('span');
    label.textContent = step.label;
    item.append(icon, label);
    const action = step.complete ? null : launchpadStepAction(step.action);
    if (action) item.appendChild(action);
    steps.appendChild(item);
  });
  launchpad.removeAttribute('hidden');
}

// Social steps for members in their first weeks (from /api/for-you/first-week).
function firstWeekSteps(firstWeek) {
  if (!firstWeek?.show) return [];
  const steps = [{
    complete: Boolean(firstWeek.friend),
    label: firstWeek.friend ? 'Friend added' : 'Add a friend to see what they track',
    action: { kind: 'button', text: 'Add a friend', dataset: { action: 'launchpad-add-friend' } },
  }];
  const target = firstWeek.review_target;
  steps.push({
    complete: Boolean(firstWeek.public_review),
    label: firstWeek.public_review ? 'Public review shared'
      : target ? `Share a public review of ${target.title}` : 'Share a public review from any title page',
    action: target && typeof target.path === 'string' && target.path.startsWith('/titles/')
      ? { kind: 'link', text: 'Write it', href: `${target.path}#write-review` } : null,
  });
  if (firstWeek.email_available) {
    const verified = Boolean(firstWeek.verified);
    steps.push({
      complete: Boolean(firstWeek.weekly_email),
      label: firstWeek.weekly_email ? 'Weekly email on'
        : verified ? 'Get a weekly email when something you track comes out' : 'Verify your email to get the weekly release email',
      action: verified ? { kind: 'button', text: 'Turn on', dataset: { action: 'launchpad-weekly-email' } } : null,
    });
  }
  return steps;
}

function launchpadStepAction(action) {
  if (!action) return null;
  const element = document.createElement(action.kind === 'link' ? 'a' : 'button');
  element.className = 'library-launchpad__step-action';
  element.textContent = action.text;
  if (action.kind === 'link') element.href = action.href;
  else {
    element.type = 'button';
    Object.assign(element.dataset, action.dataset);
  }
  return element;
}

function openLaunchpadAddFriend() {
  if (typeof window.openFriendRequestModal === 'function') window.openFriendRequestModal();
}

async function enableLaunchpadWeeklyEmail(button) {
  const summary = document.getElementById('libraryLaunchpadSummary');
  if (button) button.disabled = true;
  try {
    const response = await authenticatedFetch(`${API_BASE}/api/for-you/email`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: true }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Could not turn on the weekly email. Please try again.');
    if (summary) summary.textContent = 'Weekly email on. Every email has a one-click unsubscribe.';
    scheduleLibraryLaunchpadRefresh(false);
  } catch (error) {
    if (summary) summary.textContent = error.message || 'Could not turn on the weekly email. Please try again.';
    if (button) button.disabled = false;
  }
}

function dailyDashboardSessionKey() {
  if (!hasStoredAuth()) return null;
  const user = typeof getUser === 'function' ? getUser() : null;
  const token = typeof getToken === 'function' ? getToken() : null;
  return JSON.stringify([dailyDashboardState.epoch, user?.id ?? user?.username ?? null, token]);
}

function resetDailyDashboard() {
  dailyDashboardState.epoch++;
  dailyDashboardState.openRequest++;
  dailyDashboardState.items = [];
  dailyDashboardState.expanded = false;
  dailyDashboardState.mutationPending = false;
  dailyDashboardState.refreshAfterMutation = false;
  refreshNextUpQueue.request = (refreshNextUpQueue.request || 0) + 1;
  refreshLibraryPulse.request = (refreshLibraryPulse.request || 0) + 1;
  ++todaysPickRequest;
  todaysPickSelection = null;
  for (const id of ['libraryPulse', 'todaysPick', 'nextUpQueue']) {
    document.getElementById(id)?.setAttribute('hidden', '');
  }
  for (const id of ['nextUpQueueItems', 'libraryPulseContinue', 'libraryPulseReflect', 'todaysPickName', 'todaysPickCategory', 'todaysPickReason']) {
    document.getElementById(id)?.replaceChildren();
  }
  const reflections = document.getElementById('libraryPulseReflections');
  if (reflections) { reflections.open = false; reflections.hidden = true; }
  const toggle = document.getElementById('nextUpQueueToggle');
  if (toggle) { toggle.hidden = true; toggle.disabled = false; toggle.setAttribute('aria-expanded', 'false'); }
  const status = document.getElementById('libraryNavigationStatus');
  if (status) { status.hidden = true; status.textContent = ''; }
}

async function openDashboardItem(button) {
  const session = dailyDashboardSessionKey();
  if (!session) return false;
  const status = document.getElementById('libraryNavigationStatus');
  if (status) { status.hidden = false; status.textContent = ''; }
  if (editingRowId !== null) {
    if (status) status.textContent = 'Save or cancel your current edit before opening another title.';
    return false;
  }
  const id = Number(button.dataset.pulseItemId);
  const category = button.dataset.pulseTab;
  if (!Number.isInteger(id) || id < 1 || id > 2147483647 || !LIBRARY_SEARCH_SOURCES.some(source => source.tab === category)) {
    if (status) status.textContent = 'That title is unavailable. Refresh your library and try again.';
    return false;
  }
  const request = ++dailyDashboardState.openRequest;
  const active = () => request === dailyDashboardState.openRequest && session === dailyDashboardSessionKey();
  const title = button.dataset.pulseTitle || 'Untitled';
  const openingMessage = `Opening “${title}”…`;
  if (status) status.textContent = openingMessage;
  const opened = await openLibraryItem({ id, category, title }, {
    button, reasonElement: status,
    shouldContinue: (expectedTab = currentTab) => active() && editingRowId === null && currentTab === expectedTab,
  });
  if (active() && status && (opened || status.textContent === openingMessage)) { status.hidden = true; status.textContent = ''; }
  return opened;
}

async function navigateLibraryTab(tabName) {
  const session = dailyDashboardSessionKey();
  const content = document.getElementById(`${tabName}-tab`);
  if (!session || !content || getTabButton(tabName)?.style.display === 'none') return false;
  if (editingRowId !== null) {
    alert('Save or cancel your current edit before opening another category.');
    return false;
  }
  const request = ++dailyDashboardState.openRequest;
  await switchTab(tabName);
  if (request !== dailyDashboardState.openRequest || session !== dailyDashboardSessionKey()
    || currentTab !== tabName || editingRowId !== null) return false;
  const heading = content.querySelector('h2, h3') || content;
  heading.tabIndex = -1;
  heading.focus({ preventScroll: true });
  heading.scrollIntoView({ block: 'start', behavior: 'auto' });
  return true;
}

function renderLibraryPulseList(container, items, emptyMessage) {
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('p');
    empty.className = 'library-pulse__empty';
    empty.textContent = emptyMessage;
    container.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'library-pulse__item';
    button.dataset.action = 'pulse-open-item';
    button.dataset.pulseTab = item.category;
    button.dataset.pulseItemId = String(item.id);
    button.dataset.pulseTitle = item.title;
    const copy = document.createElement('span');
    copy.className = 'library-pulse__item-copy';
    const title = document.createElement('span');
    title.className = 'library-pulse__item-title';
    title.textContent = item.title;
    const meta = document.createElement('span');
    meta.className = 'library-pulse__item-meta';
    const prompts = Array.isArray(item.prompts) && item.prompts.length ? item.prompts.join(' · ') : item.status_label;
    meta.textContent = `${item.category_label} · ${prompts}`;
    copy.append(title, meta);
    if (typeof window !== 'undefined') window.OmniProgress?.appendSummary(copy, item);
    const action = document.createElement('span');
    action.className = 'library-pulse__item-action';
    action.textContent = 'Open →';
    button.append(copy, action);
    if (typeof window !== 'undefined' && window.OmniProgress && ['tv-shows', 'anime', 'books'].includes(item.category)) {
      const row = document.createElement('div');
      row.className = 'library-pulse__progress-row';
      row.appendChild(button);
      window.OmniProgress.appendAction(row, item);
      container.appendChild(row);
    } else container.appendChild(button);
  });
}

function renderLibraryPulse(pulse) {
  const pulseElement = document.getElementById('libraryPulse');
  if (!pulseElement) return;
  if (returnDeckActive) {
    pulseElement.setAttribute('hidden', '');
    return;
  }
  const continueItems = Array.isArray(pulse?.continue_items) ? pulse.continue_items : [];
  const reflectionItems = Array.isArray(pulse?.reflection_items) ? pulse.reflection_items : [];
  if (!continueItems.length && !reflectionItems.length) {
    pulseElement.setAttribute('hidden', '');
    return;
  }
  renderLibraryPulseList(
    document.getElementById('libraryPulseContinue'),
    continueItems.slice(0, 2),
    'Nothing unfinished right now. Add a future watch, read, listen, or play when inspiration strikes.'
  );
  renderLibraryPulseList(
    document.getElementById('libraryPulseReflect'),
    reflectionItems,
    'Your saved items already have ratings and notes. Nice work keeping the story behind your library.'
  );
  const reflections = document.getElementById('libraryPulseReflections');
  if (reflections) reflections.hidden = !reflectionItems.length;
  const count = document.getElementById('libraryPulseReflectionCount');
  if (count) count.textContent = `(${reflectionItems.length})`;
  pulseElement.removeAttribute('hidden');
}

function renderTodaysPick(payload, { showEmpty = false } = {}) {
  const section = document.getElementById('todaysPick');
  const pick = payload?.pick;
  if (!section) return;
  if (returnDeckActive) {
    section.setAttribute('hidden', '');
    return;
  }
  todaysPickSelection = pick || null;
  todaysPickCandidateCount = Number(payload?.candidate_count) || 0;
  document.getElementById('todaysPickName').textContent = pick?.title || 'Nothing unfinished here yet.';
  document.getElementById('todaysPickCategory').textContent = pick?.category_label || '';
  document.getElementById('todaysPickReason').textContent = pick?.reason || 'Choose another category or add a title to your library.';
  document.getElementById('todaysPickOpen').hidden = !pick;
  document.getElementById('todaysPickAnother').hidden = todaysPickCandidateCount < 2;
  if (!pick && !todaysPickCandidateCount && !document.getElementById('todaysPickFilter')?.value && !showEmpty) {
    section.setAttribute('hidden', '');
    return;
  }
  section.removeAttribute('hidden');
}

async function refreshTodaysPick() {
  if (!hasStoredAuth()) return;
  const session = dailyDashboardSessionKey();
  const request = ++todaysPickRequest;
  const open = document.getElementById('todaysPickOpen');
  const another = document.getElementById('todaysPickAnother');
  open.disabled = another.disabled = true;
  const params = new URLSearchParams({ offset: String(todaysPickOffset) });
  const category = document.getElementById('todaysPickFilter').value;
  if (category) params.set('category', category);
  try {
    const response = await authenticatedFetch(`${API_BASE}/statistics/today/?${params}`);
    if (!response.ok) throw new Error('Could not load a pick.');
    const payload = await response.json();
    if (request === todaysPickRequest && session === dailyDashboardSessionKey()) renderTodaysPick(payload);
  } catch (error) {
    if (request === todaysPickRequest && session === dailyDashboardSessionKey()) {
      renderTodaysPick(null, { showEmpty: true });
      document.getElementById('todaysPickReason').textContent = 'Could not load a pick. Change the category to try again.';
    }
  } finally {
    if (request === todaysPickRequest && session === dailyDashboardSessionKey()) open.disabled = another.disabled = false;
  }
}

function tryAnotherPick() {
  todaysPickOffset = (todaysPickOffset + 1) % Math.max(todaysPickCandidateCount, 1);
  refreshTodaysPick();
}

async function openTodaysPick() {
  return openLibraryItem(todaysPickSelection);
}

async function openLibraryItem(pick, options = {}) {
  const guarded = typeof options.shouldContinue === 'function';
  const canContinue = (tab) => !guarded || (options.shouldContinue(tab) && currentTab === tab);
  const startingTab = guarded ? currentTab : null;
  if (!canContinue(startingTab)) return false;
  if (editingRowId !== null) {
    alert('Save or cancel your current edit before opening another title.');
    return false;
  }
  const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === pick?.category);
  if (!source) return false;
  const reason = options.reasonElement || document.getElementById('todaysPickReason');
  if (getTabButton(source.tab)?.style.display === 'none') {
    if (reason) reason.textContent = 'Enable this media category in your settings to open this title.';
    return false;
  }
  const button = options.button === null ? null : options.button || document.getElementById('todaysPickOpen');
  if (button) button.disabled = true;
  try {
    // Let an existing list request finish before changing its search input.
    const busy = () => ({ movies: isLoadingMovies, 'tv-shows': isLoadingTVShows,
      anime: isLoadingAnime, 'video-games': isLoadingVideoGames,
      music: isLoadingMusic, books: isLoadingBooks })[source.tab];
    const deadline = Date.now() + 10000;
    while (busy() && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 50));
      if (!canContinue(startingTab)) return false;
    }
    if (!canContinue(startingTab)) return false;
    if (busy()) throw new Error('The library is still loading. Please try opening the title again.');
    libraryFilters.delete(source.tab);
    document.getElementById(source.input).value = pick.title;
    libraryPages.set(source.tab, { offset: 0, total: 0, focusId: Number(pick.id),
      signature: libraryPageSignature(source.tab) });
    renderLibraryFilters(source.tab);
    await switchTab(source.tab);
    if (!canContinue(source.tab)) return false;
    if (options.focusReady) await options.focusReady;
    if (!canContinue(source.tab)) return false;
    const row = document.querySelector(
      `[data-next-up-category="${source.tab}"][data-next-up-item-id="${Number(pick.id)}"]`
    )?.closest('tr');
    if (!row) throw new Error('This title could not be located. Refresh your pick and try again.');
    document.querySelectorAll('.pick-focused').forEach(element => element.classList.remove('pick-focused'));
    row.classList.add('pick-focused');
    row.tabIndex = -1;
    row.focus({ preventScroll: true });
    row.scrollIntoView({ block: 'center', behavior: 'auto' });
    return true;
  } catch (error) {
    if (guarded && !options.shouldContinue()) return false;
    if (reason) reason.textContent = error.message || 'Could not open this title. Please try again.';
    return false;
  } finally {
    if (button) button.disabled = false;
  }
}

function captureNextUpQueueFocus() {
  const focused = document.activeElement;
  const row = focused?.closest?.('[data-next-up-row-id]');
  if (!row || !document.getElementById('nextUpQueueItems')?.contains(row)) return null;
  return {
    id: row.dataset.nextUpRowId,
    index: dailyDashboardState.items.findIndex(item => String(item.id) === row.dataset.nextUpRowId),
    action: focused.dataset.action,
    direction: focused.dataset.nextUpDirection,
  };
}

function restoreNextUpQueueFocus(focus) {
  if (!focus) return;
  const container = document.getElementById('nextUpQueueItems');
  const rows = Array.from(container.children).filter(row => row.dataset.nextUpRowId);
  const row = rows.find(candidate => candidate.dataset.nextUpRowId === focus.id)
    || rows[Math.min(Math.max(focus.index, 0), rows.length - 1)];
  const buttons = row ? Array.from(row.querySelectorAll('button')).filter(button => !button.disabled) : [];
  const target = buttons.find(button => button.dataset.action === focus.action && button.dataset.nextUpDirection === focus.direction)
    || buttons.find(button => button.dataset.action === focus.action) || buttons[0]
    || document.getElementById('quickCaptureButton') || getTabButton(currentTab);
  target?.focus({ preventScroll: true });
}

function toggleNextUpQueue() {
  if (dailyDashboardState.mutationPending) return;
  dailyDashboardState.expanded = !dailyDashboardState.expanded;
  renderNextUpQueue(dailyDashboardState.items);
}

function renderNextUpQueue(items) {
  const queueElement = document.getElementById('nextUpQueue');
  const container = document.getElementById('nextUpQueueItems');
  if (!queueElement || !container) return;
  const focus = captureNextUpQueueFocus();
  dailyDashboardState.items = Array.isArray(items) ? items : [];
  items = dailyDashboardState.items;
  const shown = dailyDashboardState.expanded ? items : items.slice(0, 3);
  const summary = document.getElementById('nextUpQueueSummary');
  if (summary) {
    summary.textContent = items.length ? `${shown.length} of ${items.length} ${items.length === 1 ? 'title' : 'titles'} · Your order, your pace.` : 'Your next good story starts here.';
    summary.tabIndex = -1;
  }
  const toggle = document.getElementById('nextUpQueueToggle');
  if (toggle) {
    toggle.hidden = items.length < 2;
    toggle.disabled = dailyDashboardState.mutationPending;
    toggle.textContent = dailyDashboardState.expanded ? 'Show less' : `Manage queue (${items.length})`;
    toggle.setAttribute('aria-expanded', String(dailyDashboardState.expanded));
  }
  container.setAttribute('aria-busy', String(dailyDashboardState.mutationPending));
  container.replaceChildren();
  if (!items.length) {
    queueElement.setAttribute('hidden', '');
    restoreNextUpQueueFocus(focus);
    return;
  } else {
    shown.forEach((item, index) => {
      const row = document.createElement('div');
      row.className = `next-up-queue__item${item.available ? '' : ' is-unavailable'}`;
      row.dataset.nextUpRowId = String(item.id);
      const order = document.createElement('span');
      order.className = 'next-up-queue__order';
      order.textContent = String(index + 1);
      const copy = document.createElement('div');
      copy.className = 'next-up-queue__copy';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const meta = document.createElement('span');
      meta.textContent = item.available ? item.category_label : 'This library item was deleted';
      copy.append(title, meta);
      if (typeof window !== 'undefined') window.OmniProgress?.appendSummary(copy, item);
      const controls = document.createElement('div');
      controls.className = 'next-up-queue__controls';
      if (item.available) {
        const open = document.createElement('button');
        open.type = 'button';
        open.className = 'next-up-queue__open';
        open.dataset.action = 'pulse-open-item';
        open.dataset.pulseTab = item.category;
        open.dataset.pulseItemId = String(item.item_id);
        open.dataset.pulseTitle = item.title;
        open.textContent = 'Open';
        open.setAttribute('aria-label', `Open ${item.title}`);
        controls.appendChild(open);
        if (typeof window !== 'undefined') window.OmniProgress?.appendAction(controls, item);
      }
      const up = document.createElement('button');
      up.type = 'button';
      up.className = 'next-up-queue__icon-button';
      up.dataset.action = 'move-next-up';
      up.dataset.nextUpId = item.id;
      up.dataset.nextUpPosition = Math.max(index - 1, 0);
      up.dataset.nextUpDirection = 'up';
      up.disabled = index === 0 || dailyDashboardState.mutationPending;
      up.setAttribute('aria-label', `Move ${item.title} up`);
      up.textContent = '↑';
      const down = document.createElement('button');
      down.type = 'button';
      down.className = 'next-up-queue__icon-button';
      down.dataset.action = 'move-next-up';
      down.dataset.nextUpId = item.id;
      down.dataset.nextUpPosition = index + 1;
      down.dataset.nextUpDirection = 'down';
      down.disabled = index === items.length - 1 || dailyDashboardState.mutationPending;
      down.setAttribute('aria-label', `Move ${item.title} down`);
      down.textContent = '↓';
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'next-up-queue__remove';
      remove.dataset.action = 'remove-next-up';
      remove.dataset.nextUpId = item.id;
      remove.disabled = dailyDashboardState.mutationPending;
      remove.setAttribute('aria-label', `Remove ${item.title} from Next Up`);
      remove.textContent = 'Remove';
      if (dailyDashboardState.expanded) controls.append(up, down);
      controls.appendChild(remove);
      row.append(order, copy, controls);
      container.appendChild(row);
    });
  }
  queueElement.removeAttribute('hidden');
  restoreNextUpQueueFocus(focus);
}

async function refreshNextUpQueue(shouldContinue = () => true) {
  if (!hasStoredAuth()) return;
  const session = dailyDashboardSessionKey();
  const request = refreshNextUpQueue.request = (refreshNextUpQueue.request || 0) + 1;
  try {
    const response = await authenticatedFetch(`${API_BASE}/next-up/`);
    if (response.ok) {
      const items = await response.json();
      if (request === refreshNextUpQueue.request && !dailyDashboardState.mutationPending && shouldContinue() && session === dailyDashboardSessionKey()) renderNextUpQueue(items);
    }
  } catch (error) {
    // The queue is supplementary; never interrupt the tracker if it is unavailable.
  }
}

async function addToNextUp(category, itemId) {
  if (!category || !Number.isInteger(itemId) || itemId < 1) return;
  const session = dailyDashboardSessionKey();
  if (!session) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/next-up/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, item_id: itemId }),
    });
    if (session !== dailyDashboardSessionKey()) return;
    if (response.status === 409) {
      alert('That item is already in your Next Up queue.');
      return;
    }
    if (!response.ok) throw new Error('Unable to add queue item');
    // A move response may have been captured before this addition committed.
    // Re-read once the mutation settles instead of discarding the added title's refresh.
    if (dailyDashboardState.mutationPending) dailyDashboardState.refreshAfterMutation = true;
    const queueRefresh = dailyDashboardState.mutationPending ? null : refreshNextUpQueue();
    await Promise.all([queueRefresh, refreshLibraryPulse(), refreshTodaysPick()]);
  } catch (error) {
    if (session === dailyDashboardSessionKey()) alert('Could not add that item to Next Up. Please try again.');
  }
}

async function moveNextUp(queueId, position) {
  const session = dailyDashboardSessionKey();
  if (!session || dailyDashboardState.mutationPending || !Number.isInteger(queueId) || queueId < 1 || !Number.isInteger(position) || position < 0) return;
  dailyDashboardState.mutationPending = true;
  const mutation = ++dailyDashboardState.mutationRequest;
  refreshNextUpQueue.request = (refreshNextUpQueue.request || 0) + 1;
  const toggle = document.getElementById('nextUpQueueToggle');
  if (toggle) toggle.disabled = true;
  document.getElementById('nextUpQueueItems')?.setAttribute('aria-busy', 'true');
  try {
    const response = await authenticatedFetch(`${API_BASE}/next-up/${queueId}/position`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position }),
    });
    if (!response.ok) throw new Error('Unable to move queue item');
    const items = await response.json();
    if (session !== dailyDashboardSessionKey()) return;
    dailyDashboardState.mutationPending = false;
    // A queue read started during this move may contain the earlier order.
    refreshNextUpQueue.request = (refreshNextUpQueue.request || 0) + 1;
    renderNextUpQueue(items);
    refreshLibraryPulse();
    refreshTodaysPick();
  } catch (error) {
    if (session === dailyDashboardSessionKey()) alert('Could not reorder Next Up. Please try again.');
  } finally {
    if (session === dailyDashboardSessionKey() && mutation === dailyDashboardState.mutationRequest) {
      dailyDashboardState.mutationPending = false;
      if (toggle) toggle.disabled = false;
      document.getElementById('nextUpQueueItems')?.setAttribute('aria-busy', 'false');
      if (dailyDashboardState.refreshAfterMutation) {
        dailyDashboardState.refreshAfterMutation = false;
        await refreshNextUpQueue();
      }
    }
  }
}

async function removeNextUp(queueId) {
  const session = dailyDashboardSessionKey();
  if (!session || dailyDashboardState.mutationPending || !Number.isInteger(queueId) || queueId < 1) return;
  dailyDashboardState.mutationPending = true;
  const mutation = ++dailyDashboardState.mutationRequest;
  refreshNextUpQueue.request = (refreshNextUpQueue.request || 0) + 1;
  const toggle = document.getElementById('nextUpQueueToggle');
  if (toggle) toggle.disabled = true;
  document.getElementById('nextUpQueueItems')?.setAttribute('aria-busy', 'true');
  try {
    const response = await authenticatedFetch(`${API_BASE}/next-up/${queueId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to remove queue item');
    if (session !== dailyDashboardSessionKey()) return;
    dailyDashboardState.mutationPending = false;
    renderNextUpQueue(dailyDashboardState.items.filter(item => item.id !== queueId));
    dailyDashboardState.refreshAfterMutation = false;
    await Promise.all([refreshNextUpQueue(), refreshLibraryPulse(), refreshTodaysPick()]);
  } catch (error) {
    if (session === dailyDashboardSessionKey()) alert('Could not remove that item from Next Up. Please try again.');
  } finally {
    if (session === dailyDashboardSessionKey() && mutation === dailyDashboardState.mutationRequest) {
      dailyDashboardState.mutationPending = false;
      if (toggle) toggle.disabled = false;
      document.getElementById('nextUpQueueItems')?.setAttribute('aria-busy', 'false');
      if (dailyDashboardState.refreshAfterMutation) {
        dailyDashboardState.refreshAfterMutation = false;
        await refreshNextUpQueue();
      }
    }
  }
}

async function refreshLibraryLaunchpad() {
  if (isLibraryLaunchpadDismissed() || !hasStoredAuth()) return;
  try {
    const [response, firstWeek] = await Promise.all([
      authenticatedFetch(`${API_BASE}/statistics/insights/`),
      authenticatedFetch(`${API_BASE}/api/for-you/first-week`)
        .then((reply) => (reply.ok ? reply.json() : null)).catch(() => null),
    ]);
    if (response.ok) renderLibraryLaunchpad(await response.json(), firstWeek);
  } catch (error) {
    // Guidance is optional; it should never interrupt the main tracker.
  }
}

async function refreshLibraryPulse(shouldContinue = () => true) {
  if (!hasStoredAuth()) return;
  const session = dailyDashboardSessionKey();
  const request = refreshLibraryPulse.request = (refreshLibraryPulse.request || 0) + 1;
  try {
    const response = await authenticatedFetch(`${API_BASE}/statistics/pulse/`);
    if (response.ok) {
      const pulse = await response.json();
      if (request === refreshLibraryPulse.request && shouldContinue() && session === dailyDashboardSessionKey()) renderLibraryPulse(pulse);
    }
  } catch (error) {
    // Pulse is optional and should never interrupt the tracker.
  }
}

const dashboardLayoutRefreshes = new Set();
let scheduledDashboardLayoutRefresh = null;

function waitForDashboardLayoutRefreshes() {
  // Initial producers have settled: capture their running and scheduled batches
  // once, without waiting for later refreshes caused by normal interaction.
  return Promise.allSettled(Array.from(dashboardLayoutRefreshes));
}

function scheduleLibraryLaunchpadRefresh(refreshDecisionCards = true) {
  launchpadDecisionRefreshRequested = launchpadDecisionRefreshRequested || refreshDecisionCards;
  if (!scheduledDashboardLayoutRefresh) {
    const batch = {};
    batch.promise = new Promise(resolve => { batch.resolve = resolve; });
    scheduledDashboardLayoutRefresh = batch;
    dashboardLayoutRefreshes.add(batch.promise);
    batch.promise.then(() => dashboardLayoutRefreshes.delete(batch.promise));
  }
  window.clearTimeout(launchpadRefreshTimer);
  launchpadRefreshTimer = window.setTimeout(() => {
    const batch = scheduledDashboardLayoutRefresh;
    scheduledDashboardLayoutRefresh = null;
    const shouldRefreshDecisionCards = launchpadDecisionRefreshRequested;
    launchpadDecisionRefreshRequested = false;
    const launchpadRequest = refreshLibraryLaunchpad();
    const queueRequest = refreshNextUpQueue();
    window.refreshYearGoals?.();
    if (shouldRefreshDecisionCards) refreshDashboardDecisionCards();
    Promise.allSettled([launchpadRequest, queueRequest, decisionCardsRefreshPromise]).then(batch.resolve);
  }, 250);
}

const loadMovieLibrary = loadMovies;
loadMovies = async function (...args) {
  const result = await loadMovieLibrary(...args);
  enhanceLibraryCards('movieTable');
  if (!libraryPages.get('movies')?.browseOnly) {
    invalidateLibrarySearchIndex();
    const refreshDecisionCards = !initialMovieLibraryLoad;
    initialMovieLibraryLoad = false;
    scheduleLibraryLaunchpadRefresh(refreshDecisionCards);
  }
  return result;
};

const loadTVShowLibrary = loadTVShows;
loadTVShows = async function (...args) {
  const result = await loadTVShowLibrary(...args);
  enhanceLibraryCards('tvShowTable');
  if (!libraryPages.get('tv-shows')?.browseOnly) {
    invalidateLibrarySearchIndex();
    scheduleLibraryLaunchpadRefresh();
  }
  return result;
};

const loadAnimeLibrary = loadAnime;
loadAnime = async function (...args) {
  const result = await loadAnimeLibrary(...args);
  enhanceLibraryCards('animeTable');
  if (!libraryPages.get('anime')?.browseOnly) {
    invalidateLibrarySearchIndex();
    scheduleLibraryLaunchpadRefresh();
  }
  return result;
};

const loadVideoGameLibrary = loadVideoGames;
loadVideoGames = async function (...args) {
  const result = await loadVideoGameLibrary(...args);
  enhanceLibraryCards('videoGameTable');
  if (!libraryPages.get('video-games')?.browseOnly) {
    invalidateLibrarySearchIndex();
    scheduleLibraryLaunchpadRefresh();
  }
  return result;
};

const loadMusicLibrary = loadMusic;
loadMusic = async function (...args) {
  const result = await loadMusicLibrary(...args);
  enhanceLibraryCards('musicTable');
  if (!libraryPages.get('music')?.browseOnly) {
    invalidateLibrarySearchIndex();
    scheduleLibraryLaunchpadRefresh();
  }
  return result;
};

const loadBookLibrary = loadBooks;
loadBooks = async function (...args) {
  const result = await loadBookLibrary(...args);
  enhanceLibraryCards('bookTable');
  if (!libraryPages.get('books')?.browseOnly) {
    invalidateLibrarySearchIndex();
    scheduleLibraryLaunchpadRefresh();
  }
  return result;
};

// Import completion reuses the existing library and dashboard refresh paths.
if (window.OmniImportStudio) {
  const activeImportLibraryLoads = new Map();
  let importLibraryRefreshEpoch = 0;
  const trackImportLibraryLoad = (category, load) => function (...args) {
    const request = load(...args);
    // A duplicate invocation can return immediately while the first load is
    // still running. Keep tracking the first load until it has rendered.
    if (!activeImportLibraryLoads.has(category) && request?.then) {
      activeImportLibraryLoads.set(category, request);
      const finished = () => {
        if (activeImportLibraryLoads.get(category) === request) activeImportLibraryLoads.delete(category);
      };
      request.then(finished, finished);
    }
    return request;
  };
  loadMovies = trackImportLibraryLoad('movies', loadMovies);
  loadTVShows = trackImportLibraryLoad('tv-shows', loadTVShows);
  loadAnime = trackImportLibraryLoad('anime', loadAnime);
  loadVideoGames = trackImportLibraryLoad('video-games', loadVideoGames);
  loadMusic = trackImportLibraryLoad('music', loadMusic);
  loadBooks = trackImportLibraryLoad('books', loadBooks);

  const resetImportSession = window.OmniImportStudio.reset;
  window.OmniImportStudio.reset = (...args) => {
    importLibraryRefreshEpoch++;
    return resetImportSession?.(...args);
  };
  window.addEventListener('pagehide', () => { importLibraryRefreshEpoch++; });
  window.addEventListener('storage', event => {
    if (event.key === null || ['omnitrackr_user', 'omnitrackr_token'].includes(event.key)) importLibraryRefreshEpoch++;
  });

  const refreshImportedCategory = async (category, pending = activeImportLibraryLoads.get(category)) => {
    const account = importStudioAccountKey();
    const epoch = importLibraryRefreshEpoch;
    if (pending) {
      try { await pending; } catch (_) { /* A failed old load still needs a fresh request. */ }
    }
    if (epoch !== importLibraryRefreshEpoch || account !== importStudioAccountKey()
        || currentTab !== category || editingRowId !== null) return;
    return libraryPageConfig(category)?.[2]();
  };

  window.OmniImportStudio.canOpenCategory = category => {
    const button = getTabButton(category);
    return !!button && button.style.display !== 'none';
  };
  window.OmniImportStudio.refresh = counts => {
    invalidateLibrarySearchIndex();
    Object.keys(categoryStatsCache).forEach(key => { delete categoryStatsCache[key]; });
    Object.keys(counts).filter(category => counts[category] > 0).forEach(category => libraryPages.delete(category));
    scheduleLibraryLaunchpadRefresh();
    if (counts[currentTab] > 0 && editingRowId === null) return refreshImportedCategory(currentTab);
  };
  window.OmniImportStudio.openCategory = category => {
    if (!window.OmniImportStudio.canOpenCategory(category)) return;
    if (editingRowId !== null) {
      document.getElementById('importStudioStatus').textContent = 'Your import is saved. Save or cancel your current library edit before opening another category.';
      return;
    }
    const source = LIBRARY_SEARCH_SOURCES.find(entry => entry.tab === category);
    if (!source) return;
    libraryFilters.delete(category);
    document.getElementById(source.input).value = '';
    libraryPages.delete(category);
    window.closeAccountModal();
    const pending = activeImportLibraryLoads.get(category);
    switchTab(category);
    getTabButton(category)?.focus();
    if (pending) return refreshImportedCategory(category, pending);
  };
}

// Load initial data
setupLibrarySearch();
const initialMovieLibraryRequest = loadMovies();
scheduleLibraryLaunchpadRefresh(false);
const initialReturnDeckRequest = bootstrapReturnDeck();
const dashboardStartupLayoutReady = Promise.allSettled([
  initialMovieLibraryRequest,
  initialReturnDeckRequest,
]).then(waitForDashboardLayoutRefreshes);
// The library was kept invisible while the cards above it loaded (see preauth.js).
dashboardStartupLayoutReady.then(() => document.documentElement?.classList.remove('dashboard-settling'));

// ============================================================================
// Landing Page Enhancements: Scroll Animations and User Count
// ============================================================================

// Intersection Observer for fade-in on scroll animations
let scrollObserver = null;

function initScrollAnimations() {
  // Only initialize if landing page is visible
  const landingPage = document.getElementById('landingPage');
  if (!landingPage || landingPage.style.display !== 'block') {
    return;
  }

  // Clean up existing observer if any
  if (scrollObserver) {
    scrollObserver.disconnect();
  }

  // Create Intersection Observer
  scrollObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        // Unobserve after animation to improve performance
        scrollObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  // Observe all elements with fade-in-on-scroll class
  const fadeElements = document.querySelectorAll('.fade-in-on-scroll');
  fadeElements.forEach(el => {
    scrollObserver.observe(el);
  });
}

// Fetch and display user count
async function fetchUserCount() {
  const userCountDisplay = document.getElementById('userCountDisplay');
  if (!userCountDisplay) return;

  // Only fetch if landing page is visible
  const landingPage = document.getElementById('landingPage');
  if (!landingPage || landingPage.style.display !== 'block') {
    userCountDisplay.style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/user-count`);
    if (!response.ok) {
      throw new Error('Failed to fetch user count');
    }
    const data = await response.json();
    const count = data.count || 0;
    userCountDisplay.textContent = `${count} users tracking their media already`;
    userCountDisplay.style.display = 'block';
  } catch (error) {
    // Graceful degradation: hide the element on error
    userCountDisplay.style.display = 'none';
    console.error('Error fetching user count:', error);
  }
}

// Initialize landing page enhancements when DOM is ready
function initLandingPageEnhancements() {
  const landingPage = document.getElementById('landingPage');
  if (!landingPage) return;

  // Add fade-in-on-scroll class to feature cards and FAQ items
  const featureCards = document.querySelectorAll('.feature-card');
  featureCards.forEach(card => {
    card.classList.add('fade-in-on-scroll');
  });

  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    item.classList.add('fade-in-on-scroll');
  });

  // Initialize scroll animations
  initScrollAnimations();

  // Fetch user count
  fetchUserCount();
}

// Call on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
  initLandingPageEnhancements();
});

// Also call when landing page becomes visible (after login/logout)
// This will be called from auth.js when showing/hiding landing page
window.initLandingPageEnhancements = initLandingPageEnhancements;

// Screenshot Lightbox Functions
function openScreenshotModal(imageSrc, caption) {
  const modal = document.getElementById('screenshotModal');
  const modalImage = document.getElementById('screenshotModalImage');
  const modalCaption = document.getElementById('screenshotModalCaption');
  
  if (modal && modalImage && modalCaption) {
    modalImage.src = imageSrc;
    modalImage.alt = caption;
    modalCaption.textContent = caption;
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
  }
}

function closeScreenshotModal(event) {
  const modal = document.getElementById('screenshotModal');
  if (!modal) return;
  
  if (event) {
    event.stopPropagation();
    if (event.target === modal || event.target.classList.contains('screenshot-modal-close')) {
      modal.classList.remove('show');
      document.body.style.overflow = '';
    }
  } else {
    modal.classList.remove('show');
    document.body.style.overflow = '';
  }
}

window.openScreenshotModal = openScreenshotModal;
window.closeScreenshotModal = closeScreenshotModal;

document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    const modal = document.getElementById('screenshotModal');
    if (modal && modal.classList.contains('show')) {
      closeScreenshotModal();
    }
  }
});

// Cleanup observer on page unload
window.addEventListener('beforeunload', function() {
  if (scrollObserver) {
    scrollObserver.disconnect();
    scrollObserver = null;
  }
});

