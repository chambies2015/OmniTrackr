/* Public browsing is local to this page; saving always requires an explicit submit. */
(() => {
  const filters = document.getElementById('trail-filters');
  if (filters) {
    const search = document.getElementById('trail-search');
    const format = document.getElementById('trail-format');
    const cards = Array.from(document.querySelectorAll('.trail[data-search]'));
    const normalize = value => value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    function filterTrails() {
      const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
      let count = 0;
      for (const card of cards) {
        card.hidden = !(terms.every(term => normalize(card.dataset.search).includes(term))
          && (!format.value || card.dataset.formats.split(' ').includes(format.value)));
        if (!card.hidden) count++;
      }
      document.getElementById('trail-results').textContent = `${count} of ${cards.length} trails${format.value ? ` including ${format.options[format.selectedIndex].text}` : ''}`;
      document.getElementById('trail-empty').hidden = count > 0;
    }
    search.addEventListener('input', filterTrails);
    format.addEventListener('change', filterTrails);
    document.getElementById('trail-reset').addEventListener('click', () => {
      search.value = ''; format.value = ''; filterTrails(); search.focus();
    });
    filters.hidden = false;
    filterTrails();
  }

  const panel = document.querySelector('[data-trail]');
  if (!panel) return;
  const status = document.getElementById('status');
  const form = document.getElementById('saveForm');
  const preview = document.getElementById('preview');
  const save = document.getElementById('save');
  const signin = document.getElementById('signin');
  const selectionKey = `omnitrackr_discover_selection:${panel.dataset.trail}`;
  let selectedKeys = null;
  let busy = false;

  // Only public catalog keys are retained, never library matches or account data.
  try {
    const saved = JSON.parse(sessionStorage.getItem(selectionKey));
    if (saved && Number.isFinite(saved.at) && saved.at <= Date.now() && Date.now() - saved.at < 86400000
      && Array.isArray(saved.keys) && saved.keys.length <= 6 && saved.keys.every(key => typeof key === 'string')) {
      selectedKeys = saved.keys;
    }
    sessionStorage.removeItem(selectionKey);
  } catch (_) {}

  async function request(action, options = {}) {
    const headers = {'Content-Type': 'application/json'};
    // Support existing legacy token sessions as well as HttpOnly cookies.
    try { const token = localStorage.getItem('omnitrackr_token'); if (token) headers.Authorization = `Bearer ${token}`; } catch (_) {}
    const response = await fetch(`/api/discover/${panel.dataset.trail}/${action}`, {...options, headers, credentials: 'same-origin'});
    if (response.status === 401) {
      if (selectedKeys !== null) {
        try { sessionStorage.setItem(selectionKey, JSON.stringify({at: Date.now(), keys: selectedKeys})); } catch (_) {}
      }
      signin.hidden = false;
      form.hidden = true;
      throw new Error('Sign in to continue with this collection. You’ll return here to review your picks before saving.');
    }
    if (!response.ok) throw new Error('Could not complete that request. Please try again.');
    signin.hidden = true;
    return response.json();
  }

  function setBusy(value) {
    busy = value;
    preview.disabled = value; save.disabled = value;
    document.getElementById('choices').disabled = value;
    panel.setAttribute('aria-busy', String(value));
  }

  async function previewPicks() {
    if (busy) return;
    if (!form.hidden) selectedKeys = Array.from(form.querySelectorAll('input:checked'), input => input.value);
    setBusy(true);
    status.textContent = 'Checking your library…';
    try {
      const data = await request('preview');
      const choices = document.getElementById('choices');
      const legend = document.createElement('legend'); legend.textContent = 'Titles to save';
      choices.replaceChildren(legend);
      for (const item of data.items) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox'; input.name = 'pick'; input.value = item.key;
        input.checked = selectedKeys === null || selectedKeys.includes(item.key);
        const text = document.createElement('span');
        text.textContent = `${item.title} · ${item.category} — ${item.existing ? 'Reuse existing title match; keep your notes and progress' : 'Add as unfinished and unrated'}`;
        label.append(input, text); choices.append(label);
      }
      form.hidden = false; status.textContent = 'Choose what to save. Nothing has been added yet.';
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); }
  }
  preview.addEventListener('click', previewPicks);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || form.hidden) return;
    const keys = Array.from(form.querySelectorAll('input:checked'), input => input.value);
    if (!keys.length) { status.textContent = 'Select at least one pick.'; return; }
    selectedKeys = keys;
    setBusy(true);
    status.textContent = 'Saving your picks…';
    try {
      const result = await request('save', {method:'POST', body:JSON.stringify({keys})});
      status.textContent = `Saved to your private collection. ${result.created} new titles; ${result.reused} existing titles reused. `;
      const link = document.createElement('a');
      link.href = Number.isSafeInteger(result.collection_id) && result.collection_id > 0 ? `/?collection=${result.collection_id}` : '/';
      link.textContent = 'Open your collection →'; status.append(link);
      form.hidden = true;
      try { sessionStorage.removeItem(selectionKey); } catch (_) {}
      link.focus();
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); }
  });

  // A return from sign-in performs only the read-only preview, never a save.
  if (window.location.hash === '#save-picks') previewPicks();
})();
