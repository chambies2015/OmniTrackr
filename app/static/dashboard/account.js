// @lazy-chunk lazy/statistics.js
// Event listeners
document.getElementById('loadMovies').addEventListener('click', () => loadMovies());
document.getElementById('loadTVShows').addEventListener('click', () => loadTVShows());
document.getElementById('loadAnime').addEventListener('click', () => loadAnime());
document.getElementById('loadVideoGames').addEventListener('click', () => loadVideoGames());
document.getElementById('loadMusic').addEventListener('click', () => loadMusic());
document.getElementById('loadBooks').addEventListener('click', () => loadBooks());

// Automatic sorting and search
document.getElementById('movieSort').addEventListener('change', () => loadMovies());
document.getElementById('tvSort').addEventListener('change', () => loadTVShows());
document.getElementById('animeSort').addEventListener('change', () => loadAnime());
document.getElementById('videoGameSort').addEventListener('change', () => loadVideoGames());
document.getElementById('musicSort').addEventListener('change', () => loadMusic());
document.getElementById('bookSort').addEventListener('change', () => loadBooks());

// Automatic search with debounce
let movieSearchTimeout;
document.getElementById('movieSearch').addEventListener('input', (e) => {
  clearTimeout(movieSearchTimeout);
  movieSearchTimeout = setTimeout(() => {
    loadMovies();
  }, 300); // Wait 300ms after user stops typing
});

let tvSearchTimeout;
document.getElementById('tvSearch').addEventListener('input', (e) => {
  clearTimeout(tvSearchTimeout);
  tvSearchTimeout = setTimeout(() => {
    loadTVShows();
  }, 300); // Wait 300ms after user stops typing
});

let animeSearchTimeout;
document.getElementById('animeSearch').addEventListener('input', (e) => {
  clearTimeout(animeSearchTimeout);
  animeSearchTimeout = setTimeout(() => {
    loadAnime();
  }, 300); // Wait 300ms after user stops typing
});

let videoGameSearchTimeout;
document.getElementById('videoGameSearch').addEventListener('input', (e) => {
  clearTimeout(videoGameSearchTimeout);
  videoGameSearchTimeout = setTimeout(() => {
    loadVideoGames();
  }, 300); // Wait 300ms after user stops typing
});

let musicSearchTimeout;
document.getElementById('musicSearch').addEventListener('input', (e) => {
  clearTimeout(musicSearchTimeout);
  musicSearchTimeout = setTimeout(() => {
    loadMusic();
  }, 300);
});

let bookSearchTimeout;
document.getElementById('bookSearch').addEventListener('input', (e) => {
  clearTimeout(bookSearchTimeout);
  bookSearchTimeout = setTimeout(() => {
    loadBooks();
  }, 300);
});

// Export/Import event listeners
document.getElementById('exportMovies').addEventListener('click', exportData);
document.getElementById('exportTVShows').addEventListener('click', exportData);
document.getElementById('exportAnime').addEventListener('click', exportData);
document.getElementById('exportVideoGames').addEventListener('click', exportData);
document.getElementById('exportMusic').addEventListener('click', exportData);
document.getElementById('exportBooks').addEventListener('click', exportData);
document.getElementById('importMovies').addEventListener('click', () => document.getElementById('importFile').click());
document.getElementById('importTVShows').addEventListener('click', () => document.getElementById('importTVFile').click());
document.getElementById('importAnime').addEventListener('click', () => document.getElementById('importAnimeFile').click());
document.getElementById('importVideoGames').addEventListener('click', () => document.getElementById('importVideoGameFile').click());
document.getElementById('importMusic').addEventListener('click', () => document.getElementById('importMusicFile').click());
document.getElementById('importBooks').addEventListener('click', () => document.getElementById('importBookFile').click());
document.getElementById('importFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importTVFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importAnimeFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importVideoGameFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importMusicFile').addEventListener('change', (e) => importData(e.target));
document.getElementById('importBookFile').addEventListener('change', (e) => importData(e.target));

