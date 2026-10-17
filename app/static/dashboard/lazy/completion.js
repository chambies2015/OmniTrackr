let activeCompletionMomentId = null;
let activeCompletionCategory = null;
let completionSaving = false;
const COMPLETION_RELOADERS = {
  movies: 'loadMovies', 'tv-shows': 'loadTVShows', anime: 'loadAnime',
  'video-games': 'loadVideoGames', music: 'loadMusic', books: 'loadBooks',
};

function countReviewWords(text) {
  const words = String(text || '').match(/[A-Za-z0-9À-ɏ'’]+/g);
  return words ? words.length : 0;
}

// Live guidance under the finish-modal review box (thresholds mirror review_quality.py).
function completionReviewHint(words) {
  if (words === 0) return '';
  if (words < 15) return `${words} word${words === 1 ? '' : 's'}: keep going, a couple of sentences is plenty`;
  if (words < 40) return `${words} words: a little more and it gets its own page`;
  if (words < 150) return `${words} words: good, this can have its own review page`;
  return `${words} words: a thorough review, thank you`;
}

function updateCompletionReviewMeter() {
  const text = document.getElementById('completionReviewText');
  const count = document.getElementById('completionReviewCount');
  const save = document.getElementById('completionRitualSave');
  const words = countReviewWords(text && text.value);
  if (count) count.textContent = completionReviewHint(words);
  if (save) save.textContent = words ? 'Save reflection and review' : 'Save reflection';
}

function completionReviewMessage(result) {
  if (!result.public) return { text: 'Review saved to your library. Only you can see it.' };
  if (result.standalone) return { text: 'Your review is live on OmniTrackr. ', link: result.review_url, linkText: 'See your review' };
  if (result.listed) {
    return {
      text: 'Your review is on the reviews page and the title page. Add a few more sentences from your library any time and it gets its own page. ',
      link: result.title_url, linkText: 'See the title page',
    };
  }
  return { text: "Review saved. It's a little short to show publicly yet; add a sentence or two from your library and it will appear." };
}

function showCompletionResult(message) {
  const box = document.getElementById('completionReviewResult');
  if (!box) return;
  box.replaceChildren(document.createTextNode(message.text));
  if (message.link && (message.link.startsWith('/reviews/') || /^\/titles\/[a-z]+\/[a-z0-9-]+$/.test(message.link))) {
    const link = document.createElement('a');
    link.href = message.link;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = message.linkText;
    box.appendChild(link);
  }
  box.hidden = false;
}

async function openCompletionMoment(category, itemId) {
  if (!category || !Number.isInteger(itemId) || itemId < 1) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/completion-moments/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, item_id: itemId }),
    });
    if (response.status === 409) {
      alert('Mark this item finished before adding a reflection.');
      return;
    }
    if (!response.ok) throw new Error('Unable to start reflection');
    const moment = await response.json();
    activeCompletionMomentId = moment.id;
    activeCompletionCategory = category;
    document.getElementById('completionRitualTitle').textContent = moment.title;
    document.getElementById('completionRitualTakeaway').value = moment.takeaway || '';
    document.getElementById('completionRitualFavorite').checked = Boolean(moment.favorite);
    const step = document.getElementById('completionReviewStep');
    const text = document.getElementById('completionReviewText');
    const result = document.getElementById('completionReviewResult');
    if (step) step.hidden = moment.has_review !== false;
    if (text) { text.value = ''; text.oninput = updateCompletionReviewMeter; }
    const visibility = document.getElementById('completionReviewPublic');
    if (visibility) visibility.checked = true;
    if (result) { result.hidden = true; result.replaceChildren(); }
    const save = document.getElementById('completionRitualSave');
    if (save) save.dataset.action = 'save-completion-ritual';
    const skip = document.getElementById('completionRitualSkip');
    if (skip) skip.hidden = false;
    updateCompletionReviewMeter();
    document.getElementById('completionRitualModal').style.display = 'flex';
  } catch (error) {
    alert('Could not open the finish ritual. Please try again.');
  }
}

function closeCompletionRitual() {
  const modal = document.getElementById('completionRitualModal');
  if (modal) modal.style.display = 'none';
  activeCompletionMomentId = null;
  activeCompletionCategory = null;
}

