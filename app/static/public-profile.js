// Account → Public profile settings. Server text is only ever set as textContent.
(function () {
  'use strict';

  const BIO_MAX = 280;
  const FIELDS = {
    show_stats: 'profileShowStats',
    show_favorites: 'profileShowFavorites',
    show_reviews: 'profileShowReviews',
    show_collections: 'profileShowCollections',
  };
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

  function absoluteUrl(path) {
    try { return new URL(path, window.location.origin).href; } catch (error) { return path; }
  }

  function updateCount() {
    const bio = $('profileBio');
    const count = $('profileBioCount');
    if (!bio || !count) return;
    const length = bio.value.length;
    count.textContent = `${length}/${BIO_MAX}`;
    count.classList.toggle('is-over', length > BIO_MAX);
  }

  function showLink(settings) {
    const row = $('profileLinkRow');
    const link = $('profileLink');
    if (!row || !link) return;
    const path = settings && typeof settings.url === 'string' && settings.url.startsWith('/u/') ? settings.url : null;
    row.hidden = !(path && settings.enabled);
    if (path) {
      link.href = path;
      link.textContent = absoluteUrl(path).replace(/^https?:\/\//, '');
    }
  }

  function apply(settings) {
    loaded = settings;
    $('profileEnabled').checked = !!settings.enabled;
    $('profileBio').value = settings.bio || '';
    Object.entries(FIELDS).forEach(([field, id]) => { $(id).checked = settings[field] !== false; });
    showLink(settings);
    updateCount();
    const notes = [];
    if (Array.isArray(settings.private_categories) && settings.private_categories.length) {
      notes.push(`Private categories stay hidden: ${settings.private_categories.join(', ')}.`);
    }
    if (settings.statistics_private) notes.push('Library counts stay hidden because your statistics are private.');
    const note = $('profilePrivateNote');
    note.textContent = notes.join(' ');
    note.hidden = notes.length === 0;
  }

  async function load() {
    if (!$('publicProfileForm')) return;
    message('profileError', '');
    message('profileSuccess', '');
    try {
      const response = await fetch(`${apiBase()}/api/profile/settings`, fetchOptions());
      if (!response.ok) throw new Error('load failed');
      apply(await response.json());
    } catch (error) {
      message('profileError', 'Could not load your public profile settings.');
    }
  }

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    message('profileError', '');
    message('profileSuccess', '');
    const bio = $('profileBio').value;
    if (bio.length > BIO_MAX) {
      message('profileError', `Keep your bio to ${BIO_MAX} characters.`);
      return;
    }
    const body = { enabled: $('profileEnabled').checked, bio };
    Object.entries(FIELDS).forEach(([field, id]) => { body[field] = $(id).checked; });
    saving = true;
    $('profileSave').disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/profile/settings`, fetchOptions({
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Could not save your public profile.';
        message('profileError', detail);
        return;
      }
      apply(data);
      message('profileSuccess', data.enabled ? 'Saved. Your public profile is on.' : 'Saved. Your public profile is off.');
    } catch (error) {
      message('profileError', 'Could not save your public profile.');
    } finally {
      saving = false;
      $('profileSave').disabled = false;
    }
  }

  async function copyLink() {
    const link = $('profileLink');
    if (!link || !loaded || !loaded.url) return;
    const url = absoluteUrl(loaded.url);
    try {
      await navigator.clipboard.writeText(url);
      message('profileSuccess', 'Link copied.');
    } catch (error) {
      message('profileSuccess', url);
    }
  }

  function wrapAccountLoader() {
    const original = window.loadAccountInfo;
    if (typeof original !== 'function' || original.__publicProfileWrapped) return;
    const wrapped = async function () {
      const result = await original.apply(this, arguments);
      load();
      return result;
    };
    wrapped.__publicProfileWrapped = true;
    window.loadAccountInfo = wrapped;
  }

  async function openFromHash(attempt = 0) {
    if (window.location.hash !== '#public-profile') return;
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn || typeof window.openAccountModal !== 'function') {
      // The dashboard may still be restoring the session.
      if (attempt < 10) setTimeout(() => openFromHash(attempt + 1), 500);
      return;
    }
    await window.openAccountModal();
    const section = $('publicProfileSection');
    if (section && section.scrollIntoView) section.scrollIntoView({ block: 'start' });
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keep the hash */ }
  }

  function init() {
    const form = $('publicProfileForm');
    if (!form) return;
    form.addEventListener('submit', save);
    $('profileBio').addEventListener('input', updateCount);
    $('profileCopyLink').addEventListener('click', copyLink);
    wrapAccountLoader();
    updateCount();
    setTimeout(openFromHash, 600);
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.PublicProfileSettings = { load, apply };
  if (typeof module !== 'undefined' && module.exports) module.exports = { load, apply, save };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
