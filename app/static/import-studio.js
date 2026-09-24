/* Private, preview-first CSV migration. Files and previews live only in this page. */
let importStudioPreview = null;
let importStudioContext = null;
let importStudioController = null;
let importStudioGeneration = 0;
let importStudioFileGeneration = 0;
let importStudioInspecting = false;
let importStudioApplying = false;
let importStudioFilter = 'all';
const IMPORT_STUDIO_PAGE_SIZE = 25;
const importStudioMappingFields = [
  ['category', 'Media category'], ['title', 'Title'], ['year', 'Year'],
  ['creator', 'Director / artist / author'], ['rating', 'Rating (0–10)'],
  ['status', 'Completion / status'], ['review', 'Private note / review'],
  ['genre', 'Genre'], ['seasons', 'Seasons'], ['episodes', 'Episodes'], ['release_date', 'Release date']
];
const importStudioCategories = {
  movies: ['Movies', 'Watched', 'Not watched'], 'tv-shows': ['TV shows', 'Watched', 'Not watched'],
  anime: ['Anime', 'Watched', 'Not watched'], 'video-games': ['Games', 'Played', 'Not played'],
  music: ['Music', 'Listened', 'Not listened'], books: ['Books', 'Read', 'Not read']
};

function importStudioElement(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function importStudioAccountKey() {
  try {
    const user = getUser();
    return JSON.stringify([user?.id ?? user?.username ?? null, getToken()]);
  } catch (_) { return ''; }
}

function getImportStudioMapping() {
  const mapping = {};
  document.querySelectorAll('[data-import-map-target]').forEach(select => {
    if (select.value) mapping[select.dataset.importMapTarget] = select.value;
  });
  return mapping;
}

function importStudioSnapshot() {
  return {
    file: document.getElementById('importStudioFile')?.files?.[0],
    source: document.getElementById('importStudioSource')?.value || 'auto',
    category: document.getElementById('importStudioCategory')?.value || '',
    mapping: JSON.stringify(getImportStudioMapping()), account: importStudioAccountKey()
  };
}

function importStudioMatches(snapshot) {
  const now = importStudioSnapshot();
  return snapshot && ['file', 'source', 'category', 'mapping', 'account'].every(key => now[key] === snapshot[key]);
}

async function requestImportStudio(path, body, controller) {
  let timedOut = false, onAbort;
  const cancelled = new Promise((_, reject) => {
    onAbort = () => {
      const error = new Error(timedOut ? 'The request timed out.' : 'Request cancelled.');
      error.name = timedOut ? 'TimeoutError' : 'AbortError';
      reject(error);
    };
    controller.signal.addEventListener('abort', onAbort, {once: true});
  });
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, 45000);
  try {
    return await Promise.race([cancelled, (async () => {
      const response = await authenticatedFetch(`${API_BASE}/import-studio/${path}/`, {method: 'POST', body, signal: controller.signal, cache: 'no-store'});
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error('The server response could not be read.'); }
      return {response, data};
    })()]);
  } finally {
    window.clearTimeout(timeout);
    controller.signal.removeEventListener('abort', onAbort);
  }
}

function updateImportStudioControls() {
  const busy = !!importStudioController;
  const preview = document.getElementById('importStudioPreviewButton');
  const apply = document.getElementById('importStudioApplyButton');
  if (preview) preview.disabled = busy || importStudioInspecting || importStudioApplying;
  if (apply) apply.disabled = busy || importStudioApplying || !importStudioPreview?.ready_count || !importStudioMatches(importStudioContext);
  document.querySelectorAll('#importStudioForm input, #importStudioForm select').forEach(el => { el.disabled = importStudioApplying; });
  for (const id of ['importStudioConfirmButton', 'importStudioCancelButton']) {
    const el = document.getElementById(id);
    if (el) el.disabled = importStudioApplying;
  }
  for (const id of ['importStudioPrevious', 'importStudioNext', 'importStudioFilter']) {
    const el = document.getElementById(id);
    if (el) el.disabled = busy || importStudioApplying || el.dataset.unavailable === 'true';
  }
  document.getElementById('importStudioResults')?.setAttribute('aria-busy', String(busy));
}