async function saveCompletionReview(momentId, review, isPublic) {
  const response = await authenticatedFetch(`${API_BASE}/completion-moments/${momentId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review, public: isPublic }),
  });
  if (response.status === 409) return { conflict: true };
  if (!response.ok) throw new Error('Unable to save review');
  return response.json();
}

async function saveCompletionRitual() {
  if (!activeCompletionMomentId || completionSaving) return;
  const momentId = activeCompletionMomentId;
  const category = activeCompletionCategory;
  const takeaway = document.getElementById('completionRitualTakeaway').value;
  const favorite = document.getElementById('completionRitualFavorite').checked;
  const step = document.getElementById('completionReviewStep');
  const reviewBox = document.getElementById('completionReviewText');
  const review = step && !step.hidden && reviewBox ? reviewBox.value.trim() : '';
  completionSaving = true;
  try {
    const response = await authenticatedFetch(`${API_BASE}/completion-moments/${momentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ takeaway, favorite }),
    });
    if (!response.ok) throw new Error('Unable to save reflection');
    if (typeof loadMonthlyReplay === 'function') loadMonthlyReplay();
    if (!review) {
      closeCompletionRitual();
      return;
    }
    let result;
    try {
      result = await saveCompletionReview(momentId, review, document.getElementById('completionReviewPublic').checked);
    } catch (error) {
      alert('Your reflection was saved, but the review could not be. Your text is still here; please try again.');
      return;
    }
    if (result.conflict) {
      showCompletionResult({ text: 'This title already has a review, so nothing was replaced. You can edit it from your library.' });
    } else {
      showCompletionResult(completionReviewMessage(result));
      const reload = typeof globalThis !== 'undefined' ? globalThis[COMPLETION_RELOADERS[category]] : null;
      if (typeof reload === 'function') reload();
    }
    step.hidden = true;
    reviewBox.value = '';
    const save = document.getElementById('completionRitualSave');
    if (save) { save.textContent = 'Done'; save.dataset.action = 'close-completion-ritual'; }
    const skip = document.getElementById('completionRitualSkip');
    if (skip) skip.hidden = true;
  } catch (error) {
    alert('Could not save your reflection. Please try again.');
  } finally {
    completionSaving = false;
  }
}

function renderMonthlyReplay(replay) {
  const section = document.getElementById('monthlyReplay');
  const period = document.getElementById('monthlyReplayPeriod');
  const content = document.getElementById('monthlyReplayContent');
  if (!section || !period || !content) return;
  period.textContent = replay.month_label || 'This month';
  content.replaceChildren();

  const stats = document.createElement('div');
  stats.className = 'monthly-replay__stats';
  [
    [replay.completed_count || 0, 'finished'],
    [replay.reflection_count || 0, 'reflections'],
    [replay.favorite_count || 0, 'favorites'],
  ].forEach(([value, label]) => {
    const stat = document.createElement('div');
    stat.className = 'monthly-replay__stat';
    const number = document.createElement('strong');
    number.textContent = String(value);
    const caption = document.createElement('span');
    caption.textContent = label;
    stat.append(number, caption);
    stats.appendChild(stat);
  });
  content.appendChild(stats);

  const highlights = Array.isArray(replay.highlights) ? replay.highlights : [];
  if (!highlights.length) {
    const empty = document.createElement('p');
    empty.className = 'monthly-replay__empty';
    empty.textContent = 'Finish something and add a private reflection to start this month’s time capsule.';
    content.appendChild(empty);
  } else {
    const list = document.createElement('div');
    list.className = 'monthly-replay__highlights';
    highlights.forEach((item) => {
      const card = document.createElement('div');
      card.className = 'monthly-replay__highlight';
      const title = document.createElement('strong');
      title.textContent = `${item.favorite ? '★ ' : ''}${item.title}`;
      const meta = document.createElement('span');
      meta.textContent = [item.category_label, item.rating != null ? `${Number(item.rating).toFixed(1)}/10` : 'Unrated'].join(' · ');
      card.append(title, meta);
      if (item.takeaway) {
        const takeaway = document.createElement('p');
        takeaway.textContent = item.takeaway;
        card.appendChild(takeaway);
      }
      list.appendChild(card);
    });
    content.appendChild(list);
  }
  section.removeAttribute('hidden');
}

async function loadMonthlyReplay() {
  if (!hasStoredAuth()) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/completion-moments/replay/`);
    if (response.ok) renderMonthlyReplay(await response.json());
  } catch (error) {
    // Monthly Replay is supplemental and should never block the statistics dashboard.
  }
}

// ============================================================================
