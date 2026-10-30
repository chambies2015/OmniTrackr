/**
 * Authentication Module for OmniTrackr
 * Handles JWT token management, login, registration, and authenticated API calls
 */

// Constants
const TOKEN_KEY = 'omnitrackr_token';
const USER_KEY = 'omnitrackr_user';
const RETURN_PROMPT_KEY = 'omnitrackr_return_prompt';
const DISCOVER_AUTH_RETURN_KEY = 'omnitrackr_discover_auth_return';
const DISCOVER_AUTH_RETURN_TTL = 24 * 60 * 60 * 1000;
let discoverAuthReturnContext = null;
const DEMO_START_KEY = 'omnitrackr_demo_start';
let demoStartContext = null;
// Where a newcomer was headed before signing up: the demo, or importing an existing library.
const START_INTENTS = ['demo', 'import'];
// Authentication is also used by the standalone public landing page, which
// intentionally does not load the much larger private dashboard bundle.
const AUTH_IS_LOCAL = (location.protocol === 'file:' || location.origin === 'null' || location.origin === '');
const AUTH_API_BASE = AUTH_IS_LOCAL ? 'http://127.0.0.1:8000' : '';

// Keep a visitor's chosen Discover, review, title, or collection page through
// same-tab registration and email verification. Returning only opens a preview;
// saving always requires the visitor's explicit confirmation on that page.
function validateDiscoverAuthReturn(value) {
    if (typeof value !== 'string' || value.length > 180) return null;
    const match = value.match(/^\/discover\/(?:monthly\/)?[a-z0-9-]+(?:#save-picks)?$/);
    // Compare the entire match as JavaScript's $ can precede a final newline.
    if (match && match[0] === value) return value;
    const review = value.match(/^\/reviews\/([1-9]\d{0,9})\/save\?category=(movie|tv_show|anime|video_game|music|book)$/);
    if (review && review[0] === value && Number(review[1]) <= 2147483647) return value;
    const radar = value.match(/^\/release-radar(?:\/(?:movies|tv|anime|games)(?:\/(?:\d{4}-\d{2}|(?:winter|spring|summer|fall)-\d{4}))?)?$/);
    if (radar && radar[0] === value) return value;
    const title = value.match(/^\/titles\/(?:movie|tv|anime|game|album|book)\/[a-z0-9-]{1,130}(?:\?take=[A-Za-z0-9_-]{16,64})?#write-review$/);
    if (title && title[0] === value) return value;
    const invite = value.match(/^\/join\/[A-Za-z0-9_-]{16,32}$/);
    if (invite && invite[0] === value) return value;
    // Shared lists: the list's join link, the member's lists and one list.
    const sharedList = value.match(/^\/lists(?:\/join\/[A-Za-z0-9_-]{16,32}|\/[1-9]\d{0,9})?$/);
    if (sharedList && sharedList[0] === value) return value;
    // Group polls: the poll page and the page that makes them.
    const poll = value.match(/^\/tonight(?:\/[A-Za-z0-9_-]{16,32})?$/);
    if (poll && poll[0] === value) return value;
    // Daily, Pick for me, tier lists, "If you liked" and "In order" guides and the dashboard cards they link to.
    const tool = value.match(/^(?:\/daily(?:\/[1-9]\d{0,4})?|\/pick|\/tier-list|\/if-you-liked\/[a-z0-9-]{1,80}|\/in-order\/[a-z0-9-]{1,80}|\/#challenge|\/#release-calendar)$/);
    if (tool && tool[0] === value) return value;
    const collection = value.match(/^\/collections\/public\/([1-9]\d{0,9})\/save$/);
    return collection && collection[0] === value && Number(collection[1]) <= 2147483647 ? value : null;
}

function clearDiscoverAuthReturn() {
    discoverAuthReturnContext = null;
    try {
        sessionStorage.removeItem(DISCOVER_AUTH_RETURN_KEY);
    } catch (error) {
        // Navigation and authentication still work without browser storage.
    }
}

function getDiscoverAuthReturn() {
    try {
        const context = discoverAuthReturnContext
            || JSON.parse(sessionStorage.getItem(DISCOVER_AUTH_RETURN_KEY));
        const now = Date.now();
        if (
            context
            && validateDiscoverAuthReturn(context.path)
            && Number.isFinite(context.created_at)
            && context.created_at <= now
            && now - context.created_at < DISCOVER_AUTH_RETURN_TTL
        ) {
            return context.path;
        }
    } catch (error) {
        // Ignore malformed state or unavailable browser storage.
    }
    clearDiscoverAuthReturn();
    return null;
}

function captureDiscoverAuthReturn() {
    // An expired cookie may select the full dashboard shell before authentication
    // fails. Capture the same strictly allowlisted root-page intent in either shell.
    if (window.location.pathname !== '/') return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has('next')) return;
    const values = params.getAll('next');
    const path = values.length === 1 ? validateDiscoverAuthReturn(values[0]) : null;
    clearDiscoverAuthReturn();
    if (!path) return;
    discoverAuthReturnContext = { path, created_at: Date.now() };
    try {
        sessionStorage.setItem(DISCOVER_AUTH_RETURN_KEY, JSON.stringify(discoverAuthReturnContext));
    } catch (error) {
        // The current page can still return correctly when storage is blocked.
    }
}

function consumeDiscoverAuthReturn() {
    const path = getDiscoverAuthReturn();
    const start = getStartIntent();
    clearDiscoverAuthReturn();
    clearDemoStartIntent();
    return path || (start ? `/?start=${start}` : '/');
}

function clearDemoStartIntent() {
    demoStartContext = null;
    try {
        sessionStorage.removeItem(DEMO_START_KEY);
    } catch (error) {
        // Optional onboarding must also work when browser storage is blocked.
    }
}

function getDemoStartIntent() {
    return getStartIntent() !== null;
}

function getStartIntent() {
    try {
        const context = demoStartContext || JSON.parse(sessionStorage.getItem(DEMO_START_KEY));
        const now = Date.now();
        if (START_INTENTS.includes(context?.source) && Number.isFinite(context.created_at)
            && context.created_at <= now && now - context.created_at < DISCOVER_AUTH_RETURN_TTL) {
            return context.source;
        }
    } catch (error) {
        // Ignore expired, malformed, or unavailable session state.
    }
    clearDemoStartIntent();
    return null;
}

// A friend's /join link sends visitors to /?invite=<token>#signup; signing up from
// this tab sends the token along so the two become friends once the email is verified.
const FRIEND_INVITE_KEY = 'omnitrackr_friend_invite';

function validFriendInvite(value) {
    return typeof value === 'string' && /^[A-Za-z0-9_-]{16,32}$/.test(value) ? value : null;
}

function captureFriendInvite() {
    if (window.location.pathname !== '/') return;
    const values = new URLSearchParams(window.location.search).getAll('invite');
    const token = values.length === 1 ? validFriendInvite(values[0]) : null;
    if (!token) return;
    try {
        sessionStorage.setItem(FRIEND_INVITE_KEY, token);
    } catch (error) {
        // The invite still applies while this page stays open.
    }
    window.omnitrackrFriendInvite = token;
}

function getFriendInvite() {
    try {
        return validFriendInvite(window.omnitrackrFriendInvite) || validFriendInvite(sessionStorage.getItem(FRIEND_INVITE_KEY));
    } catch (error) {
        return validFriendInvite(window.omnitrackrFriendInvite);
    }
}

function clearFriendInvite() {
    window.omnitrackrFriendInvite = null;
    try {
        sessionStorage.removeItem(FRIEND_INVITE_KEY);
    } catch (error) {
        // Nothing stored.
    }
}

function captureDemoStartIntent() {
    if (document.documentElement.dataset.publicShell !== 'true' || window.location.pathname !== '/') return;
    const params = new URLSearchParams(window.location.search);
    // An explicitly chosen Discover, review, or collection destination takes priority.
    if (params.has('next')) {
        clearDemoStartIntent();
        return;
    }
    if (!params.has('start')) return;
    clearDemoStartIntent();
    const values = params.getAll('start');
    if (values.length !== 1 || !START_INTENTS.includes(values[0]) || getDiscoverAuthReturn()
        || ['token', 'reset_token', 'email_verified', 'password_reset', 'email_change_token', 'email_change']
            .some(key => params.has(key))) return;
    // This is navigation-only state: no demo titles, notes, or credentials cross over.
    demoStartContext = { source: values[0], created_at: Date.now() };
    try {
        sessionStorage.setItem(DEMO_START_KEY, JSON.stringify(demoStartContext));
    } catch (error) {
        // The current page still provides the same fixed return destination.
    }
}

// ============================================================================
// Token Management
// ============================================================================

// Remembers that this browser has signed in before (kept after logging out), so the
// homepage can offer "Log in" first to members and "Create account" first to newcomers.
const KNOWN_MEMBER_KEY = 'omnitrackr_known_member';

function saveAuthData(token, user) {
    // The cookie is authoritative. Keep this tab usable if browser storage is denied,
    // and never reuse a legacy token that could not be removed during a new login.
    getUser.current = user;
    recoverCookieSession.generation = (recoverCookieSession.generation || 0) + 1;
    let needsFallback = Boolean(getUser.storageBlocked);
    try { localStorage.removeItem(TOKEN_KEY); } catch (_) { needsFallback = true; }
    try { localStorage.setItem(USER_KEY, JSON.stringify(user)); } catch (_) { needsFallback = true; }
    try { localStorage.setItem(KNOWN_MEMBER_KEY, '1'); } catch (_) { /* optional */ }
    if (!needsFallback) delete getUser.current;
    try {
        if (needsFallback) sessionStorage.setItem('omnitrackr_session_user', JSON.stringify(user));
        else sessionStorage.removeItem('omnitrackr_session_user');
    } catch (_) { /* The in-memory user and HttpOnly cookie still work. */ }
}

function knownMember() {
    if (getUser()) return true;
    try {
        return Boolean(localStorage.getItem(KNOWN_MEMBER_KEY) || localStorage.getItem(TOKEN_KEY));
    } catch (_) { return false; }
}

function getToken() {
    if (Object.hasOwn(getUser, 'current') || getSessionAuthUser()) return null;
    try { return localStorage.getItem(TOKEN_KEY); }
    catch (_) { getUser.storageBlocked = true; return null; }
}

function getSessionAuthUser() {
    try {
        const user = JSON.parse(sessionStorage.getItem('omnitrackr_session_user') || 'null');
        return user && typeof user === 'object' && !Array.isArray(user) ? user : null;
    } catch (_) { return null; }
}

function getUser() {
    if (Object.hasOwn(getUser, 'current')) return getUser.current;
    const fallback = getSessionAuthUser();
    if (fallback) return fallback;
    try {
        const value = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
        return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
    } catch (_) { getUser.storageBlocked = true; return null; }
}

function clearAuth({ preserveReturn = false } = {}) {
    // Clear the authoritative in-memory state even if persisted values cannot be removed.
    if (typeof getUser === 'function') getUser.current = null;
    if (typeof recoverCookieSession === 'function') {
        recoverCookieSession.generation = (recoverCookieSession.generation || 0) + 1;
    }
    try { sessionStorage.removeItem('omnitrackr_session_user'); } catch (_) {}
    try { localStorage.removeItem(TOKEN_KEY); } catch (_) {}
    try { localStorage.removeItem(USER_KEY); } catch (_) {}
    // Storage events do not fire in this tab, including when a background request expires.
    window.OmniProgress?.reset();
    window.OmniImportStudio?.reset();
    window.resetDailyDashboard?.();
    window.resetLibraryBrowsing?.();
    window.resetFriendsPanel?.();
    window.resetSiteStatsLink?.();
    window.resetForYou?.();
    window.resetYearGoals?.();
    window.resetFriendRecs?.();
    window.resetFriendFeed?.();
    window.resetInstallCard?.();
    window.resetMonthlyChallenge?.();
    window.resetSeasonCard?.();
    window.resetOnThisDay?.();
    window.resetBadges?.();
    if (!preserveReturn) clearDiscoverAuthReturn();
    clearDemoStartIntent();
    try {
        sessionStorage.removeItem(RETURN_PROMPT_KEY);
    } catch (error) {
        // Authentication still works when session storage is unavailable.
    }
}

function isAuthenticated() {
    return !!getUser() || !!getToken();
}

function canRecoverCookieSession() {
    // The server only sends the private shell for a signed-in cookie, so recover the member when
    // browser storage is denied or was emptied while the cookie lived on (Safari clears it after a week).
    return !Object.hasOwn(getUser, 'current') && (getUser.storageBlocked || !getUser())
        && document.documentElement?.dataset?.publicShell !== 'true'
        && Boolean(document.getElementById('mainContainer'));
}

function recoverCookieSession() {
    if (!canRecoverCookieSession()) return Promise.resolve(false);
    if (recoverCookieSession.pending) return recoverCookieSession.pending;
    const generation = recoverCookieSession.generation || 0;
    const controller = new AbortController();
    let timeout;
    const pending = (async () => {
        try {
            const user = await Promise.race([
                (async () => {
                    const response = await fetch(`${AUTH_API_BASE}/account/me`, {
                        credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
                    });
                    if (!response.ok) return null;
                    return response.json();
                })(),
                new Promise((_, reject) => {
                    timeout = setTimeout(() => { controller.abort(); reject(new Error('Session recovery timed out')); }, 10000);
                }),
            ]);
            if (generation !== (recoverCookieSession.generation || 0)) return false;
            if (!user || !Number.isSafeInteger(user.id) || user.id < 1 || typeof user.username !== 'string') return false;
            saveAuthData(null, user);
            return true;
        } catch (_) { return false; }
        finally { clearTimeout(timeout); }
    })();
    recoverCookieSession.pending = pending;
    pending.finally(() => {
        if (recoverCookieSession.pending === pending) recoverCookieSession.pending = null;
    });
    return pending;
}

//  ============================================================================
// Authenticated Fetch Wrapper
// ============================================================================

async function authenticatedFetch(url, options = {}) {
    let token = getToken();
    if (!isAuthenticated() && canRecoverCookieSession()) {
        await recoverCookieSession();
        token = getToken();
    }

    if (!isAuthenticated()) {
        showAuthModal();
        throw new Error('Not authenticated');
    }

    // Include the HttpOnly session cookie. Keep Authorization only for legacy sessions.
    options.headers = {
        ...options.headers
    };
    if (token) {
        options.headers.Authorization = `Bearer ${token}`;
    }
    options.credentials = options.credentials || 'same-origin';

    try {
        const response = await fetch(url, options);

        // Handle 401 Unauthorized - token expired or invalid
        if (response.status === 401) {
            // Keep a chosen save preview while recovering an expired session.
            // Explicit logout still clears navigation intent along with credentials.
            clearAuth({ preserveReturn: true });
            showAuthModal();
            throw new Error('Session expired. Please login again.');
        }

        return response;
    } catch (error) {
        // Network error or other fetch error
        if (error.message === 'Session expired. Please login again.') {
            throw error;
        }
        throw error;
    }
}

// ============================================================================
// Authentication API Calls
// ============================================================================

// Turn any API error body into one sentence a person can act on.
function authErrorMessage(body, fallback) {
    // Rate limits answer {"error": "Rate limit exceeded: ..."} with no detail.
    if (body && typeof body.error === 'string' && /rate limit/i.test(body.error)) {
        return 'Too many attempts. Please wait a minute and try again.';
    }
    const detail = body && body.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
        const first = detail[0] || {};
        const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1] || '') : '';
        const labels = { email: 'Email', username: 'Username', password: 'Password' };
        const label = labels[field] || 'This field';
        if (first.type === 'string_too_short' || /at least/i.test(first.msg || '')) {
            const min = first.ctx && first.ctx.min_length;
            return `${label} is too short${min ? ` (at least ${min} characters)` : ''}.`;
        }
        if (first.type === 'string_too_long' || /at most/i.test(first.msg || '')) {
            const max = first.ctx && first.ctx.max_length;
            return `${label} is too long${max ? ` (at most ${max} characters)` : ''}.`;
        }
        if (first.type === 'missing') return `${label} is required.`;
        return `${label}: ${String(first.msg || 'please check this field').replace(/^Value error, /, '')}`;
    }
    return fallback;
}

// Anonymous sign-up funnel counters (see /site-stats). Never blocks anything.
const reportedFunnelEvents = new Set();
function reportFunnelEvent(event) {
    if (reportedFunnelEvents.has(event)) return;
    reportedFunnelEvents.add(event);
    try {
        // A beacon never delays the page or navigation.
        if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function' && typeof Blob === 'function') {
            navigator.sendBeacon('/api/funnel', new Blob([JSON.stringify({ event })], { type: 'application/json' }));
        }
    } catch (error) { /* analytics only */ }
}
window.reportFunnelEvent = reportFunnelEvent;

const USERNAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{2,29}$/;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Mirrors app/signup_rules.py so most mistakes are caught before the round trip.
// Returns the field to point at and what to say, or null.
function signupFieldProblem(email, username, password, confirmPassword) {
    if (!email || !EMAIL_PATTERN.test(email)) return { field: 'registerEmail', message: 'Enter the email address you want to use, like name@example.com.' };
    const trimmed = (username || '').trim();
    if (trimmed.length < 3 || trimmed.length > 30) return { field: 'registerUsername', message: 'Usernames need 3–30 characters.' };
    if (!USERNAME_PATTERN.test(trimmed)) return { field: 'registerUsername', message: 'Usernames can use letters, numbers, dots, dashes or underscores, and must start with a letter or number.' };
    if ((password || '').length < 8) return { field: 'registerPassword', message: 'Use at least 8 characters for your password.' };
    if (password !== confirmPassword) return { field: 'registerConfirmPassword', message: "The two passwords don't match." };
    return null;
}

function signupProblem(email, username, password, confirmPassword) {
    const problem = signupFieldProblem(email, username, password, confirmPassword);
    return problem ? problem.message : null;
}

// Which sign-up box a server answer is about, so the message can sit under it.
function signupFieldFor(message) {
    const text = String(message || '').toLowerCase();
    if (/password/.test(text)) return 'registerPassword';
    if (/username/.test(text)) return 'registerUsername';
    if (/e-?mail/.test(text)) return 'registerEmail';
    return null;
}

