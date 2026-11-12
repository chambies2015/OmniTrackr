// Awards season: the ballot on /awards/<show> and the dashboard card.
// Server text is only ever set as textContent.
(function () {
  'use strict';

  const FLASH_KEY = 'omnitrackr_ballot_flash';
  const $ = id => document.getElementById(id);

  function draftKey(show) {
    return `omnitrackr_ballot_${show}`;
  }

  function readStorage(store, key) {
    try { return window[store].getItem(key); } catch (error) { return null; }
  }

  function writeStorage(store, key, value) {
    try {
      if (value === null) window[store].removeItem(key);
      else window[store].setItem(key, value);
    } catch (error) { /* storage blocked: the ballot still works for this visit */ }
  }

  function readDraft(show) {
    try {
      const saved = JSON.parse(readStorage('localStorage', draftKey(show)) || '{}');
      return saved && typeof saved === 'object' && !Array.isArray(saved) ? saved : {};
    } catch (error) {
      return {};
    }
  }

  function countText(picked, total) {
    if (total > 0 && picked >= total) return `All ${total} picked`;
    return `${picked} of ${total} picked`;
  }

  // Picks made before signing up fill only the categories the member hasn't picked since.
  function mergeDraft(draft, saved) {
    const extra = {};
    Object.keys(draft || {}).forEach(category => {
      if (typeof draft[category] === 'string' && !(saved && saved[category])) extra[category] = draft[category];
    });
    return extra;
  }

  function apiErrorText(body, fallback) {
    if (body && typeof body.detail === 'string') return body.detail;
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
  async function shareLink(url, name) {
    const text = `My ${name} ballot on OmniTrackr`;
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
      return 'Link copied. It shows your picks and nothing from your library.';
    } catch (error) {
      return `Your link: ${url}`;
    }
  }

  function reloadWith(message) {
    writeStorage('sessionStorage', FLASH_KEY, message);
    window.location.hash = 'ballot';
    window.location.reload();
  }

  // ---------------------------------------------------------------- the show page

  function initBallot(section) {
    const show = section.dataset.show;
    const name = section.dataset.name || 'awards';
    const member = section.dataset.member === '1';
    const open = section.dataset.state === 'open';
    const total = Number(section.dataset.total) || 0;
    const api = `/api/awards/${encodeURIComponent(show)}`;
    const form = section.querySelector('[data-award-form]');
    const statusNode = section.querySelector('[data-award-status]');
    let busy = false;
    let resetArmed = false;
    let saveTimer = null;
    let pending = {};

    function status(text, tone) {
      if (!statusNode) return;
      statusNode.textContent = text || '';
      if (tone) statusNode.dataset.tone = tone; else delete statusNode.dataset.tone;
    }

    function picks() {
      const chosen = {};
      if (!form) return chosen;
      form.querySelectorAll('input[type="radio"]:checked').forEach(input => { chosen[input.name] = input.value; });
      return chosen;
    }

    function paint() {
      if (!form) return;
      const chosen = picks();
      form.querySelectorAll('.aw-cat').forEach(category => {
        const key = category.dataset.category;
        category.querySelectorAll('.aw-nom').forEach(row => {
          row.classList.toggle('aw-nom--picked', chosen[key] === row.dataset.nominee);
        });
        const clear = category.querySelector('[data-award-clear]');
        if (clear) clear.hidden = !chosen[key];
        const jump = section.querySelector(`[data-award-jump="${key}"]`);
        if (jump) jump.dataset.done = chosen[key] ? '1' : '0';
      });
      const picked = Object.keys(chosen).length;
      const count = section.querySelector('[data-award-count]');
      if (count) count.textContent = countText(picked, total);
      const fill = section.querySelector('.aw-progress__fill');
      if (fill) fill.style.width = `${total ? Math.round((100 * picked) / total) : 0}%`;
      const share = section.querySelector('[data-award-action="share"]');
      if (share && member) share.hidden = picked === 0;
    }

    function apply(values) {
      if (!form) return;
      Object.keys(values || {}).forEach(category => {
        form.querySelectorAll('input[type="radio"]').forEach(input => {
          if (input.name === category && input.value === values[category]) input.checked = true;
        });
      });
    }

    async function flush() {
      saveTimer = null;
      const changes = pending;
      pending = {};
      if (!Object.keys(changes).length) return;
      try {
        await send('PUT', `${api}/ballot`, { picks: changes });
        status('Saved.');
      } catch (error) {
        status(error.message, 'error');
      }
    }

    function queue(category, nominee) {
      if (!member) {
        const draft = readDraft(show);
        if (nominee) draft[category] = nominee; else delete draft[category];
        writeStorage('localStorage', draftKey(show), Object.keys(draft).length ? JSON.stringify(draft) : null);
        status('Kept in this browser. Make a free account to save it.');
        return;
      }
      pending[category] = nominee;
      status('Saving…');
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(flush, 400);
    }

    const flash = readStorage('sessionStorage', FLASH_KEY);
    if (flash) {
      writeStorage('sessionStorage', FLASH_KEY, null);
      status(flash);
    }

    if (form && open) {
      const draft = readDraft(show);
      if (!member) {
        apply(draft);
      } else if (Object.keys(draft).length) {
        // Picks made before signing up: keep them for categories not picked since, then drop the draft.
        const extra = mergeDraft(draft, picks());
        writeStorage('localStorage', draftKey(show), null);
        if (Object.keys(extra).length) {
          apply(extra);
          send('PUT', `${api}/ballot`, { picks: extra })
            .then(() => status('The picks you made before signing up are saved to your account.'))
            .catch(error => status(error.message, 'error'));
        }
      }
      form.addEventListener('change', event => {
        const input = event.target;
        if (!input || input.type !== 'radio') return;
        paint();
        queue(input.name, input.value);
      });
      form.addEventListener('click', event => {
        const clear = event.target.closest('[data-award-clear]');
        if (!clear) return;
        const category = clear.dataset.awardClear;
        form.querySelectorAll('input[type="radio"]').forEach(input => { if (input.name === category) input.checked = false; });
        paint();
        queue(category, null);
      });
    }
    paint();

    section.addEventListener('click', async event => {
      const add = event.target.closest('[data-award-add]');
      if (add) {
        if (add.disabled) return;
        add.disabled = true;
        try {
          const data = await send('POST', `${api}/add`, { id: add.dataset.awardAdd });
          const chip = document.createElement('a');
          chip.className = 'aw-chip';
          chip.href = data.library_url;
          chip.textContent = 'In your library ✓';
          // The same title can be nominated in several categories: mark them all.
          document.querySelectorAll('[data-award-add]').forEach(button => {
            if (button.dataset.awardAdd === add.dataset.awardAdd) button.replaceWith(chip.cloneNode(true));
          });
          status(data.state === 'created' ? `${data.title} is in your library.` : `${data.title} was already in your library.`);
        } catch (error) {
          add.disabled = false;
          status(error.message, 'error');
        }
        return;
      }

      const winner = event.target.closest('[data-award-winner]');
      if (winner) {
        if (busy) return;
        busy = true;
        try {
          const undo = winner.getAttribute('aria-pressed') === 'true';
          await send('PUT', `${api}/results`, { category: winner.dataset.awardCategory, nominee: undo ? null : winner.dataset.awardWinner });
          writeStorage('sessionStorage', FLASH_KEY, undo ? 'Winner removed.' : 'Winner saved.');
          window.location.hash = `cat-${winner.dataset.awardCategory}`;
          window.location.reload();
        } catch (error) {
          status(error.message, 'error');
          busy = false;
        }
        return;
      }

      const button = event.target.closest('[data-award-action]');
      if (!button || busy) return;
      const action = button.dataset.awardAction;
      if (action === 'signup') {
        if (!Object.keys(picks()).length) { status('Pick at least one winner first.', 'error'); return; }
        beacon('ballot_signup_clicked');
        window.location.assign(section.dataset.signup);
        return;
      }
      if (action === 'reset' && !resetArmed) {
        resetArmed = true;
        button.textContent = 'Press again to clear every pick';
        return;
      }
      busy = true;
      try {
        if (saveTimer) { clearTimeout(saveTimer); await flush(); }
        if (action === 'share') {
          const data = await send('PUT', `${api}/share`);
          const message = data.url ? await shareLink(data.url, name) : '';
          if (section.dataset.shared !== '1') {
            reloadWith(message || 'Your ballot link is live.');
            return;
          }
          status(message);
        } else if (action === 'unshare') {
          await send('DELETE', `${api}/share`);
          reloadWith('Sharing stopped. The old link no longer works.');
        } else if (action === 'reset' || action === 'unfollow') {
          await send('DELETE', `${api}/ballot`);
          reloadWith(action === 'reset' ? 'Ballot cleared.' : 'Reminder removed.');
        } else if (action === 'follow') {
          await send('PUT', `${api}/follow`);
          reloadWith('Done. You will get a notification when the ballot opens.');
        }
      } catch (error) {
        status(error.message, 'error');
      } finally {
        busy = false;
      }
    });
  }

  // ---------------------------------------------------------------- dashboard card

  const card = { request: 0 };

  function cardDismissKey(data) {
    let who = 'member';
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) who = String(user.id);
    } catch (error) { /* shared key */ }
    return `omnitrackr_ballot_card_hidden_${who}_${data.slug}_${data.state === 'open' ? 'open' : 'results'}`;
  }

  function cardCopy(data) {
    const days = data.days_left;
    const left = days === 0 ? 'Picks lock today' : `${days} day${days === 1 ? '' : 's'} until picks lock`;
    if (data.state !== 'open') {
      return {
        eyebrow: data.name,
        title: `You called ${data.correct} of ${data.judged}`,
        summary: data.state === 'results'
          ? 'Every winner is in. See which ones you got and how other members voted.'
          : `${data.decided} of ${data.total} winners announced so far.`,
        action: 'See how it went',
        href: `${data.page}#ballot`,
      };
    }
    if (!data.picked) {
      return {
        eyebrow: data.name,
        title: 'The nominees are in. Pick the winners',
        summary: `${data.total} categories. ${left}, and you get a score after the show.`,
        action: 'Fill in your ballot',
        href: `${data.page}#ballot`,
      };
    }
    if (data.picked < data.total) {
      return {
        eyebrow: data.name,
        title: `${data.picked} of ${data.total} picked`,
        summary: `${left}. You can skip categories, and change any pick until then.`,
        action: 'Finish your ballot',
        href: `${data.page}#ballot`,
      };
    }
    return {
      eyebrow: data.name,
      title: 'Your ballot is in',
      summary: `${left}. Share it so friends can try to beat your score.`,
      action: data.shared ? 'See your ballot' : 'Share your ballot',
      href: data.shared && data.url ? data.url : `${data.page}#ballot`,
    };
  }

  function renderCard(data) {
    const section = $('awardsBallot');
    if (!section) return;
    if (!data || !data.show || readStorage('localStorage', cardDismissKey(data)) === '1') {
      section.hidden = true;
      return;
    }
    const copy = cardCopy(data);
    $('awardsBallotEyebrow').textContent = copy.eyebrow;
    $('awardsBallotTitle').textContent = copy.title;
    $('awardsBallotSummary').textContent = copy.summary;
    const link = $('awardsBallotLink');
    link.textContent = copy.action;
    link.href = copy.href;
    section.dataset.dismissKey = cardDismissKey(data);
    section.hidden = false;
  }

  // The shows here run from The Game Awards in December to the Oscars in March, and nominees
  // start landing in November. From April to October there is nothing to ask the server for.
  function cardSeason(now) {
    const month = (now || new Date()).getUTCMonth();
    return month >= 10 || month <= 2;
  }

  async function refreshAwardsBallot() {
    const section = $('awardsBallot');
    if (!section) return;
    if (!cardSeason()) { section.hidden = true; return; }
    const request = ++card.request;
    try {
      const response = await fetch('/api/awards/card', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== card.request) return;
      renderCard(data);
    } catch (error) {
      // The card is optional; the dashboard works without it.
    }
  }

  function resetAwardsBallot() {
    card.request += 1;
    const section = $('awardsBallot');
    if (section) section.hidden = true;
  }

  function initCard() {
    const dismiss = $('awardsBallotDismiss');
    if (!dismiss) return;
    dismiss.addEventListener('click', () => {
      const section = $('awardsBallot');
      if (section && section.dataset.dismissKey) writeStorage('localStorage', section.dataset.dismissKey, '1');
      if (section) section.hidden = true;
    });
  }

  function init() {
    const section = $('ballot');
    if (section && section.dataset.show) initBallot(section);
    initCard();
  }

  if (typeof window !== 'undefined') {
    window.refreshAwardsBallot = refreshAwardsBallot;
    window.resetAwardsBallot = resetAwardsBallot;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { countText, mergeDraft, cardCopy, cardSeason };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
