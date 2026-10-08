// ============================================================================
// Recommendation Postcards
// ============================================================================

let recommendationFriends = [];

function postcardElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function recommendationError(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (error) {
    return fallback;
  }
}

async function loadRecommendationFriends() {
  try {
    const response = await authenticatedFetch(`${API_BASE}/friends`);
    recommendationFriends = response.ok ? await response.json() : [];
  } catch (error) {
    recommendationFriends = [];
  }
}

function renderRecommendationRequests(postcards) {
  const container = document.getElementById('recommendationRequests');
  if (!container) return;
  container.replaceChildren();
  if (!postcards.length) {
    const empty = postcardElement('div', 'postcards-empty');
    empty.append(postcardElement('strong', '', 'No postcards sent yet.'), postcardElement('span', '', 'Ask a focused question above—the best prompts are about a mood, moment, or specific curiosity.'));
    container.appendChild(empty);
    return;
  }
  postcards.forEach((postcard) => {
    const card = postcardElement('article', `postcard-request postcard-request--${postcard.state}`);
    const state = postcardElement('span', 'postcard-state', postcard.state);
    const prompt = postcardElement('h4', '', postcard.prompt);
    const meta = postcardElement('p', 'postcard-meta', `${postcard.response_count}/${postcard.max_responses} replies · closes ${new Date(postcard.expires_at).toLocaleDateString()}`);
    const categories = postcardElement('p', 'postcard-categories', postcard.categories.map(item => item.label).join(' · '));
    const actions = postcardElement('div', 'postcard-actions');
    const copy = postcardElement('button', 'action-btn', 'Copy guest link');
    copy.type = 'button'; copy.dataset.action = 'copy-recommendation-link'; copy.dataset.sharePath = postcard.share_path;
    actions.appendChild(copy);
    if (postcard.state === 'open' && recommendationFriends.length) {
      const select = document.createElement('select');
      select.id = `recommendationFriend-${postcard.id}`;
      select.setAttribute('aria-label', 'Choose a friend');
      const placeholder = document.createElement('option');
      placeholder.value = ''; placeholder.textContent = 'Choose a friend';
      select.appendChild(placeholder);
      recommendationFriends.forEach((friendship) => {
        const option = document.createElement('option');
        option.value = String(friendship.friend.id);
        option.textContent = friendship.friend.username;
        select.appendChild(option);
      });
      const invite = postcardElement('button', 'action-btn secondary', 'Invite');
      invite.type = 'button'; invite.dataset.action = 'invite-recommendation-friend'; invite.dataset.requestId = String(postcard.id);
      actions.append(select, invite);
    }
    if (postcard.state === 'open') {
      const close = postcardElement('button', 'action-btn secondary', 'Close');
      close.type = 'button'; close.dataset.action = 'close-recommendation-request'; close.dataset.requestId = String(postcard.id);
      actions.appendChild(close);
    }
    card.append(state, prompt, meta, categories, actions);
    container.appendChild(card);
  });
}

function renderRecommendationInbox(entries) {
  const container = document.getElementById('recommendationInbox');
  if (!container) return;
  container.replaceChildren();
  if (!entries.length) {
    const empty = postcardElement('div', 'postcards-empty');
    empty.append(postcardElement('strong', '', 'Your inbox is quiet.'), postcardElement('span', '', 'Replies will arrive here as private cards for you to review.'));
    container.appendChild(empty);
    return;
  }
  entries.forEach((entry) => {
    const card = postcardElement('article', `postcard-reply postcard-reply--${entry.status}`);
    const header = postcardElement('div', 'postcard-reply__header');
    header.append(postcardElement('span', 'postcard-reply__category', entry.category_label), postcardElement('span', 'postcard-state', entry.status));
    const title = postcardElement('h4', '', entry.title);
    const from = postcardElement('p', 'postcard-meta', `From ${entry.guest_name} · ${new Date(entry.created_at).toLocaleDateString()}`);
    const reason = postcardElement('blockquote', '', entry.reason);
    card.append(header, title, from, reason);
    if (entry.status !== 'accepted') {
      const actions = postcardElement('div', 'postcard-actions');
      [['save', 'Save for later'], ['library', 'Add to library'], ['next-up', 'Add to Next Up'], ['dismiss', 'Dismiss']].forEach(([action, label]) => {
        const button = postcardElement('button', action === 'dismiss' ? 'action-btn secondary' : 'action-btn', label);
        button.type = 'button'; button.dataset.action = 'triage-recommendation'; button.dataset.submissionId = String(entry.id); button.dataset.triageAction = action;
        actions.appendChild(button);
      });
      card.appendChild(actions);
    } else {
      card.appendChild(postcardElement('p', 'postcard-accepted-note', 'Accepted into your library. The original recommendation remains here as context.'));
    }
    container.appendChild(card);
  });
}

