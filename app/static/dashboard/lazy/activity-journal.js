// Private cross-media activity journal
// ============================================================================

const ACTIVITY_PAGE_SIZE = 30;
let activityTimelineOffset = 0;
let activityWeekOffset = 0;
let activityDiaryMonth = null;
let activityDiaryData = null;
let activityDiarySelected = null;

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
  return { movies: '🎬', 'tv-shows': '📺', anime: '🎌', 'video-games': '🎮', music: '🎵', books: '📚', manga: '🗯️', podcasts: '🎙️' }[category] || '•';
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
    await Promise.all([loadActivityTimeline(true), loadActivityRecap(), loadActivityDiary()]);
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
    await Promise.all([loadActivityTimeline(true), loadActivityRecap(), loadActivityDiary()]);
  } catch (error) {
    alert('Could not remove that journal entry. Please try again.');
  }
}

// Diary: a month calendar of finishes and revisits
// ----------------------------------------------------------------------------

function diaryThumb(entry, className) {
  const thumb = document.createElement('span');
  thumb.className = className;
  if (entry.image) {
    const img = document.createElement('img');
    img.src = entry.image;
    img.alt = '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.addEventListener('error', () => { img.remove(); thumb.textContent = activityIcon(entry.category); }, { once: true });
    thumb.appendChild(img);
  } else {
    thumb.textContent = activityIcon(entry.category);
  }
  return thumb;
}

function diaryDayLabel(isoDate) {
  const [year, month, day] = isoDate.split('-').map(Number);
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
    .format(new Date(year, month - 1, day));
}

function diaryStatsText(data) {
  if (!data.entry_count) return 'Nothing logged this month yet.';
  const parts = [`${data.finished_count} finished`];
  if (data.repeat_count) parts.push(`${data.repeat_count} ${data.repeat_count === 1 ? 'revisit' : 'revisits'}`);
  parts.push(`${data.active_days} ${data.active_days === 1 ? 'day' : 'days'} with something logged`);
  return parts.join(' · ');
}

function renderActivityDiaryGrid(data) {
  const grid = document.getElementById('activityDiaryGrid');
  if (!grid) return;
  grid.replaceChildren();
  for (let blank = 0; blank < data.first_weekday; blank += 1) {
    const cell = document.createElement('span');
    cell.className = 'activity-diary__cell activity-diary__cell--blank';
    cell.setAttribute('aria-hidden', 'true');
    grid.appendChild(cell);
  }
  for (let day = 1; day <= data.days_in_month; day += 1) {
    const iso = `${data.month}-${String(day).padStart(2, '0')}`;
    const entries = (data.days && data.days[iso]) || [];
    const cell = document.createElement(entries.length ? 'button' : 'span');
    cell.className = 'activity-diary__cell';
    if (iso === data.today) cell.classList.add('is-today');
    if (iso > data.today) cell.classList.add('is-future');
    const number = document.createElement('span');
    number.className = 'activity-diary__date';
    number.textContent = String(day);
    cell.appendChild(number);
    if (entries.length) {
      cell.type = 'button';
      cell.dataset.action = 'activity-diary-day';
      cell.dataset.diaryDate = iso;
      cell.classList.add('has-entries');
      if (iso === activityDiarySelected) cell.classList.add('is-selected');
      cell.setAttribute('aria-pressed', iso === activityDiarySelected ? 'true' : 'false');
      cell.setAttribute('aria-label', `${diaryDayLabel(iso)}: ${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}`);
      const thumbs = document.createElement('span');
      thumbs.className = 'activity-diary__thumbs';
      entries.slice(0, 3).forEach(entry => thumbs.appendChild(diaryThumb(entry, 'activity-diary__thumb')));
      cell.appendChild(thumbs);
      const count = document.createElement('span');
      count.className = 'activity-diary__count';
      count.textContent = entries.length > 3 ? `+${entries.length - 3}` : String(entries.length);
      if (entries.length <= 3) count.classList.add('activity-diary__count--compact');
      cell.appendChild(count);
    }
    grid.appendChild(cell);
  }
}

