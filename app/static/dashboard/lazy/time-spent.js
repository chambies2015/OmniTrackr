// Time spent: estimated hours across the library, with a downloadable card.
let timeSpentData = null;
let timeSpentRequestId = 0;

function formatTimeSpentHours(hours) {
  if (hours > 0 && hours < 10) return `${Number(hours).toFixed(1).replace(/\.0$/, '')}`;
  return Math.round(hours).toLocaleString();
}

async function loadTimeSpent() {
  if (!hasStoredAuth()) return;
  const requestId = ++timeSpentRequestId;
  const status = document.getElementById('timeSpentStatus');
  const download = document.getElementById('timeSpentDownload');
  if (status) status.textContent = 'Adding up your library…';
  try {
    const response = await authenticatedFetch(`${API_BASE}/statistics/time-spent/`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Time spent could not be worked out.');
    if (requestId !== timeSpentRequestId) return;
    timeSpentData = data;
    renderTimeSpent();
    if (download) download.disabled = !(data.minutes >= 60);
  } catch (error) {
    if (requestId === timeSpentRequestId && status) status.textContent = error.message;
  }
}

function renderTimeSpent() {
  const data = timeSpentData;
  const status = document.getElementById('timeSpentStatus');
  const content = document.getElementById('timeSpentContent');
  const method = document.getElementById('timeSpentMethod');
  if (!data || !content) return;
  if (!data.minutes) {
    if (status) status.textContent = 'Mark a few titles as finished, or save your place in one, and your hours will show up here.';
    content.innerHTML = '';
    if (method) method.innerHTML = '';
    return;
  }
  if (status) {
    const steam = data.measured
      ? ` ${data.measured.toLocaleString()} game${data.measured === 1 ? '' : 's'} use${data.measured === 1 ? 's' : ''} your real hours from Steam.`
      : '';
    status.textContent = (data.typical
      ? `Counted ${data.titles.toLocaleString()} titles. ${data.typical.toLocaleString()} of them used a typical length because we don't have theirs yet.`
      : `Counted ${data.titles.toLocaleString()} titles, all with their own lengths.`) + steam;
  }
  const rows = data.categories.filter(row => row.minutes > 0);
  const largest = Math.max(...rows.map(row => row.minutes), 1);
  const bars = rows.map(row => {
    const width = Math.max(2, (100 * row.minutes) / largest);
    const titles = `${row.titles.toLocaleString()} title${row.titles === 1 ? '' : 's'}${row.measured ? `, ${row.measured.toLocaleString()} from Steam` : ''}`;
    const thisYear = row.year_minutes ? `, ${formatTimeSpentHours(row.year_hours)} h finished in ${data.year}` : '';
    return `<li class="time-spent__row" title="${escapeHtml(`${row.label}: about ${formatTimeSpentHours(row.hours)} hours ${row.verb}, ${titles}${thisYear}`)}">
      <span class="time-spent__label">${escapeHtml(row.label)}</span>
      <span class="time-spent__track" aria-hidden="true"><span class="time-spent__bar" data-width="${width.toFixed(1)}"></span></span>
      <span class="time-spent__value"><strong>${formatTimeSpentHours(row.hours)} h</strong><small>${titles}</small></span>
    </li>`;
  }).join('');
  const yearLine = data.year_minutes
    ? `<p class="time-spent__year"><strong>${formatTimeSpentHours(data.year_minutes / 60)} hours</strong> of that is titles you finished in ${data.year}.</p>`
    : `<p class="time-spent__year">Nothing finished in ${data.year} has a date yet. Titles you mark finished from now on count here.</p>`;
  content.innerHTML = `
    <div class="time-spent__hero">
      <p class="time-spent__total"><strong>${data.hours.toLocaleString()}</strong> hours</p>
      <p class="time-spent__compare">${escapeHtml(data.comparison)}</p>
      ${yearLine}
    </div>
    <ul class="time-spent__bars" aria-label="Estimated hours by category">${bars}</ul>`;
  // The dashboard CSP blocks style attributes, so widths go in through the CSSOM.
  content.querySelectorAll('.time-spent__bar').forEach(bar => bar.style.setProperty('--w', `${bar.dataset.width}%`));
  if (method) {
    const defaults = rows.map(row => `<li><strong>${escapeHtml(row.label)}:</strong> ${escapeHtml(row.default_note)}${row.typical ? ` (used for ${row.typical.toLocaleString()} of yours)` : ''}.</li>`).join('');
    method.innerHTML = `<p>Finished titles count in full. Shows, anime, books, manga, podcasts and audiobooks you're partway into count up to the episode, page or chapter you last saved. Everything else counts as zero, so rewatches and abandoned games aren't in here. Games you imported from Steam are the exception: they count the hours Steam recorded, finished or not.</p>
      <p>${escapeHtml(data.sources_note)} When we don't have a title's length, we use a typical one:</p>
      <ul>${defaults}</ul>
      <p>"This year" only counts titles with a finish date in ${data.year} from your journal or a completion note.</p>`;
  }
}

function buildTimeSpentCanvas() {
  const data = timeSpentData;
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 1500;
  const context = canvas.getContext('2d');
  const background = context.createLinearGradient(0, 0, 1200, 1500);
  background.addColorStop(0, '#0f172a');
  background.addColorStop(.6, '#1e1b4b');
  background.addColorStop(1, '#0b3a46');
  context.fillStyle = background;
  context.fillRect(0, 0, 1200, 1500);

  context.fillStyle = '#ffffff';
  context.font = '700 38px Arial, sans-serif';
  context.fillText('OmniTrackr', 72, 86);
  context.fillStyle = '#fbbf24';
  context.font = '700 20px Arial, sans-serif';
  context.textAlign = 'right';
  context.fillText('TIME SPENT', 1128, 84);
  context.textAlign = 'left';

  context.fillStyle = '#c7d2fe';
  context.font = '700 22px Arial, sans-serif';
  context.fillText('ESTIMATED HOURS ACROSS MY LIBRARY', 72, 200);
  context.fillStyle = '#ffffff';
  fitCanvasFont(context, `${data.hours.toLocaleString()} hours`, 150, 70, 1056);
  context.fillText(`${data.hours.toLocaleString()} hours`, 72, 350);
  context.fillStyle = '#cbd5e1';
  context.font = '28px Arial, sans-serif';
  drawWrappedCanvasText(context, data.comparison, 72, 410, 1056, 38, 2);

  const rows = data.categories.filter(row => row.minutes > 0).slice(0, 8);
  const largest = Math.max(...rows.map(row => row.minutes), 1);
  rows.forEach((row, index) => {
    const y = 540 + index * 100;
    context.fillStyle = '#e2e8f0';
    context.font = '700 26px Arial, sans-serif';
    context.fillText(row.label, 72, y);
    context.textAlign = 'right';
    context.fillText(`${formatTimeSpentHours(row.hours)} h`, 1128, y);
    context.textAlign = 'left';
    context.fillStyle = 'rgba(255,255,255,.1)';
    drawCanvasRoundedRect(context, 72, y + 18, 1056, 22, 11);
    context.fill();
    context.fillStyle = '#fbbf24';
    drawCanvasRoundedRect(context, 72, y + 18, Math.max(22, 1056 * row.minutes / largest), 22, 11);
    context.fill();
  });

  context.strokeStyle = 'rgba(255,255,255,.16)';
  context.beginPath();
  context.moveTo(72, 1392);
  context.lineTo(1128, 1392);
  context.stroke();
  context.fillStyle = '#94a3b8';
  context.font = '21px Arial, sans-serif';
  context.fillText(`${data.titles.toLocaleString()} titles, lengths estimated`, 72, 1440);
  context.textAlign = 'right';
  context.fillStyle = '#e2e8f0';
  context.font = '700 22px Arial, sans-serif';
  context.fillText('omnitrackr.xyz', 1128, 1440);
  return canvas;
}

function downloadTimeSpent() {
  if (!timeSpentData || timeSpentData.minutes < 60) return;
  buildTimeSpentCanvas().toBlob(blob => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `omnitrackr-time-spent-${new Date().toISOString().slice(0, 10)}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const status = document.getElementById('timeSpentStatus');
    if (status) status.textContent = 'Card downloaded on this device. Nothing was published.';
  }, 'image/png');
}
