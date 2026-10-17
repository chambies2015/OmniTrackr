// Private cross-media activity journal
// ============================================================================

const ACTIVITY_PAGE_SIZE = 30;
let activityTimelineOffset = 0;
let activityWeekOffset = 0;

function localDateTimeValue(date = new Date()) {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}

function setupActivityJournal() {
  const input = document.getElementById('activityOccurredAt');
  if (input && !input.value) input.value = localDateTimeValue();
}

async function populateActivityItems() {
  const category = document.getElementById('activityCategory')?.value;
  const select = document.getElementById('activityItem');
  if (!category || !select) return;
  select.disabled = true;
  select.replaceChildren(new Option('Loading your library…', ''));
  await refreshLibrarySearchIndex();
  const items = librarySearchIndex
    .filter(item => item.tab === category)
    .sort((a, b) => a.title.localeCompare(b.title));
  select.replaceChildren(new Option(items.length ? 'Choose a library item' : 'No items in this category yet', ''));
  items.forEach(item => select.appendChild(new Option(item.title, String(item.id))));
  select.disabled = !items.length;
}

function activityQuery(reset) {
  if (reset) activityTimelineOffset = 0;
  const params = new URLSearchParams({ limit: String(ACTIVITY_PAGE_SIZE), offset: String(activityTimelineOffset) });
  const category = document.getElementById('activityFilterCategory')?.value;
  const action = document.getElementById('activityFilterAction')?.value;
  if (category) params.set('category', category);
  if (action) params.set('action', action);
  return params;
}

function formatActivityDate(value) {
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short', day: 'numeric', year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
    hour: 'numeric', minute: '2-digit'
  }).format(date);
}

function activityIcon(category) {
  return { movies: '🎬', 'tv-shows': '📺', anime: '🎌', 'video-games': '🎮', music: '🎵', books: '📚' }[category] || '•';
}

function buildActivityCard(entry) {
  const article = document.createElement('article');
  article.className = 'activity-entry';
  const marker = document.createElement('span');
  marker.className = 'activity-entry__marker';
  marker.textContent = activityIcon(entry.category);
  const copy = document.createElement('div');
  copy.className = 'activity-entry__copy';
  const top = document.createElement('div');
  top.className = 'activity-entry__top';
  const heading = document.createElement('h4');
  heading.textContent = entry.title;
  const date = document.createElement('time');
  date.dateTime = entry.occurred_at;
  date.textContent = formatActivityDate(entry.occurred_at);
  top.append(heading, date);
  const meta = document.createElement('p');
  meta.className = 'activity-entry__meta';
  meta.textContent = `${entry.action_label} · ${entry.category_label}${entry.rating != null ? ` · ${Number(entry.rating).toFixed(1)}/10 snapshot` : ''}`;
  copy.append(top, meta);
  if (entry.note) {
    const note = document.createElement('p');
    note.className = 'activity-entry__note';
    note.textContent = entry.note;
    copy.appendChild(note);
  }
  const actions = document.createElement('div');
  actions.className = 'activity-entry__actions';
  const open = document.createElement('button');
  open.type = 'button';
  open.className = 'activity-entry__open';
  open.dataset.action = 'activity-open-library';
  open.dataset.pulseTab = entry.category;
  open.textContent = 'Open library';
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'activity-entry__delete';
  remove.dataset.action = 'delete-activity';
  remove.dataset.activityId = entry.id;
  remove.textContent = 'Remove entry';
  actions.append(open, remove);
  article.append(marker, copy, actions);
  return article;
}

async function loadActivityTimeline(reset = true) {
  if (!hasStoredAuth()) return;
  const container = document.getElementById('activityTimeline');
  const more = document.getElementById('activityLoadMore');
  if (!container || !more) return;
  if (reset) container.textContent = 'Loading your private history…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/activity/?${activityQuery(reset)}`);
    if (!response.ok) throw new Error('Unable to load journal');
    const entries = await response.json();
    if (reset) container.replaceChildren();
    entries.forEach(entry => container.appendChild(buildActivityCard(entry)));
    if (reset && !entries.length) {
      const empty = document.createElement('div');
      empty.className = 'activity-empty';
      empty.innerHTML = '<strong>Your journal starts with the next moment.</strong><span>Log something you begin, revisit, or want to remember. Existing library history has not been guessed or backfilled.</span>';
      container.appendChild(empty);
    }
    activityTimelineOffset += entries.length;
    more.hidden = entries.length < ACTIVITY_PAGE_SIZE;
  } catch (error) {
    if (reset) container.textContent = 'Could not load your journal. Please try again.';
    more.hidden = true;
  }
}

