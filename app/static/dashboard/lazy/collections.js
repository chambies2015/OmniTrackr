async function loadCollections() {
  if (!hasStoredAuth()) return;
  try {
    const response = await authenticatedFetch(`${API_BASE}/collections/`);
    if (!response.ok) throw new Error('Unable to load collections');
    collectionsCache = await response.json();
    renderCollections(collectionsCache);
    loadModeratorInsights();
    return collectionsCache;
  } catch (error) {
    const container = document.getElementById('collectionsList');
    if (container) container.textContent = 'Could not load collections. Please try again.';
    return null;
  }
}

function renderCollections(collections) {
  const container = document.getElementById('collectionsList');
  if (!container) return;
  container.replaceChildren();
  if (!collections.length) {
    const empty = document.createElement('p');
    empty.className = 'collections-empty';
    empty.textContent = 'Start with a feeling, a theme, or a future plan. Then add anything from your library — including anime.';
    container.appendChild(empty);
    return;
  }
  collections.forEach((collection) => {
    const card = document.createElement('article');
    card.id = `collection-${collection.id}`;
    card.className = 'collection-card';
    const header = document.createElement('div');
    header.className = 'collection-card__header';
    const copy = document.createElement('div');
    const name = document.createElement('h3');
    name.textContent = collection.name;
    const count = document.createElement('span');
    count.className = 'collection-card__count';
    count.textContent = `${collection.items.length} item${collection.items.length === 1 ? '' : 's'}`;
    copy.append(name, count);
    const actions = document.createElement('div');
    actions.className = 'collection-card__actions';
    const status = document.createElement('span');
    status.className = `collection-card__status${collection.is_public ? ' is-public' : ''}`;
    status.textContent = collection.is_public
      ? ({
          approved: 'Public · Discoverable',
          rejected: 'Public · Blocked',
          suspended: 'Public · Temporarily unlisted',
        }[collection.moderation_status] || 'Public · Direct link only')
      : 'Private';
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'collection-card__edit';
    edit.dataset.action = 'open-collection-studio';
    edit.dataset.collectionId = collection.id;
    edit.textContent = 'Edit & share';
    actions.append(status, edit);
    if (collection.is_public && collection.public_url) {
      const publicLink = document.createElement('a');
      publicLink.className = 'collection-card__public-link';
      publicLink.href = collection.public_url;
      publicLink.target = '_blank';
      publicLink.rel = 'noopener noreferrer';
      publicLink.textContent = 'View public page ↗';
      actions.appendChild(publicLink);
    }
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'collection-card__delete';
    remove.dataset.action = 'delete-collection';
    remove.dataset.collectionId = collection.id;
    remove.textContent = 'Delete';
    actions.appendChild(remove);
    header.append(copy, actions);
    card.appendChild(header);
    if (collection.description) {
      const description = document.createElement('p');
      description.className = 'collection-card__description';
      description.textContent = collection.description;
      card.appendChild(description);
    }
    const itemList = document.createElement('div');
    itemList.className = 'collection-card__items';
    if (!collection.items.length) {
      const empty = document.createElement('p');
      empty.className = 'collection-card__empty';
      empty.textContent = 'Open any media tab and choose Collect to add the first item.';
      itemList.appendChild(empty);
    } else {
      collection.items.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = `collection-card__item${item.available ? '' : ' is-unavailable'}`;
        const itemCopy = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = item.title;
        const meta = document.createElement('span');
        meta.textContent = item.available ? item.category_label : 'Deleted library item';
        itemCopy.append(title, meta);
        if (item.curator_note) {
          const note = document.createElement('p');
          note.className = 'collection-card__item-note';
          note.textContent = item.curator_note;
          itemCopy.appendChild(note);
        }
        const controls = document.createElement('div');
        controls.className = 'collection-card__item-controls';
        const up = document.createElement('button');
        up.type = 'button';
        up.dataset.action = 'move-collection-item';
        up.dataset.collectionId = collection.id;
        up.dataset.collectionItemId = item.id;
        up.dataset.collectionPosition = Math.max(index - 1, 0);
        up.disabled = index === 0;
        up.setAttribute('aria-label', `Move ${item.title} up`);
        up.textContent = '↑';
        const down = document.createElement('button');
        down.type = 'button';
        down.dataset.action = 'move-collection-item';
        down.dataset.collectionId = collection.id;
        down.dataset.collectionItemId = item.id;
        down.dataset.collectionPosition = index + 1;
        down.disabled = index === collection.items.length - 1;
        down.setAttribute('aria-label', `Move ${item.title} down`);
        down.textContent = '↓';
        const removeItem = document.createElement('button');
        removeItem.type = 'button';
        removeItem.dataset.action = 'remove-collection-item';
        removeItem.dataset.collectionId = collection.id;
        removeItem.dataset.collectionItemId = item.id;
        removeItem.textContent = 'Remove';
        const editNote = document.createElement('button');
        editNote.type = 'button';
        editNote.dataset.action = 'edit-collection-note';
        editNote.dataset.collectionId = collection.id;
        editNote.dataset.collectionItemId = item.id;
        editNote.textContent = item.curator_note ? 'Edit note' : 'Add note';
        controls.append(up, down, editNote, removeItem);
        row.append(itemCopy, controls);
        itemList.appendChild(row);
      });
    }
    card.appendChild(itemList);
    container.appendChild(card);
  });
}

function moderatorNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(Number(value) || 0);
}

function moderatorDate(value, includeTime = false) {
  if (!value) return 'No activity yet';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Unknown';
  return new Intl.DateTimeFormat(undefined, includeTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' }).format(parsed);
}

function appendModeratorMetric(container, label, value, detail) {
  const card = document.createElement('article');
  card.className = 'moderator-metric';
  const labelElement = document.createElement('span');
  labelElement.textContent = label;
  const valueElement = document.createElement('strong');
  valueElement.textContent = moderatorNumber(value);
  const detailElement = document.createElement('small');
  detailElement.textContent = detail;
  card.append(labelElement, valueElement, detailElement);
  container.appendChild(card);
}

function renderModeratorStatList(container, rows) {
  container.replaceChildren();
  rows.forEach(([label, value]) => {
    const row = document.createElement('div');
    const term = document.createElement('dt');
    term.textContent = label;
    const description = document.createElement('dd');
    description.textContent = moderatorNumber(value);
    row.append(term, description);
    container.appendChild(row);
  });
}

function renderModeratorInsights(data) {
  const panel = document.getElementById('moderatorInsightsPanel');
  const metricGrid = document.getElementById('moderatorMetricGrid');
  if (!panel || !metricGrid) return;
  panel.hidden = false;
  document.getElementById('moderatorInsightsGenerated').textContent = `Updated ${moderatorDate(data.generated_at, true)}`;
  document.getElementById('moderatorInsightsPrivacy').textContent = data.privacy_note;

  metricGrid.replaceChildren();
  appendModeratorMetric(metricGrid, 'Accounts', data.users.total, `${moderatorNumber(data.users.new_30_days)} joined in 30 days`);
  appendModeratorMetric(metricGrid, 'Libraries started', data.users.with_library_items, `${moderatorNumber(data.users.active)} active · ${moderatorNumber(data.users.verified)} verified`);
  appendModeratorMetric(metricGrid, 'Library items', data.content.total_items, `${moderatorNumber(data.content.completion_percentage)}% marked complete`);
  appendModeratorMetric(metricGrid, 'Public reach', data.moderation.views, `${moderatorNumber(data.moderation.helpful)} helpful votes`);

  const growth = document.getElementById('moderatorGrowthChart');
  const maxSignups = Math.max(1, ...data.growth.map(day => day.signups));
  growth.replaceChildren();
  data.growth.forEach(day => {
    const bar = document.createElement('span');
    bar.style.height = `${Math.max(3, (day.signups / maxSignups) * 100)}%`;
    bar.title = `${moderatorDate(`${day.date}T12:00:00`)}: ${day.signups} new account${day.signups === 1 ? '' : 's'}`;
    growth.appendChild(bar);
  });
  document.getElementById('moderatorGrowthTotal').textContent = `${moderatorNumber(data.users.new_30_days)} total`;

  const activationStages = document.getElementById('moderatorActivationStages');
  activationStages.replaceChildren();
  data.activation.forEach((stage, index) => {
    const item = document.createElement('article');
    item.className = 'moderator-activation-stage';
    const step = document.createElement('span');
    step.textContent = String(index + 1).padStart(2, '0');
    const copy = document.createElement('div');
    const label = document.createElement('strong');
    label.textContent = stage.label;
    const rate = document.createElement('small');
    rate.textContent = index === 0
      ? 'Baseline'
      : `${moderatorNumber(stage.step_rate)}% from prior step · ${moderatorNumber(stage.account_rate)}% of accounts`;
    copy.append(label, rate);
    const count = document.createElement('b');
    count.textContent = moderatorNumber(stage.count);
    item.append(step, copy, count);
    activationStages.appendChild(item);
  });

  const categoryStats = document.getElementById('moderatorCategoryStats');
  const maxCategory = Math.max(1, ...data.content.categories.map(category => category.total));
  categoryStats.replaceChildren();
  data.content.categories.forEach(category => {
    const row = document.createElement('div');
    row.className = 'moderator-category-row';
    const label = document.createElement('span');
    label.textContent = category.label;
    const bar = document.createElement('div');
    bar.className = 'moderator-category-bar';
    const fill = document.createElement('i');
    fill.style.width = `${(category.total / maxCategory) * 100}%`;
    bar.appendChild(fill);
    const total = document.createElement('strong');
    total.textContent = moderatorNumber(category.total);
    row.append(label, bar, total);
    categoryStats.appendChild(row);
  });
  document.getElementById('moderatorCompletionRate').textContent = `${moderatorNumber(data.content.completion_percentage)}% complete`;

  renderModeratorStatList(document.getElementById('moderatorEngagementStats'), [
    ['Journal entries · 7 days', data.engagement.activity_entries_7_days],
    ['Journal entries · 30 days', data.engagement.activity_entries_30_days],
    ['Journal contributors · 30 days', data.engagement.active_journal_users_30_days],
    ['Completion moments', data.engagement.completion_moments],
    ['Next Up entries', data.engagement.next_up_items],
    ['Rated library items', data.content.rated_items],
    ['Written reviews', data.content.reviewed_items],
    ['Public reviews', data.content.public_reviews],
    ['Custom tracker items', data.content.custom_items],
    ['Friendships', data.engagement.friendships],
    ['Recommendation requests', data.engagement.recommendation_requests],
    ['Recommendation replies', data.engagement.recommendation_submissions],
    ['Welcome Back shown', data.engagement.return_deck_shown],
    ['Welcome Back opened', data.engagement.return_deck_opened],
    ['Welcome Back dismissed', data.engagement.return_deck_dismissed],
  ]);
  const safetyRows = [
    ['Public collections', data.moderation.public],
    ['Direct-link only', data.moderation.pending],
    ['Discoverable', data.moderation.approved],
    ['Automatically unlisted', data.moderation.collection_unlistings],
    ['Emergency blocks', data.moderation.rejected],
    ['Reports', data.moderation.reports],
    ['Public review reports', data.moderation.review_reports],
    ['Review versions unlisted', data.moderation.review_unlistings],
    ['Unverified over 7 days', data.users.unverified_older_than_7_days],
    ['Deactivated accounts', data.users.deactivated],
    ['Empty libraries', data.users.without_library_items],
  ];
  data.moderation.reports_by_reason.slice(0, 3).forEach(report => {
    safetyRows.push([`Reports · ${report.reason}`, report.count]);
  });
  renderModeratorStatList(document.getElementById('moderatorSafetyStats'), safetyRows);

  const usersBody = document.getElementById('moderatorUsersBody');
  usersBody.replaceChildren();
  data.recent_users.forEach(user => {
    const row = document.createElement('tr');
    const username = document.createElement('td');
    username.textContent = user.username;
    const statusCell = document.createElement('td');
    const status = document.createElement('span');
    status.className = `moderator-user-status${user.is_active && user.is_verified ? ' is-healthy' : ''}`;
    status.textContent = !user.is_active ? 'Inactive' : user.is_verified ? 'Verified' : 'Unverified';
    statusCell.appendChild(status);
    const values = [
      moderatorDate(user.joined_at),
      moderatorNumber(user.library_items),
      moderatorNumber(user.activity_entries),
      moderatorNumber(user.public_collections),
      moderatorDate(user.last_activity_at),
    ];
    row.append(username, statusCell, ...values.map(value => {
      const cell = document.createElement('td');
      cell.textContent = value;
      return cell;
    }));
    usersBody.appendChild(row);
  });
}

