// /join/<token> for signed-in members: add the inviter as a friend with one click.
(function () {
  const button = document.querySelector('[data-join-accept]');
  const status = document.querySelector('[data-join-status]');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const response = await fetch(`/api/friends/invite/${encodeURIComponent(button.dataset.token)}/accept`, {
        method: 'POST', credentials: 'same-origin',
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401) {
        window.location.href = `/?next=${encodeURIComponent(window.location.pathname)}#landing-auth`;
        return;
      }
      if (!response.ok) throw new Error(data.detail || 'Could not add your friend. Please try again.');
      status.textContent = data.added ? `You and ${data.friend} are now friends.` : `You and ${data.friend} are already friends.`;
      button.remove();
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  });
}());
