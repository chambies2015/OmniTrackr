// Title discussion boards: inline spoilers for everyone; posting, editing, reports and
// moderator tools for signed-in members. Pages are rendered on the server; after a
// change we reload so what you see is exactly what everyone else sees.
(function () {
  'use strict';

  function authHeaders(json) {
    const headers = { Accept: 'application/json' };
    if (json) headers['Content-Type'] = 'application/json';
    try {
      const token = localStorage.getItem('omnitrackr_token');
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch (error) { /* cookie session */ }
    return headers;
  }

  function signIn() {
    window.location.href = `/?next=${encodeURIComponent(window.location.pathname + window.location.hash)}#landing-auth`;
  }

  async function send(method, url, body) {
    const response = await fetch(url, {
      method, credentials: 'same-origin', headers: authHeaders(body !== undefined),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 401) {
      signIn();
      throw new Error('Sign in to keep going.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 429 && typeof data.detail !== 'string') throw new Error("You're going a bit fast. Wait a minute and try again.");
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Please try again.');
    }
    return data;
  }

  function goTo(url) {
    if (!/^\/titles\/[a-z]+\/[a-z0-9-]+\/discussions(\/\d+)?(#[a-z0-9-]+)?$/.test(url || '')) {
      window.location.reload();
      return;
    }
    const [path, hash] = url.split('#');
    if (path === window.location.pathname) {
      history.replaceState(null, '', hash ? `#${hash}` : window.location.pathname);
      window.location.reload();
    } else {
      window.location.href = url;
    }
  }

  // ---------- Inline spoilers ----------
  function toggleSpoiler(span) {
    const shown = span.classList.toggle('is-shown');
    span.setAttribute('aria-pressed', shown ? 'true' : 'false');
  }
  document.addEventListener('click', (event) => {
    const span = event.target.closest('.disc-spoiler');
    if (span && !span.classList.contains('is-shown')) toggleSpoiler(span);
  });
  document.addEventListener('keydown', (event) => {
    const span = event.target.closest && event.target.closest('.disc-spoiler');
    if (span && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      toggleSpoiler(span);
    }
  });

  function threadId(element) {
    const holder = element.closest('[data-disc-thread]');
    return holder ? holder.dataset.discThread : null;
  }

  function replyId(element) {
    return element.dataset.replyId ? Number(element.dataset.replyId) : null;
  }

  // ---------- Start a discussion ----------
  const start = document.querySelector('[data-disc-start]');
  if (start) {
    const status = start.querySelector('.disc-form__status');
    if (window.location.hash === '#start') start.closest('details').open = true;
    start.addEventListener('submit', async (event) => {
      event.preventDefault();
      const subject = start.elements.subject.value.trim();
      const body = start.elements.body.value.trim();
      if (subject.length < 6) {
        status.textContent = 'Give your discussion a title of a few words.';
        start.elements.subject.focus();
        return;
      }
      if (body.length < 20) {
        status.textContent = 'Write a sentence or two to get people talking.';
        start.elements.body.focus();
        return;
      }
      const button = start.querySelector('[type="submit"]');
      button.disabled = true;
      status.textContent = 'Posting…';
      try {
        const data = await send('POST', `/api/titles/${encodeURIComponent(start.dataset.kind)}/${encodeURIComponent(start.dataset.slug)}/discussions`,
          { subject, body, spoiler: start.elements.spoiler.checked });
        goTo(data.url);
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    });
  }

  // ---------- Reply ----------
  const replyForm = document.querySelector('[data-disc-reply]');
  if (replyForm) {
    const status = replyForm.querySelector('.disc-form__status');
    replyForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const body = replyForm.elements.body.value.trim();
      if (body.length < 2) {
        status.textContent = 'Write a few words first.';
        replyForm.elements.body.focus();
        return;
      }
      const button = replyForm.querySelector('[type="submit"]');
      button.disabled = true;
      status.textContent = 'Posting…';
      try {
        const data = await send('POST', `/api/discussions/${threadId(replyForm)}/replies`, { body, spoiler: replyForm.elements.spoiler.checked });
        goTo(data.url);
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    });
  }

  // ---------- Edit your own post ----------
  function openEditor(button) {
    const post = button.closest('.disc-post');
    const content = post.querySelector('.disc-post__content');
    if (!content || post.querySelector('.disc-edit')) return;
    const form = document.createElement('form');
    form.className = 'disc-edit';
    const label = document.createElement('label');
    label.className = 'disc-form__label';
    label.textContent = 'Edit your post';
    const area = document.createElement('textarea');
    area.name = 'body';
    area.rows = 5;
    area.maxLength = button.dataset.replyId ? 3000 : 5000;
    area.value = content.dataset.raw || '';
    label.append(area);
    const check = document.createElement('label');
    check.className = 'disc-form__check';
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.name = 'spoiler';
    box.checked = content.dataset.spoiler === 'true';
    check.append(box, ' Has spoilers');
    const row = document.createElement('div');
    row.className = 'disc-edit__row';
    const save = document.createElement('button');
    save.type = 'submit';
    save.className = 'site-btn site-btn--primary site-btn--sm';
    save.textContent = 'Save';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'site-btn site-btn--ghost site-btn--sm';
    cancel.textContent = 'Cancel';
    const status = document.createElement('p');
    status.className = 'disc-form__status';
    status.setAttribute('role', 'status');
    row.append(save, cancel, status);
    form.append(label, check, row);
    content.hidden = true;
    content.after(form);
    area.focus();
    cancel.addEventListener('click', () => { form.remove(); content.hidden = false; });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      save.disabled = true;
      status.textContent = 'Saving…';
      try {
        await send('PATCH', `/api/discussions/${threadId(button)}`, { body: area.value, spoiler: box.checked, reply_id: replyId(button) });
        goTo(`${window.location.pathname}#${post.id}`);
      } catch (error) {
        status.textContent = error.message;
        save.disabled = false;
      }
    });
  }

  // ---------- Delete (asks twice, no pop-up) ----------
  async function remove(button) {
    if (button.dataset.armed !== 'true') {
      button.dataset.armed = 'true';
      button.dataset.label = button.textContent;
      button.textContent = 'Delete for good?';
      setTimeout(() => {
        if (button.isConnected && button.dataset.armed === 'true') {
          button.dataset.armed = '';
          button.textContent = button.dataset.label;
        }
      }, 5000);
      return;
    }
    button.disabled = true;
    const reply = replyId(button);
    try {
      const data = await send('DELETE', `/api/discussions/${threadId(button)}${reply ? `?reply_id=${reply}` : ''}`);
      if (!reply && data.state === 'deleted' && window.location.pathname !== '/discussions/moderation') goTo(data.board);
      else window.location.reload();
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message;
    }
  }

  // ---------- Moderator tools ----------
  async function moderate(button) {
    button.disabled = true;
    try {
      await send('POST', `/api/discussions/${threadId(button)}/moderate`, { action: button.dataset.discMod, reply_id: replyId(button) });
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message;
    }
  }

  document.addEventListener('click', (event) => {
    const edit = event.target.closest('[data-disc-edit]');
    if (edit) openEditor(edit);
    const del = event.target.closest('[data-disc-delete]');
    if (del) remove(del);
    const mod = event.target.closest('[data-disc-mod]');
    if (mod) moderate(mod);
  });

  // ---------- Reports ----------
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-disc-report]');
    if (!form) return;
    event.preventDefault();
    const status = form.querySelector('.disc-report__status');
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    status.textContent = 'Sending…';
    try {
      const data = await send('POST', `/api/discussions/${threadId(form)}/report`, { reason: form.elements.reason.value, reply_id: replyId(form) });
      status.textContent = data.duplicate ? 'You already reported this one. Thanks.'
        : data.hidden ? 'Thanks. It is hidden now until a moderator looks at it.'
          : 'Thanks for letting us know. A moderator will take a look.';
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  });
}());
