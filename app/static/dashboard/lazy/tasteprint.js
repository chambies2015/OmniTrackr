// Private Tasteprint and local share-card rendering
// ============================================================================

let tasteprintData = null;
let tasteprintRequestId = 0;
let tasteprintSelectedInsights = new Set();

function selectedTasteprintCategories() {
  return Array.from(document.querySelectorAll('[data-tasteprint-category]:checked')).map(input => input.value);
}

function selectedTasteprintInsights() {
  if (!tasteprintData) return [];
  return tasteprintData.insights.filter(insight => tasteprintSelectedInsights.has(insight.key)).slice(0, 6);
}

function renderTasteprintCategories(data) {
  const container = document.getElementById('tasteprintCategoryControls');
  if (!container) return;
  container.replaceChildren();
  const selected = new Set(data.selected_categories || []);
  (data.available_categories || []).forEach(category => {
    const label = document.createElement('label');
    label.className = 'tasteprint__category';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = category.key;
    input.checked = selected.has(category.key);
    input.dataset.tasteprintCategory = '';
    input.dataset.changeAction = 'tasteprint-category';
    const name = document.createElement('span');
    name.textContent = category.label;
    const meta = document.createElement('small');
    const flags = [];
    if (category.private) flags.push('private');
    if (category.hidden) flags.push('hidden');
    meta.textContent = `${category.total} item${category.total === 1 ? '' : 's'}${flags.length ? ` · ${flags.join(' · ')}` : ''}`;
    label.append(input, name, meta);
    container.appendChild(label);
  });
}

function renderTasteprintProgress(data) {
  const container = document.getElementById('tasteprintProgress');
  if (!container) return;
  container.replaceChildren();
  if (data.ready) return;
  const panel = document.createElement('div');
  panel.className = 'tasteprint__progress-panel';
  const heading = document.createElement('strong');
  heading.textContent = 'Your Tasteprint is still developing.';
  const detail = document.createElement('span');
  const needs = [];
  if (data.needed_items) needs.push(`${data.needed_items} more library item${data.needed_items === 1 ? '' : 's'}`);
  if (data.needed_ratings) needs.push(`${data.needed_ratings} more rating${data.needed_ratings === 1 ? '' : 's'}`);
  detail.textContent = needs.length
    ? `Add ${needs.join(' and ')} across the selected categories to unlock an evidence-backed share card.`
    : 'Select at least one category with enough history to build the card.';
  panel.append(heading, detail);
  container.appendChild(panel);
}

function updateTasteprintSelection(event) {
  const input = event?.target;
  if (!input) return;
  if (input.checked && !tasteprintSelectedInsights.has(input.value) && tasteprintSelectedInsights.size >= 6) {
    input.checked = false;
    const status = document.getElementById('tasteprintStatus');
    if (status) status.textContent = 'Choose up to six insights for a readable share card.';
  } else if (input.checked) {
    tasteprintSelectedInsights.add(input.value);
  } else {
    tasteprintSelectedInsights.delete(input.value);
  }
  renderTasteprintCard();
}

function renderTasteprintCard() {
  const card = document.getElementById('tasteprintCard');
  const insights = document.getElementById('tasteprintInsights');
  if (!card || !insights || !tasteprintData) return;
  const includeName = document.getElementById('tasteprintIncludeName')?.checked;
  document.getElementById('tasteprintCardName').textContent = includeName ? `${tasteprintData.display_name}'s Tasteprint` : 'My Tasteprint';
  const includedLabels = (tasteprintData.available_categories || [])
    .filter(category => tasteprintData.selected_categories.includes(category.key) && category.total > 0)
    .map(category => category.label);
  document.getElementById('tasteprintCardScope').textContent = `${tasteprintData.total_items} items · ${tasteprintData.rated_items} rated · ${includedLabels.join(' + ') || 'No categories selected'}`;
  insights.replaceChildren();
  (tasteprintData.insights || []).forEach((insight, index) => {
    const item = document.createElement('div');
    item.className = `tasteprint-card__insight${index < 6 ? '' : ' is-excluded'}`;
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = insight.key;
    checkbox.checked = tasteprintSelectedInsights.has(insight.key);
    checkbox.dataset.tasteprintInsight = '';
    checkbox.dataset.changeAction = 'tasteprint-insight';
    checkbox.setAttribute('aria-label', `Include ${insight.label} on share card`);
    const label = document.createElement('label');
    label.textContent = insight.label;
    const value = document.createElement('h5');
    value.textContent = insight.value;
    const detail = document.createElement('p');
    detail.textContent = insight.detail;
    item.append(checkbox, label, value, detail);
    insights.appendChild(item);
  });
  if (!tasteprintData.insights.length) {
    const empty = document.createElement('p');
    empty.textContent = 'Select categories with library history to reveal your first patterns.';
    insights.appendChild(empty);
  }
  card.hidden = false;
  const canShare = tasteprintData.ready && selectedTasteprintInsights().length > 0;
  document.getElementById('tasteprintDownload').disabled = !canShare;
  document.getElementById('tasteprintCopy').disabled = !canShare;
}

