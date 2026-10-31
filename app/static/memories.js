// Dashboard: On this day. What the member finished, started or wrote on today's date in earlier
// years, six months ago and a month ago, from GET /activity/on-this-day/. Hidden when there's
// nothing, and for the rest of the day once dismissed. Server text is only ever set as textContent.
(function () {
  'use strict';

  const state = { request: 0, data: null };
  const $ = id => document.getElementById(id);
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');
  const CATEGORIES = ['movies', 'tv-shows', 'anime', 'video-games', 'music', 'books', 'manga', 'podcasts', 'audiobooks'];

  function fetchOptions(options = {}) {
    if (typeof authFetchOptions === 'function') return authFetchOptions(options);
    return { credentials: 'same-origin', ...options };
  }

  function memberKey() {
    try {
      const user = typeof getUser === 'function' ? getUser() : null;
      if (user && user.id) return String(user.id);
    } catch (error) { /* shared key */ }
    return 'member';
  }

  function hiddenKey() {
    return `omnitrackr_memories_hidden_${memberKey()}`;
  }

  function hiddenToday(day) {
    try { return localStorage.getItem(hiddenKey()) === day; } catch (error) { return false; }
  }

  function safeImage(value) {
    return typeof value === 'string' && /^https?:\/\/[^\s"'<>]+$/.test(value) ? value : null;
  }

  function usable(memory) {
    return memory && typeof memory.line === 'string' && typeof memory.label === 'string';
  }

  function libraryTitle(memory) {
    return CATEGORIES.includes(memory.category) && Number.isInteger(memory.item_id) && memory.item_id > 0;
  }

  function moreText(more) {
    if (!more) return '';
    return more === 1 ? 'And one more thing that day.' : `And ${more} more things that day.`;
  }

  function initials(title) {
    const letters = String(title || '').trim().split(/\s+/).slice(0, 2).map(word => word[0] || '').join('');
    return letters.toUpperCase() || '★';
  }

  function button(text, action, index, primary = false) {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = primary ? 'on-this-day__action on-this-day__action--primary' : 'on-this-day__action';
    element.dataset.memoryAction = action;
    element.dataset.memoryIndex = String(index);
    element.textContent = text;
    return element;
  }

  function memoryItem(memory, index) {
    const item = document.createElement('li');
    item.className = 'on-this-day__item';
    const art = document.createElement('div');
    art.className = 'on-this-day__art';
    const image = safeImage(memory.image);
    if (image) {
      const img = document.createElement('img');
      img.src = image;
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => { img.remove(); art.textContent = initials(memory.title); }, { once: true });
      art.appendChild(img);
    } else {
      art.textContent = initials(memory.title);
    }

    const body = document.createElement('div');
    body.className = 'on-this-day__body';
    const when = document.createElement('p');
    when.className = 'on-this-day__when';
    when.textContent = memory.category_label ? `${memory.label} · ${memory.category_label}` : memory.label;
    const line = document.createElement('p');
    line.className = 'on-this-day__line';
    line.textContent = memory.line;
    body.append(when, line);
    if (typeof memory.note === 'string' && memory.note) {
      const note = document.createElement('blockquote');
      note.className = 'on-this-day__note';
      note.textContent = memory.note;
      body.appendChild(note);
    }
    const more = moreText(Number(memory.more) || 0);
    if (more) {
      const extra = document.createElement('p');
      extra.className = 'on-this-day__more';
      extra.textContent = more;
      body.appendChild(extra);
    }

    const actions = document.createElement('div');
    actions.className = 'on-this-day__actions';
    if (libraryTitle(memory)) {
      actions.appendChild(button('Open', 'open', index, true));
      if (memory.finished) actions.appendChild(button('Add to Next Up again', 'next-up', index));
      if (memory.finished && memory.kind === 'finished' && !memory.note) {
        actions.appendChild(button('Write a reflection', 'reflect', index));
      }
    }
    actions.appendChild(button('Save as image', 'image', index));
    body.appendChild(actions);
    item.append(art, body);
    return item;
  }

  function render(data) {
    state.data = data;
    const section = $('onThisDay');
    if (!section) return;
    const found = data && Array.isArray(data.memories) ? data.memories.filter(usable) : [];
    if (!found.length || hiddenToday(String(data.date || ''))) {
      section.hidden = true;
      return;
    }
    state.data = { ...data, memories: found };
    const list = $('onThisDayList');
    list.replaceChildren(...found.map(memoryItem));
    $('onThisDayStatus').textContent = '';
    section.hidden = false;
    if (window.location.hash === '#on-this-day') {
      section.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
  }

  async function refreshOnThisDay() {
    if (!$('onThisDay')) return;
    const request = ++state.request;
    try {
      const offset = new Date().getTimezoneOffset();
      const response = await fetch(`${apiBase()}/activity/on-this-day/?tz_offset_minutes=${offset}`,
        fetchOptions({ headers: { Accept: 'application/json' } }));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== state.request) return;
      render(data);
    } catch (error) {
      // The card is optional; the dashboard works without it.
    }
  }

  function resetOnThisDay() {
    state.request += 1;
    state.data = null;
    const section = $('onThisDay');
    if (section) section.hidden = true;
  }

  function wrap(context, text, x, y, width, lineHeight, maxLines) {
    const words = String(text).split(/\s+/);
    let line = '';
    let lines = 0;
    for (let index = 0; index < words.length; index += 1) {
      const next = line ? `${line} ${words[index]}` : words[index];
      if (context.measureText(next).width > width && line) {
        lines += 1;
        if (lines === maxLines) {
          context.fillText(`${line.replace(/[.,;:]?$/, '')}…`, x, y);
          return y + lineHeight;
        }
        context.fillText(line, x, y);
        y += lineHeight;
        line = words[index];
      } else {
        line = next;
      }
    }
    if (line) context.fillText(line, x, y);
    return y + lineHeight;
  }

  // The card is drawn from text only, so no cover art leaves the device and the canvas stays exportable.
  function memoryCanvas(memory) {
    const canvas = document.createElement('canvas');
    canvas.width = 1080;
    canvas.height = 1080;
    const context = canvas.getContext('2d');
    const background = context.createLinearGradient(0, 0, 1080, 1080);
    background.addColorStop(0, '#1e1b4b');
    background.addColorStop(1, '#0f3b48');
    context.fillStyle = background;
    context.fillRect(0, 0, 1080, 1080);
    context.fillStyle = '#ffffff';
    context.font = '700 36px Arial, sans-serif';
    context.fillText('OmniTrackr', 72, 104);
    context.fillStyle = '#fcd34d';
    context.font = '700 22px Arial, sans-serif';
    context.textAlign = 'right';
    context.fillText('ON THIS DAY', 1008, 102);
    context.textAlign = 'left';
    context.fillStyle = '#c7d2fe';
    context.font = '700 34px Arial, sans-serif';
    context.fillText(String(memory.label).toUpperCase(), 72, 330);
    context.fillStyle = '#ffffff';
    context.font = '700 62px Arial, sans-serif';
    let y = wrap(context, memory.line, 72, 420, 936, 78, 4);
    if (memory.note) {
      context.fillStyle = '#e2e8f0';
      context.font = 'italic 34px Georgia, serif';
      wrap(context, `“${memory.note}”`, 72, y + 30, 936, 48, 4);
    }
    context.fillStyle = '#e2e8f0';
    context.font = '700 24px Arial, sans-serif';
    context.textAlign = 'right';
    context.fillText('omnitrackr.xyz', 1008, 1008);
    return canvas;
  }

  function saveImage(memory) {
    const status = $('onThisDayStatus');
    memoryCanvas(memory).toBlob(blob => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `omnitrackr-on-this-day-${String(state.data?.date || '').slice(0, 10) || 'memory'}.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      if (status) status.textContent = 'Image saved on this device. Nothing was published.';
    }, 'image/png');
  }

  async function act(action, memory, element) {
    const status = $('onThisDayStatus');
    if (action === 'image') return saveImage(memory);
    if (!libraryTitle(memory)) return;
    if (action === 'open' && typeof openLibraryItem === 'function') {
      await openLibraryItem({ category: memory.category, id: memory.item_id, title: memory.title },
        { button: element, reasonElement: status });
    } else if (action === 'next-up' && typeof addToNextUp === 'function') {
      await addToNextUp(memory.category, memory.item_id);
    } else if (action === 'reflect' && typeof openCompletionMoment === 'function') {
      await openCompletionMoment(memory.category, memory.item_id);
    }
  }

  function init() {
    document.addEventListener('click', event => {
      if (!event.target.closest) return;
      if (event.target.closest('#onThisDayDismiss')) {
        try { localStorage.setItem(hiddenKey(), String(state.data?.date || '')); } catch (error) { /* this visit only */ }
        const section = $('onThisDay');
        if (section) section.hidden = true;
        return;
      }
      const target = event.target.closest('[data-memory-action]');
      if (!target || !state.data) return;
      const memory = state.data.memories[Number(target.dataset.memoryIndex)];
      if (memory) act(target.dataset.memoryAction, memory, target);
    });
  }

  if (typeof window !== 'undefined') {
    window.refreshOnThisDay = refreshOnThisDay;
    window.resetOnThisDay = resetOnThisDay;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { moreText, initials, safeImage, usable, libraryTitle, render, hiddenKey };
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