function renderActivityRecap(recap) {
  const period = document.getElementById('activityRecapPeriod');
  const content = document.getElementById('activityRecapContent');
  const newer = document.getElementById('activityNewerWeek');
  if (!period || !content || !newer) return;
  period.textContent = recap.period_label;
  newer.disabled = activityWeekOffset === 0;
  content.replaceChildren();
  const stats = document.createElement('div');
  stats.className = 'activity-recap__stats';
  [[recap.entry_count, 'moments'], [recap.completed_count, 'finished'], [recap.reflection_count, 'with notes']].forEach(([value, label]) => {
    const stat = document.createElement('div');
    stat.className = 'activity-recap__stat';
    const number = document.createElement('strong'); number.textContent = String(value || 0);
    const caption = document.createElement('span'); caption.textContent = label;
    stat.append(number, caption); stats.appendChild(stat);
  });
  content.appendChild(stats);
  const categories = Array.isArray(recap.category_counts) ? recap.category_counts : [];
  if (categories.length) {
    const mix = document.createElement('p');
    mix.className = 'activity-recap__mix';
    mix.textContent = categories.map(item => `${activityIcon(item.category)} ${item.label} ${item.count}`).join('   ·   ');
    content.appendChild(mix);
  } else {
    const empty = document.createElement('p');
    empty.className = 'activity-recap__empty';
    empty.textContent = activityWeekOffset ? 'No moments were logged this week.' : 'Your week is unwritten. Log one media moment whenever it feels worth remembering.';
    content.appendChild(empty);
  }
}

async function loadActivityRecap() {
  if (!hasStoredAuth()) return;
  try {
    const timezoneOffset = new Date().getTimezoneOffset();
    const response = await authenticatedFetch(`${API_BASE}/activity/weekly/?offset=${activityWeekOffset}&tz_offset_minutes=${timezoneOffset}`);
    if (response.ok) renderActivityRecap(await response.json());
  } catch (error) {
    const content = document.getElementById('activityRecapContent');
    if (content) content.textContent = 'Could not load this week right now.';
  }
}

function changeActivityWeek(delta) {
  activityWeekOffset = Math.max(0, Math.min(52, activityWeekOffset + delta));
  loadActivityRecap();
}

async function createActivityEntry(event) {
  event.preventDefault();
  const status = document.getElementById('activityFormStatus');
  const localWhen = document.getElementById('activityOccurredAt').value;
  const payload = {
    category: document.getElementById('activityCategory').value,
    item_id: Number(document.getElementById('activityItem').value),
    action: document.getElementById('activityAction').value,
    note: document.getElementById('activityNote').value,
    occurred_at: localWhen ? new Date(localWhen).toISOString() : new Date().toISOString(),
  };
  if (!payload.item_id) { status.textContent = 'Choose something from your library first.'; return; }
  status.textContent = 'Saving…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/activity/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || 'Could not save this moment');
    }
    document.getElementById('activityNote').value = '';
    document.getElementById('activityOccurredAt').value = localDateTimeValue();
    status.textContent = 'Moment saved.';
    await Promise.all([loadActivityTimeline(true), loadActivityRecap()]);
  } catch (error) {
    status.textContent = error.message || 'Could not save this moment. Please try again.';
  }
}

async function deleteActivityEntry(entryId) {
  if (!Number.isInteger(entryId) || entryId < 1) return;
  if (!confirm('Remove this journal entry? The media item will stay in your library.')) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/activity/${entryId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Unable to remove journal entry');
    await Promise.all([loadActivityTimeline(true), loadActivityRecap()]);
  } catch (error) {
    alert('Could not remove that journal entry. Please try again.');
  }
}

async function loadActivityJournal() {
  setupActivityJournal();
  await Promise.all([populateActivityItems(), loadActivityTimeline(true), loadActivityRecap()]);
}