function renderRecommendationInvitations(invitations) {
  const container = document.getElementById('recommendationInvitations');
  if (!container) return;
  container.replaceChildren();
  const openInvitations = invitations.filter(invitation => !invitation.responded);
  if (!openInvitations.length) {
    const empty = postcardElement('div', 'postcards-empty');
    empty.append(postcardElement('strong', '', 'No postcards need a reply.'), postcardElement('span', '', 'When a friend asks for a pick, their question will appear here.'));
    container.appendChild(empty);
    return;
  }
  openInvitations.forEach((invitation) => {
    const card = postcardElement('article', 'postcard-invitation');
    card.append(postcardElement('p', 'postcard-meta', `From ${invitation.sender_username} · closes ${new Date(invitation.expires_at).toLocaleDateString()}`), postcardElement('h4', '', invitation.prompt));
    const form = postcardElement('form', 'postcard-invitation__form');
    form.dataset.submitAction = 'respond-recommendation'; form.dataset.requestId = String(invitation.request_id);
    const categoryLabel = postcardElement('label', '', 'Media type');
    const select = document.createElement('select'); select.name = 'category'; select.required = true;
    invitation.categories.forEach((category) => { const option = document.createElement('option'); option.value = category.value; option.textContent = category.label; select.appendChild(option); });
    categoryLabel.appendChild(select);
    const titleLabel = postcardElement('label', '', 'Title');
    const title = document.createElement('input'); title.name = 'title'; title.maxLength = 200; title.required = true; title.placeholder = 'Your pick'; titleLabel.appendChild(title);
    const reasonLabel = postcardElement('label', '', 'Why it fits');
    const reason = document.createElement('textarea'); reason.name = 'reason'; reason.minLength = 20; reason.maxLength = 500; reason.rows = 3; reason.required = true; reason.placeholder = 'Give them a specific reason to try it.'; reasonLabel.appendChild(reason);
    const submit = postcardElement('button', 'action-btn', 'Send recommendation'); submit.type = 'submit';
    const formStatus = postcardElement('span', 'postcard-form-status'); formStatus.setAttribute('role', 'status');
    form.append(categoryLabel, titleLabel, reasonLabel, submit, formStatus);
    card.appendChild(form);
    container.appendChild(card);
  });
}

async function loadRecommendationPostcards() {
  const requestsContainer = document.getElementById('recommendationRequests');
  if (!requestsContainer || !hasStoredAuth()) return;
  try {
    await loadRecommendationFriends();
    const [requestsResponse, inboxResponse, invitationsResponse] = await Promise.all([
      authenticatedFetch(`${API_BASE}/recommendations/requests/`),
      authenticatedFetch(`${API_BASE}/recommendations/inbox/`),
      authenticatedFetch(`${API_BASE}/recommendations/invitations/`),
    ]);
    if (!requestsResponse.ok || !inboxResponse.ok || !invitationsResponse.ok) throw new Error('Unable to load postcards');
    const [postcards, inbox, invitations] = await Promise.all([requestsResponse.json(), inboxResponse.json(), invitationsResponse.json()]);
    renderRecommendationRequests(postcards);
    renderRecommendationInbox(inbox);
    renderRecommendationInvitations(invitations);
  } catch (error) {
    requestsContainer.textContent = 'Could not load your postcards. Please try again.';
  }
}

async function createRecommendationRequest(event) {
  event.preventDefault();
  const form = event.target;
  const status = document.getElementById('recommendationCreateStatus');
  const categories = Array.from(form.querySelectorAll('input[name="recommendationCategory"]:checked')).map(input => input.value);
  if (!categories.length) { status.textContent = 'Choose at least one media type.'; return; }
  const button = form.querySelector('button[type="submit"]'); button.disabled = true; status.textContent = 'Creating…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/recommendations/requests/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        prompt: document.getElementById('recommendationPrompt').value,
        categories,
        expires_in_days: Number(document.getElementById('recommendationExpiry').value),
        max_responses: Number(document.getElementById('recommendationMaxResponses').value),
      }),
    });
    if (!response.ok) throw new Error(await recommendationError(response, 'Could not create the postcard.'));
    form.reset();
    form.querySelectorAll('input[name="recommendationCategory"]').forEach(input => { input.checked = true; });
    document.getElementById('recommendationExpiry').value = '7'; document.getElementById('recommendationMaxResponses').value = '10';
    status.textContent = 'Postcard ready.';
    await loadRecommendationPostcards();
  } catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
}

async function copyRecommendationLink(sharePath) {
  const link = new URL(sharePath, location.origin).href;
  try { await navigator.clipboard.writeText(link); alert('Guest link copied. It contains access to this one postcard only.'); }
  catch (error) { window.prompt('Copy this guest link:', link); }
}

async function closeRecommendationRequest(requestId) {
  if (!confirm('Close this postcard? Existing replies stay in your inbox, but the link will stop accepting new ones.')) return;
  const response = await authenticatedFetch(`${API_BASE}/recommendations/requests/${requestId}/close`, { method: 'POST' });
  if (!response.ok) { alert(await recommendationError(response, 'Could not close the postcard.')); return; }
  loadRecommendationPostcards();
}

async function inviteRecommendationFriend(requestId) {
  const select = document.getElementById(`recommendationFriend-${requestId}`);
  const friendId = Number(select?.value);
  if (!friendId) { alert('Choose a friend first.'); return; }
  const response = await authenticatedFetch(`${API_BASE}/recommendations/requests/${requestId}/invite`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ friend_id: friendId }),
  });
  if (!response.ok) { alert(await recommendationError(response, 'Could not send the invitation.')); return; }
  alert('Postcard invitation sent.');
  loadRecommendationPostcards();
}

async function triageRecommendation(submissionId, action) {
  const response = await authenticatedFetch(`${API_BASE}/recommendations/submissions/${submissionId}/triage`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }),
  });
  if (!response.ok) { alert(await recommendationError(response, 'Could not update that recommendation.')); return; }
  librarySearchIndexReady = false;
  loadRecommendationPostcards();
}

async function respondToRecommendation(event) {
  event.preventDefault();
  const form = event.target; const button = form.querySelector('button[type="submit"]'); const status = form.querySelector('[role="status"]');
  button.disabled = true; status.textContent = 'Sending…';
  const response = await authenticatedFetch(`${API_BASE}/recommendations/requests/${form.dataset.requestId}/respond`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      category: form.elements.category.value, title: form.elements.title.value, reason: form.elements.reason.value,
    }),
  });
  if (!response.ok) { status.textContent = await recommendationError(response, 'Could not send your recommendation.'); button.disabled = false; return; }
  status.textContent = 'Delivered.';
  loadRecommendationPostcards();
}