// ----------------------------------------------------------------------------
// Form helpers shared by the sign-in forms and account settings
// ----------------------------------------------------------------------------

// Show a message under one box. The box points at it with aria-describedby, so a
// screen reader reads it when focus lands there. Returns false when the page has
// no spot for it, so the caller can fall back to the message at the top.
function showFieldError(fieldId, message, { focus = true } = {}) {
    const field = document.getElementById(fieldId);
    const slot = document.getElementById(`${fieldId}Error`);
    if (!field || !slot) return false;
    slot.textContent = message;
    slot.hidden = false;
    if (typeof field.setAttribute === 'function') field.setAttribute('aria-invalid', 'true');
    if (focus && typeof field.focus === 'function') field.focus();
    return true;
}

function clearFieldError(fieldId) {
    const field = document.getElementById(fieldId);
    const slot = document.getElementById(`${fieldId}Error`);
    if (slot) { slot.textContent = ''; slot.hidden = true; }
    if (field && typeof field.removeAttribute === 'function') field.removeAttribute('aria-invalid');
}

function clearFormErrors(form) {
    if (!form || typeof form.querySelectorAll !== 'function') return;
    form.querySelectorAll('[aria-invalid="true"]').forEach(field => clearFieldError(field.id));
}

// A rough guide while typing. The server's check (signup_rules.password_problem)
// decides; this only warns early about the obvious cases it turns down.
const GUESSABLE_PASSWORD = /^(password|passw0rd|p@ssw0rd|qwerty|qwertyuiop|letmein|welcome|iloveyou|admin|abc|omnitrackr|changeme|test)[0-9!.]*$/;

function passwordStrength(password, { username = '', email = '' } = {}) {
    const value = String(password || '');
    if (!value) return { level: 0, text: '' };
    if (value.length < 8) {
        const left = 8 - value.length;
        return { level: 1, text: `${left} more character${left === 1 ? '' : 's'} to go` };
    }
    const lowered = value.toLowerCase();
    const name = String(username || '').trim().toLowerCase();
    const mailbox = String(email || '').split('@')[0].trim().toLowerCase();
    const sequence = '0123456789abcdefghijklmnopqrstuvwxyz';
    if (GUESSABLE_PASSWORD.test(lowered) || new Set(lowered).size <= 2 || sequence.includes(lowered)
        || (name.length >= 3 && lowered.includes(name) && lowered.length - name.length < 4)
        || (mailbox.length >= 3 && lowered === mailbox)) {
        return { level: 1, text: 'Easy to guess. Try a short phrase instead.' };
    }
    const kinds = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(kind => kind.test(value)).length;
    if (value.length >= 16 || (value.length >= 12 && kinds >= 2)) return { level: 4, text: 'Strong' };
    if (value.length >= 12 || kinds >= 3) return { level: 3, text: 'Good' };
    return { level: 2, text: 'Okay. Longer is harder to guess.' };
}