function resetImportStudioPreview() {
  if (importStudioApplying) return;
  importStudioGeneration++;
  importStudioController?.abort();
  importStudioController = null;
  importStudioPreview = null;
  importStudioContext = null;
  importStudioFilter = 'all';
  const results = document.getElementById('importStudioResults');
  if (results) { results.hidden = true; results.replaceChildren(); }
  const confirmation = document.getElementById('importStudioConfirm');
  if (confirmation) confirmation.hidden = true;
  const status = document.getElementById('importStudioStatus');
  if (status) status.textContent = 'Preview your current file and options before importing.';
  updateImportStudioControls();
}

function clearImportStudioSession() {
  importStudioApplying = false;
  importStudioInspecting = false;
  importStudioFileGeneration++;
  resetImportStudioPreview();
  const file = document.getElementById('importStudioFile');
  if (file) file.value = '';
  document.getElementById('importStudioMapping')?.replaceChildren();
  for (const id of ['importStudioStatus', 'importStudioConfirmSummary']) {
    const el = document.getElementById(id);
    if (el) el.textContent = '';
  }
}

function parseDelimitedHeader(text) {
  const firstLine = text.replace(/^\uFEFF/, '').split(/\r?\n/, 1)[0] || '';
  const delimiter = [',', '\t', ';'].reduce((best, candidate) =>
    firstLine.split(candidate).length > firstLine.split(best).length ? candidate : best, ',');
  const fields = [];
  let current = '', quoted = false;
  for (let i = 0; i < firstLine.length; i++) {
    const c = firstLine[i];
    if (c === '"') {
      if (quoted && firstLine[i + 1] === '"') { current += '"'; i++; }
      else quoted = !quoted;
    } else if (c === delimiter && !quoted) { fields.push(current.trim()); current = ''; }
    else current += c;
  }
  fields.push(current.trim());
  return fields.filter(Boolean).slice(0, 100);
}

async function inspectImportStudioFile() {
  if (importStudioApplying) return;
  resetImportStudioPreview();
  const generation = ++importStudioFileGeneration;
  const snapshot = importStudioSnapshot();
  const mapping = document.getElementById('importStudioMapping');
  if (!mapping) return;
  mapping.replaceChildren();
  if (!snapshot.file) {
    importStudioInspecting = false;
    mapping.appendChild(importStudioElement('p', 'Choose a file to inspect its columns.', 'info-text'));
    updateImportStudioControls();
    return;
  }
  importStudioInspecting = true;
  updateImportStudioControls();
  const current = () => generation === importStudioFileGeneration && snapshot.file === importStudioSnapshot().file && snapshot.account === importStudioAccountKey();
  try {
    const headers = parseDelimitedHeader(await snapshot.file.slice(0, 65536).text());
    if (!current()) return;
    for (const [target, labelText] of importStudioMappingFields) {
      const label = importStudioElement('label');
      const select = importStudioElement('select');
      select.dataset.importMapTarget = target;
      const empty = importStudioElement('option', 'Automatic / not included');
      empty.value = '';
      select.appendChild(empty);
      for (const header of headers) {
        const option = importStudioElement('option', header);
        option.value = header;
        select.appendChild(option);
      }
      select.addEventListener('change', resetImportStudioPreview);
      label.append(importStudioElement('span', labelText), select);
      mapping.appendChild(label);
    }
  } catch (_) {
    if (current()) mapping.appendChild(importStudioElement('p', 'Columns could not be inspected here. You can still try Preview import.', 'info-text'));
  } finally {
    if (current()) { importStudioInspecting = false; updateImportStudioControls(); }
  }
}

function buildImportStudioFormData(includeConfirmation = false, snapshot = importStudioSnapshot()) {
  if (!snapshot.file) throw new Error('Choose a CSV or TSV file first.');
  const body = new FormData();
  body.append('file', snapshot.file);
  body.append('source', snapshot.source);
  body.append('category', snapshot.category);
  body.append('mapping_json', snapshot.mapping);
  if (includeConfirmation) body.append('fingerprint_confirmation', importStudioPreview?.fingerprint || '');
  return body;
}

function importStudioMetric(value, label) {
  const metric = importStudioElement('div', undefined, 'import-studio__metric');
  metric.append(importStudioElement('strong', value), importStudioElement('span', label));
  return metric;
}

