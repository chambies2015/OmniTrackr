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
    const startDemo = getDemoStartIntent();
    clearDiscoverAuthReturn();
    clearDemoStartIntent();
    return path || (startDemo ? '/?start=demo' : '/');
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
    try {
        const context = demoStartContext || JSON.parse(sessionStorage.getItem(DEMO_START_KEY));
        const now = Date.now();
        if (context?.source === 'demo' && Number.isFinite(context.created_at)
            && context.created_at <= now && now - context.created_at < DISCOVER_AUTH_RETURN_TTL) {
            return true;
        }
    } catch (error) {
        // Ignore expired, malformed, or unavailable session state.
    }
    clearDemoStartIntent();
    return false;
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
    if (values.length !== 1 || values[0] !== 'demo' || getDiscoverAuthReturn()
        || ['token', 'reset_token', 'email_verified', 'password_reset', 'email_change_token', 'email_change']
            .some(key => params.has(key))) return;
    // This is navigation-only state: no demo titles, notes, or credentials cross over.
    demoStartContext = { source: 'demo', created_at: Date.now() };
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
    localStorage.removeItem(TOKEN_KEY);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    try { localStorage.setItem(KNOWN_MEMBER_KEY, '1'); } catch (error) { /* optional */ }
}

function knownMember() {
    try {
        return Boolean(localStorage.getItem(KNOWN_MEMBER_KEY) || localStorage.getItem(USER_KEY) || localStorage.getItem(TOKEN_KEY));
    } catch (error) {
        return false;
    }
}

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
}

function clearAuth({ preserveReturn = false } = {}) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    // Storage events do not fire in this tab, including when a background request expires.
    window.OmniProgress?.reset();
    window.OmniImportStudio?.reset();
    window.resetDailyDashboard?.();
    window.resetLibraryBrowsing?.();
    window.resetFriendsPanel?.();
    window.resetSiteStatsLink?.();
    window.resetForYou?.();
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

//  ============================================================================
// Authenticated Fetch Wrapper
// ============================================================================

