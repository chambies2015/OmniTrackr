// Dashboard entry points to Year in Review.
// - December and January: the "your year is ready" banner.
// - November: a "your year so far" card with the year to date and one thing still in reach.
// The server decides who sees what; the month checks here only save a request the rest of the year.
// Server text is only ever set as textContent.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const NOVEMBER = 10;
  // loadedAt: the script asks once as it loads and auth.js asks again when it shows the
  // dashboard; an answer this fresh is reused instead of fetched twice.
  const state = { request: 0, pending: null, loadedAt: 0 };
  const REUSE_MS = 20000;

  // Titles ticked off with no date aren't in the recap yet: the banner sends the member to date them first.
  function showFill(season, link) {
    const fill = season.fill;
    const undated = fill && Number.isInteger(fill.undated) ? fill.undated : 0;
    const url = fill && typeof fill.url === 'string' && /^\/year-in-review\/\d{4}\/fill$/.test(fill.url) ? fill.url : null;
    if (!undated || !url) return;
    const text = $('yearInReviewBannerText');
    const since = typeof fill.dated_from === 'string' && /^[A-Z][a-z]{2,8}$/.test(fill.dated_from) ? fill.dated_from : null;
    const titles = undated === 1 ? '1 title in your library is' : `${undated.toLocaleString('en-US')} titles in your library are`;
    if (text) {
      text.textContent = since
        ? `It counts what you finished from ${since} on. ${titles} ticked off with no date: give each one a month and it joins your ${season.year}.`
        : `${titles} ticked off with no date: give each one a month and it joins your ${season.year}.`;
    }
    if (link) {
      link.href = url;
      link.textContent = `Fill in your ${season.year}`;
    }
  }

  function showRecapBanner() {
    const banner = $('yearInReviewBanner');
    if (!banner) return;
    const month = new Date().getMonth();
    if (month !== 11 && month !== 0) return;
    fetch('/api/year-in-review-season', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(response => (response.ok ? response.json() : null))
      .then(season => {
        if (!season || !season.year) return;
        const link = $('yearInReviewBannerLink');
        const title = $('yearInReviewBannerTitle');
        if (link) link.href = `${season.url}#story`;
        if (title) title.textContent = `Your ${season.year} in media is ready`;
        showFill(season, link);
        banner.hidden = false;
      })
      .catch(() => { /* the banner simply stays hidden */ });
  }

  // ------------------------------------------------------------ November: your year so far

  function memberKey() {
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) return String(user.id);
    } catch (error) { /* shared key */ }
    return 'member';
  }

  function hiddenKey(year) {
    return `omnitrackr_year_so_far_hidden_${memberKey()}_${year}`;
  }

  function isHidden(year) {
    try { return typeof localStorage !== 'undefined' && localStorage.getItem(hiddenKey(year)) === '1'; } catch (error) { return false; }
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text;
  }

  function number(value) {
    return Number(value).toLocaleString('en-US');
  }

  function safeLink(value, year) {
    return typeof value === 'string' && /^\/year-in-review\/\d{4}(\?from=[a-z-]+)?$/.test(value) ? value : `/year-in-review/${year}`;
  }

  function render(data) {
    const card = $('yearSoFar');
    if (!card) return;
    const year = data && Number.isInteger(data.year) ? data.year : null;
    if (!year || !Number.isInteger(data.finished) || data.finished < 1 || isHidden(year)) {
      card.hidden = true;
      return;
    }
    card.dataset.year = String(year);
    setText('yearSoFarTitle', `Your ${year} so far`);
    setText('yearSoFarFinished', number(data.finished));
    setText('yearSoFarFinishedLabel', data.finished === 1 ? 'title finished' : 'titles finished');

    const hours = Number.isInteger(data.hours) && data.hours > 0 ? data.hours : null;
    const hoursTile = $('yearSoFarHoursTile');
    if (hoursTile) hoursTile.hidden = !hours;
    if (hours) {
      setText('yearSoFarHours', `~${number(hours)}`);
      setText('yearSoFarHoursLabel', hours === 1 ? 'hour' : 'hours');
    }

    const shelf = data.top_shelf && typeof data.top_shelf.noun === 'string' ? data.top_shelf : null;
    const genre = typeof data.genre === 'string' && data.genre ? data.genre : null;
    const tasteTile = $('yearSoFarTasteTile');
    if (tasteTile) tasteTile.hidden = !(genre || shelf);
    if (genre) {
      setText('yearSoFarTaste', genre);
      setText('yearSoFarTasteLabel', 'top genre');
    } else if (shelf) {
      setText('yearSoFarTaste', shelf.noun.charAt(0).toUpperCase() + shelf.noun.slice(1));
      setText('yearSoFarTasteLabel', 'most finished');
    }

    setText('yearSoFarHint', typeof data.hint === 'string' ? data.hint : '');
    const daysLeft = Number.isInteger(data.days_left) ? data.days_left : null;
    const meter = $('yearSoFarMeter');
    if (meter) {
      meter.hidden = daysLeft === null;
      if (daysLeft !== null) {
        const length = (year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)) ? 366 : 365;
        const done = Math.max(0, Math.min(100, Math.round(((length - daysLeft) / length) * 100)));
        const fill = $('yearSoFarMeterFill');
        if (fill) fill.style.width = `${done}%`;
        meter.setAttribute('aria-valuenow', String(done));
        setText('yearSoFarDaysLeft', daysLeft === 1 ? '1 day left' : `${daysLeft} days left`);
      }
    }
    const opens = typeof data.recap_opens === 'string' ? data.recap_opens : 'December 1';
    const since = typeof data.since === 'string' && data.since ? ` Counting from ${data.since}, when OmniTrackr started dating what you finish.` : '';
    setText('yearSoFarNote', `Your full recap opens ${opens}, with a story image to post.${since}`);
    const link = $('yearSoFarLink');
    if (link) link.href = safeLink(data.url, year);
    card.hidden = false;
  }

  function refreshYearSoFar() {
    if (!$('yearSoFar')) return Promise.resolve();
    if (state.pending) return state.pending;
    if (state.loadedAt && Date.now() - state.loadedAt < REUSE_MS) return Promise.resolve();
    const request = ++state.request;
    state.pending = fetch('/api/year-in-review-so-far', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (request !== state.request) return;
        render(data);
        if (data) state.loadedAt = Date.now();
      })
      .catch(() => { /* the card is optional */ })
      .finally(() => { state.pending = null; });
    return state.pending;
  }

  function resetYearSoFar() {
    state.request += 1;
    state.pending = null;
    state.loadedAt = 0;
    const card = $('yearSoFar');
    if (card) card.hidden = true;
  }

  function hideUntilDecember() {
    const card = $('yearSoFar');
    if (!card) return;
    try { localStorage.setItem(hiddenKey(card.dataset.year || ''), '1'); } catch (error) { /* hides for this visit */ }
    card.hidden = true;
  }

  showRecapBanner();
  if ($('yearSoFar') && new Date().getMonth() === NOVEMBER) refreshYearSoFar();
  const dismiss = $('yearSoFarDismiss');
  if (dismiss && typeof dismiss.addEventListener === 'function') dismiss.addEventListener('click', hideUntilDecember);
  if (typeof window !== 'undefined') {
    window.refreshYearSoFar = () => (new Date().getMonth() === NOVEMBER ? refreshYearSoFar() : Promise.resolve());
    window.resetYearSoFar = resetYearSoFar;
  }
}());