function renderImportStudioValues(item) {
  const box = importStudioElement('div', undefined, 'import-studio__values');
  const value = item.values;
  if (!value) { box.textContent = 'Correct this row in your source file, then preview again.'; return box; }
  const labels = importStudioCategories[item.category] || ['', 'Finished', 'Not finished'];
  const facts = [value.creator, value.release_date || (value.year || null),
    value.rating == null ? 'Not rated' : `${value.rating}/10`, value.completed ? labels[1] : labels[2],
    value.genre, value.seasons == null ? null : `${value.seasons} seasons`, value.episodes == null ? null : `${value.episodes} episodes`].filter(value => value !== null && value !== undefined && value !== '');
  box.appendChild(importStudioElement('p', facts.join(' · ')));
  if (value.review) {
    const note = importStudioElement('details');
    note.append(importStudioElement('summary', 'Private note'), importStudioElement('p', value.review, 'import-studio__note'));
    box.appendChild(note);
  }
  if (item.status === 'duplicate') box.appendChild(importStudioElement('p', 'From your file; the existing library entry will be kept.', 'info-text'));
  return box;
}

function renderImportStudioPreview(data, focusId) {
  const results = document.getElementById('importStudioResults');
  if (!results) return;
  results.replaceChildren();
  results.hidden = false;
  const summary = importStudioElement('div', undefined, 'import-studio__summary');
  summary.append(importStudioMetric(data.total_rows, 'Rows read'), importStudioMetric(data.ready_count, 'Ready to import'),
    importStudioMetric(data.duplicate_count, 'Duplicates skipped'), importStudioMetric(data.invalid_count, 'Rows needing attention'));
  results.append(summary, importStudioElement('p', 'Review the values from your file below. Notes stay private. Filtering this preview does not change which ready rows will be imported.', 'info-text'));
  const controls = importStudioElement('div', undefined, 'import-studio__review-controls');
  const label = importStudioElement('label');
  label.appendChild(importStudioElement('span', 'Review rows'));
  const filter = importStudioElement('select');
  filter.id = 'importStudioFilter';
  for (const [value, text] of [['all', 'All rows'], ['ready', 'Ready to import'], ['duplicate', 'Duplicates'], ['invalid', 'Needs attention']]) {
    const option = importStudioElement('option', text); option.value = value; filter.appendChild(option);
  }
  filter.value = importStudioFilter;
  filter.addEventListener('change', () => filterImportStudioPreview(filter.value));
  label.appendChild(filter); controls.appendChild(label);
  const total = data.preview_total ?? data.total_rows;
  const offset = data.preview_offset ?? 0;
  const count = data.preview?.length || 0;
  controls.appendChild(importStudioElement('p', total ? `Rows ${offset + 1}–${offset + count} of ${total} matching rows` : 'No matching rows.', 'info-text'));
  const pages = importStudioElement('div', undefined, 'import-studio__pages');
  for (const [name, delta, unavailable] of [['Previous', -1, offset === 0], ['Next', 1, offset + count >= total]]) {
    const button = importStudioElement('button', name, 'action-btn');
    button.type = 'button'; button.id = `importStudio${name}`;
    button.dataset.unavailable = String(unavailable); button.disabled = unavailable;
    button.setAttribute('aria-label', `${name} preview page`);
    button.addEventListener('click', () => changeImportStudioPage(Math.max(0, offset + delta * IMPORT_STUDIO_PAGE_SIZE)));
    pages.appendChild(button);
  }
  controls.appendChild(pages);
  results.appendChild(controls);
  const wrap = importStudioElement('div', undefined, 'import-studio__table-wrap');
  wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Import preview rows');
  const table = importStudioElement('table', undefined, 'import-studio__table');
  table.appendChild(importStudioElement('caption', 'Proposed import values'));
  const head = importStudioElement('thead'), headRow = importStudioElement('tr');
  for (const title of ['CSV row', 'Title', 'Outcome', 'Values from your file']) {
    const th = importStudioElement('th', title); th.scope = 'col'; headRow.appendChild(th);
  }
  head.appendChild(headRow); table.appendChild(head);
  const body = importStudioElement('tbody');
  for (const item of data.preview || []) {
    const row = importStudioElement('tr');
    const number = importStudioElement('td', item.row); number.dataset.label = 'CSV row';
    const title = importStudioElement('th', item.title); title.scope = 'row';
    title.appendChild(importStudioElement('span', importStudioCategories[item.category]?.[0] || 'Unrecognized category', 'import-studio__category'));
    const outcome = importStudioElement('td', undefined, 'import-studio__outcome'); outcome.dataset.label = 'Outcome';
    const labels = {ready: 'Ready to import', duplicate: 'Duplicate — skipped', invalid: 'Needs attention'};
    outcome.appendChild(importStudioElement('strong', labels[item.status] || 'Needs attention'));
    if (item.reason) outcome.appendChild(importStudioElement('p', item.reason));
    const values = importStudioElement('td'); values.dataset.label = 'Values from your file'; values.appendChild(renderImportStudioValues(item));
    row.append(number, title, outcome, values); body.appendChild(row);
  }
  table.appendChild(body); wrap.appendChild(table); results.appendChild(wrap);
  if (focusId) document.getElementById(focusId)?.focus();
}

