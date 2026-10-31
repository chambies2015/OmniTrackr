// Passkeys. Two jobs in one file so both pages load the same code:
//  - the log-in card: a "Log in with a passkey" button, plus the browser's own
//    passkey suggestions in the username box (conditional mediation);
//  - Settings > Sign-in: the member's passkeys, with add, rename and remove.
// The checks happen on the server (app/passkeys.py); this file moves bytes
// between the server's JSON and navigator.credentials.
(function () {
  const $ = id => document.getElementById(id);
  const authBase = () => (typeof AUTH_API_BASE === 'string' ? AUTH_API_BASE : (typeof API_BASE === 'string' ? API_BASE : ''));
  const apiBase = () => (typeof API_BASE === 'string' ? API_BASE : '');

  function supported() {
    return typeof window !== 'undefined' && typeof window.PublicKeyCredential === 'function'
      && typeof navigator !== 'undefined' && navigator.credentials
      && typeof navigator.credentials.get === 'function' && typeof navigator.credentials.create === 'function';
  }

  // ---------------------------------------------------------------- bytes <-> base64url

  function toBytes(text) {
    const padded = String(text).replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(padded + '='.repeat((4 - padded.length % 4) % 4));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  }

  function toText(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function creationOptions(options) {
    return {
      ...options,
      challenge: toBytes(options.challenge),
      user: { ...options.user, id: toBytes(options.user.id) },
      excludeCredentials: (options.excludeCredentials || []).map(item => ({ ...item, id: toBytes(item.id) })),
    };
  }

  function requestOptions(options) {
    return {
      ...options,
      challenge: toBytes(options.challenge),
      allowCredentials: (options.allowCredentials || []).map(item => ({ ...item, id: toBytes(item.id) })),
    };
  }

  function serialize(credential) {
    const response = credential.response || {};
    const out = {
      id: credential.id,
      rawId: toText(credential.rawId),
      type: credential.type || 'public-key',
      authenticatorAttachment: credential.authenticatorAttachment || null,
      response: { clientDataJSON: toText(response.clientDataJSON) },
    };
    if (response.attestationObject) {
      out.response.attestationObject = toText(response.attestationObject);
      out.response.transports = typeof response.getTransports === 'function' ? response.getTransports() : [];
    }
    if (response.authenticatorData) {
      out.response.authenticatorData = toText(response.authenticatorData);
      out.response.signature = toText(response.signature);
      out.response.userHandle = response.userHandle ? toText(response.userHandle) : null;
    }
    return out;
  }

  // ---------------------------------------------------------------- shared

  function errorText(body, fallback) {
    if (typeof apiErrorText === 'function') return apiErrorText(body, fallback);
    return body && typeof body.detail === 'string' ? body.detail : fallback;
  }

  async function postJson(url, body, fetcher) {
    const response = await (fetcher || fetch)(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body === undefined ? {} : body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(errorText(data, response.status === 429
        ? 'Too many attempts. Please wait a minute and try again.'
        : 'Something went wrong. Please try again.'));
      error.status = response.status;
      error.fromServer = true;
      throw error;
    }
    return data;
  }

  function busy(button, text) {
    if (!button) return () => {};
    const label = button.textContent;
    button.disabled = true;
    button.textContent = text;
    return () => { button.disabled = false; button.textContent = label; };
  }

  // What the browser's own errors mean for a person.
  function explain(error, fallback) {
    if (!error) return fallback;
    if (error.fromServer) return error.message;
    switch (error.name) {
      case 'NotAllowedError':
      case 'AbortError':
        return '';  // Cancelled, or the prompt timed out. Not an error worth a message.
      case 'InvalidStateError':
        return 'This device already has a passkey for your account. Use that one, or remove it in Settings first.';
      case 'SecurityError':
        return "Passkeys only work on the site's own web address over https.";
      case 'NotSupportedError':
        return "This device can't make the kind of passkey we need. Try another device, or a security key.";
      default:
        return fallback;
    }
  }

  // ---------------------------------------------------------------- log-in card

  // Only one passkey prompt can be open at a time, so the autofill (conditional)
  // request and the button's own request take turns. `generation` lets a
  // conditional request that was superseded while its challenge was still
  // loading step aside instead of fighting the button for the prompt.
  let conditionalController = null;
  let conditionalStarted = false;
  let generation = 0;
  let optionsInFlight = null;

  function loginError(text) {
    if (!text) return;
    if (typeof displayAuthError === 'function') displayAuthError(text);
  }

  async function assert(mediation, mine) {
    optionsInFlight = postJson(`${authBase()}/auth/passkey/options`);
    let options;
    try {
      options = await optionsInFlight;
    } finally {
      optionsInFlight = null;
    }
    if (mine !== undefined && mine !== generation) return null;  // the button took over meanwhile
    const request = { publicKey: requestOptions(options) };
    if (mediation === 'conditional') {
      conditionalController = typeof AbortController === 'function' ? new AbortController() : null;
      request.mediation = 'conditional';
      if (conditionalController) request.signal = conditionalController.signal;
    }
    const credential = await navigator.credentials.get(request);
    if (mine !== undefined && mine !== generation) return null;
    if (!credential) throw Object.assign(new Error('No passkey was used.'), { name: 'NotAllowedError' });
    const data = await postJson(`${authBase()}/auth/passkey/login`, serialize(credential));
    if (typeof finishLogin === 'function') finishLogin(data);
    return data;
  }

  // Offer saved passkeys in the username box's autofill list. Chrome, Safari and
  // Edge show them once a conditional request is pending; nothing shows otherwise.
  async function startConditional() {
    if (conditionalStarted || !supported()) return;
    if (typeof PublicKeyCredential.isConditionalMediationAvailable !== 'function') return;
    conditionalStarted = true;
    let available = false;
    try { available = await PublicKeyCredential.isConditionalMediationAvailable(); } catch (_) { available = false; }
    if (!available) return;
    const mine = ++generation;
    try {
      await assert('conditional', mine);
    } catch (error) {
      if (mine !== generation) return;  // superseded; whoever took over reports its own result
      conditionalStarted = false;
      conditionalController = null;
      // Autofill runs in the background, so only a verdict from the server is worth a message.
      if (error && error.fromServer) loginError(error.message);
    }
  }

  function stopConditional() {
    generation += 1;
    if (conditionalController) conditionalController.abort();
    conditionalController = null;
    conditionalStarted = false;
  }

  async function loginWithButton(button) {
    stopConditional();
    // A challenge the autofill request asked for a moment ago must land before ours,
    // since the newest challenge cookie is the one the server will check.
    if (optionsInFlight) await optionsInFlight.catch(() => {});
    if (typeof clearFormErrors === 'function') {
      const form = $('loginFormElement');
      if (form) clearFormErrors(form);
    }
    const done = busy(button, 'Waiting for your device…');
    let signedIn = false;
    try {
      signedIn = Boolean(await assert('optional'));
    } catch (error) {
      loginError(explain(error, "That passkey didn't work. Try again, or log in with your password."));
    } finally {
      done();
      if (!signedIn) startConditional();
    }
  }

  function initLogin() {
    const button = $('passkeyLoginButton');
    if (!button || !supported()) return;
    button.hidden = false;
    button.addEventListener('click', () => loginWithButton(button));
    const username = $('loginUsername');
    if (username && typeof username.setAttribute === 'function') username.setAttribute('autocomplete', 'username webauthn');
    // Ask for a challenge the first time someone goes to type, not on every page view.
    [username, $('loginPassword')].forEach(field => {
      if (field && typeof field.addEventListener === 'function') field.addEventListener('focus', () => startConditional());
    });
  }

  // ---------------------------------------------------------------- settings

  let state = { passkeys: [], has_password: true, limit: 10 };
  let openEditor = null;  // { id, kind: 'rename' | 'remove' }

  function section() { return $('passkeySection'); }

  function say(kind, text) {
    const error = $('passkeyError');
    const success = $('passkeySuccess');
    [error, success].forEach(element => {
      if (!element) return;
      element.textContent = '';
      element.style.display = 'none';
    });
    const target = kind === 'error' ? error : success;
    if (target && text) {
      // Screen readers hear the result without the focus moving off the form.
      if (typeof target.setAttribute === 'function') target.setAttribute('role', kind === 'error' ? 'alert' : 'status');
      target.textContent = text;
      target.style.display = 'block';
    }
  }

  function call(path, body) {
    const fetcher = typeof authenticatedFetch === 'function' ? authenticatedFetch : fetch;
    if (body === undefined) {
      return fetcher(`${apiBase()}/account/passkeys${path}`).then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw Object.assign(new Error(errorText(data, 'Something went wrong. Please try again.')), { fromServer: true });
        return data;
      });
    }
    return postJson(`${apiBase()}/account/passkeys${path}`, body, fetcher);
  }

  function formatDate(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function usedText(iso) {
    if (!iso) return 'Not used yet';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const days = Math.floor((Date.now() - date.getTime()) / 86400000);
    if (days <= 0) return 'Used today';
    if (days === 1) return 'Used yesterday';
    if (days < 30) return `Used ${days} days ago`;
    return `Last used ${formatDate(iso)}`;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // A small line drawing per kind of passkey: security key, synced passkey, or this device.
  const ICON_PATHS = {
    key: ['M15.5 7.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z', 'M9.6 10.4 3 17v3h3l1-1v-2h2v-2h2l1.4-1.4'],
    cloud: ['M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 9.1 4.5 4.5 0 0 0 7 18Z', 'm9.5 13.5 2 2 3.5-4'],
    device: ['M8 3h8a1.5 1.5 0 0 1 1.5 1.5v15A1.5 1.5 0 0 1 16 21H8a1.5 1.5 0 0 1-1.5-1.5v-15A1.5 1.5 0 0 1 8 3Z', 'M11 17.5h2'],
  };

  function iconFor(item) {
    const kind = item.transports.includes('usb') || item.transports.includes('nfc') ? 'key' : item.backed_up ? 'cloud' : 'device';
    if (typeof document.createElementNS !== 'function') return el('span', '', kind);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.8');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    ICON_PATHS[kind].forEach(d => {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      svg.appendChild(path);
    });
    return svg;
  }

  function passwordField(id) {
    const wrap = el('div', 'account-field');
    const label = el('label', 'account-field__label', 'Current password');
    label.htmlFor = id;
    const box = el('div', 'auth-password');
    const input = el('input');
    input.type = 'password';
    input.id = id;
    input.autocomplete = 'current-password';
    box.appendChild(input);
    wrap.append(label, box);
    return wrap;
  }

  function editor(item) {
    const form = el('form', 'passkeys__editor');
    form.noValidate = true;
    if (openEditor.kind === 'rename') {
      const field = el('div', 'account-field');
      const label = el('label', 'account-field__label', 'Name');
      label.htmlFor = 'passkeyRenameInput';
      const input = el('input');
      input.type = 'text';
      input.id = 'passkeyRenameInput';
      input.maxLength = 60;
      input.value = item.name;
      input.autocomplete = 'off';
      field.append(label, input);
      const row = el('div', 'passkeys__editor-actions');
      const save = el('button', 'action-btn', 'Save');
      save.type = 'submit';
      const cancel = el('button', 'action-btn two-factor__quiet', 'Cancel');
      cancel.type = 'button';
      cancel.dataset.passkeyCancel = '1';
      row.append(save, cancel);
      form.append(field, row);
      form.addEventListener('submit', event => {
        event.preventDefault();
        rename(item, input.value, save);
      });
    } else {
      form.appendChild(el('p', 'account-field__hint',
        `Remove ${item.name}? It stops opening your library right away. The passkey stays on that device until you delete it there too.`));
      if (state.has_password) form.appendChild(passwordField('passkeyRemovePassword'));
      const row = el('div', 'passkeys__editor-actions');
      const remove = el('button', 'action-btn danger-btn', 'Remove passkey');
      remove.type = 'submit';
      const keep = el('button', 'action-btn two-factor__quiet', 'Keep it');
      keep.type = 'button';
      keep.dataset.passkeyCancel = '1';
      row.append(remove, keep);
      form.append(row);
      form.addEventListener('submit', event => {
        event.preventDefault();
        const password = $('passkeyRemovePassword');
        removePasskey(item, password ? password.value : '', remove);
      });
    }
    return form;
  }

  function renderList() {
    const list = $('passkeyList');
    if (!list) return;
    const items = state.passkeys.map(item => {
      const li = el('li', 'passkeys__item');
      li.dataset.passkeyId = String(item.id);
      const icon = el('span', 'passkeys__icon');
      icon.setAttribute('aria-hidden', 'true');
      icon.appendChild(iconFor(item));
      const body = el('div', 'passkeys__body');
      body.appendChild(el('strong', 'passkeys__name', item.name));
      const meta = [`Added ${formatDate(item.created_at)}`, usedText(item.last_used_at)];
      if (item.backed_up) meta.push('Synced across your devices');
      body.appendChild(el('span', 'passkeys__meta', meta.filter(Boolean).join(' · ')));
      const actions = el('div', 'passkeys__actions');
      // Every row has the same two buttons; the name says which passkey each one is for.
      const renameButton = el('button', 'two-factor__link', 'Rename');
      renameButton.type = 'button';
      renameButton.dataset.passkeyRename = String(item.id);
      renameButton.setAttribute('aria-label', `Rename ${item.name}`);
      const removeButton = el('button', 'two-factor__link passkeys__remove', 'Remove');
      removeButton.type = 'button';
      removeButton.dataset.passkeyRemove = String(item.id);
      removeButton.setAttribute('aria-label', `Remove ${item.name}`);
      actions.append(renameButton, removeButton);
      li.append(icon, body, actions);
      if (openEditor && openEditor.id === item.id) li.appendChild(editor(item));
      return li;
    });
    list.replaceChildren(...items);
    list.hidden = items.length === 0;
  }

  function render() {
    const root = section();
    if (!root) return;
    const count = state.passkeys.length;
    const badge = $('passkeyBadge');
    if (badge) {
      badge.textContent = count === 0 ? 'None yet' : count === 1 ? '1 passkey' : `${count} passkeys`;
      badge.classList.toggle('is-on', count > 0);
    }
    const empty = $('passkeyEmpty');
    if (empty) empty.hidden = count > 0;
    root.querySelectorAll('[data-passkey-password]').forEach(field => { field.hidden = !state.has_password; });
    const addForm = $('passkeyAddForm');
    const unsupported = $('passkeyUnsupported');
    const full = $('passkeyFull');
    const canAdd = supported() && count < state.limit;
    if (addForm) addForm.hidden = !canAdd;
    if (unsupported) unsupported.hidden = supported();
    if (full) full.hidden = !(supported() && count >= state.limit);
    renderList();
  }

  async function refresh() {
    if (!section()) return;
    try {
      state = await call('');
      openEditor = null;
      render();
    } catch (error) {
      say('error', "Couldn't load your passkeys. Close Settings and open it again.");
    }
  }

  async function add(event) {
    event.preventDefault();
    say();
    const nameInput = $('passkeyName');
    const passwordInput = $('passkeyAddPassword');
    const password = passwordInput ? passwordInput.value : '';
    if (state.has_password && !password) {
      say('error', 'Enter your current password first.');
      if (passwordInput && typeof passwordInput.focus === 'function') passwordInput.focus();
      return;
    }
    const button = event.target.querySelector('button[type="submit"]');
    const done = busy(button, 'Waiting for your device…');
    try {
      const options = await call('/options', { password });
      const credential = await navigator.credentials.create({ publicKey: creationOptions(options) });
      if (!credential) throw Object.assign(new Error('Nothing was made.'), { name: 'NotAllowedError' });
      const result = await call('/register', { name: nameInput ? nameInput.value : '', credential: serialize(credential) });
      state = result;
      if (nameInput) nameInput.value = '';
      if (passwordInput) passwordInput.value = '';
      render();
      const added = result.added ? result.added.name : 'Your passkey';
      say('success', `${added} is ready. Next time, choose "Log in with a passkey" on the log-in page, or pick it from the username box.`);
    } catch (error) {
      const text = explain(error, "Couldn't add that passkey. Try again, or try another device.");
      say('error', text || 'No passkey was made.');
    } finally {
      done();
    }
  }

  async function rename(item, value, button) {
    say();
    const name = String(value || '').trim();
    if (!name) {
      say('error', 'Give the passkey a name, like the device it lives on.');
      return;
    }
    const done = busy(button, 'Saving…');
    try {
      state = await call(`/${item.id}/rename`, { name });
      openEditor = null;
      render();
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  async function removePasskey(item, password, button) {
    say();
    if (state.has_password && !password) {
      say('error', 'Enter your current password to remove a passkey.');
      return;
    }
    const done = busy(button, 'Removing…');
    try {
      state = await call(`/${item.id}/remove`, { password });
      openEditor = null;
      render();
      say('success', `${item.name} was removed. We emailed you about the change.`);
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  function initSettings() {
    const root = section();
    if (!root) return;
    const addForm = $('passkeyAddForm');
    if (addForm && typeof addForm.addEventListener === 'function') addForm.addEventListener('submit', add);
    root.addEventListener('click', event => {
      const target = event.target.closest('button');
      if (!target || !root.contains(target)) return;
      if (target.dataset.passkeyRename) {
        openEditor = { id: Number(target.dataset.passkeyRename), kind: 'rename' };
        say();
        renderList();
        const input = $('passkeyRenameInput');
        if (input && typeof input.focus === 'function') input.focus();
      } else if (target.dataset.passkeyRemove) {
        openEditor = { id: Number(target.dataset.passkeyRemove), kind: 'remove' };
        say();
        renderList();
        // The question ("Remove X?") is read out, and Keep it is one Tab away from Remove passkey.
        const form = $('passkeyList') && typeof $('passkeyList').querySelector === 'function'
          ? $('passkeyList').querySelector('.passkeys__editor') : null;
        if (form && typeof form.focus === 'function') {
          form.tabIndex = -1;
          form.focus({ preventScroll: true });
        }
      } else if (target.dataset.passkeyCancel) {
        openEditor = null;
        renderList();
      }
    });
    render();

    const modal = $('accountModal');
    if (!modal) return;
    let open = false;
    const check = () => {
      const visible = modal.style.display !== 'none' && modal.style.display !== '';
      if (visible && !open) refresh();
      if (!visible && open) { openEditor = null; say(); }
      open = visible;
    };
    if (typeof MutationObserver === 'function') {
      new MutationObserver(check).observe(modal, { attributes: true, attributeFilter: ['style'] });
    }
    check();
  }

  function init() {
    initLogin();
    initSettings();
  }

  window.OmniPasskeys = {
    supported, toBytes, toText, serialize, creationOptions, requestOptions, explain,
    refresh, render, startConditional, loginWithButton,
    get state() { return state; },
    set state(value) { state = value; },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
