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
            throw new Error(error.detail || 'Please verify your email address before logging in.');
        }
        throw new Error(error.detail || 'Invalid credentials');
    }

    const data = await response.json();
    saveAuthData(data.access_token, data.user);
    hideAuthModal();
    showMainUI();

    // Load initial data
    loadMovies();
    updateUserDisplay();
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        clearAuth();
        location.reload();
    }
}

// ============================================================================
// UI Functions
// ============================================================================

function showAuthModal() {
    document.getElementById('authModal').style.display = 'flex';
    document.getElementById('mainContainer').style.display = 'none';
    document.getElementById('authError').textContent = '';

    // Hide both forms initially
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';

    // Show login  form by default
    showLoginForm();
}

function hideAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

function showMainUI() {
    document.getElementById('mainContainer').style.display = 'block';
    document.getElementById('authModal').style.display = 'none';
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
}

function showRegisterForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('forgotPasswordForm').style.display = 'none';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Register for OmniTrackr';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
}

function showForgotPasswordForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('forgotPasswordForm').style.display = 'block';
    document.getElementById('resetPasswordForm').style.display = 'none';
    document.getElementById('authTitle').textContent = 'Reset Password';
    document.getElementById('authError').textContent = '';
    document.getElementById('authSuccess').style.display = 'none';
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
}

function updateUserDisplay() {
    const user = getUser();
    if (user) {
        document.getElementById('userDisplay').textContent = `👤 ${user.username}`;
        document.getElementById('logoutBtn').style.display = 'inline-block';
    }
}

function displayAuthError(message) {
    document.getElementById('authError').textContent = message;
    document.getElementById('authSuccess').style.display = 'none';
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
    
    // Handle email verification
    if (verifyToken && emailVerified === 'true') {
        handleEmailVerification(verifyToken);
        return;
    }
    
    // Handle password reset
    if (resetToken) {
        showAuthModal();
        showResetPasswordForm(resetToken);
        return;
    }
    
    // Handle successful verification redirect
    if (emailVerified === 'true' && !verifyToken) {
        showAuthModal();
        displayAuthSuccess('✅ Email verified successfully! You can now log in.');
        showLoginForm();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }
    
    // Handle successful password reset redirect
    if (passwordReset === 'true') {
        showAuthModal();
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

async function handleEmailVerification(token) {
    showAuthModal();
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