function updatePasswordStrength(field) {
    const meter = document.getElementById(field.dataset.passwordStrength);
    if (!meter) return;
    const username = document.getElementById('registerUsername');
    const email = document.getElementById('registerEmail');
    const result = passwordStrength(field.value, {
        username: field.id === 'registerPassword' && username ? username.value : '',
        email: field.id === 'registerPassword' && email ? email.value : '',
    });
    meter.hidden = result.level === 0;
    meter.dataset.level = String(result.level);
    const text = meter.querySelector('.auth-strength__text');
    if (text) text.textContent = result.level ? `Strength: ${result.text}` : '';
}

let passwordHelpersReady = false;
function setupPasswordHelpers() {
    if (passwordHelpersReady || typeof document.addEventListener !== 'function') return;
    passwordHelpersReady = true;
    document.addEventListener('click', event => {
        const toggle = event.target && event.target.closest ? event.target.closest('[data-password-toggle]') : null;
        if (!toggle) return;
        const field = document.getElementById(toggle.dataset.passwordToggle);
        if (!field) return;
        const show = field.type === 'password';
        field.type = show ? 'text' : 'password';
        toggle.textContent = show ? 'Hide' : 'Show';
        toggle.setAttribute('aria-pressed', String(show));
    });
    document.addEventListener('input', event => {
        const field = event.target;
        if (!field || !field.id) return;
        if (field.getAttribute && field.getAttribute('aria-invalid') === 'true') clearFieldError(field.id);
        if (field.dataset && field.dataset.passwordStrength) updatePasswordStrength(field);
    });
}

// A username taken from the start of the email address ("sam.lee@…" → "sam.lee"),
// or '' when nothing usable is left. The server still checks it is free.
function suggestUsername(email) {
    let base = String(email || '').split('@')[0].split('+')[0].replace(/[^A-Za-z0-9_.-]/g, '').replace(/^[^A-Za-z0-9]+/, '').slice(0, 30);
    if (base.length && base.length < 3) base = `${base}${'123'.slice(0, 3 - base.length)}`;
    return USERNAME_PATTERN.test(base) ? base : '';
}

// Fill the username from the email until the visitor types their own.
function setupUsernameSuggestion() {
    const email = document.getElementById('registerEmail');
    const username = document.getElementById('registerUsername');
    if (!email || !username) return;
    username.addEventListener('input', () => { username.dataset.edited = username.value ? 'true' : ''; });
    email.addEventListener('input', () => {
        if (username.dataset.edited === 'true') return;
        username.value = suggestUsername(email.value);
    });
}