async function loadImportStudioPreview(offset = 0, filter = 'all', focusId) {
  if (importStudioApplying || importStudioInspecting) return;
  importStudioController?.abort();
  const generation = ++importStudioGeneration;
  const snapshot = importStudioSnapshot();
  const controller = importStudioController = new AbortController();
  const status = document.getElementById('importStudioStatus');
  document.getElementById('importStudioConfirm').hidden = true;
  updateImportStudioControls();
  status.textContent = 'Reading and comparing your file…';
  const current = () => generation === importStudioGeneration && importStudioMatches(snapshot);
  try {
    const body = buildImportStudioFormData(false, snapshot);
    body.append('status_filter', filter); body.append('offset', String(offset)); body.append('limit', String(IMPORT_STUDIO_PAGE_SIZE));
    const {response, data} = await requestImportStudio('preview', body, controller);
    if (!current()) return;
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The file could not be previewed.');
    if (!data.fingerprint || !Array.isArray(data.preview)) throw new Error('The preview response was incomplete.');
    importStudioPreview = data; importStudioContext = snapshot; importStudioFilter = filter;
    renderImportStudioPreview(data, focusId);
    status.textContent = `Preview complete: ${data.ready_count} ready, ${data.duplicate_count} duplicates, ${data.invalid_count} needing attention. Nothing has been saved.`;
  } catch (error) {
    if (current() && error.name !== 'AbortError') {
      status.textContent = `${error.message} Your file and options are still here. Try Preview import again.`;
      const select = document.getElementById('importStudioFilter');
      if (select) select.value = importStudioFilter;
    }
  } finally {
    if (generation === importStudioGeneration) { importStudioController = null; updateImportStudioControls(); }
  }
}

async function previewLibraryImport(event) {
  event?.preventDefault();
  if (importStudioApplying || importStudioInspecting) return;
  resetImportStudioPreview();
  return loadImportStudioPreview();
}

function changeImportStudioPage(offset) {
  if (!importStudioPreview || !importStudioMatches(importStudioContext)) return;
  return loadImportStudioPreview(offset, importStudioFilter, 'importStudioFilter');
}

function filterImportStudioPreview(filter) {
  if (!['all', 'ready', 'duplicate', 'invalid'].includes(filter) || !importStudioPreview || !importStudioMatches(importStudioContext)) return;
  return loadImportStudioPreview(0, filter, 'importStudioFilter');
}

function applyLibraryImport() {
  if (importStudioApplying || importStudioController || !importStudioPreview?.ready_count) return;
  if (!importStudioMatches(importStudioContext)) { resetImportStudioPreview(); return; }
  document.getElementById('importStudioConfirmSummary').textContent = `Import all ${importStudioPreview.ready_count} ready rows? ${importStudioPreview.duplicate_count} duplicates and ${importStudioPreview.invalid_count} invalid rows will be skipped. Existing entries will keep their values. Imported notes stay private.`;
  document.getElementById('importStudioConfirm').hidden = false;
  document.getElementById('importStudioConfirmButton').focus();
}

function cancelLibraryImport() {
  if (importStudioApplying) return;
  document.getElementById('importStudioConfirm').hidden = true;
  document.getElementById('importStudioApplyButton').focus();
}