function renderActivityDiaryDay(data) {
  const panel = document.getElementById('activityDiaryDay');
  if (!panel) return;
  panel.replaceChildren();
  const entries = activityDiarySelected && data.days ? data.days[activityDiarySelected] || [] : [];
  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'activity-diary__empty';
    const strong = document.createElement('strong');
    const copy = document.createElement('span');
    if (data.earliest_month) {
      strong.textContent = 'A quiet month.';
      copy.textContent = 'Days with something finished or revisited show a cover. Pick one to see what you logged.';
    } else {
      strong.textContent = 'Your diary fills in as you finish things.';
      copy.textContent = 'Mark a title watched, read, played or listened to, or log a rewatch below, and it lands on today. Coming from Letterboxd? ';
      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'activity-diary__link';
      link.dataset.action = 'launchpad-import';
      link.textContent = 'Import your diary with its dates';
      copy.appendChild(link);
    }
    empty.append(strong, copy);
    panel.appendChild(empty);
    return;
  }
  const heading = document.createElement('h4');
  heading.textContent = diaryDayLabel(activityDiarySelected);
  const list = document.createElement('ul');
  list.className = 'activity-diary__entries';
  entries.forEach(entry => {
    const row = document.createElement('li');
    row.className = 'activity-diary__entry';
    const copy = document.createElement('div');
    copy.className = 'activity-diary__entry-copy';
    const title = document.createElement('strong');
    title.textContent = entry.title;
    const meta = document.createElement('span');
    const bits = [entry.category_label];
    if (entry.repeat) bits.push(`↻ ${entry.visit_label}`);
    if (entry.rating != null) bits.push(`${Number(entry.rating).toFixed(1)}/10`);
    meta.textContent = bits.join(' · ');
    copy.append(title, meta);
    if (entry.note) {
      const note = document.createElement('p');
      note.textContent = entry.note;
      copy.appendChild(note);
    }
    row.append(diaryThumb(entry, 'activity-diary__entry-art'), copy);
    if (entry.item_id) {
      const again = document.createElement('button');
      again.type = 'button';
      again.className = 'action-btn secondary activity-diary__again';
      again.dataset.action = 'activity-diary-log-again';
      again.dataset.diaryCategory = entry.category;
      again.dataset.diaryItemId = String(entry.item_id);
      again.textContent = { 'video-games': 'Log a replay', music: 'Log a relisten', books: 'Log a reread', manga: 'Log a reread', podcasts: 'Log a relisten' }[entry.category] || 'Log a rewatch';
      row.appendChild(again);
    }
    list.appendChild(row);
  });
  panel.append(heading, list);
}

function renderActivityDiary(data) {
  activityDiaryData = data;
  const title = document.getElementById('activityDiaryTitle');
  const stats = document.getElementById('activityDiaryStats');
  if (title) title.textContent = data.label;
  if (stats) stats.textContent = diaryStatsText(data);
  const older = document.getElementById('activityDiaryOlder');
  const newer = document.getElementById('activityDiaryNewer');
  const today = document.getElementById('activityDiaryToday');
  if (older) older.disabled = !data.previous_month;
  if (newer) newer.disabled = !data.next_month;
  if (today) today.disabled = !data.next_month;
  const days = Object.keys(data.days || {}).sort();
  if (!activityDiarySelected || !days.includes(activityDiarySelected)) activityDiarySelected = days[days.length - 1] || null;
  renderActivityDiaryGrid(data);
  renderActivityDiaryDay(data);
}

async function loadActivityDiary() {
  if (!hasStoredAuth()) return;
  const params = new URLSearchParams({ tz_offset_minutes: String(new Date().getTimezoneOffset()) });
  if (activityDiaryMonth) params.set('month', activityDiaryMonth);
  try {
    const response = await authenticatedFetch(`${API_BASE}/activity/diary/?${params}`);
    if (!response.ok) throw new Error('Unable to load diary');
    renderActivityDiary(await response.json());
  } catch (error) {
    const panel = document.getElementById('activityDiaryDay');
    if (panel) panel.textContent = 'Could not load your diary right now.';
  }
}

function changeActivityDiaryMonth(direction) {
  if (!activityDiaryData) return;
  const target = direction < 0 ? activityDiaryData.previous_month : activityDiaryData.next_month;
  if (!target && direction !== 0) return;
  activityDiaryMonth = direction === 0 ? null : target;
  activityDiarySelected = null;
  loadActivityDiary();
}

function selectActivityDiaryDay(isoDate) {
  if (!activityDiaryData || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate || '')) return;
  activityDiarySelected = isoDate;
  renderActivityDiaryGrid(activityDiaryData);
  renderActivityDiaryDay(activityDiaryData);
}

async function logActivityDiaryAgain(category, itemId) {
  const categorySelect = document.getElementById('activityCategory');
  if (!categorySelect || !Number.isInteger(itemId) || itemId < 1) return;
  categorySelect.value = category;
  await populateActivityItems();
  const item = document.getElementById('activityItem');
  if (item) item.value = String(itemId);
  document.getElementById('activityAction').value = 'revisited';
  document.getElementById('activityOccurredAt').value = localDateTimeValue();
  document.getElementById('activityForm')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('activityNote')?.focus({ preventScroll: true });
}

async function loadActivityJournal() {
  setupActivityJournal();
  await Promise.all([populateActivityItems(), loadActivityTimeline(true), loadActivityRecap(), loadActivityDiary()]);
}