async function register(email, username, password) {
    const invite = getFriendInvite();
    const response = await fetch(`${AUTH_API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invite ? { email, username, password, invite } : { email, username, password })
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(authErrorMessage(error, 'Something went wrong creating your account. Please try again.'));
    }

    await response.json();
    clearFriendInvite();
    document.getElementById('registerFormElement').reset();
    showVerificationSent(email);
}

// After sign-up: switch to the log-in form with the email filled in and the resend button ready.
function showVerificationSent(email) {
    showLoginForm(false);
    document.getElementById('authTitle').textContent = 'Check your inbox';
    setAuthContext('One last step before your library opens.');
    const loginField = document.getElementById('loginUsername');
    if (loginField) loginField.value = email;
    let saved = 0;
    try { saved = (JSON.parse(localStorage.getItem('omnitrackr_guest_list') || '[]') || []).length; } catch (error) { saved = 0; }
    const keep = saved ? ` Your ${saved} saved title${saved === 1 ? '' : 's'} will be added to your library when you log in.` : '';
    displayAuthSuccess(`Almost there! We sent a link to ${email}. Open it to activate your account (it works for 48 hours), then log in here.${keep} No email after a few minutes? Check spam, or resend it below.`);
    const resend = document.getElementById('resendVerificationContainer');
    if (resend) resend.style.display = 'block';
    // Waiting for the email is a good minute to start the library: quiz answers move in at first log-in.
    const success = document.getElementById('authSuccess');
    if (success && typeof document.createElement === 'function' && typeof success.appendChild === 'function') {
        const tip = document.createElement('p');
        tip.className = 'auth-quiz-tip';
        tip.append('While you wait: ');
        const link = document.createElement('a');
        link.href = '/taste-quiz';
        link.textContent = 'take the 1-minute taste quiz';
        tip.append(link, '. Your answers are added to your library when you log in.');
        success.appendChild(tip);
    }
}

async function login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${AUTH_API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        credentials: 'same-origin',
        body: formData
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        if (response.status === 429) throw new Error(authErrorMessage(error, 'Too many attempts. Please wait a minute and try again.'));
        // Check if it's an email verification error (403)
        if (response.status === 403) {
            const errorMsg = error.detail || 'Please verify your email address before logging in.';
            // Check if it's a deactivated account error
            if (errorMsg.toLowerCase().includes('deactivated') || errorMsg.toLowerCase().includes('reactivate')) {
                // Show reactivation option
                displayAuthError(errorMsg + ' Click "Reactivate Account" below to reactivate.');
                // Show reactivation button
                showReactivateOption(username);
                throw new Error(errorMsg);
            }
            throw new Error(errorMsg);
        }
        throw new Error(error.detail || 'Invalid credentials');
    }

    const data = await response.json();
    saveAuthData(data.access_token, data.user);
    try {
        if (
            data.return_prompt?.eligible
            && Number(data.return_prompt.days_away) >= 3
            && typeof data.return_prompt.engagement_token === 'string'
            && data.return_prompt.engagement_token.length >= 32
        ) {
            sessionStorage.setItem(RETURN_PROMPT_KEY, JSON.stringify({
                days_away: Math.min(Number(data.return_prompt.days_away), 90),
                engagement_token: data.return_prompt.engagement_token,
                created_at: Date.now(),
                shown: false,
            }));
        } else {
            sessionStorage.removeItem(RETURN_PROMPT_KEY);
        }
    } catch (error) {
        // The return deck is optional and never blocks login.
    }
    // The anonymous page deliberately does not include private dashboard markup.
    // Reload after the session cookie is set so the server can return the full app.
    window.location.assign(consumeDiscoverAuthReturn());
}

async function logout() {
    if (confirm('Are you sure you want to logout?')) {
        // Stop this member's phone/desktop notifications on this device first.
        if (window.omniPush && typeof window.omniPush.forgetDevice === 'function') {
            await window.omniPush.forgetDevice();
        }
        try {
            await fetch(`${AUTH_API_BASE}/auth/logout`, {
                method: 'POST',
                credentials: 'same-origin'
            });
        } catch (error) {
            console.error('Logout request failed:', error);
        }
        clearAuth();
        location.reload();
    }
}

// Make logout globally accessible
window.logout = logout;

// ============================================================================
// UI Functions
// ============================================================================

function showAuthModal() {
    // Show landing page instead of modal
    document.getElementById('landingPage').style.display = 'block';
    // Initialize landing page enhancements
    if (window.initLandingPageEnhancements) {
      window.initLandingPageEnhancements();
    }
    const mainContainer = document.getElementById('mainContainer');
    if (mainContainer) {
        mainContainer.style.display = 'none';
    }
    document.getElementById('authError').textContent = '';
    
    // Hide user display and logout button when showing landing page
    const userDisplay = document.getElementById('userDisplay');
    const logoutBtn = document.getElementById('logoutBtn');
    if (userDisplay) userDisplay.style.display = 'none';
    if (logoutBtn) logoutBtn.style.display = 'none';
    
    // Hide notification bell
    const notificationBell = document.getElementById('notificationBell');
    if (notificationBell) {
        notificationBell.style.display = 'none';
    }
    
    window.resetFriendsPanel?.();
    window.resetSiteStatsLink?.();
    window.resetForYou?.();
    window.resetYearGoals?.();
    window.resetFriendRecs?.();
    window.resetFriendFeed?.();
    window.resetInstallCard?.();
    window.resetMonthlyChallenge?.();
    window.resetSeasonCard?.();
    window.resetOnThisDay?.();
    window.resetBadges?.();
    
    // Hide footer for logged-in view when showing landing page
    const mainFooter = document.getElementById('mainFooter');
    if (mainFooter) {
        mainFooter.style.display = 'none';
    }

    // Hide both forms initially
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';

    // Show login form by default (no scroll on initial load)
    showLoginForm(false);
}

function hideAuthModal() {
    // Hide landing page
    document.getElementById('landingPage').style.display = 'none';
}

function showMainUI() {
    // Public responses intentionally omit private controls. A successful login sets
    // the HttpOnly cookie and then reloads into the complete dashboard response.
    if (!document.getElementById('mainContainer')) {
        window.location.assign('/');
        return;
    }
    document.getElementById('mainContainer').style.display = 'block';
    document.getElementById('landingPage').style.display = 'none';
    // Show footer for logged-in view
    const mainFooter = document.getElementById('mainFooter');
    if (mainFooter) {
        mainFooter.style.display = 'block';
    }
    // Show notification bell
    const notificationBell = document.getElementById('notificationBell');
    if (notificationBell) {
        notificationBell.style.display = 'flex';
    }
    if (typeof restoreSidebarState === 'function') restoreSidebarState();
    
    // Load friends list and notification count
    if (typeof loadFriendsList === 'function') {
        loadFriendsList();
    }
    window.refreshSiteStatsLink?.();
    // home.js waits for these home cards before showing the library, so it doesn't jump,
    // and reuses them for its first refresh instead of asking a second time.
    const homeCards = [window.refreshForYou?.(), window.refreshYearGoals?.()];
    window.refreshFriendRecs?.();
    window.refreshFriendFeed?.();
    homeCards.push(window.refreshMonthlyChallenge?.(), window.refreshSeasonCard?.(), window.refreshBadges?.(),
        window.refreshOnThisDay?.());
    window.dashboardHomeCards = homeCards;
    window.refreshInstallCard?.();
    if (typeof updateNotificationCount === 'function') {
        updateNotificationCount();
        // Set up interval to refresh notification count every 30 seconds
        if (typeof notificationCountInterval !== 'undefined' && notificationCountInterval) {
            clearInterval(notificationCountInterval);
        }
        if (typeof setInterval !== 'undefined') {
            notificationCountInterval = setInterval(updateNotificationCount, 30000);
        }
    }
}

function showLoginForm(scroll = true) {
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('resendVerificationContainer').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Log in to OmniTrackr';
    setAuthContext('Welcome back. Pick up where you left off.');
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    clearAuthFormErrors();
    const reactivateContainer = document.getElementById('reactivateContainer');
    if (reactivateContainer) {
        reactivateContainer.style.display = 'none';
    }
    if (scroll) revealAuthCard();
}

// Switching forms starts each one without old messages under its boxes.
function clearAuthFormErrors() {
    ['loginFormElement', 'registerFormElement', 'forgotPasswordFormElement', 'resetPasswordFormElement']
        .forEach(id => clearFormErrors(document.getElementById(id)));
}

// The line under the form title, when the page has one.
function setAuthContext(text) {
    const context = document.querySelector('.auth-container .auth-context');
    if (context) context.textContent = text;
}

// Bring the form card into view: in a pop-up on the homepage (public-landing.js),
// otherwise by scrolling to the sign-up section.
function revealAuthCard() {
    if (!landingVisible()) return;
    if (window.OmniAuthDialog && window.OmniAuthDialog.open()) return;
    setTimeout(() => {
        document.querySelector('.landing-auth')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
}

function landingVisible() {
    const landing = document.getElementById('landingPage');
    if (!landing) return false;
    if (typeof getComputedStyle !== 'function') return landing.style.display === 'block';
    return getComputedStyle(landing).display !== 'none';
}

function showRegisterForm(scroll = true, { report = true } = {}) {
    if (report) reportFunnelEvent('signup_form_opened');
    try {
        if ((JSON.parse(localStorage.getItem('omnitrackr_guest_list') || '[]') || []).length) reportFunnelEvent('guest_list_signup');
    } catch (error) { /* no saved list */ }
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Create your free account';
    setAuthContext('Free, private by default, and ready in under a minute.');
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    clearAuthFormErrors();
    if (scroll) revealAuthCard();
}

function showForgotPasswordForm(scroll = true) {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'block';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Reset your password';
    setAuthContext('It happens. We\'ll email you a link.');
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    clearAuthFormErrors();
    if (scroll) revealAuthCard();
}

function showResetPasswordForm(resetToken = null, scroll = true) {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'block';
    document.getElementById('authTitle').textContent = 'Choose a new password';
    setAuthContext('You\'ll use it the next time you log in.');
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    clearAuthFormErrors();
    if (resetToken) {
        document.getElementById('resetPasswordFormElement').dataset.resetToken = resetToken;
    }
    if (scroll) revealAuthCard();
}

function updateUserDisplay() {
    const user = getUser();
    if (user) {
        const userDisplay = document.getElementById('userDisplay');
        const userDisplayText = document.getElementById('userDisplayText');
        const userProfilePicture = document.getElementById('userProfilePicture');
        
        if (userDisplayText) {
            userDisplayText.textContent = user.username;
        }
        
        if (userProfilePicture) {
            if (user.profile_picture_url) {
                userProfilePicture.src = user.profile_picture_url;
            } else {
                userProfilePicture.src = '/static/default-avatar.svg';
            }
        }
        
        userDisplay.style.display = 'inline-flex';
        userDisplay.onclick = openAccountModal;
        document.getElementById('logoutBtn').style.display = 'inline-block';
    } else {
        document.getElementById('userDisplay').style.display = 'none';
        document.getElementById('logoutBtn').style.display = 'none';
    }
}

function displayAuthError(message) {
    document.getElementById('authError').textContent = message;
    document.getElementById('authSuccess').style.display = 'none';
}

function showReactivateOption(usernameOrEmail) {
    // Create or show reactivate button
    let reactivateContainer = document.getElementById('reactivateContainer');
    if (!reactivateContainer) {
        reactivateContainer = document.createElement('div');
        reactivateContainer.id = 'reactivateContainer';
        reactivateContainer.className = 'reactivate-container';
        document.getElementById('loginForm').appendChild(reactivateContainer);
    }
    
    reactivateContainer.innerHTML = `
        <button type="button" id="reactivateBtn" class="action-btn action-btn-full">
            Reactivate Account
        </button>
    `;
    
    document.getElementById('reactivateBtn').onclick = () => {
        const password = document.getElementById('loginPassword').value;
        if (!password) {
            displayAuthError('Please enter your password to reactivate your account.');
            return;
        }
        reactivateAccount(usernameOrEmail, password);
    };
    
    reactivateContainer.style.display = 'block';
}

async function reactivateAccount(usernameOrEmail, password) {
    const reactivateBtn = document.getElementById('reactivateBtn');
    const originalText = reactivateBtn.textContent;
    reactivateBtn.disabled = true;
    reactivateBtn.textContent = 'Reactivating...';
    
    try {
        const response = await fetch(`${AUTH_API_BASE}/auth/reactivate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: usernameOrEmail,
                password: password
            })
        });
        
        if (response.ok) {
            const user = await response.json();
            displayAuthSuccess('Account reactivated successfully! You can now log in.');
            // Hide reactivate button
            document.getElementById('reactivateContainer').style.display = 'none';
            // Clear password field for security
            document.getElementById('loginPassword').value = '';
        } else {
            const error = await response.json();
            displayAuthError(error.detail || 'Failed to reactivate account. Please try again.');
        }
    } catch (error) {
        displayAuthError('Failed to reactivate account. Please try again.');
    } finally {
        reactivateBtn.disabled = false;
        reactivateBtn.textContent = originalText;
    }
}

