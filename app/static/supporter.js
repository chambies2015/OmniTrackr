// Account → Supporter: Ko-fi supporter code, status and cosmetic perks. Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  let loaded = null;
  let saving = false;
  const CHECKED_KEY = 'ot-supporter-checked';
  const WELCOMED_KEY = 'ot-supporter-welcomed';
  const RECHECK_MS = 6 * 60 * 60 * 1000;

  function stored(key) {
    try { return window.localStorage.getItem(key); } catch (error) { return null; }
  }

  function store(key, value) {
    try { window.localStorage.setItem(key, value); } catch (error) { /* private mode */ }
  }

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function message(id, text) {
    const node = $(id);
    if (!node) return;
    node.textContent = text || '';
    node.style.display = text ? 'block' : 'none';
  }

  function monthYear(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }

  function longDate(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' });
  }

  function statusText(status) {
    if (status.active) {
      const since = monthYear(status.since);
      const until = longDate(status.active_until);
      const who = status.founding ? 'Thank you for being a founding supporter of OmniTrackr' : 'Thank you for supporting OmniTrackr';
      const head = `${who}${since ? ` since ${since}` : ''}!`;
      if (status.member && status.tier_name) return `${head} You're a ${status.tier_name} member, so your perks renew with your Ko-fi membership.`;
      if (status.monthly) return `${head} Your perks renew with your Ko-fi membership.`;
      return `${head}${until ? ` Your perks are on until ${until}.` : ''}`;
    }
    if (status.since) {
      return 'Your supporter perks have ended. Support again on Ko-fi any time to switch them back on.';
    }
    return null;
  }

  const ACCENT_NAME = /^[a-z]{1,16}$/;

  function renderPreview(status, accent) {
    const box = $('supporterPreview');
    const badge = $('supporterPreviewBadge');
    if (!box || !badge) return;
    box.hidden = !status.active || !status.level;
    if (box.hidden) return;
    badge.className = 'supporter-preview__badge';
    if (status.founding) badge.classList.add('supporter-preview__badge--founding');
    if (accent && ACCENT_NAME.test(accent)) badge.classList.add(`supporter-preview__badge--${accent}`);
    badge.textContent = `${status.founding ? '★' : '♥'} ${status.level}`;
  }

  function renderAccents(status) {
    const box = $('supporterAccents');
    if (!box) return;
    box.querySelectorAll('label, .supporter-accent__hint').forEach(node => node.remove());
    const unlocked = new Set(Array.isArray(status.unlocked_accents) ? status.unlocked_accents : []);
    const options = [null].concat(Array.isArray(status.accents) ? status.accents.filter(a => ACCENT_NAME.test(a)) : []);
    let locked = false;
    options.forEach(accent => {
      const label = document.createElement('label');
      label.className = 'supporter-accent';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'supporterAccent';
      input.value = accent || '';
      input.checked = (status.accent || null) === accent;
      input.disabled = !status.active || (accent !== null && !unlocked.has(accent));
      if (status.active && input.disabled) {
        locked = true;
        label.classList.add('supporter-accent--locked');
      }
      input.addEventListener('change', () => { renderPreview(status, accent); tintBanners(accent); });
      const swatch = document.createElement('span');
      swatch.className = `supporter-accent__swatch supporter-accent__swatch--${accent || 'none'}`;
      swatch.setAttribute('aria-hidden', 'true');
      const text = document.createElement('span');
      text.textContent = accent || 'Default';
      label.append(input, swatch, text);
      box.appendChild(label);
    });
    if (locked) {
      const hint = document.createElement('p');
      hint.className = 'info-text supporter-accent__hint';
      hint.textContent = `Gold unlocks for founding supporters and after ${Number(status.gold_months) || 6} months of support.`;
      box.appendChild(hint);
    }
  }

  const BANNER_NAMES = {
    aurora: 'Aurora', filmstrip: 'Film strip', pixels: 'Pixels', pages: 'Pages', vinyl: 'Vinyl', stars: 'Stars',
    neon: 'Neon', marquee: 'Marquee', comic: 'Comic',
  };

  const DAY_MS = 24 * 60 * 60 * 1000;

  // The membership pitch, or what the member's tier adds. Null hides the box.
  function membershipText(status) {
    if (status.member) {
      if (status.tier === 'directors_cut') return null;
      if (status.tier === 'season_pass') {
        return 'Your Season Pass includes the member themes, frames and banners, and lets your banner and frame move. Director\'s Cut adds gold and your name in the credits at the top of the supporter wall.';
      }
      return `Your ${status.tier_name || 'membership'} includes the Midnight and Matinee themes, the neon and orbit frames and three member banners. Season Pass lets your banner and frame move, and Director's Cut adds gold and a spot in the wall's credits.`;
    }
    if (status.active) {
      const until = status.active_until ? new Date(status.active_until) : null;
      const days = until && !Number.isNaN(until.getTime()) ? Math.ceil((until.getTime() - Date.now()) / DAY_MS) : null;
      const ending = days !== null && days <= 7 ? `Your perks end in ${days <= 1 ? 'a day' : `${days} days`}. ` : '';
      return `${ending}A monthly membership keeps your perks on without topping up, and adds two member app themes, two frames and three banners. Tiers start at $3 a month.`;
    }
    return 'Monthly members also get the Midnight and Matinee app themes, extra frames and banners, and higher tiers make them move and add gold. Tiers start at $3 a month.';
  }

  function renderMembership(status) {
    const box = $('supporterMembership');
    if (!box) return;
    const text = membershipText(status);
    box.hidden = !text;
    if (!text) return;
    $('supporterMembershipText').textContent = text;
    const link = $('supporterTiersLink');
    if (link && typeof status.tiers_url === 'string' && status.tiers_url.startsWith('https://ko-fi.com/')) link.href = status.tiers_url;
    if (link) link.textContent = status.member ? 'Change tier on Ko-fi ↗' : 'See memberships ↗';
  }

  // What each way of supporting adds, so the choice is clear before anyone goes to Ko-fi.
  // Prices come from the server (supporters.TIERS); the wording matches /supporters.
  const TIER_PERKS = {
    popcorn: 'Member tag on your profile, the Midnight and Matinee app themes, neon and orbit frames, and three member banners',
    season_pass: 'Everything in Popcorn, and your banner can move',
    directors_cut: 'Everything in Season Pass, plus gold and your name in the credits at the top of the supporter wall',
  };

  function renderTiers(status) {
    const list = $('supporterTiers');
    if (!list) return;
    list.replaceChildren();
    const tip = document.createElement('li');
    tip.className = 'supporter-tier';
    const tipName = document.createElement('strong');
    tipName.textContent = 'One-time tip';
    const tipPrice = document.createElement('span');
    tipPrice.className = 'supporter-tier__price';
    tipPrice.textContent = 'Any amount';
    const tipPerks = document.createElement('span');
    tipPerks.className = 'supporter-tier__perks';
    tipPerks.textContent = 'Supporter badge, app themes, profile colors, banners and frames, and six showcase spots for 30 days';
    tip.append(tipName, tipPrice, tipPerks);
    list.appendChild(tip);
    (Array.isArray(status.tiers) ? status.tiers : []).forEach(tier => {
      if (!tier || typeof tier.slug !== 'string' || typeof tier.name !== 'string' || !Number.isFinite(tier.price)) return;
      const item = document.createElement('li');
      item.className = 'supporter-tier';
      if (status.member && status.tier === tier.slug) item.classList.add('supporter-tier--current');
      const name = document.createElement('strong');
      name.textContent = tier.name;
      const price = document.createElement('span');
      price.className = 'supporter-tier__price';
      price.textContent = `$${tier.price} a month`;
      const perks = document.createElement('span');
      perks.className = 'supporter-tier__perks';
      perks.textContent = TIER_PERKS[tier.slug] || 'Monthly member extras';
      item.append(name, price, perks);
      if (item.classList.contains('supporter-tier--current')) {
        const badge = document.createElement('span');
        badge.className = 'supporter-tier__current';
        badge.textContent = 'Your tier';
        item.appendChild(badge);
      }
      list.appendChild(item);
    });
  }

  function renderMotion(status) {
    const input = $('supporterMotion');
    if (!input) return;
    input.checked = status.banner_motion === true;
    input.disabled = !status.can_animate;
    const hint = $('supporterMotionHint');
    if (hint) hint.hidden = !!status.can_animate;
  }

  // Banner and frame swatches take the accent color that's picked right now, like the profile will.
  function tintBanners(accent) {
    ['supporterBanners', 'supporterFrames'].forEach(id => {
      const box = $(id);
      if (!box) return;
      Array.from(box.classList).filter(name => name.startsWith('supporter-banners--accent-'))
        .forEach(name => box.classList.remove(name));
      if (accent && ACCENT_NAME.test(accent)) box.classList.add(`supporter-banners--accent-${accent}`);
    });
  }

  const THEME_NAMES = {
    lagoon: 'Lagoon', sunset: 'Sunset', sakura: 'Sakura', ocean: 'Ocean', forest: 'Forest', crimson: 'Crimson',
    gilded: 'Gilded', midnight: 'Midnight', matinee: 'Matinee',
  };
  const FRAME_NAMES = { halo: 'Halo', film: 'Film reel', sparkle: 'Sparkle', pixel: 'Pixel', neon: 'Neon', orbit: 'Orbit' };

  function names(list) {
    return Array.isArray(list) ? list.filter(name => typeof name === 'string' && ACCENT_NAME.test(name)) : [];
  }

  function themeApi() {
    return window.OmniAppTheme && typeof window.OmniAppTheme.preview === 'function' ? window.OmniAppTheme : null;
  }

  function themeSwatch(theme) {
    const swatch = document.createElement('span');
    swatch.className = `supporter-theme__swatch supporter-theme__swatch--${theme || 'default'}`;
    swatch.setAttribute('aria-hidden', 'true');
    swatch.append(document.createElement('span'), document.createElement('span'));
    return swatch;
  }

  function hintLine(box, text) {
    const hint = document.createElement('p');
    hint.className = 'info-text supporter-accent__hint';
    hint.textContent = text;
    box.appendChild(hint);
  }

  // App theme: what the member's own app looks like. Picking one shows it right away; saving keeps it.
  function renderThemes(status) {
    const box = $('supporterThemes');
    if (!box) return;
    box.querySelectorAll('label, .supporter-accent__hint').forEach(node => node.remove());
    const gold = names(status.gold_themes);
    const member = names(status.member_themes);
    const unlocked = new Set(names(status.unlocked_themes));
    const options = [null].concat(names(status.themes), gold, member);
    let lockedGold = false;
    let lockedMember = false;
    options.forEach(theme => {
      const label = document.createElement('label');
      label.className = 'supporter-theme';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'supporterTheme';
      input.value = theme || '';
      input.checked = (status.app_theme || null) === theme;
      input.disabled = !status.active || (theme !== null && !unlocked.has(theme));
      if (status.active && input.disabled) {
        label.classList.add('supporter-theme--locked');
        if (gold.includes(theme)) lockedGold = true;
        if (member.includes(theme)) lockedMember = true;
      }
      if (member.includes(theme)) label.classList.add('supporter-theme--member');
      input.addEventListener('change', () => { const api = themeApi(); if (api) api.preview(theme); });
      const text = document.createElement('span');
      text.textContent = theme ? (THEME_NAMES[theme] || theme) : 'Default';
      label.append(input, themeSwatch(theme), text);
      box.appendChild(label);
    });
    if (!status.active) hintLine(box, 'Your theme comes back on when your support does.');
    else if (lockedMember) hintLine(box, 'Midnight and Matinee come with a monthly membership.');
    if (status.active && lockedGold) hintLine(box, `Gilded unlocks with gold: for founding supporters and after ${Number(status.gold_months) || 6} months of support.`);
  }

  function frameSample(frame) {
    const wrap = document.createElement('span');
    wrap.className = frame ? `avatar-frame avatar-frame--${frame}` : 'avatar-frame';
    wrap.setAttribute('aria-hidden', 'true');
    const face = document.createElement('span');
    face.className = 'avatar-frame__face';
    const user = typeof getUser === 'function' ? getUser() : null;
    face.textContent = user && typeof user.username === 'string' && user.username ? user.username.charAt(0).toUpperCase() : 'A';
    wrap.appendChild(face);
    if (frame) {
      const art = document.createElement('span');
      art.className = 'avatar-frame__art';
      wrap.appendChild(art);
    }
    return wrap;
  }

  function renderFrames(status) {
    const box = $('supporterFrames');
    if (!box) return;
    box.querySelectorAll('label, .supporter-accent__hint').forEach(node => node.remove());
    const member = names(status.member_frames);
    const unlocked = new Set(names(status.unlocked_frames));
    const options = [null].concat(names(status.frames), member);
    let lockedMember = false;
    options.forEach(frame => {
      const label = document.createElement('label');
      label.className = 'supporter-frame';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'supporterFrame';
      input.value = frame || '';
      input.checked = (status.frame || null) === frame;
      input.disabled = !status.active || (frame !== null && !unlocked.has(frame));
      if (status.active && input.disabled && member.includes(frame)) {
        lockedMember = true;
        label.classList.add('supporter-frame--locked');
      }
      if (member.includes(frame)) label.classList.add('supporter-frame--member');
      const swatch = document.createElement('span');
      swatch.className = 'supporter-frame__swatch';
      swatch.appendChild(frameSample(frame));
      const text = document.createElement('span');
      text.textContent = frame ? (FRAME_NAMES[frame] || frame) : 'None';
      label.append(input, swatch, text);
      box.appendChild(label);
    });
    if (!status.active) hintLine(box, 'Frames come back on when your support does.');
    else if (lockedMember) hintLine(box, 'Neon and orbit come with a monthly membership.');
  }

  // Not supporting right now: let them try the app themes on this page, nothing saved.
  function renderTry(status) {
    const box = $('supporterTry');
    const list = $('supporterTryList');
    if (!box || !list) return;
    box.hidden = !!status.active;
    if (box.hidden) return;
    list.replaceChildren();
    const options = [null].concat(names(status.themes), names(status.gold_themes), names(status.member_themes));
    options.forEach(theme => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'supporter-try__theme';
      button.setAttribute('aria-pressed', theme === null ? 'true' : 'false');
      const text = document.createElement('span');
      text.textContent = theme ? (THEME_NAMES[theme] || theme) : 'Default';
      button.append(themeSwatch(theme), text);
      button.addEventListener('click', () => {
        const api = themeApi();
        if (!api) return;
        if (theme) api.preview(theme); else api.restore();
        list.querySelectorAll('button').forEach(other => other.setAttribute('aria-pressed', other === button ? 'true' : 'false'));
      });
      list.appendChild(button);
    });
  }

  // Keep this device's copy of the theme in step with what the server allows right now.
  function syncTheme(status) {
    const api = themeApi();
    if (api && typeof api.remember === 'function') api.remember(status && typeof status.shown_theme === 'string' ? status.shown_theme : null);
  }

  function renderBanners(status) {
    const box = $('supporterBanners');
    if (!box) return;
    box.querySelectorAll('label, .supporter-accent__hint').forEach(node => node.remove());
    const memberBanners = Array.isArray(status.member_banners) ? status.member_banners.filter(b => ACCENT_NAME.test(b)) : [];
    const unlocked = new Set(Array.isArray(status.unlocked_banners) ? status.unlocked_banners : []);
    const options = [null].concat(Array.isArray(status.banners) ? status.banners.filter(b => ACCENT_NAME.test(b)) : [], memberBanners);
    let lockedMember = false;
    options.forEach(banner => {
      const label = document.createElement('label');
      label.className = 'supporter-banner';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'supporterBanner';
      input.value = banner || '';
      input.checked = (status.banner || null) === banner;
      input.disabled = !status.active || (banner !== null && !unlocked.has(banner));
      if (status.active && input.disabled && memberBanners.includes(banner)) {
        lockedMember = true;
        label.classList.add('supporter-banner--locked');
      }
      if (memberBanners.includes(banner)) label.classList.add('supporter-banner--member');
      const swatch = document.createElement('span');
      swatch.className = banner ? 'supporter-banner__swatch' : 'supporter-banner__swatch supporter-banner__swatch--none';
      swatch.setAttribute('aria-hidden', 'true');
      if (banner) {
        // The art is drawn at profile size and scaled down, so the preview matches the real banner.
        const art = document.createElement('span');
        art.className = `supporter-banner__art profile-banner profile-banner--${banner}`;
        swatch.appendChild(art);
      }
      const text = document.createElement('span');
      text.textContent = banner ? (BANNER_NAMES[banner] || banner) : 'None';
      label.append(input, swatch, text);
      box.appendChild(label);
    });
    if (!status.active) {
      const hint = document.createElement('p');
      hint.className = 'info-text supporter-accent__hint';
      hint.textContent = 'Banners come back on when your support does.';
      box.appendChild(hint);
    } else if (lockedMember) {
      const hint = document.createElement('p');
      hint.className = 'info-text supporter-accent__hint';
      hint.textContent = 'Neon, marquee and comic come with a monthly membership.';
      box.appendChild(hint);
    }
    tintBanners(status.accent);
  }

  function apply(status) {
    loaded = status;
    $('supporterCode').textContent = status.code || '-';
    const link = $('supporterKofiLink');
    if (link && typeof status.kofi_url === 'string' && status.kofi_url.startsWith('https://ko-fi.com/')) {
      link.href = status.kofi_url;
    }
    const text = statusText(status);
    if (text) $('supporterStatus').textContent = text;
    const form = $('supporterForm');
    form.hidden = !status.since;
    $('supporterShowBadge').checked = status.show_badge !== false;
    if ($('supporterOnWall')) $('supporterOnWall').checked = status.on_wall === true;
    renderAccents(status);
    renderBanners(status);
    renderFrames(status);
    renderThemes(status);
    renderMotion(status);
    renderTry(status);
    syncTheme(status);
    renderMembership(status);
    renderTiers(status);
    renderPreview(status, status.accent);
  }

  async function load() {
    if (!$('supporterSection')) return;
    message('supporterError', '');
    message('supporterSuccess', '');
    try {
      const response = await fetch(`${apiBase()}/api/supporter`, fetchOptions());
      if (!response.ok) throw new Error('load failed');
      apply(await response.json());
    } catch (error) {
      message('supporterError', 'Could not load your supporter details.');
    }
  }

  async function save(event) {
    event.preventDefault();
    if (saving || !loaded) return;
    message('supporterError', '');
    message('supporterSuccess', '');
    const body = { show_badge: $('supporterShowBadge').checked };
    if ($('supporterOnWall')) body.on_wall = $('supporterOnWall').checked;
    const picked = document.querySelector('input[name="supporterAccent"]:checked');
    if (loaded.active && picked) body.accent = picked.value || null;
    const banner = document.querySelector('input[name="supporterBanner"]:checked');
    if (loaded.active && banner) body.banner = banner.value || null;
    if (loaded.can_animate && $('supporterMotion')) body.banner_motion = $('supporterMotion').checked;
    const frame = document.querySelector('input[name="supporterFrame"]:checked');
    if (loaded.active && frame) body.frame = frame.value || null;
    const theme = document.querySelector('input[name="supporterTheme"]:checked');
    if (loaded.active && theme) body.app_theme = theme.value || null;
    saving = true;
    $('supporterSave').disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/supporter`, fetchOptions({
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        message('supporterError', typeof data.detail === 'string' ? data.detail : 'Could not save your supporter settings.');
        return;
      }
      apply(data);
      message('supporterSuccess', 'Saved.');
    } catch (error) {
      message('supporterError', 'Could not save your supporter settings.');
    } finally {
      saving = false;
      $('supporterSave').disabled = false;
    }
  }

  // "Donated but don't see your badge?": a Ko-fi email gets a confirmation link; a transaction ID waits for the owner.
  function claimStatus(text, tone) {
    const node = $('supporterClaimStatus');
    if (!node) return;
    node.textContent = text || '';
    node.className = `supporter-claim__status${tone ? ` supporter-claim__status--${tone}` : ''}`;
  }

  let claiming = false;

  async function claim(event) {
    event.preventDefault();
    const input = $('supporterClaimValue');
    const value = input.value.trim();
    if (claiming) return;
    if (value.length < 3) {
      claimStatus('Type the email you used on Ko-fi, or the transaction ID from your receipt.', 'error');
      input.focus();
      return;
    }
    claiming = true;
    $('supporterClaimSubmit').disabled = true;
    claimStatus('Looking…');
    try {
      const response = await fetch(`${apiBase()}/api/supporter/claim`, fetchOptions({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      }));
      const data = await response.json().catch(() => ({}));
      if (response.status === 429) {
        claimStatus('That was a lot of tries. Wait an hour and try again, or write to us from the Contact page.', 'error');
        return;
      }
      if (!response.ok) {
        claimStatus(typeof data.detail === 'string' ? data.detail : 'Could not look that up. Please try again.', 'error');
        return;
      }
      claimStatus(data.message || '', data.status === 'none' ? '' : 'ok');
      if (data.supporter) apply(data.supporter);
    } catch (error) {
      claimStatus('Could not look that up. Check your connection and try again.', 'error');
    } finally {
      claiming = false;
      $('supporterClaimSubmit').disabled = false;
    }
  }

  async function copyCode() {
    if (!loaded || !loaded.code) return;
    try {
      await navigator.clipboard.writeText(loaded.code);
      message('supporterSuccess', 'Code copied. Paste it into your Ko-fi message.');
    } catch (error) {
      message('supporterSuccess', loaded.code);
    }
  }

  function wrapAccountLoader() {
    const original = window.loadAccountInfo;
    if (typeof original !== 'function' || original.__supporterWrapped) return;
    const wrapped = async function () {
      const result = await original.apply(this, arguments);
      load();
      return result;
    };
    wrapped.__supporterWrapped = true;
    window.loadAccountInfo = wrapped;
  }

  async function openFromHash(attempt = 0) {
    if (window.location.hash !== '#supporter') return;
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn || typeof window.openAccountModal !== 'function') {
      if (attempt < 10) setTimeout(() => openFromHash(attempt + 1), 500);
      return;
    }
    await window.openAccountModal();
    const section = $('supporterSection');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  async function openSettings() {
    if (typeof window.openAccountModal !== 'function') return;
    await window.openAccountModal();
    const section = $('supporterSection');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
  }

  function showWelcome(status) {
    if (document.querySelector('.supporter-welcome')) return;
    const box = document.createElement('aside');
    box.className = 'supporter-welcome';
    box.setAttribute('role', 'status');
    const title = document.createElement('strong');
    title.textContent = status.founding ? '★ You\'re a founding supporter!' : '♥ Your supporter perks are on!';
    const text = document.createElement('p');
    text.textContent = 'Thank you for keeping OmniTrackr running. Pick a color theme for your app, a banner and frame for your profile, and choose whether to join the supporter wall.';
    const actions = document.createElement('div');
    actions.className = 'supporter-welcome__actions';
    const pick = document.createElement('button');
    pick.type = 'button';
    pick.className = 'action-btn';
    pick.textContent = 'Style my profile';
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'supporter-welcome__close';
    close.textContent = 'Later';
    const dismiss = () => {
      store(WELCOMED_KEY, status.since || 'yes');
      box.remove();
    };
    pick.addEventListener('click', () => { dismiss(); openSettings(); });
    close.addEventListener('click', dismiss);
    actions.append(pick, close);
    box.append(title, text, actions);
    document.body.appendChild(box);
  }

  // Once a newly linked supporter opens the app, say thank you and point at their perks.
  async function checkWelcome(attempt = 0) {
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn) {
      if (attempt < 6) setTimeout(() => checkWelcome(attempt + 1), 1000);
      return;
    }
    const fromKofi = /(^|\.)ko-fi\.com$/i.test((() => { try { return new URL(document.referrer).hostname; } catch (e) { return ''; } })());
    const last = Number(stored(CHECKED_KEY)) || 0;
    const themeKnown = !themeApi() || typeof themeApi().known !== 'function' || themeApi().known();
    if (!fromKofi && themeKnown && Date.now() - last < RECHECK_MS) return;
    store(CHECKED_KEY, String(Date.now()));
    try {
      const response = await fetch(`${apiBase()}/api/supporter`, fetchOptions());
      if (!response.ok) return;
      const status = await response.json();
      syncTheme(status);
      if (status.active && stored(WELCOMED_KEY) !== (status.since || 'yes')) showWelcome(status);
    } catch (error) { /* the thank-you is optional */ }
  }

  function init() {
    if (!$('supporterSection')) return;
    $('supporterForm').addEventListener('submit', save);
    $('supporterCopyCode').addEventListener('click', copyCode);
    if ($('supporterClaimForm')) $('supporterClaimForm').addEventListener('submit', claim);
    wrapAccountLoader();
    setTimeout(openFromHash, 600);
    if (window.location.hash !== '#supporter') setTimeout(() => checkWelcome(), 2500);
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.SupporterSettings = { load, apply };
  if (typeof module !== 'undefined' && module.exports) module.exports = { load, apply, statusText, showWelcome, membershipText, claim, renderThemes, renderFrames, renderTry };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
