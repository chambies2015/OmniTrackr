// Notification Functions
// ============================================================================

async function loadNotifications() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications`);
    if (response.ok) {
      const notifications = await response.json();
      const notificationList = document.getElementById('notificationList');

      if (notifications.length === 0) {
        notificationList.innerHTML = '<p class="no-notifications">No notifications</p>';
        return;
      }

      notificationList.innerHTML = notifications.map(notif => {
        const date = new Date(notif.created_at);
        const timeAgo = getTimeAgo(date);
        let actionButtons = '';

        if (notif.type === 'friend_request_received' && notif.friend_request_id) {
          actionButtons = `
            <button class="notification-action-btn accept-btn" data-action="accept-friend-request" data-request-id="${notif.friend_request_id}">Accept</button>
            <button class="notification-action-btn deny-btn" data-action="deny-friend-request" data-request-id="${notif.friend_request_id}">Deny</button>
          `;
        } else if (notif.type === 'recommendation_received' || notif.type === 'recommendation_invitation') {
          actionButtons = '<button class="notification-action-btn" data-action="open-recommendation-postcards">Open Postcards</button>';
        }

        return `
          <div class="notification-item ${notif.read_at ? 'read' : 'unread'}" data-notification-id="${notif.id}">
            <div class="notification-content">
              <p class="notification-message">${escapeHtml(notif.message)}</p>
              <span class="notification-time">${timeAgo}</span>
              ${actionButtons}
            </div>
            <button class="notification-dismiss" data-action="dismiss-notification" data-notification-id="${notif.id}" title="Dismiss">✕</button>
          </div>
        `;
      }).join('');
    }
  } catch (error) {
    console.error('Failed to load notifications:', error);
  }
}

async function updateNotificationCount() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications/count`);
    if (response.ok) {
      const data = await response.json();
      const notificationDot = document.getElementById('notificationDot');

      if (!notificationDot) {
        console.warn('Notification dot element not found');
        return;
      }

      if (data.count > 0) {
        notificationDot.style.display = 'flex'; // Use flex to center the number
        notificationDot.textContent = data.count > 99 ? '99+' : data.count.toString();
        console.log(`Notification count updated: ${data.count}`);
      } else {
        notificationDot.style.display = 'none';
        console.log('No unread notifications');
      }
    } else {
      console.error('Failed to get notification count:', response.status, response.statusText);
    }
  } catch (error) {
    console.error('Failed to update notification count:', error);
  }
}

window.toggleNotificationDropdown = function () {
  const dropdown = document.getElementById('notificationDropdown');
  if (dropdown.style.display === 'none' || dropdown.style.display === '') {
    dropdown.style.display = 'block';
    loadNotifications();
  } else {
    dropdown.style.display = 'none';
  }
}

