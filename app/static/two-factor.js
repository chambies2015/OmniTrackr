// Settings > Sign-in > Two-factor sign-in: set up an authenticator app, show the
// recovery codes once, and turn it off again. The code step at log-in lives in auth.js.
(function () {
  const $ = id => document.getElementById(id);
  const base = () => (typeof API_BASE === 'string' ? API_BASE : '');
  let state = { enabled: false, has_password: true, recovery_codes_left: 0, enabled_at: null };
  let shownCodes = [];

  function section() { return $('twoFactorSection'); }

  function say(kind, text) {
    const error = $('twoFactorError');
    const success = $('twoFactorSuccess');
    [error, success].forEach(element => {
      if (!element) return;
      element.textContent = '';
      element.style.display = 'none';
    });
    const target = kind === 'error' ? error : success;
    if (target && text) {
      target.textContent = text;
      target.style.display = 'block';
    }
  }

  function errorText(body, fallback) {
    if (typeof apiErrorText === 'function') return apiErrorText(body, fallback);
    return body && typeof body.detail === 'string' ? body.detail : fallback;
  }

  async function call(path, body) {
    const options = body === undefined ? {} : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    };
    const response = await authenticatedFetch(`${base()}/account/two-factor${path}`, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorText(data, 'Something went wrong. Please try again.'));
    return data;
  }

  function showPanel(name) {
    const root = section();
    if (!root) return;
    root.querySelectorAll('[data-two-factor-panel]').forEach(panel => {
      panel.hidden = panel.dataset.twoFactorPanel !== name;
    });
  }

  function formatDate(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function render() {
    const root = section();
    if (!root) return;
    const badge = $('twoFactorBadge');
    if (badge) {
      badge.textContent = state.enabled ? 'On' : 'Off';
      badge.classList.toggle('is-on', state.enabled);
    }
    // Accounts made with Google have no password yet, so there's nothing to ask for.
    root.querySelectorAll('[data-two-factor-password]').forEach(field => { field.hidden = !state.has_password; });
    root.querySelectorAll('[data-two-factor-password-hint]').forEach(hint => { hint.hidden = !state.has_password; });
    if (shownCodes.length) return showPanel('codes');
    if (!state.enabled) return showPanel('off');
    const summary = $('twoFactorSummary');
    if (summary) {
      const since = formatDate(state.enabled_at);
      const left = state.recovery_codes_left;
      const codes = left === 0
        ? 'You have no recovery codes left. Get a new set below so a lost phone can\'t lock you out.'
        : `${left} recovery code${left === 1 ? '' : 's'} left.`;
      summary.textContent = `${since ? `On since ${since}. ` : ''}${codes}`;
      summary.classList.toggle('is-warning', left <= 2);
    }
    showPanel('on');
  }

  async function refresh() {
    if (!section()) return;
    try {
      state = await call('');
      render();
    } catch (error) {
      say('error', "Couldn't load your two-factor settings. Close Settings and open it again.");
    }
  }

  function clearInputs() {
    ['twoFactorStartPassword', 'twoFactorEnableCode', 'twoFactorManageCode', 'twoFactorManagePassword']
      .forEach(id => { const input = $(id); if (input) input.value = ''; });
  }

  function busy(button, text) {
    if (!button) return () => {};
    const label = button.textContent;
    button.disabled = true;
    button.textContent = text;
    return () => { button.disabled = false; button.textContent = label; };
  }

  function showCodes(codes) {
    shownCodes = codes.slice();
    const list = $('twoFactorCodes');
    if (list) {
      list.replaceChildren(...codes.map(code => {
        const item = document.createElement('li');
        item.textContent = code;
        return item;
      }));
    }
    render();
  }

  function codesText() {
    return [
      'OmniTrackr recovery codes',
      `Saved ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`,
      '',
      'Each code works once, in place of a code from your authenticator app.',
      '',
      ...shownCodes,
      '',
    ].join('\n');
  }

  async function start(event) {
    event.preventDefault();
    say();
    const password = $('twoFactorStartPassword')?.value || '';
    if (state.has_password && !password) {
      say('error', 'Enter your current password first.');
      return;
    }
    const done = busy(event.target.querySelector('button[type="submit"]'), 'Getting a code ready…');
    try {
      const setup = await call('/setup', { password });
      $('twoFactorQr').src = setup.qr_code;
      $('twoFactorKey').textContent = setup.secret;
      const link = $('twoFactorAppLink');
      if (link) link.href = setup.otpauth_uri;
      clearInputs();
      showPanel('setup');
      $('twoFactorEnableCode')?.focus();
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  async function enable(event) {
    event.preventDefault();
    say();
    const code = ($('twoFactorEnableCode')?.value || '').replace(/\s+/g, '');
    if (!/^\d{6}$/.test(code)) {
      say('error', 'Type the six digits your app shows for OmniTrackr.');
      return;
    }
    const done = busy(event.target.querySelector('button[type="submit"]'), 'Checking…');
    try {
      const result = await call('/enable', { code });
      state = result;
      clearInputs();
      showCodes(result.recovery_codes || []);
      say('success', 'Two-factor sign-in is on. Save your recovery codes before you close this.');
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  async function manage(action, button) {
    say();
    const code = ($('twoFactorManageCode')?.value || '').trim();
    const password = $('twoFactorManagePassword')?.value || '';
    if (!code) {
      say('error', 'Enter a code from your app or one of your recovery codes.');
      return;
    }
    if (state.has_password && !password) {
      say('error', 'Enter your current password too.');
      return;
    }
    if (action === 'disable' && typeof confirm === 'function'
        && !confirm('Turn off two-factor sign-in? Logging in will only need your password again.')) return;
    const done = busy(button, action === 'disable' ? 'Turning off…' : 'Making new codes…');
    try {
      const result = await call(action === 'disable' ? '/disable' : '/recovery-codes', { code, password });
      state = result;
      clearInputs();
      if (action === 'disable') {
        render();
        say('success', 'Two-factor sign-in is off. We emailed you about the change.');
      } else {
        showCodes(result.recovery_codes || []);
        say('success', 'New recovery codes are ready. The old ones no longer work.');
      }
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  async function forgetBrowsers(button) {
    say();
    const done = busy(button, 'Working…');
    try {
      const result = await call('/forget-browsers', {});
      say('success', result.message || 'Done. Every browser will ask for a code at the next sign-in.');
    } catch (error) {
      say('error', error.message);
    } finally {
      done();
    }
  }

  async function copyCodes(button) {
    try {
      await navigator.clipboard.writeText(codesText());
      const done = busy(button, 'Copied');
      setTimeout(done, 1500);
    } catch (error) {
      say('error', "Couldn't copy. Select the codes and copy them by hand, or download them.");
    }
  }

  function downloadCodes() {
    const blob = new Blob([codesText()], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'omnitrackr-recovery-codes.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function reset() {
    shownCodes = [];
    clearInputs();
    const list = $('twoFactorCodes');
    if (list) list.replaceChildren();
    const qr = $('twoFactorQr');
    if (qr) qr.removeAttribute('src');
    const key = $('twoFactorKey');
    if (key) key.textContent = '';
  }

  function init() {
    const root = section();
    if (!root) return;
    $('twoFactorStartForm')?.addEventListener('submit', start);
    $('twoFactorEnableForm')?.addEventListener('submit', enable);
    $('twoFactorManageForm')?.addEventListener('submit', event => event.preventDefault());
    root.addEventListener('click', event => {
      const target = event.target.closest('button');
      if (!target || !root.contains(target)) return;
      if (target.matches('[data-two-factor-cancel]')) {
        reset();
        say();
        render();
      } else if (target.matches('[data-two-factor-action]')) {
        manage(target.dataset.twoFactorAction, target);
      } else if (target.matches('[data-two-factor-forget]')) {
        forgetBrowsers(target);
      } else if (target.matches('[data-two-factor-copy]')) {
        copyCodes(target);
      } else if (target.matches('[data-two-factor-download]')) {
        downloadCodes();
      } else if (target.matches('[data-two-factor-done]')) {
        shownCodes = [];
        say();
        render();
      }
    });

    // Load the current state whenever Settings opens; start fresh when it closes.
    // Watching the dialog catches every way it opens (menu, avatar, /#settings-signin links).
    const modal = $('accountModal');
    if (!modal) return;
    let open = false;
    const check = () => {
      const visible = modal.style.display !== 'none' && modal.style.display !== '';
      if (visible && !open) refresh();
      if (!visible && open) reset();
      open = visible;
    };
    if (typeof MutationObserver === 'function') {
      new MutationObserver(check).observe(modal, { attributes: true, attributeFilter: ['style'] });
    }
    check();
  }

  window.OmniTwoFactor = { refresh, render, codesText };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