// Auto-resize textarea for movie review
const movieReviewTextarea = document.getElementById('movieReview');
if (movieReviewTextarea) {
  movieReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for TV show review
const tvReviewTextarea = document.getElementById('tvReview');
if (tvReviewTextarea) {
  tvReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for anime review
const animeReviewTextarea = document.getElementById('animeReview');
if (animeReviewTextarea) {
  animeReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Auto-resize textarea for video game review
const videoGameReviewTextarea = document.getElementById('videoGameReview');
if (videoGameReviewTextarea) {
  videoGameReviewTextarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.max(60, this.scrollHeight) + 'px';
  });
}

// Collapsible form toggle function
window.toggleCollapsible = function (formId) {
  const content = document.getElementById(formId + 'Content');
  const icon = document.getElementById(formId + 'Icon');
  const expanding = content.hidden || !content.classList.contains('expanded');
  document.querySelectorAll('[data-toggle-collapsible]').forEach(toggle => {
    if (toggle.dataset.toggleCollapsible === formId) {
      toggle.setAttribute('aria-expanded', String(expanding));
    }
  });

  if (expanding) {
    content.hidden = false;
    content.style.display = 'block';
    content.classList.add('expanded');
    icon.classList.add('rotated');
  } else {
    content.classList.remove('expanded');
    icon.classList.remove('rotated');
    // Wait for animation to complete before hiding
    setTimeout(() => {
      if (!content.classList.contains('expanded')) {
        content.hidden = true;
        content.style.display = 'none';
      }
    }, 300);
  }
};

// Account Management Functions
window.openAccountModal = async function () {
  const modal = document.getElementById('accountModal');
  modal.style.display = 'flex';
  await loadAccountInfo();
}

window.closeAccountModal = function () {
  const modal = document.getElementById('accountModal');
  modal.style.display = 'none';
  // Clear all form errors and success messages
  document.querySelectorAll('.error-message, .success-message').forEach(el => {
    el.textContent = '';
    el.style.display = 'none';
  });
  // Reset forms
  document.getElementById('changeUsernameForm').reset();
  document.getElementById('changeEmailForm').reset();
  document.getElementById('changePasswordForm').reset();
  document.getElementById('deactivateAccountForm').reset();
}

window.loadAccountInfo = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/me`);
    if (response.ok) {
      const user = await response.json();
      document.getElementById('accountUsername').textContent = user.username;
      document.getElementById('accountEmail').textContent = user.email;

      // Format created date
      if (user.created_at) {
        const createdDate = new Date(user.created_at);
        document.getElementById('accountCreated').textContent = createdDate.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });
      } else {
        document.getElementById('accountCreated').textContent = 'Unknown';
      }

      // Email verification status
      document.getElementById('accountVerified').textContent = user.is_verified ? '✓ Verified' : '✗ Not Verified';
      document.getElementById('accountVerified').style.color = user.is_verified ? '#4caf50' : '#f44336';
    } else {
      console.error('Failed to load account info');
    }
  } catch (error) {
    console.error('Error loading account info:', error);
  }
}

window.changeUsername = async function (event) {
  event.preventDefault();
  const newUsername = document.getElementById('newUsername').value;
  const password = document.getElementById('usernamePassword').value;
  const errorEl = document.getElementById('usernameError');
  const successEl = document.getElementById('usernameSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/username`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_username: newUsername, password: password })
    });

    if (response.ok) {
      const updatedUser = await response.json();

      // The server refreshed the session cookie, so the member stays signed in.
      closeAccountModal();
      try {
        localStorage.removeItem('omnitrackr_token');
        localStorage.setItem('omnitrackr_user', JSON.stringify(updatedUser));
      } catch (storageError) {
        // The cookie session still works without storage.
      }
      alert(`Username changed to ${updatedUser.username}. Use it the next time you log in.`);
      location.reload();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change username';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change username. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.changeEmail = async function (event) {
  event.preventDefault();
  const newEmail = document.getElementById('newEmail').value;
  const password = document.getElementById('emailPassword').value;
  const errorEl = document.getElementById('emailError');
  const successEl = document.getElementById('emailSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/email`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_email: newEmail, password: password })
    });

    if (response.ok) {
      const data = await response.json();
      successEl.textContent = data.message || 'Verification email sent to new address. Please check your email.';
      successEl.style.display = 'block';
      document.getElementById('changeEmailForm').reset();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change email';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change email. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.changePassword = async function (event) {
  event.preventDefault();
  const currentPassword = document.getElementById('currentPassword').value;
  const newPassword = document.getElementById('accountNewPassword').value;
  const confirmPassword = document.getElementById('accountConfirmNewPassword').value;
  const errorEl = document.getElementById('passwordError');
  const successEl = document.getElementById('passwordSuccess');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  if (newPassword !== confirmPassword) {
    errorEl.textContent = 'New passwords do not match';
    errorEl.style.display = 'block';
    return;
  }

  if (newPassword.length < 6) {
    errorEl.textContent = 'Password must be at least 6 characters';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });

    if (response.ok) {
      const data = await response.json();
      successEl.textContent = data.message || 'Password changed successfully!';
      successEl.style.display = 'block';
      document.getElementById('changePasswordForm').reset();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to change password';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to change password. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.deactivateAccount = async function (event) {
  event.preventDefault();
  const password = document.getElementById('deactivatePassword').value;
  const errorEl = document.getElementById('deactivateError');

  errorEl.textContent = '';
  errorEl.style.display = 'none';

  if (!confirm('Are you sure you want to deactivate your account? You can reactivate within 90 days, but after that your account will be permanently deleted.')) {
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/deactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password })
    });

    if (response.ok) {
      const data = await response.json();
      alert(data.message || 'Account deactivated successfully. You will be logged out.');
      logout();
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to deactivate account';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to deactivate account. Please try again.';
    errorEl.style.display = 'block';
  }
}

