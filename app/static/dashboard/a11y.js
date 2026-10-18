// Keyboard and screen reader support around existing dashboard behaviour:
// overlay dialogs announce themselves, take focus, keep Tab inside and hand
// focus back when they close; inline row editing keeps the reader's place.
// Nothing here changes what a dialog or row does, only where focus goes.

const A11Y_FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])', 'textarea:not([disabled])', 'summary', '[tabindex]:not([tabindex="-1"])',
].join(', ');
const A11Y_DIALOG_FALLBACK_LABELS = { imagePopupModal: 'Image preview' };
const a11yDialogOpeners = new Map();

function a11yFocusableIn(root) {
  return Array.from(root.querySelectorAll(A11Y_FOCUSABLE))
    .filter(element => element.getClientRects().length > 0 && !element.closest('[hidden], [inert]'));
}

function a11yCanTakeFocus(element) {
  return !!element && element.isConnected && element.getClientRects().length > 0 && !element.disabled;
}

function a11yOpenOverlayDialogs() {
  return Array.from(document.querySelectorAll('.modal-overlay')).filter(isElementShown);
}

function a11yLabelOverlayDialog(overlay) {
  if (!overlay.hasAttribute('role')) overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  if (overlay.hasAttribute('aria-labelledby') || overlay.hasAttribute('aria-label')) return;
  const heading = overlay.querySelector('.modal-header h2, h2, h3');
  if (heading) {
    if (!heading.id) heading.id = `${overlay.id || 'dialog'}Heading`;
    overlay.setAttribute('aria-labelledby', heading.id);
  } else {
    overlay.setAttribute('aria-label', A11Y_DIALOG_FALLBACK_LABELS[overlay.id] || 'Dialog');
  }
}

function a11yDialogOpened(overlay) {
  const active = document.activeElement;
  if (active && active !== document.body && !overlay.contains(active)) a11yDialogOpeners.set(overlay, active);
  // Dialogs that focus their own field (quick capture, search) do so right after
  // showing; only step in when focus is still outside once they have run.
  setTimeout(() => {
    if (!isElementShown(overlay) || overlay.contains(document.activeElement)) return;
    const content = overlay.querySelector('.modal-content') || overlay;
    if (!content.hasAttribute('tabindex')) content.setAttribute('tabindex', '-1');
    content.focus({ preventScroll: true });
  }, 60);
}

function a11yDialogClosed(overlay) {
  const opener = a11yDialogOpeners.get(overlay);
  a11yDialogOpeners.delete(overlay);
  const active = document.activeElement;
  const focusWasInside = !active || active === document.body || overlay.contains(active);
  if (focusWasInside && a11yCanTakeFocus(opener) && !a11yOpenOverlayDialogs().length) {
    opener.focus({ preventScroll: true });
  }
}

function a11yWatchOverlayDialogs() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    a11yLabelOverlayDialog(overlay);
    let shown = isElementShown(overlay);
    new MutationObserver(() => {
      const now = isElementShown(overlay);
      if (now === shown) return;
      shown = now;
      if (now) a11yDialogOpened(overlay); else a11yDialogClosed(overlay);
    }).observe(overlay, { attributes: true, attributeFilter: ['style', 'hidden', 'class'] });
  });
}

// Tab and Shift+Tab cycle inside the topmost open dialog.
document.addEventListener('keydown', event => {
  if (event.key !== 'Tab' || event.defaultPrevented) return;
  const open = a11yOpenOverlayDialogs();
  const overlay = open[open.length - 1];
  if (!overlay) return;
  const focusable = a11yFocusableIn(overlay);
  if (!focusable.length) { event.preventDefault(); return; }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  const inside = overlay.contains(active);
  if (event.shiftKey && (!inside || active === first || !focusable.includes(active))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (!inside || active === last)) {
    event.preventDefault();
    first.focus();
  }
});

// Inline row editing re-renders the row, which drops focus on the page body.
// Move it to the first field on Edit and back to the row's Edit button after
// Save or Cancel, so keyboard and screen reader users keep their place.
const A11Y_ROW_EDIT = /\b(edit|save|cancel)-(movie|tv|anime|video-game|music|book)-btn\b/;
const A11Y_ROW_ID_KEYS = { movie: 'movieId', tv: 'tvId', anime: 'animeId', 'video-game': 'gameId', music: 'musicId', book: 'bookId' };
const A11Y_ROW_ID_ATTRS = { movie: 'movie', tv: 'tv', anime: 'anime', 'video-game': 'game', music: 'music', book: 'book' };
const a11yEditingRows = {};

function a11yWhenFound(find, act, timeoutMs) {
  const started = Date.now();
  (function poll() {
    const found = find();
    if (found) { act(found); return; }
    if (Date.now() - started < timeoutMs) setTimeout(poll, 60);
  })();
}

document.addEventListener('click', event => {
  const button = event.target.closest && event.target.closest('button');
  const match = button && button.className.match(A11Y_ROW_EDIT);
  if (!match) return;
  const [, action, kind] = match;
  const attr = A11Y_ROW_ID_ATTRS[kind];
  const id = button.dataset[A11Y_ROW_ID_KEYS[kind]] || a11yEditingRows[kind];
  if (!id) return;
  if (action === 'edit') {
    a11yEditingRows[kind] = id;
    a11yWhenFound(
      () => document.querySelector(`.save-${kind}-btn[data-${attr}-id="${CSS.escape(id)}"]`)?.closest('tr'),
      row => {
        const field = row.querySelector('input:not([type="hidden"]), textarea, select');
        if (field && !row.contains(document.activeElement)) field.focus({ preventScroll: true });
      },
      1500,
    );
    return;
  }
  a11yWhenFound(
    () => {
      const edit = document.querySelector(`.edit-${kind}-btn[data-${attr}-id="${CSS.escape(id)}"]`);
      return a11yCanTakeFocus(edit) ? edit : null;
    },
    edit => {
      delete a11yEditingRows[kind];
      const active = document.activeElement;
      if (!active || active === document.body || !active.isConnected) edit.focus({ preventScroll: true });
    },
    5000,
  );
});

// The skip link lands on the open library, past the home cards above it.
document.addEventListener('click', event => {
  if (!event.target.closest || !event.target.closest('#skipToLibrary')) return;
  const target = document.querySelector('.tab-content.active') || document.getElementById('mainContainer');
  if (!target) return;
  event.preventDefault();
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: 'start' });
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', a11yWatchOverlayDialogs);
} else {
  a11yWatchOverlayDialogs();
}
