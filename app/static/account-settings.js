// Settings dialog: the section menu, links like /#settings-privacy, and a short
// "Saved" note that stays in view while the page scrolls. Saving itself stays in
// dashboard/account.js and the scripts that own each section (push.js fills the
// phone notifications panel).
(function () {
  const $ = id => document.getElementById(id);
  const GROUPS = ['profile', 'signin', 'privacy', 'notifications', 'data', 'membership', 'danger'];
  const TOAST_MS = 4000;
  let toastTimer = null;

  function groupFromHash(hash) {
    if (hash === '#settings') return 'profile';
    const match = /^#settings-([a-z]+)$/.exec(hash || '');
    return match && GROUPS.includes(match[1]) ? match[1] : null;
  }

  function markCurrent(key) {
    document.querySelectorAll('[data-settings-link]').forEach(link => {
      if (link.dataset.settingsLink === key) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  }

  function showGroup(key, { focus = true } = {}) {
    const group = $(`settings-${key}`);
    if (!group) return;
    markCurrent(key);
    // Scroll only the settings column, so the dialog's header and menu stay put.
    const panels = $('accountSettingsPanels');
    const top = Math.max(0, group.offsetTop - 4);
    if (panels && typeof panels.scrollTo === 'function') {
      // Older browsers reject 'instant'; a plain jump is fine there.
      try { panels.scrollTo({ top, behavior: 'instant' }); } catch (error) { panels.scrollTop = top; }
    } else if (typeof group.scrollIntoView === 'function') group.scrollIntoView({ block: 'start' });
    if (focus && typeof group.focus === 'function') group.focus({ preventScroll: true });
    // The section menu scrolls sideways on phones; keep the chosen item in view.
    const link = document.querySelector(`[data-settings-link="${key}"]`);
    if (link && typeof link.scrollIntoView === 'function') link.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  // The section being read: the last one whose top has passed the upper third
  // of the column, or the last one when the column is scrolled to the end.
  function currentGroup(panels) {
    const groups = Array.from(panels.querySelectorAll('[data-settings-group]'));
    if (!groups.length) return null;
    if (panels.scrollTop + panels.clientHeight >= panels.scrollHeight - 2) return groups[groups.length - 1].dataset.settingsGroup;
    const line = panels.scrollTop + panels.clientHeight / 3;
    let current = groups[0];
    groups.forEach(group => { if (group.offsetTop <= line) current = group; });
    return current.dataset.settingsGroup;
  }

  function watchScroll() {
    const panels = $('accountSettingsPanels');
    if (!panels) return;
    let queued = false;
    panels.addEventListener('scroll', () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        const key = currentGroup(panels);
        if (key) markCurrent(key);
      });
    }, { passive: true });
  }

  // A success message often appears far down a long form, after a scroll. Repeat
  // it in a note pinned to the bottom of the dialog so it can't be missed.
  function showToast(text, { announce = true } = {}) {
    const toast = $('accountToast');
    if (!toast || !text) return;
    toast.textContent = text;
    // Messages that are already read out where they appear shouldn't be read twice.
    if (announce) toast.removeAttribute('aria-hidden');
    else toast.setAttribute('aria-hidden', 'true');
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, TOAST_MS);
  }

  function messageShown(element) {
    return element.textContent.trim() !== '' && element.style.display !== 'none' && !element.hidden;
  }

  function watchMessages() {
    const panels = $('accountSettingsPanels');
    if (!panels || typeof MutationObserver !== 'function') return;
    // Errors are read out as soon as they appear, next to the form they belong to.
    panels.querySelectorAll('.error-message').forEach(element => {
      if (!element.hasAttribute('role')) element.setAttribute('role', 'alert');
    });
    const last = new WeakMap();
    const check = () => {
      panels.querySelectorAll('.success-message').forEach(element => {
        const text = messageShown(element) ? element.textContent.trim() : '';
        if (text && last.get(element) !== text) {
          showToast(text, { announce: !element.hasAttribute('role') });
        }
        last.set(element, text);
      });
    };
    new MutationObserver(check).observe(panels, {
      subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['style', 'hidden'],
    });
  }

  async function openFromHash(attempt = 0) {
    const key = groupFromHash(window.location.hash);
    if (!key) return;
    const signedIn = typeof getUser === 'function' && getUser();
    if (!signedIn || typeof window.openAccountModal !== 'function') {
      // The dashboard may still be restoring the session.
      if (attempt < 10) setTimeout(() => openFromHash(attempt + 1), 500);
      return;
    }
    await window.openAccountModal();
    showGroup(key);
    try {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);
    } catch (error) { /* keeping the hash is harmless */ }
  }

  function init() {
    const modal = $('accountModal');
    if (!modal) return;
    modal.addEventListener('click', event => {
      const link = event.target.closest('[data-settings-link]');
      if (link) {
        event.preventDefault();
        showGroup(link.dataset.settingsLink);
      }
    });
    watchScroll();
    watchMessages();
    openFromHash();
    window.addEventListener('hashchange', () => openFromHash());
  }

  window.OmniSettings = { groupFromHash, showGroup, showToast };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
