(function () {
  'use strict';
  const token = location.pathname.split('/').filter(Boolean).pop();
  const loading = document.getElementById('postcardLoading');
  const content = document.getElementById('postcardContent');
  const unavailable = document.getElementById('postcardUnavailable');
  const form = document.getElementById('postcardResponseForm');
  let postcard = null;

  function showUnavailable(title, message) {
    loading.hidden = true;
    content.hidden = true;
    unavailable.hidden = false;
    document.getElementById('postcardUnavailableTitle').textContent = title;
    document.getElementById('postcardUnavailableMessage').textContent = message;
  }

  async function loadPostcard() {
    try {
      const response = await fetch(`/recommendations/public/${encodeURIComponent(token)}`, { credentials: 'omit' });
      if (!response.ok) throw new Error('not-found');
      postcard = await response.json();
      if (postcard.state !== 'open') {
        showUnavailable('This postcard is complete.', postcard.state === 'expired' ? 'Its reply window has ended.' : 'It is no longer accepting recommendations.');
        return;
      }
      document.getElementById('postcardOwner').textContent = postcard.owner_username;
      document.getElementById('postcardPrompt').textContent = postcard.prompt;
      document.getElementById('postcardRemaining').textContent = `${postcard.remaining} thoughtful ${postcard.remaining === 1 ? 'reply' : 'replies'} still welcome · closes ${new Date(postcard.expires_at).toLocaleDateString()}`;
      const stamps = document.getElementById('postcardCategories');
      const categorySelect = document.getElementById('postcardCategory');
      postcard.categories.forEach((category) => {
        const stamp = document.createElement('span');
        stamp.textContent = category.label;
        stamps.appendChild(stamp);
        const option = document.createElement('option');
        option.value = category.value;
        option.textContent = category.label;
        categorySelect.appendChild(option);
      });
      loading.hidden = true;
      content.hidden = false;
    } catch (error) {
      showUnavailable('This postcard could not be opened.', 'Check the link with the person who sent it.');
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const status = document.getElementById('postcardFormStatus');
    button.disabled = true;
    status.textContent = 'Delivering…';
    const payload = {
      guest_name: document.getElementById('postcardGuestName').value,
      category: document.getElementById('postcardCategory').value,
      title: document.getElementById('postcardRecommendationTitle').value,
      reason: document.getElementById('postcardReason').value,
      website: document.getElementById('postcardWebsite').value,
    };
    try {
      const response = await fetch(`/recommendations/public/${encodeURIComponent(token)}`, {
        method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Could not send this recommendation.');
      form.replaceChildren();
      const thanks = document.createElement('div');
      thanks.className = 'postcard-thanks';
      const heading = document.createElement('h2');
      heading.textContent = 'Postcard delivered.';
      const note = document.createElement('p');
      note.textContent = 'It will wait in their private inbox until they decide what to do with it.';
      thanks.append(heading, note);
      form.appendChild(thanks);
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  });

  loadPostcard();
})();