async function authenticatedFetch(url, options = {}) {
    const token = getToken();

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

// Mirrors app/signup_rules.py so most mistakes are caught before the round trip.
function signupProblem(email, username, password, confirmPassword) {
    if (!email || !email.includes('@')) return 'Enter the email address you want to use.';
    const trimmed = (username || '').trim();
    if (trimmed.length < 3 || trimmed.length > 30) return 'Usernames need 3–30 characters.';
    if (!USERNAME_PATTERN.test(trimmed)) return 'Usernames can use letters, numbers, dots, dashes or underscores, and must start with a letter or number.';
    if ((password || '').length < 8) return 'Use at least 8 characters for your password.';
    if (password !== confirmPassword) return "The two passwords don't match.";
    return null;
}

async function register(email, username, password) {
    const response = await fetch(`${AUTH_API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password })
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(authErrorMessage(error, 'Something went wrong creating your account. Please try again.'));
    }

    await response.json();
    document.getElementById('registerFormElement').reset();
    showVerificationSent(email);
}

// After sign-up: switch to the log-in form with the email filled in and the resend button ready.
function showVerificationSent(email) {
    showLoginForm(false);
    document.getElementById('authTitle').textContent = 'Check your inbox';
    const loginField = document.getElementById('loginUsername');
    if (loginField) loginField.value = email;
    let saved = 0;
    try { saved = (JSON.parse(localStorage.getItem('omnitrackr_guest_list') || '[]') || []).length; } catch (error) { saved = 0; }
    const keep = saved ? ` Your ${saved} saved title${saved === 1 ? '' : 's'} will be added to your library when you log in.` : '';
    displayAuthSuccess(`Almost there! We sent a link to ${email}. Open it to activate your account (it works for 48 hours), then log in here.${keep} No email after a few minutes? Check spam, or resend it below.`);
    const resend = document.getElementById('resendVerificationContainer');
    if (resend) resend.style.display = 'block';
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
        const error = await response.json();
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
    window.refreshForYou?.();
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
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    const reactivateContainer = document.getElementById('reactivateContainer');
    if (reactivateContainer) {
        reactivateContainer.style.display = 'none';
    }
    if (scroll && landingVisible()) {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
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
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    if (scroll && landingVisible()) {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function showForgotPasswordForm(scroll = true) {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'block';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Reset Password';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    if (scroll && landingVisible()) {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function showResetPasswordForm(resetToken = null, scroll = true) {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'block';
    document.getElementById('authTitle').textContent = 'Reset Password';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    if (resetToken) {
        document.getElementById('resetPasswordFormElement').dataset.resetToken = resetToken;
    }
    if (scroll && landingVisible()) {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
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
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;

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
        }
    });

    // Resend verification email button
    document.getElementById('resendVerificationBtn').addEventListener('click', async () => {
        const usernameOrEmail = document.getElementById('loginUsername').value;
        
        // Extract email - if it contains @, use it; otherwise we'll need to prompt
        let email = usernameOrEmail;
        if (!email || !email.includes('@')) {
            // If username was entered, prompt for email
            email = prompt('Please enter your email address to resend the verification email:');
            if (!email || !email.includes('@')) {
                displayAuthError('Please enter a valid email address.');
                return;
            }
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
            btn.textContent = 'Resend Verification Email';
        }
    });

    document.getElementById('registerFormElement').addEventListener('focusin', () => reportFunnelEvent('signup_form_opened'));

    // Register form submission
    document.getElementById('registerFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('registerEmail').value.trim();
        const username = document.getElementById('registerUsername').value.trim();
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('registerConfirmPassword').value;

        const problem = signupProblem(email, username, password, confirmPassword);
        if (problem) {
            reportFunnelEvent('signup_rejected_invalid');
            displayAuthError(problem);
            return;
        }

        const button = e.target.querySelector('button[type="submit"]');
        const label = button ? button.textContent : '';
        if (button) { button.disabled = true; button.textContent = 'Creating your account…'; }
        try {
            await register(email, username, password);
        } catch (error) {
            displayAuthError(error.message);
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
        const email = document.getElementById('forgotPasswordEmail').value;

        try {
            const response = await fetch(`${AUTH_API_BASE}/auth/request-password-reset?email=${encodeURIComponent(email)}`, {
                method: 'POST',
            });

            if (response.ok) {
                displayAuthSuccess('If that email is registered, you will receive a password reset link. Please check your email.');
                document.getElementById('forgotPasswordFormElement').reset();
            } else {
                const error = await response.json();
                displayAuthError(error.detail || 'Failed to send reset link');
            }
        } catch (error) {
            displayAuthError('Failed to send reset link. Please try again.');
        }
    });

    // Reset password form submission
    document.getElementById('resetPasswordFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmNewPassword').value;

        if (newPassword !== confirmPassword) {
            displayAuthError('Passwords do not match');
            return;
        }

        if (newPassword.length < 6) {
            displayAuthError('Password must be at least 6 characters');
            return;
        }

        // Get token from URL or dataset
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('reset_token') || 
                     e.target.dataset.resetToken || 
                     urlParams.get('token');

        if (!token) {
            displayAuthError('Invalid reset link');
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
                }, 2000);
            } else {
                const error = await response.json();
                displayAuthError(error.detail || 'Failed to reset password');
            }
        } catch (error) {
            displayAuthError('Failed to reset password. Please try again.');
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

function initAuth() {
    captureDiscoverAuthReturn();
    captureDemoStartIntent();
    setupAuthHandlers();

    // Check URL parameters for email verification or password reset
    const urlParams = new URLSearchParams(window.location.search);
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
        // Scroll to auth section
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
        showResetPasswordForm(resetToken);
        return;
    }
    
    // Handle successful verification redirect
    if (emailVerified === 'true' && !verifyToken) {
        showAuthModal();
        // Scroll to auth section
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
        displayAuthSuccess('✅ Email verified successfully! You can now log in.');
        showLoginForm();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }
    
    // Handle successful password reset redirect
    if (passwordReset === 'true') {
        showAuthModal();
        // Scroll to auth section
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
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
        if (window.location.hash === '#signup') {
            showRegisterForm();
            return;
        }
        if (urlParams.getAll('start').length === 1 && urlParams.get('start') === 'demo'
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
        showAuthModal();
    } else {
        showMainUI();
        updateUserDisplay();
    }
}

async function handleEmailChangeVerification(token) {
    // If user is logged in, show success message and reload account info
    if (isAuthenticated()) {
        try {
            const response = await authenticatedFetch(`${AUTH_API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`);
            const data = await response.json();
            
            if (response.ok) {
                alert('✅ ' + (data.message || 'Email changed successfully!'));
                // Reload account info if modal is open
                if (typeof loadAccountInfo === 'function') {
                    await loadAccountInfo();
                }
                // Update user display
                updateUserDisplay();
            } else {
                alert('❌ ' + (data.detail || 'Email change verification failed'));
            }
        } catch (error) {
            alert('❌ Failed to verify email change. Please try again.');
        }
        
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    } else {
        // User not logged in, show auth modal with success message
        showAuthModal();
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
        displayAuthSuccess('✅ Email changed successfully! Please log in with your new email.');
        showLoginForm();
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function handleEmailVerification(token) {
    showAuthModal();
    // Scroll to auth section
    document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
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
            showLoginForm();
            displayAuthSuccess('Email verified! Log in to open your library.');
            const loginField = document.getElementById('loginUsername');
            if (loginField && data.login_hint) loginField.value = data.login_hint;
            const passwordField = document.getElementById('loginPassword');
            if (passwordField) passwordField.focus();
        } else {
            displayAuthError(data.detail || 'Email verification failed');
            setTimeout(() => {
                window.history.replaceState({}, document.title, window.location.pathname);
                showLoginForm();
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

// "Start tracking" links elsewhere point at /#signup; follow them on the homepage too.
if (typeof window.addEventListener === 'function') window.addEventListener('hashchange', () => {
    if (window.location.hash === '#signup' && document.documentElement.dataset.publicShell === 'true'
        && document.getElementById('registerForm')) {
        showRegisterForm();
    }
});
