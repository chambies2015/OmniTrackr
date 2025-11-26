/**
 * Authentication Module for StreamTracker
 * Handles JWT token management, login, registration, and authenticated API calls
 */

// Constants
const TOKEN_KEY = 'streamtracker_token';
const USER_KEY = 'streamtracker_user';

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

    // Auto-login after successful registration
    await login(username, password);
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
    document.getElementById('authTitle').textContent = 'Login to StreamTracker';
    document.getElementById('authError').textContent = '';
}

function showRegisterForm() {
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('authTitle').textContent = 'Register for StreamTracker';
    document.getElementById('authError').textContent = '';
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
        } catch (error) {
            displayAuthError(error.message);
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

    // Logout button
    document.getElementById('logoutBtn').addEventListener('click', logout);
}

// ============================================================================
// Initialization
// ============================================================================

function initAuth() {
    setupAuthHandlers();

    if (!isAuthenticated()) {
        showAuthModal();
    } else {
        showMainUI();
        updateUserDisplay();
    }
}

// Initialize authentication when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAuth);
} else {
    initAuth();
}