async function loadTasteprint(useCurrentSelection = false) {
  if (!hasStoredAuth()) return;
  const requestId = ++tasteprintRequestId;
  const status = document.getElementById('tasteprintStatus');
  if (status) status.textContent = 'Reading your private aggregates…';
  try {
    let url = `${API_BASE}/statistics/tasteprint/`;
    if (useCurrentSelection) {
      url += `?categories=${encodeURIComponent(selectedTasteprintCategories().join(','))}`;
    }
    const response = await authenticatedFetch(url);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Tasteprint could not be generated.');
    if (requestId !== tasteprintRequestId) return;
    tasteprintData = data;
    tasteprintSelectedInsights = new Set((data.insights || []).slice(0, 6).map(insight => insight.key));
    renderTasteprintCategories(data);
    renderTasteprintProgress(data);
    renderTasteprintCard();
    if (status) {
      status.textContent = data.ready
        ? `${data.insights.length} evidence-backed patterns found. Choose up to six for your card.`
        : `Using ${data.total_items} selected items and ${data.rated_items} ratings. Preliminary patterns stay private until the share card unlocks.`;
    }
  } catch (error) {
    if (requestId === tasteprintRequestId && status) status.textContent = error.message;
  }
}

function tasteprintShareText() {
  const includeName = document.getElementById('tasteprintIncludeName')?.checked;
  const heading = includeName ? `${tasteprintData.display_name}'s OmniTrackr Tasteprint` : 'My OmniTrackr Tasteprint';
  const lines = selectedTasteprintInsights().map(insight => `${insight.label}: ${insight.value} — ${insight.detail}`);
  return [heading, ...lines, 'Built from my media history at omnitrackr.xyz'].join('\n');
}

async function copyTasteprintText() {
  if (!tasteprintData?.ready || !selectedTasteprintInsights().length) return;
  const text = tasteprintShareText();
  const status = document.getElementById('tasteprintStatus');
  try {
    await navigator.clipboard.writeText(text);
  } catch (error) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }
  if (status) status.textContent = 'Tasteprint summary copied. Nothing was published.';
}

function drawWrappedCanvasText(context, text, x, y, maxWidth, lineHeight, maxLines = 3) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = '';
  words.forEach(word => {
    const candidate = line ? `${line} ${word}` : word;
    if (context.measureText(candidate).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  });
  if (line) lines.push(line);
  lines.slice(0, maxLines).forEach((value, index) => {
    let rendered = value;
    if (index === maxLines - 1 && lines.length > maxLines) rendered = `${value.replace(/[.,;:]?$/, '')}…`;
    context.fillText(rendered, x, y + index * lineHeight);
  });
  return Math.min(lines.length, maxLines) * lineHeight;
}

function fitCanvasFont(context, text, maximumSize, minimumSize, maximumWidth) {
  let size = maximumSize;
  do {
    context.font = `700 ${size}px Arial, sans-serif`;
    if (context.measureText(text).width <= maximumWidth) return;
    size -= 2;
  } while (size >= minimumSize);
}

function drawCanvasRoundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  if (typeof context.roundRect === 'function') {
    context.roundRect(x, y, width, height, radius);
  } else {
    context.rect(x, y, width, height);
  }
}