// Privacy Settings Functions
window.loadPrivacySettings = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/privacy`);
    if (response.ok) {
      const privacy = await response.json();
      document.getElementById('moviesPrivate').checked = privacy.movies_private;
      document.getElementById('tvShowsPrivate').checked = privacy.tv_shows_private;
      document.getElementById('animePrivate').checked = privacy.anime_private;
      document.getElementById('videoGamesPrivate').checked = privacy.video_games_private;
      document.getElementById('musicPrivate').checked = privacy.music_private;
      document.getElementById('booksPrivate').checked = privacy.books_private;
      document.getElementById('statisticsPrivate').checked = privacy.statistics_private;
      updateDataPrivacyDashboard(privacy);
    }
  } catch (error) {
    console.error('Failed to load privacy settings:', error);
  }
}

function updateDataPrivacyDashboard(privacy) {
  const privateCountEl = document.getElementById('dataDashboardPrivateCount');
  const publicReviewsEl = document.getElementById('dataDashboardPublicReviews');
  if (!privateCountEl && !publicReviewsEl) return;

  const privateCategories = [
    ['Movies', privacy.movies_private],
    ['TV Shows', privacy.tv_shows_private],
    ['Anime', privacy.anime_private],
    ['Video Games', privacy.video_games_private],
    ['Music', privacy.music_private],
    ['Books', privacy.books_private],
    ['Statistics', privacy.statistics_private],
  ].filter((entry) => entry[1]).map((entry) => entry[0]);

  if (privateCountEl) {
    privateCountEl.textContent = privateCategories.length
      ? `${privateCategories.length} private (${privateCategories.join(', ')})`
      : 'No major categories private';
  }

  if (publicReviewsEl) {
    publicReviewsEl.textContent = 'Controlled per item before appearing on public review pages';
  }
}

window.updatePrivacySettings = async function (event) {
  event.preventDefault();

  const moviesPrivate = document.getElementById('moviesPrivate').checked;
  const tvShowsPrivate = document.getElementById('tvShowsPrivate').checked;
  const animePrivate = document.getElementById('animePrivate').checked;
  const videoGamesPrivate = document.getElementById('videoGamesPrivate').checked;
  const musicPrivate = document.getElementById('musicPrivate').checked;
  const booksPrivate = document.getElementById('booksPrivate').checked;
  const statisticsPrivate = document.getElementById('statisticsPrivate').checked;

  const errorDiv = document.getElementById('privacyError');
  const successDiv = document.getElementById('privacySuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/privacy`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        movies_private: moviesPrivate,
        tv_shows_private: tvShowsPrivate,
        anime_private: animePrivate,
        video_games_private: videoGamesPrivate,
        music_private: musicPrivate,
        books_private: booksPrivate,
        statistics_private: statisticsPrivate
      })
    });

    if (response.ok) {
      const privacy = await response.json();
      updateDataPrivacyDashboard(privacy);
      successDiv.textContent = 'Privacy settings updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to update privacy settings';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to update privacy settings';
    errorDiv.style.display = 'block';
    console.error('Error updating privacy settings:', error);
  }
}

