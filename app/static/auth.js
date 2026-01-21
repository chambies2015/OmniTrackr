/**
 * Authentication Module for OmniTrackr
 * Handles JWT token management, login, registration, and authenticated API calls
 */

// Constants
const TOKEN_KEY = 'omnitrackr_token';
const USER_KEY = 'omnitrackr_user';

// ============================================================================
// Token Management
// ============================================================================

function saveAuthData(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
}

function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

function isAuthenticated() {
    return !!getToken();
}

//  ============================================================================
// Authenticated Fetch Wrapper
// ============================================================================

async function authenticatedFetch(url, options = {}) {
    const token = getToken();

    if (!token) {
        showAuthModal();
        throw new Error('Not authenticated');
    }

    // Add Authorization header
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    try {
        const response = await fetch(url, options);

        // Handle 401 Unauthorized - token expired or invalid
        if (response.status === 401) {
            clearAuth();
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

async function register(email, username, password) {
    const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Registration failed');
    }

    const user = await response.json();

    // Show success message about email verification
    displayAuthSuccess('Registration successful! Please check your email to verify your account. You can login once verified.');
    
    // Clear form
    document.getElementById('registerFormElement').reset();
    
    // Don't auto-redirect - let user read the message and click back to login manually
}

async function login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
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
    hideAuthModal();
    showMainUI();

    // Load initial data
    loadMovies();
    if (typeof loadCustomTabs === 'function') {
        loadCustomTabs();
    }
    updateUserDisplay();
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
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
    document.getElementById('mainContainer').style.display = 'none';
    document.getElementById('authError').textContent = '';
    
    // Hide user display and logout button when showing landing page
    document.getElementById('userDisplay').style.display = 'none';
    document.getElementById('logoutBtn').style.display = 'none';
    
    // Hide notification bell
    const notificationBell = document.getElementById('notificationBell');
    if (notificationBell) {
        notificationBell.style.display = 'none';
    }
    
    // Hide friends sidebar
    const friendsSidebar = document.getElementById('friendsSidebar');
    if (friendsSidebar) {
        friendsSidebar.style.display = 'none';
    }
    
    // Hide footer for logged-in view when showing landing page
    const mainFooter = document.getElementById('mainFooter');
    if (mainFooter) {
        mainFooter.style.display = 'none';
    }

    // Hide both forms initially
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';

    // Show login form by default
    showLoginForm();
}

function hideAuthModal() {
    // Hide landing page
    document.getElementById('landingPage').style.display = 'none';
}

function showMainUI() {
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
    // Show friends sidebar
    const friendsSidebar = document.getElementById('friendsSidebar');
    if (friendsSidebar) {
        friendsSidebar.style.display = 'block';
    }
    
    // Load friends list and notification count
    if (typeof loadFriendsList === 'function') {
        loadFriendsList();
    }
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

function showLoginForm() {
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('resendVerificationContainer').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Login to OmniTrackr';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    // Hide reactivate container
    const reactivateContainer = document.getElementById('reactivateContainer');
    if (reactivateContainer) {
        reactivateContainer.style.display = 'none';
    }
    // Scroll to auth section if on landing page
    if (document.getElementById('landingPage').style.display === 'block') {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function showRegisterForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Register for OmniTrackr';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    // Scroll to auth section if on landing page
    if (document.getElementById('landingPage').style.display === 'block') {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function showForgotPasswordForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'block';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Reset Password';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    // Scroll to auth section if on landing page
    if (document.getElementById('landingPage').style.display === 'block') {
        setTimeout(() => {
            document.querySelector('.landing-auth').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function showResetPasswordForm(resetToken = null) {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'block';
    document.getElementById('authTitle').textContent = 'Reset Password';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
    
    // Store reset token if provided
    if (resetToken) {
        document.getElementById('resetPasswordFormElement').dataset.resetToken = resetToken;
    }
    
    // Scroll to auth section if on landing page
    if (document.getElementById('landingPage').style.display === 'block') {
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
        reactivateContainer.style.marginTop = '10px';
        reactivateContainer.style.textAlign = 'center';
        document.getElementById('loginForm').appendChild(reactivateContainer);
    }
    
    reactivateContainer.innerHTML = `
        <button type="button" id="reactivateBtn" class="action-btn" style="width: 100%; margin-top: 10px;">
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
        const response = await fetch(`${API_BASE}/auth/reactivate`, {
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

function showReactivateOption(usernameOrEmail) {
    // Create or show reactivate button
    let reactivateContainer = document.getElementById('reactivateContainer');
    if (!reactivateContainer) {
        reactivateContainer = document.createElement('div');
        reactivateContainer.id = 'reactivateContainer';
        reactivateContainer.style.marginTop = '10px';
        reactivateContainer.style.textAlign = 'center';
        document.getElementById('loginForm').appendChild(reactivateContainer);
    }
    
    reactivateContainer.innerHTML = `
        <button type="button" id="reactivateBtn" class="action-btn" style="width: 100%; margin-top: 10px;">
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
        const response = await fetch(`${API_BASE}/auth/reactivate`, {
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
            const response = await fetch(`${API_BASE}/auth/resend-verification?email=${encodeURIComponent(email)}`, {
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

    // Register form submission
    document.getElementById('registerFormElement').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('registerEmail').value;
        const username = document.getElementById('registerUsername').value;
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('registerConfirmPassword').value;

        if (password !== confirmPassword) {
            displayAuthError('Passwords do not match');
            return;
        }

        if (password.length < 6) {
            displayAuthError('Password must be at least 6 characters');
            return;
        }

        try {
            await register(email, username, password);
        } catch (error) {
            displayAuthError(error.message);
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
            const response = await fetch(`${API_BASE}/auth/request-password-reset?email=${encodeURIComponent(email)}`, {
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
            const response = await fetch(`${API_BASE}/auth/reset-password?token=${encodeURIComponent(token)}&new_password=${encodeURIComponent(newPassword)}`, {
                method: 'POST',
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
    document.getElementById('logoutBtn').addEventListener('click', logout);
}

// ============================================================================
// Initialization
// ============================================================================

function initAuth() {
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
            const response = await authenticatedFetch(`${API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`);
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
        const response = await fetch(`${API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`);
        const data = await response.json();
        
        if (response.ok) {
            displayAuthSuccess(data.message + ' Redirecting to login...');
            
            // Clear URL parameters and show login after 3 seconds
            setTimeout(() => {
                window.history.replaceState({}, document.title, window.location.pathname);
                showLoginForm();
            }, 3000);
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