function buildTasteprintCanvas() {
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 1500;
  const context = canvas.getContext('2d');
  const background = context.createLinearGradient(0, 0, 1200, 1500);
  background.addColorStop(0, '#11152a');
  background.addColorStop(.56, '#24134a');
  background.addColorStop(1, '#082c32');
  context.fillStyle = background;
  context.fillRect(0, 0, 1200, 1500);

  const glow = context.createRadialGradient(1040, 110, 10, 1040, 110, 430);
  glow.addColorStop(0, 'rgba(94,234,212,.25)');
  glow.addColorStop(1, 'rgba(94,234,212,0)');
  context.fillStyle = glow;
  context.fillRect(600, 0, 600, 600);

  context.fillStyle = '#ffffff';
  context.font = '700 38px Arial, sans-serif';
  context.fillText('OmniTrackr', 72, 86);
  context.fillStyle = '#5eead4';
  context.font = '700 20px Arial, sans-serif';
  context.textAlign = 'right';
  context.fillText('MEDIA TASTEPRINT', 1128, 84);
  context.textAlign = 'left';

  const includeName = document.getElementById('tasteprintIncludeName')?.checked;
  context.fillStyle = '#c4b5fd';
  context.font = '700 20px Arial, sans-serif';
  context.fillText('A PRIVATE MEDIA PORTRAIT', 72, 190);
  context.fillStyle = '#ffffff';
  const cardTitle = includeName ? `${tasteprintData.display_name}'s Tasteprint` : 'My Tasteprint';
  fitCanvasFont(context, cardTitle, 64, 36, 1056);
  context.fillText(cardTitle, 72, 270);
  const labels = tasteprintData.available_categories
    .filter(category => tasteprintData.selected_categories.includes(category.key) && category.total > 0)
    .map(category => category.label);
  context.fillStyle = '#cbd5e1';
  context.font = '26px Arial, sans-serif';
  context.fillText(`${tasteprintData.total_items} items  ·  ${tasteprintData.rated_items} rated  ·  ${labels.join(' + ')}`, 72, 320);

  selectedTasteprintInsights().forEach((insight, index) => {
    const column = index % 2;
    const row = Math.floor(index / 2);
    const x = 72 + column * 540;
    const y = 390 + row * 260;
    context.fillStyle = 'rgba(255,255,255,.065)';
    context.strokeStyle = 'rgba(255,255,255,.17)';
    context.lineWidth = 2;
    drawCanvasRoundedRect(context, x, y, 500, 220, 20);
    context.fill();
    context.stroke();
    context.fillStyle = '#a7f3d0';
    context.font = '700 18px Arial, sans-serif';
    context.fillText(insight.label.toUpperCase(), x + 28, y + 42);
    context.fillStyle = '#ffffff';
    context.font = '700 32px Arial, sans-serif';
    drawWrappedCanvasText(context, insight.value, x + 28, y + 88, 440, 38, 2);
    context.fillStyle = '#cbd5e1';
    context.font = '21px Arial, sans-serif';
    drawWrappedCanvasText(context, insight.detail, x + 28, y + 150, 440, 28, 2);
  });

  context.strokeStyle = 'rgba(255,255,255,.16)';
  context.beginPath();
  context.moveTo(72, 1392);
  context.lineTo(1128, 1392);
  context.stroke();
  context.fillStyle = '#94a3b8';
  context.font = '21px Arial, sans-serif';
  context.fillText('Built from patterns, not recommendations', 72, 1440);
  context.textAlign = 'right';
  context.fillStyle = '#e2e8f0';
  context.font = '700 22px Arial, sans-serif';
  context.fillText('omnitrackr.xyz', 1128, 1440);
  return canvas;
}

function downloadTasteprint() {
  if (!tasteprintData?.ready || !selectedTasteprintInsights().length) return;
  const canvas = buildTasteprintCanvas();
  canvas.toBlob(blob => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `omnitrackr-tasteprint-${new Date().toISOString().slice(0, 10)}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const status = document.getElementById('tasteprintStatus');
    if (status) status.textContent = 'Tasteprint downloaded on this device. Nothing was published.';
  }, 'image/png');
}

// ============================================================================