window.loadTabVisibility = async function () {
  try {
    const response = await authenticatedFetch(`${API_BASE}/account/tab-visibility`);
    if (response.ok) {
      const tabVisibility = await response.json();
      document.getElementById('moviesVisible').checked = tabVisibility.movies_visible;
      document.getElementById('tvShowsVisible').checked = tabVisibility.tv_shows_visible;
      document.getElementById('animeVisible').checked = tabVisibility.anime_visible;
      document.getElementById('videoGamesVisible').checked = tabVisibility.video_games_visible;
      document.getElementById('musicVisible').checked = tabVisibility.music_visible;
      document.getElementById('booksVisible').checked = tabVisibility.books_visible;
      // Update tab visibility in UI
      updateTabVisibilityUI(tabVisibility);
    }
  } catch (error) {
    console.error('Failed to load tab visibility settings:', error);
    // Default to all visible if loading fails
    updateTabVisibilityUI({
      movies_visible: true,
      tv_shows_visible: true,
      anime_visible: true,
      video_games_visible: true,
      music_visible: true,
      books_visible: true
    });
  }
}

window.updateTabVisibility = async function (event) {
  event.preventDefault();

  const moviesVisible = document.getElementById('moviesVisible').checked;
  const tvShowsVisible = document.getElementById('tvShowsVisible').checked;
  const animeVisible = document.getElementById('animeVisible').checked;
  const videoGamesVisible = document.getElementById('videoGamesVisible').checked;
  const musicVisible = document.getElementById('musicVisible').checked;
  const booksVisible = document.getElementById('booksVisible').checked;

  const errorDiv = document.getElementById('tabVisibilityError');
  const successDiv = document.getElementById('tabVisibilitySuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/tab-visibility`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        movies_visible: moviesVisible,
        tv_shows_visible: tvShowsVisible,
        anime_visible: animeVisible,
        video_games_visible: videoGamesVisible,
        music_visible: musicVisible,
        books_visible: booksVisible
      })
    });

    if (response.ok) {
      const tabVisibility = await response.json();
      // Update UI immediately
      updateTabVisibilityUI(tabVisibility);
      
      successDiv.textContent = 'Tab visibility updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to update tab visibility';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to update tab visibility';
    errorDiv.style.display = 'block';
    console.error('Error updating tab visibility:', error);
  }
}

function updateTabVisibilityUI(tabVisibility) {
  // Update tab buttons visibility
  const moviesTab = getTabButton('movies');
  const tvShowsTab = getTabButton('tv-shows');
  const animeTab = getTabButton('anime');
  const videoGamesTab = getTabButton('video-games');
  const musicTab = getTabButton('music');
  const booksTab = getTabButton('books');
  
  if (moviesTab) {
    moviesTab.style.display = tabVisibility.movies_visible ? '' : 'none';
  }
  if (tvShowsTab) {
    tvShowsTab.style.display = tabVisibility.tv_shows_visible ? '' : 'none';
  }
  if (animeTab) {
    animeTab.style.display = tabVisibility.anime_visible ? '' : 'none';
  }
  if (videoGamesTab) {
    videoGamesTab.style.display = tabVisibility.video_games_visible ? '' : 'none';
  }
  if (musicTab) {
    musicTab.style.display = tabVisibility.music_visible ? '' : 'none';
  }
  if (booksTab) {
    booksTab.style.display = tabVisibility.books_visible ? '' : 'none';
  }
  
  // If current tab is hidden, switch to first visible tab
  const currentTabElement = document.querySelector('.tab.active');
  if (currentTabElement && currentTabElement.style.display === 'none') {
    // Find first visible tab
    const allTabs = document.querySelectorAll('.tab');
    for (const tab of allTabs) {
      if (tab.style.display !== 'none') {
        const tabName = tab.dataset.switchTab;
        if (tabName) {
          switchTab(tabName);
          break;
        }
      }
    }
  }
}

