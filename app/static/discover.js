const panel = document.querySelector('[data-trail]');
if (panel) {
  const status = document.getElementById('status');
  const form = document.getElementById('saveForm');
  const preview = document.getElementById('preview');
  const save = document.getElementById('save');
  async function request(action, options = {}) {
    const headers = {'Content-Type': 'application/json'};
    // Support existing legacy token sessions as well as HttpOnly cookies.
    try { const token = localStorage.getItem('omnitrackr_token'); if (token) headers.Authorization = `Bearer ${token}`; } catch (_) {}
    const response = await fetch(`/api/discover/${panel.dataset.trail}/${action}`, {...options, headers, credentials: 'same-origin'});
    if (response.status === 401) {
      document.getElementById('signin').hidden = false;
      form.hidden = true;
      throw new Error('Sign in to save your picks. You can keep exploring without an account.');
    }
    if (!response.ok) throw new Error('Could not complete that request. Please try again.');
    return response.json();
  }
  preview.addEventListener('click', async () => {
    preview.disabled = true;
    status.textContent = 'Checking your library…';
    try {
      const data = await request('preview');
      const choices = document.getElementById('choices');
      choices.replaceChildren();
      for (const item of data.items) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox'; input.name = 'pick'; input.value = item.key; input.checked = true;
        const text = document.createElement('span');
        text.textContent = `${item.title} · ${item.category} — ${item.existing ? 'Reuse existing title match; keep your notes and progress' : 'Add as unfinished and unrated'}`;
        label.append(input, text); choices.append(label);
      }
      form.hidden = false; status.textContent = 'Choose what to save. Nothing has been added yet.';
    } catch (error) { status.textContent = error.message; }
    finally { preview.disabled = false; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const keys = Array.from(form.querySelectorAll('input:checked'), input => input.value);
    if (!keys.length) { status.textContent = 'Select at least one pick.'; return; }
    save.disabled = true; preview.disabled = true;
    try {
      const result = await request('save', {method:'POST', body:JSON.stringify({keys})});
      status.textContent = `Saved to your private collection. ${result.created} new titles; ${result.reused} existing titles reused. `;
      const link = document.createElement('a'); link.href = '/'; link.textContent = 'Open your library →'; status.append(link);
      form.hidden = true;
    } catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; preview.disabled = false; }
  });
}