function displayAuthSuccess(message) {
    const successEl = document.getElementById('authSuccess');
    successEl.textContent = message;
    successEl.style.display = 'block';
    document.getElementById('authError').textContent = '';
}

// ============================================================================
// Event Handlers
// ============================================================================

function setupAuthHandlers() {
    // Login form submission
    document.getElementById('loginFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('loginUsername').value.trim();
        const password = document.getElementById('loginPassword').value;
        clearFormErrors(e.target);
        if (!username) {
            if (!showFieldError('loginUsername', 'Enter your username or the email you signed up with.')) displayAuthError('Enter your username or email.');
            return;
        }
        if (!password) {
            if (!showFieldError('loginPassword', 'Enter your password.')) displayAuthError('Enter your password.');
            return;
        }

        const button = e.target.querySelector('button[type="submit"]');
        const label = button ? button.textContent : '';
        if (button) { button.disabled = true; button.textContent = 'Logging in…'; }
        try {
            await login(username, password);
            // Hide resend button on successful login
            document.getElementById('resendVerificationContainer').style.display = 'none';
        } catch (error) {
            displayAuthError(error.message);
            // Show resend button if it's a verification error
            if (error.message.toLowerCase().includes('verify')) {
                document.getElementById('resendVerificationContainer').style.display = 'block';
            } else {
                document.getElementById('resendVerificationContainer').style.display = 'none';
            }
        } finally {
            if (button) { button.disabled = false; button.textContent = label; }
        }
    });

    // Resend verification email button. A username can't receive mail, so ask for
    // the email in a box right above the button instead of a browser prompt.
    document.getElementById('resendVerificationBtn').addEventListener('click', async () => {
        const usernameOrEmail = document.getElementById('loginUsername').value.trim();
        const emailField = document.getElementById('resendVerificationEmail');
        const emailBox = document.getElementById('resendVerificationEmailField');
        let email = EMAIL_PATTERN.test(usernameOrEmail) ? usernameOrEmail : (emailField ? emailField.value.trim() : '');
        if (!EMAIL_PATTERN.test(email)) {
            if (emailBox && emailBox.hidden) {
                emailBox.hidden = false;
                if (emailField) emailField.focus();
                return;
            }
            displayAuthError('Enter the email address you signed up with, and we\'ll resend the link.');
            if (emailField) emailField.focus();
            return;
        }

        // Disable button while sending
        const btn = document.getElementById('resendVerificationBtn');
        btn.disabled = true;
        btn.textContent = 'Sending...';

        try {
            const response = await fetch(`${AUTH_API_BASE}/auth/resend-verification?email=${encodeURIComponent(email)}`, {
                method: 'POST',
            });

            if (response.ok) {
                displayAuthSuccess('Verification email sent! Please check your inbox (and spam folder).');
                document.getElementById('resendVerificationContainer').style.display = 'none';
            } else {
                const error = await response.json();
                displayAuthError(error.detail || 'Failed to resend verification email.');
            }
        } catch (error) {
            displayAuthError('Failed to resend verification email. Please try again.');
        } finally {
            // Re-enable button
            btn.disabled = false;
            btn.textContent = 'Resend verification email';
        }
    });

    document.getElementById('registerFormElement').addEventListener('focusin', () => reportFunnelEvent('signup_form_opened'));
    setupUsernameSuggestion();

    // Register form submission
    document.getElementById('registerFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('registerEmail').value.trim();
        const username = document.getElementById('registerUsername').value.trim();
        const password = document.getElementById('registerPassword').value;
        // The homepage form has a show-password button instead of a second password box.
        const confirmField = document.getElementById('registerConfirmPassword');
        const confirmPassword = confirmField ? confirmField.value : password;

        clearFormErrors(e.target);
        const problem = signupFieldProblem(email, username, password, confirmPassword);
        if (problem) {
            reportFunnelEvent('signup_rejected_invalid');
            if (!showFieldError(problem.field, problem.message)) displayAuthError(problem.message);
            return;
        }

        const button = e.target.querySelector('button[type="submit"]');
        const label = button ? button.textContent : '';
        if (button) { button.disabled = true; button.textContent = 'Creating your account…'; }
        try {
            await register(email, username, password);
        } catch (error) {
            // "That username is taken" belongs under the username box, and so on.
            const field = signupFieldFor(error.message);
            if (!field || !showFieldError(field, error.message)) displayAuthError(error.message);
        } finally {
            if (button) { button.disabled = false; button.textContent = label; }
        }
    });

    // Switch to register
    document.getElementById('showRegister').addEventListener('click', (e) => {
        e.preventDefault();
        showRegisterForm();
    });

    // Switch to login
    document.getElementById('showLogin').addEventListener('click', (e) => {
        e.preventDefault();
        showLoginForm();
    });

    // Show forgot password
    document.getElementById('showForgotPassword').addEventListener('click', (e) => {
        e.preventDefault();
        showForgotPasswordForm();
    });

    // Back to login from forgot password
    document.getElementById('backToLogin').addEventListener('click', (e) => {
        e.preventDefault();
        showLoginForm();
    });

    // Forgot password form submission
    document.getElementById('forgotPasswordFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('forgotPasswordEmail').value.trim();
        clearFormErrors(e.target);
        if (!EMAIL_PATTERN.test(email)) {
            if (!showFieldError('forgotPasswordEmail', 'Enter the email address on your account.')) displayAuthError('Enter the email address on your account.');
            return;
        }

        const button = e.target.querySelector('button[type="submit"]');
        const label = button ? button.textContent : '';
        if (button) { button.disabled = true; button.textContent = 'Sending…'; }
        try {
            const response = await fetch(`${AUTH_API_BASE}/auth/request-password-reset?email=${encodeURIComponent(email)}`, {
                method: 'POST',
            });

            if (response.ok) {
                displayAuthSuccess(`If ${email} has an account, a reset link is on its way. It can take a few minutes, so check spam too.`);
                document.getElementById('forgotPasswordFormElement').reset();
            } else {
                const error = await response.json().catch(() => ({}));
                displayAuthError(authErrorMessage(error, "We couldn't send the reset link. Please try again."));
            }
        } catch (error) {
            displayAuthError("We couldn't send the reset link. Check your connection and try again.");
        } finally {
            if (button) { button.disabled = false; button.textContent = label; }
        }
    });

    // Reset password form submission
    document.getElementById('resetPasswordFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmNewPassword').value;

        clearFormErrors(e.target);
        if (newPassword.length < 8) {
            if (!showFieldError('newPassword', 'Use at least 8 characters for your password.')) displayAuthError('Use at least 8 characters for your password.');
            return;
        }

        if (newPassword !== confirmPassword) {
            if (!showFieldError('confirmNewPassword', "The two passwords don't match.")) displayAuthError("The two passwords don't match.");
            return;
        }

        // Get token from URL or dataset
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('reset_token') || 
                     e.target.dataset.resetToken || 
                     urlParams.get('token');

        if (!token) {
            displayAuthError('This reset link is missing its code. Open the newest link from your email, or ask for a new one.');
            return;
        }

        try {
            const response = await fetch(`${AUTH_API_BASE}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: newPassword }),
            });

            if (response.ok) {
                const data = await response.json();
                displayAuthSuccess(data.message);
                
                // Clear URL parameters and show login form after 2 seconds
                setTimeout(() => {
                    window.history.replaceState({}, document.title, window.location.pathname);
                    showLoginForm();
                    displayAuthSuccess(data.message);
                }, 2000);
            } else {
                const error = await response.json().catch(() => ({}));
                const message = authErrorMessage(error, "We couldn't save that password. The link may have expired, so ask for a new one if this keeps happening.");
                if (!/password/i.test(message) || !showFieldError('newPassword', message)) displayAuthError(message);
            }
        } catch (error) {
            displayAuthError("We couldn't save that password. Check your connection and try again.");
        }
    });

    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
}

// ============================================================================
// Initialization
// ============================================================================

// ============================================================================
// Sign in with Google
// ============================================================================

// /auth/google/callback sends people back with ?google_error=<code>. Each code has
// its own sentence here, so no text from the address bar is ever shown.
const GOOGLE_ERRORS = {
    cancelled: 'Google sign-in was cancelled. Try again, or use your email below.',
    expired: 'That Google sign-in took too long or was opened in another tab. Please try again.',
    failed: "Google sign-in didn't work this time. Please try again, or use your email below.",
    unverified: "Google hasn't verified that email address yet, so it can't be used. Use your email below instead.",
    deactivated: 'This account is deactivated. Log in with your password to reactivate it, or reset your password first.',
    unavailable: "Google sign-in isn't available right now. Use your email below.",
};

function googleErrorMessage(code) {
    return Object.hasOwn(GOOGLE_ERRORS, code) ? GOOGLE_ERRORS[code] : GOOGLE_ERRORS.failed;
}

function setupGoogleSignIn() {
    // A friend's invite link travels with the visitor to Google and back.
    if (typeof document.querySelectorAll !== 'function') return;
    document.querySelectorAll('[data-google-signin]').forEach(link => {
        link.addEventListener('click', () => {
            const invite = getFriendInvite();
            link.href = invite ? `/auth/google/start?invite=${encodeURIComponent(invite)}` : '/auth/google/start';
        });
    });
}

// The callback already set the session cookie; learn who signed in, then open the
// library (or the page the visitor was on before signing up) like a password login.
async function finishGoogleSignIn() {
    try {
        const response = await fetch(`${AUTH_API_BASE}/account/me`, { credentials: 'same-origin', cache: 'no-store' });
        const user = response.ok ? await response.json() : null;
        if (!user || !Number.isSafeInteger(user.id) || user.id < 1 || typeof user.username !== 'string') {
            throw new Error('No session');
        }
        saveAuthData(null, user);
        clearFriendInvite();
        try { sessionStorage.removeItem(RETURN_PROMPT_KEY); } catch (_) { /* optional */ }
        window.location.replace(consumeDiscoverAuthReturn());
    } catch (_) {
        window.history.replaceState({}, document.title, window.location.pathname);
        showAuthModal();
        displayAuthError(GOOGLE_ERRORS.failed);
    }
}

function initAuth() {
    captureDiscoverAuthReturn();
    captureFriendInvite();
    captureDemoStartIntent();
    setupAuthHandlers();
    setupPasswordHelpers();
    setupGoogleSignIn();

    // Check URL parameters for email verification or password reset
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.get('signed_in') === 'google' && document.documentElement.dataset.publicShell !== 'true') {
        return finishGoogleSignIn();
    }
    const verifyToken = urlParams.get('token');
    const resetToken = urlParams.get('reset_token');
    const emailVerified = urlParams.get('email_verified');
    const passwordReset = urlParams.get('password_reset');
    const emailChangeToken = urlParams.get('email_change_token');
    const emailChange = urlParams.get('email_change');
    
    // Handle email change verification
    if (emailChangeToken && emailChange === 'true') {
        handleEmailChangeVerification(emailChangeToken);
        return;
    }
    
    // Handle email verification
    if (verifyToken && emailVerified === 'true') {
        handleEmailVerification(verifyToken);
        return;
    }
    
    // Handle password reset
    if (resetToken) {
        showAuthModal();
        revealAuthCard();
        showResetPasswordForm(resetToken);
        return;
    }
    
    // Handle successful verification redirect
    if (emailVerified === 'true' && !verifyToken) {
        showAuthModal();
        revealAuthCard();
        displayAuthSuccess('✅ Email verified successfully! You can now log in.');
        showLoginForm();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }
    
    // Handle successful password reset redirect
    if (passwordReset === 'true') {
        showAuthModal();
        revealAuthCard();
        displayAuthSuccess('✅ Password reset successfully! You can now log in with your new password.');
        showLoginForm();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }

    // Verification and password-reset links must work before login. Once those
    // links have been handled, only the server-selected dashboard may show the
    // private UI; stale localStorage must not reveal it on the public shell.
    if (document.documentElement.dataset.publicShell === 'true') {
        showAuthModal();
        if (urlParams.has('google_error')) {
            if (knownMember()) showLoginForm(false);
            else showRegisterForm(false, { report: false });
            displayAuthError(googleErrorMessage(urlParams.get('google_error')));
            window.history.replaceState({}, document.title, window.location.pathname + '#landing-auth');
            revealAuthCard();
            return;
        }
        if (window.location.hash === '#signup') {
            showRegisterForm();
            return;
        }
        // "I have an account" buttons: open the log-in form even on a browser that hasn't signed in before.
        if (window.location.hash === '#login') {
            showLoginForm();
            return;
        }
        if (urlParams.getAll('start').length === 1 && START_INTENTS.includes(urlParams.get('start'))
            && getDemoStartIntent() && !getDiscoverAuthReturn()) {
            showRegisterForm();
            return;
        }
        // Newcomers who scroll to the bottom find the sign-up form, not a log-in box.
        // Counted as "opened" only once they start filling it in.
        // "Log in" links from other pages arrive as /#landing-auth (without a return path).
        if (window.location.hash === '#landing-auth' && !urlParams.has('next')) return;
        if (!knownMember()) showRegisterForm(false, { report: false });
        return;
    }

    if (!isAuthenticated()) {
        if (canRecoverCookieSession()) {
            return recoverCookieSession().then(recovered => {
                if (!recovered) { if (!isAuthenticated()) showAuthModal(); return; }
                showMainUI();
                updateUserDisplay();
                // Main-library requests await the same recovery in authenticatedFetch.
                // These optional startup readers initially skipped a missing stored user.
                for (const name of ['loadCustomTabs', 'openDashboardTargetFromLocation', 'bootstrapReturnDeck']) {
                    try { Promise.resolve(window[name]?.()).catch(() => {}); } catch (_) { /* optional */ }
                }
            });
        }
        showAuthModal();
    } else {
        showMainUI();
        updateUserDisplay();
    }
}

// The dashboard's corner notices when they are loaded, a plain alert otherwise.
function authNotice(message, tone) {
    if (typeof showNotice === 'function') showNotice(message, tone);
    else alert(message);
}

async function handleEmailChangeVerification(token) {
    // If user is logged in, show success message and reload account info
    if (isAuthenticated()) {
        try {
            const response = await authenticatedFetch(`${AUTH_API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`);
            const data = await response.json();
            
            if (response.ok) {
                authNotice(data.message || 'Your email address is updated.', 'success');
                // Reload account info if modal is open
                if (typeof loadAccountInfo === 'function') {
                    await loadAccountInfo();
                }
                // Update user display
                updateUserDisplay();
            } else {
                authNotice(typeof data.detail === 'string' ? data.detail : 'That email change link did not work. Request a new one from Account settings.');
            }
        } catch (error) {
            authNotice('Could not confirm your new email address. Please try again.');
        }
        
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    } else {
        // Not logged in here: the link still has to be confirmed with the server.
        showAuthModal();
        revealAuthCard();
        showLoginForm();
        try {
            const response = await fetch(`${AUTH_API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`, { credentials: 'same-origin' });
            const data = await response.json().catch(() => ({}));
            if (response.ok) {
                displayAuthSuccess('✅ Email changed successfully! Please log in with your new email.');
            } else {
                displayAuthError(typeof data.detail === 'string' ? data.detail : 'Email change verification failed');
            }
        } catch (error) {
            displayAuthError('Failed to verify email change. Please try again.');
        }
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function handleEmailVerification(token) {
    showAuthModal();
    revealAuthCard();
    document.getElementById('authTitle').textContent = 'Email Verification';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    
    displayAuthSuccess('Verifying your email...');
    
    try {
        const response = await fetch(`${AUTH_API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`, { credentials: 'same-origin' });
        const data = await response.json();
        
        if (response.ok) {
            window.history.replaceState({}, document.title, window.location.pathname);
            if (data.signed_in && data.user) {
                // Same browser that signed up: the server already set the session cookie.
                saveAuthData(null, data.user);
                displayAuthSuccess('Email verified. Opening your library…');
                window.location.assign(consumeDiscoverAuthReturn());
                return;
            }
            if (isAuthenticated() && document.getElementById('mainContainer')) {
                // Already signed in here (e.g. the link was opened again): stay in the library.
                hideAuthModal();
                showMainUI();
                updateUserDisplay();
                return;
            }
            showLoginForm();
            displayAuthSuccess('Email verified! Log in to open your library.');
            const loginField = document.getElementById('loginUsername');
            if (loginField && data.login_hint) loginField.value = data.login_hint;
            const passwordField = document.getElementById('loginPassword');
            if (passwordField) passwordField.focus();
        } else {
            const message = data.detail || 'Email verification failed';
            displayAuthError(message);
            setTimeout(() => {
                window.history.replaceState({}, document.title, window.location.pathname);
                showLoginForm();
                // showLoginForm clears messages; keep the reason and offer a fresh link.
                displayAuthError(message);
                const resend = document.getElementById('resendVerificationContainer');
                if (resend) resend.style.display = 'block';
            }, 3000);
        }
    } catch (error) {
        displayAuthError('Failed to verify email. Please try again.');
        setTimeout(() => {
            window.history.replaceState({}, document.title, window.location.pathname);
            showLoginForm();
        }, 3000);
    }
}

// Initialize authentication when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
} else {
    initAuth();
}

// "Start tracking" links elsewhere point at /#signup (and log-in buttons at /#login); follow them on the homepage too.
if (typeof window.addEventListener === 'function') window.addEventListener('hashchange', () => {
    if (document.documentElement.dataset.publicShell !== 'true' || !document.getElementById('registerForm')) return;
    if (window.location.hash === '#signup') showRegisterForm();
    else if (window.location.hash === '#login') showLoginForm();
});

// Other tabs can replace or clear a session. Re-read their stored identity instead
// of retaining this tab's fallback user after a cross-tab sign-in or logout.
if (typeof window.addEventListener === 'function') window.addEventListener('storage', event => {
    if (event.key !== null && event.key !== USER_KEY && event.key !== TOKEN_KEY) return;
    delete getUser.current;
    getUser.storageBlocked = false;
    recoverCookieSession.generation = (recoverCookieSession.generation || 0) + 1;
    try { sessionStorage.removeItem('omnitrackr_session_user'); } catch (_) {}
});