// Profile Picture Functions
window.handleProfilePictureSelect = async function (event) {
  const file = event.target.files[0];
  if (!file) return;

  // Validate file type
  const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
  if (!allowedTypes.includes(file.type)) {
    document.getElementById('profilePictureError').textContent = 'Invalid file type. Allowed: JPEG, PNG, GIF, WebP';
    document.getElementById('profilePictureError').style.display = 'block';
    return;
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    document.getElementById('profilePictureError').textContent = 'File size exceeds 5MB limit';
    document.getElementById('profilePictureError').style.display = 'block';
    return;
  }

  // Preview image
  const reader = new FileReader();
  reader.onload = function (e) {
    document.getElementById('profilePicturePreview').src = e.target.result;
  };
  reader.readAsDataURL(file);

  // Upload file
  const formData = new FormData();
  formData.append('file', file);

  const errorDiv = document.getElementById('profilePictureError');
  const successDiv = document.getElementById('profilePictureSuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/profile-picture`, {
      method: 'POST',
      body: formData
    });

    if (response.ok) {
      const updatedUser = await response.json();
      // Update stored user data (getUser and saveAuthData are in auth.js)
      if (typeof getUser !== 'undefined' && typeof saveAuthData !== 'undefined') {
        const user = getUser();
        if (user) {
          user.profile_picture_url = updatedUser.profile_picture_url;
          saveAuthData(null, user);
        }

        // Update display
        if (typeof updateUserDisplay !== 'undefined') {
          updateUserDisplay();
        }
      }

      successDiv.textContent = 'Profile picture updated successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);

      // Show reset button
      document.getElementById('resetProfilePictureBtn').style.display = 'inline-block';
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to upload profile picture';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to upload profile picture';
    errorDiv.style.display = 'block';
    console.error('Error uploading profile picture:', error);
  }
}

window.resetProfilePicture = async function () {
  if (!confirm('Are you sure you want to remove your profile picture?')) {
    return;
  }

  const errorDiv = document.getElementById('profilePictureError');
  const successDiv = document.getElementById('profilePictureSuccess');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';
  successDiv.textContent = '';
  successDiv.style.display = 'none';

  try {
    const response = await authenticatedFetch(`${API_BASE}/account/profile-picture`, {
      method: 'DELETE'
    });

    if (response.ok) {
      const updatedUser = await response.json();
      // Update stored user data (getUser and saveAuthData are in auth.js)
      if (typeof getUser !== 'undefined' && typeof saveAuthData !== 'undefined') {
        const user = getUser();
        if (user) {
          user.profile_picture_url = null;
          saveAuthData(null, user);
        }

        // Update display
        if (typeof updateUserDisplay !== 'undefined') {
          updateUserDisplay();
        }
      }

      // Reset preview
      document.getElementById('profilePicturePreview').src = '/static/default-avatar.svg';
      document.getElementById('profilePictureInput').value = '';
      document.getElementById('resetProfilePictureBtn').style.display = 'none';

      successDiv.textContent = 'Profile picture removed successfully';
      successDiv.style.display = 'block';
      setTimeout(() => {
        successDiv.style.display = 'none';
      }, 3000);
    } else {
      const error = await response.json();
      errorDiv.textContent = error.detail || 'Failed to remove profile picture';
      errorDiv.style.display = 'block';
    }
  } catch (error) {
    errorDiv.textContent = 'Failed to remove profile picture';
    errorDiv.style.display = 'block';
    console.error('Error removing profile picture:', error);
  }
}

// Update loadAccountInfo to also load privacy settings, tab visibility, and profile picture
const originalLoadAccountInfo = window.loadAccountInfo;
window.loadAccountInfo = async function () {
  await originalLoadAccountInfo();
  await loadPrivacySettings();
  await loadTabVisibility();

  // Load profile picture preview
  const user = getUser();
  const previewImg = document.getElementById('profilePicturePreview');
  const resetBtn = document.getElementById('resetProfilePictureBtn');

  if (previewImg) {
    if (user && user.profile_picture_url) {
      previewImg.src = user.profile_picture_url;
      if (resetBtn) resetBtn.style.display = 'inline-block';
    } else {
      previewImg.src = '/static/default-avatar.svg';
      if (resetBtn) resetBtn.style.display = 'none';
    }
  }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
  const modal = document.getElementById('accountModal');
  if (e.target === modal) {
    closeAccountModal();
  }
});

// ============================================================================
// Friends Functions
// ============================================================================

