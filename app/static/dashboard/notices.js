// Short messages about an action (a failed save, a copied link) shown in a corner of
// the page instead of a browser alert(). They are read out by screen readers and
// close on their own, errors a little later than the rest. Hovering or focusing one
// keeps it open; long or multi-line messages, such as an import summary, stay until
// they are dismissed.
const NOTICE_LIMIT = 3;
const PENDING_NOTICE_KEY = 'omnitrackr_pending_notice';

function showNotice(message, tone = 'error') {
  const text = String(message ?? '').trim();
  if (!text) return;
  const kind = ['error', 'success', 'info'].includes(tone) ? tone : 'error';
  let stack = document.getElementById('appNotices');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'appNotices';
    stack.className = 'app-notices';
  }
  // An open modal <dialog> sits above everything else on the page; show the notice inside it.
  let host = document.body;
  try { host = document.querySelector('dialog:modal') || document.body; } catch (_) { /* older browsers */ }
  if (stack.parentNode !== host) host.appendChild(stack);

  const repeat = Array.from(stack.children).find(node => node.dataset.text === text);
  if (repeat) repeat.remove();
  while (stack.children.length >= NOTICE_LIMIT) stack.firstElementChild.remove();

  const notice = document.createElement('div');
  notice.className = `app-notice app-notice--${kind}`;
  notice.dataset.text = text;
  notice.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  const body = document.createElement('p');
  body.textContent = text;
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'app-notice__close';
  close.setAttribute('aria-label', 'Dismiss');
  close.textContent = '×';
  notice.append(body, close);

  const sticky = text.includes('\n') || text.length > 220;
  const lifetime = (kind === 'error' ? 7000 : 4500) + text.length * 30;
  let timer = null;
  const dismiss = () => { clearTimeout(timer); notice.remove(); };
  const schedule = () => { clearTimeout(timer); if (!sticky) timer = setTimeout(dismiss, lifetime); };
  close.addEventListener('click', dismiss);
  notice.addEventListener('mouseenter', () => clearTimeout(timer));
  notice.addEventListener('mouseleave', schedule);
  notice.addEventListener('focusin', () => clearTimeout(timer));
  notice.addEventListener('focusout', schedule);
  stack.appendChild(notice);
  schedule();
}

// For a message about something that reloads the page right after.
function showNoticeAfterReload(message, tone = 'success') {
  try {
    sessionStorage.setItem(PENDING_NOTICE_KEY, JSON.stringify({ message: String(message), tone }));
  } catch (_) {
    showNotice(message, tone);
  }
}

(function showPendingNotice() {
  try {
    const pending = JSON.parse(sessionStorage.getItem(PENDING_NOTICE_KEY) || 'null');
    sessionStorage.removeItem(PENDING_NOTICE_KEY);
    if (pending && typeof pending.message === 'string') showNotice(pending.message, pending.tone);
  } catch (_) { /* storage blocked or the value was not ours */ }
})();

// The message to show for a failed API call. FastAPI sends `detail` as a string for
// errors we raise and as a list of field problems for validation errors; the usual
// validation wordings are rewritten into plain sentences.
const FIELD_LABELS = { title: 'Title', year: 'Year', rating: 'Rating', review: 'Review', poster_url: 'Poster',
  cover_art_url: 'Cover art', episodes: 'Episodes', seasons: 'Seasons', notes: 'Notes', name: 'Name' };
const VALIDATION_WORDING = [
  [/^Input should be less than or equal to (.+)$/, 'can be at most $1'],
  [/^Input should be greater than or equal to (.+)$/, 'must be at least $1'],
  [/^Input should be less than (.+)$/, 'must be under $1'],
  [/^Input should be greater than (.+)$/, 'must be more than $1'],
  [/^String should have at most (\d+) characters?$/, 'can be up to $1 characters'],
  [/^String should have at least (\d+) characters?$/, 'needs at least $1 characters'],
  [/^Input should be a valid integer.*$/, 'must be a whole number'],
  [/^Input should be a valid number.*$/, 'must be a number'],
  [/^Field required$/, 'is required'],
];
function apiErrorText(body, fallback) {
  const detail = body && body.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail[0] && detail[0].msg) {
    const field = (detail[0].loc || []).slice(-1)[0];
    const raw = String(detail[0].msg).replace(/^Value error, /, '');
    const label = FIELD_LABELS[field] || (typeof field === 'string' ? field.replace(/_/g, ' ') : '');
    if (!label || field === 'body') return raw;
    const rule = VALIDATION_WORDING.find(([pattern]) => pattern.test(raw));
    return rule ? `${label} ${raw.replace(rule[0], rule[1])}.` : `${label}: ${raw}`;
  }
  return fallback;
}