function renderImportStudioCompletion(data) {
  const results = document.getElementById('importStudioResults');
  results.replaceChildren(); results.hidden = false;
  const heading = importStudioElement('h4', 'Your import is complete');
  heading.tabIndex = -1;
  const summary = importStudioElement('div', undefined, 'import-studio__summary');
  summary.append(importStudioMetric(data.created_count, 'Titles added'), importStudioMetric(data.duplicate_count, 'Duplicates kept'), importStudioMetric(data.invalid_count, 'Rows skipped'));
  results.append(heading, summary);
  if (data.invalid_count) results.appendChild(importStudioElement('p', 'Your source file is still selected. Preview again and choose Needs attention to review skipped rows. Fix those rows in your file, then choose the corrected file and preview it.', 'info-text'));
  const actions = importStudioElement('div', undefined, 'import-studio__actions');
  for (const [category, count] of Object.entries(data.by_category || {})) {
    if (!count || !importStudioCategories[category]) continue;
    const label = importStudioCategories[category][0];
    if (window.OmniImportStudio.canOpenCategory && !window.OmniImportStudio.canOpenCategory(category)) {
      actions.appendChild(importStudioElement('p', `${count} added to ${label}. That tab is hidden; you can enable it in Tab Visibility below.`, 'info-text'));
      continue;
    }
    const button = importStudioElement('button', `Open ${label.toLowerCase()} (${count} added)`, 'action-btn');
    button.type = 'button'; button.dataset.importCategory = category;
    button.addEventListener('click', () => window.OmniImportStudio.openCategory?.(category));
    actions.appendChild(button);
  }
  results.appendChild(actions); heading.focus();
}

async function confirmLibraryImport() {
  if (document.getElementById('importStudioConfirm').hidden || importStudioApplying || importStudioController || !importStudioPreview?.ready_count) return;
  if (!importStudioMatches(importStudioContext)) { resetImportStudioPreview(); return; }
  const snapshot = importStudioContext;
  const body = buildImportStudioFormData(true, snapshot);
  const generation = ++importStudioGeneration;
  const controller = importStudioController = new AbortController();
  importStudioApplying = true;
  updateImportStudioControls();
  const status = document.getElementById('importStudioStatus');
  status.textContent = 'Saving the new rows as one batch…';
  const current = () => generation === importStudioGeneration && importStudioMatches(snapshot);
  try {
    const {response, data} = await requestImportStudio('apply', body, controller);
    if (!current()) return;
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The import could not be confirmed.');
    if (!Number.isInteger(data.created_count) || !data.by_category) throw new Error('The import result was incomplete.');
    importStudioPreview = null; importStudioContext = null;
    document.getElementById('importStudioConfirm').hidden = true;
    renderImportStudioCompletion(data);
    status.textContent = `Import complete: ${data.created_count} added, ${data.duplicate_count} duplicates skipped, ${data.invalid_count} invalid rows skipped.`;
    try { Promise.resolve(window.OmniImportStudio.refresh?.(data.by_category || {})).catch(() => {}); } catch (_) { /* A refresh cannot turn a completed import into a failed save. */ }
  } catch (error) {
    if (current() && error.name !== 'AbortError') {
      // A lost response can follow a committed batch. Previewing again safely
      // recognizes those entries before any further import is confirmed.
      importStudioPreview = null; importStudioContext = null;
      document.getElementById('importStudioConfirm').hidden = true;
      status.textContent = `${error.message} Your file and options are still here. Preview again before retrying; any saved matches will be skipped.`;
    }
  } finally {
    if (generation === importStudioGeneration) { importStudioController = null; importStudioApplying = false; updateImportStudioControls(); }
  }
}

async function downloadImportTemplate() {
  const category = document.getElementById('importStudioTemplateCategory')?.value || 'movies';
  const account = importStudioAccountKey();
  try {
    const response = await authenticatedFetch(`${API_BASE}/import-studio/template/${encodeURIComponent(category)}/`, {cache: 'no-store'});
    if (!response.ok) throw new Error('The template could not be downloaded.');
    const blob = await response.blob();
    if (account !== importStudioAccountKey()) return;
    const url = URL.createObjectURL(blob), link = importStudioElement('a');
    link.href = url; link.download = `omnitrackr-${category}-template.csv`;
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  } catch (error) {
    if (account === importStudioAccountKey()) document.getElementById('importStudioStatus').textContent = error.message;
  }
}

window.OmniImportStudio = {reset: clearImportStudioSession, refresh: null, openCategory: null, canOpenCategory: null};
window.addEventListener('pagehide', clearImportStudioSession);
window.addEventListener('storage', event => {
  if (event.key === null || ['omnitrackr_user', 'omnitrackr_token'].includes(event.key)) clearImportStudioSession();
});