async function loadFriendsList() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends`);
    if (response.ok) {
      const friends = await response.json();
      const friendsList = document.getElementById('friendsList');

      if (friends.length === 0) {
        friendsList.innerHTML = '<p class="no-friends">No friends yet</p>';
        return;
      }

      friendsList.innerHTML = friends.map(friend => `
        <div class="friend-item" data-friend-id="${friend.friend.id}">
          <div class="friend-item-content">
            <img class="friend-profile-picture" src="${friend.friend.profile_picture_url || '/static/default-avatar.svg'}" alt="${escapeHtml(friend.friend.username)}" data-fallback-src="/static/default-avatar.svg">
            <span class="friend-username clickable" data-action="open-friend-profile" data-friend-id="${friend.friend.id}" title="View profile">${escapeHtml(friend.friend.username)}</span>
          </div>
          <button class="unfriend-btn" data-action="unfriend-user" data-friend-id="${friend.friend.id}" title="Unfriend">✕</button>
        </div>
      `).join('');
    }
  } catch (error) {
    console.error('Failed to load friends list:', error);
  }
}

window.openFriendRequestModal = function () {
  document.getElementById('friendRequestModal').style.display = 'flex';
}

// "Friend not on OmniTrackr yet?": share the member's reusable /join link.
async function shareFriendInvite(button) {
  const status = document.getElementById('friendInviteStatus');
  if (button) button.disabled = true;
  try {
    const response = await authenticatedFetch(`${API_BASE}/api/friends/invite-link`, { method: 'POST' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || typeof data.url !== 'string') throw new Error(data.detail || 'Could not create your invite link. Please try again.');
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Join me on OmniTrackr', text: data.text, url: data.url });
        if (status) status.textContent = 'Invite sent. You will get a notification when they join.';
        return;
      } catch (error) {
        if (error && error.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(`${data.text} ${data.url}`);
      if (status) status.textContent = 'Invite link copied. Paste it in a message to your friend.';
    } catch (error) {
      if (status) status.textContent = `Copy this link and send it to your friend: ${data.url}`;
    }
  } catch (error) {
    if (status) status.textContent = error.message || 'Could not create your invite link. Please try again.';
  } finally {
    if (button) button.disabled = false;
  }
}

window.closeFriendRequestModal = function () {
  document.getElementById('friendRequestModal').style.display = 'none';
  document.getElementById('friendRequestForm').reset();
  document.getElementById('friendRequestError').style.display = 'none';
  document.getElementById('friendRequestMessage').style.display = 'none';
  const inviteStatus = document.getElementById('friendInviteStatus');
  if (inviteStatus) inviteStatus.textContent = '';
}

window.sendFriendRequest = async function (event) {
  event.preventDefault();
  const username = document.getElementById('friendRequestUsername').value.trim();
  const errorEl = document.getElementById('friendRequestError');
  const successEl = document.getElementById('friendRequestMessage');

  errorEl.textContent = '';
  errorEl.style.display = 'none';
  successEl.textContent = '';
  successEl.style.display = 'none';

  if (!username) {
    errorEl.textContent = 'Please enter a username';
    errorEl.style.display = 'block';
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ receiver_username: username })
    });

    if (response.ok) {
      successEl.textContent = `Friend request sent to ${username}!`;
      successEl.style.display = 'block';
      document.getElementById('friendRequestForm').reset();
      if (typeof scheduleLibraryLaunchpadRefresh === 'function') scheduleLibraryLaunchpadRefresh(false);
      setTimeout(() => {
        closeFriendRequestModal();
        updateNotificationCount();
      }, 1500);
    } else {
      const error = await response.json();
      errorEl.textContent = error.detail || 'Failed to send friend request';
      errorEl.style.display = 'block';
    }
  } catch (error) {
    errorEl.textContent = 'Failed to send friend request. Please try again.';
    errorEl.style.display = 'block';
  }
}

window.acceptFriendRequest = async function (requestId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/requests/${requestId}/accept`, {
      method: 'POST'
    });

    if (response.ok) {
      loadFriendsList();
      loadNotifications();
      updateNotificationCount();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to accept friend request');
    }
  } catch (error) {
    alert('Failed to accept friend request. Please try again.');
  }
}

window.denyFriendRequest = async function (requestId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/requests/${requestId}/deny`, {
      method: 'POST'
    });

    if (response.ok) {
      loadNotifications();
      updateNotificationCount();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to deny friend request');
    }
  } catch (error) {
    alert('Failed to deny friend request. Please try again.');
  }
}

window.unfriendUser = async function (friendId) {
  if (!confirm('Are you sure you want to unfriend this user?')) {
    return;
  }

  try {
    const response = await authenticatedFetch(`${API_BASE}/friends/${friendId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      loadFriendsList();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to unfriend user');
    }
  } catch (error) {
    alert('Failed to unfriend user. Please try again.');
  }
}

// ============================================================================
// @lazy-chunk lazy/friend-profile.js
