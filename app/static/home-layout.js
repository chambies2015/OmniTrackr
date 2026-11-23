// Member home layout: one "Do this next" title under the welcome strip, and a calmer board below it.
//
// OmniHomeFocus takes the first title from Continue (or, with nothing on the go, the top of Next Up)
// and shows it on its own with the button that moves it forward. Continue then lists the rest, so the
// same title isn't shown twice. Every button reuses the data-action / data-episode / data-progress
// hooks the Continue rows already use, so the existing handlers do the work.
//
// OmniHomeLayout keeps the board short. Each column shows its first few cards in page order; cards with
// nothing of the member's own in them (an invite, popular picks, an empty queue) and anything past the
// limit wait behind one "Show more" button. Nothing is removed and no card's own hide or "seen" logic
// changes: a tucked card is display:none, so cards that count a view when they scroll into sight don't
// count it until they're opened. Cards the member is in the middle of, asked for by link, or that only
// show now and then (first-week, stay-posted, support notes) are never tucked.
// Server text is only ever set with textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const PULSE_CATEGORIES = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books', 'manga', 'podcasts', 'audiobooks'];
  const MORE_KEY = 'omnitrackr_home_more';

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function validId(value) {
    const id = Number(value);
    return Number.isSafeInteger(id) && id > 0 && id <= 2147483647;
  }

  // ------------------------------------------------------------------ Do this next

  const focus = { continueItem: null, queueItem: null, key: '' };

  function letterOf(title) {
    return (String(title || '').match(/[\p{L}\p{N}]/u) || ['?'])[0].toUpperCase();
  }

  function renderCover(holder, item) {
    holder.replaceChildren();
    holder.dataset.format = item.category;
    holder.classList.remove('home-focus__cover--letter');
    const image = typeof item.image === 'string' && /^https?:\/\//.test(item.image) ? item.image : '';
    const letter = () => {
      holder.classList.add('home-focus__cover--letter');
      holder.textContent = letterOf(item.title);
    };
    if (!image) { letter(); return; }
    const img = el('img');
    img.src = image;
    img.alt = '';
    img.decoding = 'async';
    img.referrerPolicy = 'no-referrer';
    img.width = 96;
    img.height = 144;
    img.addEventListener('error', () => { img.remove(); letter(); }, { once: true });
    holder.appendChild(img);
  }

  function openButton(item, itemId) {
    const open = el('button', 'home-focus__btn home-focus__open', 'Open');
    open.type = 'button';
    open.dataset.action = 'pulse-open-item';
    open.dataset.pulseTab = item.category;
    open.dataset.pulseItemId = String(itemId);
    open.dataset.pulseTitle = item.title || '';
    open.setAttribute('aria-label', `Open ${item.title || 'this title'} in your library`);
    return open;
  }

  // A film, an album or a game nobody logged time on has nothing to step through, so this card only
  // offered "Open". "Mark watched" finishes it in one tap with the same PUT the library's done circle
  // sends, then opens the usual finish moment and refreshes Continue.
  const DONE = {
    movies: ['watched', 'watched'], 'tv-shows': ['watched', 'finished'], anime: ['watched', 'finished'],
    'video-games': ['played', 'played'], music: ['listened', 'listened'], books: ['read', 'read'],
    manga: ['read', 'read'], podcasts: ['listened', 'listened'], audiobooks: ['listened', 'finished'],
  };

  function say(message, tone) {
    if (typeof showNotice === 'function') showNotice(message, tone);
  }

  function doneButton(item, itemId) {
    const [field, word] = DONE[item.category] || [];
    if (!field || !validId(itemId)) return null;
    const title = item.title || 'this title';
    const button = el('button', 'home-focus__btn home-focus__done', `Mark ${word}`);
    button.type = 'button';
    button.setAttribute('aria-label', `Mark ${title} as ${word}`);
    button.addEventListener('click', async () => {
      if (button.disabled || typeof authenticatedFetch !== 'function') return;
      button.disabled = true;
      let saved = false;
      try {
        const base = typeof API_BASE === 'string' ? API_BASE : '';
        const response = await authenticatedFetch(`${base}/${item.category}/${itemId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [field]: true }),
        });
        saved = Boolean(response && response.ok);
      } catch (error) {
        saved = false;
      }
      button.disabled = false;
      if (!saved) {
        say('That didn\u2019t save. Try again in a moment.', 'error');
        return;
      }
      say(`${title}: marked ${word}.`, 'success');
      // The card redraws with the next title and this button goes with it, so the finish moment
      // would hand focus back to nothing when it closes. Park focus on the card's heading first.
      if (document.activeElement === button) {
        const heading = $('homeFocusTitle');
        if (heading) {
          heading.setAttribute('tabindex', '-1');
          heading.focus({ preventScroll: true });
        }
      }
      if (typeof openCompletionMoment === 'function') openCompletionMoment(item.category, itemId);
      window.OmniHomeHero?.refresh?.();
      if (typeof refreshLibraryPulse === 'function') refreshLibraryPulse();
      const config = typeof libraryPageConfig === 'function' ? libraryPageConfig(item.category) : null;
      if (config && typeof config[2] === 'function') config[2]();
    });
    return button;
  }

  function started(item) {
    return Boolean(item.progress || item.started_at || (item.episode_progress && item.episode_progress.current));
  }

  function renderFocus() {
    const section = $('homeFocus');
    if (!section) return;
    const fromContinue = Boolean(focus.continueItem);
    const item = focus.continueItem || focus.queueItem;
    if (!item) {
      focus.key = '';
      section.hidden = true;
      return;
    }
    const itemId = fromContinue ? item.id : item.item_id;
    const key = JSON.stringify([fromContinue, item.category, itemId, item.title, item.image, item.prompts, item.status_label,
      item.progress, item.episode_progress, item.started_at]);
    if (key === focus.key && !section.hidden) return;
    focus.key = key;
    section.dataset.source = fromContinue ? 'continue' : 'queue';
    section.dataset.format = item.category;

    const cover = $('homeFocusCover');
    if (cover) renderCover(cover, item);
    const eyebrow = $('homeFocusEyebrow');
    if (eyebrow) {
      eyebrow.textContent = !fromContinue ? 'First in your Next Up queue'
        : started(item) ? 'Pick up where you left off' : 'Ready when you are';
    }
    const title = $('homeFocusTitle');
    if (title) title.textContent = item.title || 'Untitled';
    const meta = $('homeFocusMeta');
    if (meta) {
      const prompts = Array.isArray(item.prompts) && item.prompts.length ? item.prompts.join(' · ') : item.status_label;
      meta.textContent = [item.category_label, prompts].filter(Boolean).join(' · ');
    }
    const progress = $('homeFocusProgress');
    if (progress) {
      progress.replaceChildren();
      window.OmniProgress?.appendSummary(progress, fromContinue ? item : { ...item, id: itemId });
      // Compact: the summary above already says where the member stopped, so the bar only counts episodes.
      window.OmniEpisodes?.appendBar(progress, fromContinue ? item : { ...item, id: itemId }, { compact: true });
      progress.hidden = !progress.textContent.trim() && !progress.querySelector('.episode-progress:not([hidden])');
    }
    const actions = $('homeFocusActions');
    if (actions) {
      actions.replaceChildren();
      const forward = fromContinue ? item : { ...item, id: itemId };
      if (!fromContinue && !item.started_at && !item.progress && validId(item.id)) {
        const start = el('button', 'home-focus__btn home-focus__start',
          item.now_label ? `Start ${String(item.now_label).toLowerCase()}` : 'Start');
        start.type = 'button';
        start.dataset.action = 'start-next-up';
        start.dataset.nextUpId = String(item.id);
        start.setAttribute('aria-label', `Start ${item.title}. It moves to the top of Next Up and into Continue.`);
        actions.appendChild(start);
      }
      window.OmniEpisodes?.appendActions(actions, forward);
      window.OmniProgress?.appendAction(actions, forward);
      if (fromContinue && !actions.querySelector('button.episode-next, button.progress-update')) {
        const done = doneButton(item, itemId);
        if (done) actions.appendChild(done);
      }
      actions.appendChild(openButton(item, itemId));
      // The first button is the one that moves the title forward: "+ S2 E6", "Update progress", "Start reading",
      // "Mark watched" or "Open".
      const first = actions.querySelector('button.episode-next, button.home-focus__start, button.progress-update, button.home-focus__done, button.home-focus__open');
      if (first) first.classList.add('home-focus__primary');
    }
    section.hidden = false;
  }

  // Continue calls this with its titles. True means the first one is shown here, so Continue skips it.
  function claim(items) {
    const list = Array.isArray(items) ? items : [];
    const first = list.find(item => item && validId(item.id) && PULSE_CATEGORIES.includes(item.category)) || null;
    if (!$('homeFocus') || (first && list[0] !== first)) {
      focus.continueItem = null;
      renderFocus();
      return false;
    }
    focus.continueItem = first;
    renderFocus();
    return Boolean(first);
  }

  // Next Up calls this with its queue. Used only when Continue has nothing to offer.
  function queue(items) {
    const list = Array.isArray(items) ? items : [];
    focus.queueItem = list.find(item => item && item.available && !item.finished && validId(item.item_id)
      && PULSE_CATEGORIES.includes(item.category)) || null;
    renderFocus();
  }

  function resetFocus() {
    focus.continueItem = null;
    focus.queueItem = null;
    focus.key = '';
    const section = $('homeFocus');
    if (section) section.hidden = true;
    ['homeFocusActions', 'homeFocusProgress', 'homeFocusCover'].forEach(id => $(id)?.replaceChildren());
  }

  // ------------------------------------------------------------------ the board

  // Links into the home screen that should always find their card.
  const HASH_CARDS = {
    '#your-week': 'yourWeek', '#backlog-draw': 'backlogDraw', '#badges': 'badgeCase', '#challenge': 'monthlyChallenge',
    '#goals': 'yearGoals', '#on-this-day': 'onThisDay', '#release-calendar': 'comingUp', '#week-one': 'weekOne',
    '#homeNews': 'homeNews', '#advent': 'adventCard', '#on-your-services': 'onYourServices', '#together': 'togetherHome',
    '#swap': 'swapHome', '#break': 'breakHome',
  };
  // Shown now and then under their own rules (first week only, a few times a year): never tucked.
  const ALWAYS = new Set(['weekOne', 'stayPosted', 'supportAsk']);
  const CAPS = { main: [3, 4], rail: [2, 3] };
  const layout = {
    sticky: new Set(), stickyFrom: 0, settledAt: 0, frame: 0, expanded: false, observer: null, media: null, started: false,
    // The card a link asked for this visit (/#goals from an email, a notification or the goals page). Card
    // scripts clear the hash once they've scrolled to it, so it's remembered here and the card stays out.
    asked: '', askedAt: 0, moved: false,
  };

  function readExpanded() {
    try { return localStorage.getItem(MORE_KEY) === '1'; } catch (error) { return false; }
  }
  function storeExpanded(value) {
    try {
      if (value) localStorage.setItem(MORE_KEY, '1');
      else localStorage.removeItem(MORE_KEY);
    } catch (error) { /* remembered for this visit only */ }
  }

  function isPhone() {
    return Boolean(layout.media && layout.media.matches);
  }

  function unitId(unit) {
    return unit.id || (unit.classList.contains('daily-dashboard') ? 'dailyDashboard' : '');
  }

  function units(column) {
    if (!column) return [];
    return Array.from(column.children).filter(node => node.matches('section[id], .daily-dashboard'));
  }

  function visible(unit) {
    if (unit.classList.contains('daily-dashboard')) return Boolean(unit.querySelector(':scope > section:not([hidden])'));
    return !unit.hidden;
  }

  function hashCard(url) {
    if (url) {
      const at = String(url).indexOf('#');
      return at >= 0 ? HASH_CARDS[String(url).slice(at)] || '' : '';
    }
    return HASH_CARDS[window.location.hash] || '';
  }

  // The member is part-way through something in this card, or it is celebrating something they did.
  function engaged(unit) {
    const id = unitId(unit);
    if (ALWAYS.has(id) || id === hashCard() || (id && id === layout.asked)) return true;
    if (document.activeElement && document.activeElement !== document.body && unit.contains(document.activeElement)) return true;
    if (unit.querySelector('[id$="Celebration"]:not([hidden])')) return true;
    if (id === 'backlogDraw') return Boolean(unit.querySelector('.backlog-draw__plan, .backlog-draw__table--up'));
    if (id === 'yourWeek') {
      // A pace is set (anything but "setup"), or Monday's recap of last week is up.
      const recap = $('yourWeekRecap');
      return Boolean(unit.dataset.status && unit.dataset.status !== 'setup') || Boolean(recap && !recap.hidden);
    }
    // Watch together only shows while a plan with friends is running, so it never waits behind "Show more".
    if (id === 'togetherHome') return true;
    // Pick swap only shows while the member is in a swap that hasn't been unwrapped for long.
    if (id === 'swapHome') return true;
    // The break planner shows in the days before a holiday, during a planned break and just after it.
    if (id === 'breakHome') return true;
    // Something on the member's list just arrived on one of their streaming services.
    if (id === 'onYourServices') return unit.dataset.status === 'new';
    // Rankings: a title finished this week, one part-way placed, or one that just landed.
    if (id === 'rankDuel') return unit.dataset.engaged === 'true' || ['fresh', 'placing', 'placed'].includes(unit.dataset.status);
    if (id === 'monthlyChallenge') return $('monthlyChallengeLeave') ? !$('monthlyChallengeLeave').hidden : false;
    return false;
  }

  // Nothing of the member's own in it right now: an invite, popular picks, an empty queue, a goal not set.
  function quiet(unit) {
    switch (unitId(unit)) {
      case 'homeNews': {
        const shows = $('homeNewsShows');
        const friends = $('homeNewsFriendList');
        const news = Boolean(friends && friends.querySelector('li:not(.home-news__empty)'));
        return (!shows || shows.hidden) && !news;
      }
      case 'nextUpQueue': return !($('nextUpQueueItems')?.children.length);
      case 'comingUp': return unit.dataset.source === 'popular';
      case 'badgeCase': return true;
      case 'rankDuel': return unit.dataset.status === 'more';
      case 'yearGoals': return !$('yearGoalsList') || $('yearGoalsList').hidden;
      default: return false;
    }
  }

  function arrangeColumn(column, cap) {
    const shown = [];
    const tucked = [];
    let strong = 0;
    const all = units(column).filter(visible);
    all.forEach(unit => {
      const id = unitId(unit);
      let show;
      if (engaged(unit) || layout.sticky.has(id)) show = true;
      else if (quiet(unit)) show = false;
      else show = strong < cap;
      if (show && !engaged(unit) && !quiet(unit)) strong += 1;
      (show ? shown : tucked).push(unit);
    });
    // A column never empties itself: with only quiet cards, the first one stays.
    if (!shown.length && tucked.length) shown.push(tucked.shift());
    units(column).forEach(unit => unit.classList.toggle('is-home-tucked', tucked.includes(unit)));
    return { shown, tucked };
  }

  function cardName(unit) {
    if (unit.classList.contains('daily-dashboard')) return 'Continue';
    const heading = unit.querySelector('h2');
    const text = heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '';
    return text.length > 36 ? `${text.slice(0, 35).trim()}…` : text;
  }

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function arrange() {
    layout.frame = 0;
    const board = document.querySelector('.home-board');
    if (!board) return;
    const phone = isPhone() ? 0 : 1;
    // Back after a while: the welcome-back deck is the thing to do, so fewer cards sit under it.
    const returning = Boolean($('returnDeck') && !$('returnDeck').hidden);
    const mainCap = returning ? Math.min(2, CAPS.main[phone]) : CAPS.main[phone];
    const main = arrangeColumn(board.querySelector('.home-board__main'), mainCap);
    const rail = arrangeColumn(board.querySelector('.home-board__rail-cards'), CAPS.rail[phone]);
    const tucked = main.tucked.concat(rail.tucked);
    if (layout.settledAt && Date.now() >= layout.stickyFrom) {
      main.shown.concat(rail.shown).forEach(unit => layout.sticky.add(unitId(unit)));
    }
    board.classList.toggle('home-board--more', layout.expanded);
    keepAskedInView();
    const more = $('homeMore');
    const toggle = $('homeMoreToggle');
    const names = $('homeMoreNames');
    if (!more || !toggle) return;
    if (!tucked.length) {
      if (!more.hidden) more.hidden = true;
      return;
    }
    const count = tucked.length;
    setText(toggle, layout.expanded ? 'Show fewer cards' : `Show ${count} more on your home`);
    if (toggle.getAttribute('aria-expanded') !== String(layout.expanded)) toggle.setAttribute('aria-expanded', String(layout.expanded));
    setText(names, layout.expanded ? '' : tucked.map(cardName).filter(Boolean).join(' · '));
    if (names) names.hidden = layout.expanded || !names.textContent;
    if (more.hidden) more.hidden = false;
  }

  // Cards above a linked card often load after its own script has scrolled to it and push it off
  // screen. For the first few seconds, until the member scrolls themselves, bring it back.
  function keepAskedInView() {
    if (!layout.asked || layout.moved || !layout.askedAt || Date.now() - layout.askedAt > 6000) return;
    const card = $(layout.asked);
    if (!card || card.hidden || card.classList.contains('is-home-tucked') || typeof card.getBoundingClientRect !== 'function') return;
    const top = card.getBoundingClientRect().top;
    const height = window.innerHeight || 0;
    if (height && (top < -4 || top > height * 0.6) && typeof card.scrollIntoView === 'function') card.scrollIntoView({ block: 'start' });
  }

  function schedule() {
    if (layout.frame) return;
    layout.frame = typeof window.requestAnimationFrame === 'function'
      ? window.requestAnimationFrame(arrange)
      : window.setTimeout(arrange, 16);
  }

  function setExpanded(value, { announce = true } = {}) {
    layout.expanded = Boolean(value);
    storeExpanded(layout.expanded);
    arrange();
    const status = $('homeMoreStatus');
    if (status && announce) status.textContent = layout.expanded ? 'More cards are showing on your home.' : 'Fewer cards are showing.';
  }

  // A link to a card that is waiting behind "Show more" brings that card out, so it lands. Only that
  // card: the member didn't choose Show more, so the rest stay put and nothing is remembered.
  function revealFor(target) {
    if (!target) return;
    layout.asked = unitId(target);
    if (target.classList?.contains('is-home-tucked')) arrange();
  }

  function watchSettle() {
    const root = document.documentElement;
    const settled = () => {
      if (layout.settledAt) return;
      layout.settledAt = Date.now();
      // Cards that don't hold the page back (first week, your week, the backlog draw) land a moment later.
      layout.stickyFrom = layout.settledAt + 2500;
      window.setTimeout(schedule, 2600);
    };
    if (!root.classList.contains('dashboard-settling')) { settled(); return; }
    if (typeof MutationObserver !== 'function') { settled(); return; }
    const watcher = new MutationObserver(() => {
      if (!root.classList.contains('dashboard-settling')) { watcher.disconnect(); settled(); }
    });
    watcher.observe(root, { attributes: true, attributeFilter: ['class'] });
  }

  function start() {
    if (layout.started) return;
    const board = document.querySelector('.home-board');
    if (!board) return;
    layout.started = true;
    layout.expanded = readExpanded();
    layout.asked = hashCard();
    if (layout.asked) {
      layout.askedAt = Date.now();
      const moved = () => { layout.moved = true; };
      ['wheel', 'touchmove', 'keydown', 'mousedown'].forEach(type => window.addEventListener(type, moved, { passive: true, once: true }));
    }
    layout.media = typeof window.matchMedia === 'function' ? window.matchMedia('(max-width: 640px)') : null;
    layout.media?.addEventListener?.('change', schedule);
    if (typeof MutationObserver === 'function') {
      layout.observer = new MutationObserver(schedule);
      layout.observer.observe(board, { attributes: true, attributeFilter: ['hidden', 'data-status', 'data-source'], childList: true, subtree: true });
      const deck = $('returnDeck');
      if (deck) layout.observer.observe(deck, { attributes: true, attributeFilter: ['hidden'] });
    }
    $('homeMoreToggle')?.addEventListener('click', () => setExpanded(!layout.expanded));
    document.addEventListener('click', event => {
      const link = event.target.closest?.('a[href^="#"]');
      const id = link && HASH_CARDS[link.getAttribute('href')];
      if (id) revealFor($(id));
    }, true);
    window.addEventListener('hashchange', event => {
      // The card's own script may have cleared the hash already, so read the one the event carried.
      const id = hashCard(event && event.newURL) || hashCard();
      if (id) revealFor($(id));
      schedule();
    });
    board.addEventListener('focusin', schedule);
    watchSettle();
    schedule();
  }

  function resetLayout() {
    layout.sticky.clear();
    layout.asked = '';
    layout.settledAt = 0;
    layout.stickyFrom = 0;
    document.querySelectorAll('.is-home-tucked').forEach(node => node.classList.remove('is-home-tucked'));
    const more = $('homeMore');
    if (more) more.hidden = true;
    if (layout.started) watchSettle();
  }

  window.OmniHomeFocus = { claim, queue, reset: resetFocus, render: renderFocus };
  // reveal: another card's button that scrolls to a card (the challenge's "Deal me in") brings it out first.
  window.OmniHomeLayout = { arrange, schedule, reset: resetLayout, start, expand: setExpanded, reveal: revealFor };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { claim, queue, resetFocus, arrange, quiet, engaged, arrangeColumn, focus, layout, start, setExpanded, revealFor };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