window.dismissNotification = async function (notificationId) {
  try {
    const response = await authenticatedFetch(`${API_BASE}/notifications/${notificationId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      loadNotifications();
      updateNotificationCount();
    } else {
      alert('Failed to dismiss notification');
    }
  } catch (error) {
    alert('Failed to dismiss notification. Please try again.');
  }
}

function getTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 4) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

// Initialize friends and notifications
document.addEventListener('DOMContentLoaded', function () {
  // Event delegation for edit/delete/save/cancel buttons (prevents XSS from inline handlers)
  // Movies table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-movie-btn')) {
      e.preventDefault();
      enableMovieEdit(e.target);
    } else if (e.target.classList.contains('delete-movie-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.movieId, 10);
      deleteMovie(id);
    } else if (e.target.classList.contains('save-movie-btn')) {
      e.preventDefault();
      saveMovieEdit(e.target);
    } else if (e.target.classList.contains('cancel-movie-btn')) {
      e.preventDefault();
      cancelMovieEdit();
    }
  });

  // TV Shows table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-tv-btn')) {
      e.preventDefault();
      enableTVEdit(e.target);
    } else if (e.target.classList.contains('delete-tv-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.tvId, 10);
      deleteTVShow(id);
    } else if (e.target.classList.contains('save-tv-btn')) {
      e.preventDefault();
      saveTVEdit(e.target);
    } else if (e.target.classList.contains('cancel-tv-btn')) {
      e.preventDefault();
      cancelTVEdit();
    }
  });

  // Anime table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-anime-btn')) {
      e.preventDefault();
      enableAnimeEdit(e.target);
    } else if (e.target.classList.contains('delete-anime-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.animeId, 10);
      deleteAnime(id);
    } else if (e.target.classList.contains('save-anime-btn')) {
      e.preventDefault();
      saveAnimeEdit(e.target);
    } else if (e.target.classList.contains('cancel-anime-btn')) {
      e.preventDefault();
      cancelAnimeEdit();
    }
  });

  // Video Games table
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('edit-video-game-btn')) {
      e.preventDefault();
      enableVideoGameEdit(e.target);
    } else if (e.target.classList.contains('delete-video-game-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.gameId, 10);
      deleteVideoGame(id);
    } else if (e.target.classList.contains('save-video-game-btn')) {
      e.preventDefault();
      saveVideoGameEdit(e.target);
    } else if (e.target.classList.contains('cancel-video-game-btn')) {
      e.preventDefault();
      cancelVideoGameEdit();
    } else if (e.target.classList.contains('delete-music-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.musicId, 10);
      deleteMusic(id);
    } else if (e.target.classList.contains('edit-music-btn')) {
      e.preventDefault();
      enableMusicEdit(e.target);
    } else if (e.target.classList.contains('save-music-btn')) {
      e.preventDefault();
      saveMusicEdit(e.target);
    } else if (e.target.classList.contains('cancel-music-btn')) {
      e.preventDefault();
      cancelMusicEdit();
    } else if (e.target.classList.contains('delete-book-btn')) {
      e.preventDefault();
      const id = parseInt(e.target.dataset.bookId, 10);
      deleteBook(id);
    } else if (e.target.classList.contains('edit-book-btn')) {
      e.preventDefault();
      enableBookEdit(e.target);
    } else if (e.target.classList.contains('save-book-btn')) {
      e.preventDefault();
      saveBookEdit(e.target);
    } else if (e.target.classList.contains('cancel-book-btn')) {
      e.preventDefault();
      cancelBookEdit();
    }
  });

  // Set up notification bell click handler
  const notificationBell = document.getElementById('notificationBell');
  if (notificationBell) {
    notificationBell.addEventListener('click', toggleNotificationDropdown);
  }

  // Set up friend request button
  const sendFriendRequestBtn = document.getElementById('sendFriendRequestBtn');
  if (sendFriendRequestBtn) {
    sendFriendRequestBtn.addEventListener('click', openFriendRequestModal);
  }

  // Close notification dropdown when clicking outside
  document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('notificationDropdown');
    const bell = document.getElementById('notificationBell');
    if (dropdown && bell && !dropdown.contains(e.target) && !bell.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });

  // Close friend request modal when clicking outside
  document.addEventListener('click', (e) => {
    const modal = document.getElementById('friendRequestModal');
    if (e.target === modal) {
      closeFriendRequestModal();
    }
  });

  initializeFriendsPanel();

  // Initialize FAQ accordion functionality
  const faqQuestions = document.querySelectorAll('.faq-question');
  faqQuestions.forEach(question => {
    question.addEventListener('click', function () {
      const isExpanded = this.getAttribute('aria-expanded') === 'true';
      const answer = this.nextElementSibling;

      // Close all other FAQ items
      faqQuestions.forEach(q => {
        if (q !== this) {
          q.setAttribute('aria-expanded', 'false');
          q.nextElementSibling.style.maxHeight = '0';
          q.nextElementSibling.style.padding = '0 24px';
        }
      });

      // Toggle current item
      if (isExpanded) {
        this.setAttribute('aria-expanded', 'false');
        answer.style.maxHeight = '0';
        answer.style.padding = '0 24px';
      } else {
        this.setAttribute('aria-expanded', 'true');
        answer.style.maxHeight = answer.scrollHeight + 'px';
        answer.style.padding = '0 24px 20px 24px';
      }
    });
  });

  // Load friends list and notification count on page load (if logged in).
  // Opening the dashboard (showMainUI in auth.js) normally starts both already;
  // starting them again would fetch twice and leave a second 30-second poll running.
  if (isAuthenticated()) {
    const alreadyStarted = Boolean(notificationCountInterval);
    if (!alreadyStarted) {
      loadFriendsList();
      updateNotificationCount();
    }
    
    // Load tab visibility settings
    dashboardTabVisibilityReady = loadTabVisibility();

    // Set up interval to refresh notification count every 30 seconds
    if (!alreadyStarted) notificationCountInterval = setInterval(updateNotificationCount, 30000);
  }
});

// Friends is an independent disclosure panel; opening it never changes page geometry.
function positionFriendsPanel() {
  const sidebar = document.getElementById('friendsSidebar');
  const toolbar = document.querySelector('.account-toolbar');
  if (!sidebar || sidebar.hidden || !toolbar) return;
  const bounds = toolbar.getBoundingClientRect();
  const viewport = document.documentElement;
  const top = Math.max(12, Math.min(bounds.bottom + 8, (window.innerHeight || viewport.clientHeight) - 160));
  const right = Math.max(12, viewport.clientWidth - bounds.right);
  sidebar.style.setProperty('--friends-panel-top', `${top}px`);
  sidebar.style.setProperty('--friends-panel-right', `${right}px`);
}

function setFriendsSidebarOpen(open, { persist = true, restoreFocus = false, focusPanel = false } = {}) {
  const sidebar = document.getElementById('friendsSidebar');
  const trigger = document.getElementById('showFriendsSidebar');
  const authenticated = isAuthenticated();
  const expanded = Boolean(open && authenticated);
  if (trigger) {
    trigger.hidden = !authenticated;
    trigger.style.removeProperty('display');
    trigger.setAttribute('aria-expanded', String(expanded));
    trigger.setAttribute('aria-controls', 'friendsSidebar');
  }
  if (!sidebar) return;
  const wasOpen = !sidebar.hidden;
  sidebar.hidden = !expanded;
  sidebar.classList.toggle('hidden', !expanded);
  sidebar.style.removeProperty('display');
  if (expanded) {
    positionFriendsPanel();
    if (focusPanel) document.getElementById('toggleFriendsSidebar')?.focus();
  } else if (restoreFocus && wasOpen && authenticated) {
    trigger?.focus();
  }
  if (persist && authenticated) {
    try {
      localStorage.setItem('friendsSidebarHidden', String(!expanded));
    } catch (error) {
      // The panel remains usable when browser storage is unavailable.
    }
  }
}

window.toggleFriendsSidebar = function () {
  const sidebar = document.getElementById('friendsSidebar');
  if (sidebar) setFriendsSidebarOpen(sidebar.hidden, { focusPanel: sidebar.hidden, restoreFocus: !sidebar.hidden });
};

window.showFriendsSidebar = function () {
  toggleFriendsSidebar();
};

function restoreSidebarState() {
  // Friends starts closed so it never covers the library on a first visit;
  // members who opened it keep it open ("false" is stored when they do).
  let sidebarHidden = true;
  try {
    sidebarHidden = localStorage.getItem('friendsSidebarHidden') !== 'false';
  } catch (error) {
    // Use the default state when browser storage is unavailable.
  }
  setFriendsSidebarOpen(!sidebarHidden, { persist: false });
}

window.resetFriendsPanel = function () {
  setFriendsSidebarOpen(false, { persist: false });
};

function friendsPanelHasActiveModal() {
  return Array.from(document.querySelectorAll('.modal-overlay, dialog[open], .screenshot-modal.show')).some(modal => {
    const style = window.getComputedStyle(modal);
    return !modal.hidden && style.display !== 'none' && style.visibility !== 'hidden';
  });
}

let friendsPanelInitialized = false;
function initializeFriendsPanel() {
  if (friendsPanelInitialized) return;
  friendsPanelInitialized = true;
  document.getElementById('toggleFriendsSidebar')?.addEventListener('click', () => {
    setFriendsSidebarOpen(false, { restoreFocus: true });
  });
  document.getElementById('showFriendsSidebar')?.addEventListener('click', showFriendsSidebar);
  // Capture phase checks overlays before their own close handlers run.
  document.addEventListener('click', event => {
    const sidebar = document.getElementById('friendsSidebar');
    const trigger = document.getElementById('showFriendsSidebar');
    if (!sidebar || sidebar.hidden || sidebar.contains(event.target) || trigger?.contains(event.target) || friendsPanelHasActiveModal()) return;
    setFriendsSidebarOpen(false);
  }, true);
  document.addEventListener('keydown', event => {
    const sidebar = document.getElementById('friendsSidebar');
    if (event.key !== 'Escape' || event.defaultPrevented || !sidebar || sidebar.hidden || friendsPanelHasActiveModal()) return;
    event.preventDefault();
    setFriendsSidebarOpen(false, { restoreFocus: true });
  }, true);
  window.addEventListener('resize', positionFriendsPanel);
  window.addEventListener('scroll', positionFriendsPanel, { passive: true });
  restoreSidebarState();
}

// @lazy-chunk lazy/completion.js
// @lazy-chunk lazy/tasteprint.js
// @lazy-chunk lazy/activity-journal.js
