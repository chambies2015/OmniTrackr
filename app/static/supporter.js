// Account → Supporter: Ko-fi supporter code, status and cosmetic perks. Server text is only ever set as textContent.
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  let loaded = null;
  let saving = false;

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
      const head = `Thank you for supporting OmniTrackr${since ? ` since ${since}` : ''}!`;
      if (status.monthly) return `${head} Your perks renew with your Ko-fi membership.`;
      return `${head}${until ? ` Your perks are on until ${until}.` : ''}`;
    }
    if (status.since) {
      return 'Your supporter perks have ended. Support again on Ko-fi any time to switch them back on.';
    }
    return null;
  }

  function renderAccents(status) {
    const box = $('supporterAccents');
    if (!box) return;
    box.querySelectorAll('label').forEach(node => node.remove());
    const options = [null].concat(Array.isArray(status.accents) ? status.accents : []);
    options.forEach(accent => {
      const label = document.createElement('label');
      label.className = 'supporter-accent';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'supporterAccent';
      input.value = accent || '';
      input.checked = (status.accent || null) === accent;
      input.disabled = !status.active;
      const swatch = document.createElement('span');
      swatch.className = `supporter-accent__swatch supporter-accent__swatch--${accent || 'none'}`;
      swatch.setAttribute('aria-hidden', 'true');
      const text = document.createElement('span');
      text.textContent = accent || 'Default';
      label.append(input, swatch, text);
      box.appendChild(label);
    });
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
    renderAccents(status);
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
    const picked = document.querySelector('input[name="supporterAccent"]:checked');
    if (loaded.active && picked) body.accent = picked.value || null;
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

  function init() {
    if (!$('supporterSection')) return;
    $('supporterForm').addEventListener('submit', save);
    $('supporterCopyCode').addEventListener('click', copyCode);
    wrapAccountLoader();
    setTimeout(openFromHash, 600);
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.SupporterSettings = { load, apply };
  if (typeof module !== 'undefined' && module.exports) module.exports = { load, apply, statusText };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
