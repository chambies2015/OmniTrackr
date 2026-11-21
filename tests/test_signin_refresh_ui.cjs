// The refreshed sign-in card: a folded username box, email slip hints, the
// "check your inbox" step and a one-box password reset.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');

function setup({ reply = { ok: true, body: {} }, saved = [] } = {}) {
  const elements = new Map();
  const requests = [];
  const windowListeners = {};
  const focused = { id: null };
  function el(id, props = {}) {
    const node = {
      id, style: {}, dataset: {}, value: '', textContent: '', hidden: false, type: 'text', attrs: {}, listeners: {},
      setAttribute(k, v) { this.attrs[k] = String(v); },
      getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener(type, fn) { this.listeners[type] = fn; },
      focus() { focused.id = id; },
      select() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      reset() {},
      ...props,
    };
    elements.set(id, node);
    return node;
  }
  const document = {
    readyState: 'loading', title: '', documentElement: { dataset: { publicShell: 'true' } },
    addEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    getElementById(id) { return ['registerConfirmPassword', 'confirmNewPassword'].includes(id) ? null : elements.get(id) || el(id); },
  };
  const location = { pathname: '/', search: '', assign() {} };
  const context = vm.createContext({
    URLSearchParams, location, document, Blob: function Blob() {},
    navigator: { sendBeacon: () => true },
    window: { location, history: { replaceState() {} }, addEventListener(type, fn) { windowListeners[type] = fn; } },
    localStorage: { getItem: key => (key === 'omnitrackr_guest_list' ? JSON.stringify(saved) : null), setItem() {}, removeItem() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: reply.ok, status: reply.status || (reply.ok ? 200 : 400), json: async () => reply.body };
    },
    setTimeout: () => 0,
    Math,
  });
  vm.runInContext(source, context);
  const form = id => el(id, {
    querySelector: selector => (selector === 'button[type="submit"]' ? document.getElementById(`${id}Button`) : null),
    querySelectorAll: () => Array.from(elements.values()).filter(item => item.attrs['aria-invalid'] === 'true'),
  });
  return { context, elements, requests, windowListeners, focused, el, form, $: id => document.getElementById(id) };
}

test('the username box folds behind one line that follows the email', () => {
  const s = setup();
  s.context.setupUsernameSuggestion();
  assert.equal(s.$('registerUsernameField').hidden, true);
  assert.equal(s.$('registerHandle').hidden, false);
  assert.equal(s.$('registerHandleFilled').hidden, true, 'no name yet');

  s.$('registerEmail').value = 'riley@example.com';
  s.$('registerEmail').listeners.input();
  assert.equal(s.$('registerUsername').value, 'riley');
  assert.equal(s.$('registerHandleName').textContent, 'riley');
  assert.equal(s.$('registerHandleFilled').hidden, false);
  assert.equal(s.$('registerHandleEmpty').hidden, true);

  s.$('registerHandleChange').listeners.click();
  assert.equal(s.$('registerUsernameField').hidden, false);
  assert.equal(s.$('registerHandle').hidden, true);
  assert.equal(s.focused.id, 'registerUsername');
});

test('a problem with the username opens the folded box', () => {
  const s = setup();
  s.context.setupUsernameSuggestion();
  assert.equal(s.$('registerUsernameField').hidden, true);
  s.context.showFieldError('registerUsername', 'Usernames need 3–30 characters.');
  assert.equal(s.$('registerUsernameField').hidden, false);
  assert.equal(s.$('registerHandle').hidden, true);
  // Opening the form again keeps a box that has a message under it.
  s.context.foldUsernameField();
  assert.equal(s.$('registerUsernameField').hidden, false);
});

test('sign-up fills an empty folded username from the email before sending', async () => {
  const s = setup({ reply: { ok: true, body: { id: 1 } } });
  const registerForm = s.form('registerFormElement');
  s.context.setupAuthHandlers();
  s.$('registerEmail').value = 'autofilled@example.com';
  s.$('registerPassword').value = 'long enough phrase';
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  assert.equal(s.requests.length, 1);
  assert.equal(JSON.parse(s.requests[0].options.body).username, 'autofilled');
});

test('a taken suggested username is swapped for another one, a typed one is left alone', async () => {
  const s = setup({ reply: { ok: false, status: 400, body: { detail: 'Username already taken. Try adding a number or a word.' } } });
  const registerForm = s.form('registerFormElement');
  s.context.setupAuthHandlers();
  s.$('registerEmail').value = 'sam@example.com';
  s.$('registerEmail').listeners.input();
  s.$('registerPassword').value = 'long enough phrase';
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  const offered = s.$('registerUsername').value;
  assert.match(offered, /^sam\d\d$/);
  assert.equal(s.$('registerUsernameError').textContent, `sam is taken, so we changed it to ${offered}. Keep it or type your own, then create your account.`);
  assert.equal(s.$('registerUsernameField').hidden, false);

  s.$('registerUsername').value = 'filmsam';
  s.$('registerUsername').listeners.input();
  await registerForm.listeners.submit({ preventDefault() {}, target: registerForm });
  assert.equal(s.$('registerUsername').value, 'filmsam');
  assert.equal(s.$('registerUsernameError').textContent, 'Username already taken. Try adding a number or a word.');
});

test('email slips in well-known domains get a one-click fix', () => {
  const s = setup();
  assert.equal(s.context.emailTypoFix('sam@gmial.com'), 'sam@gmail.com');
  assert.equal(s.context.emailTypoFix('Sam.Lee@Hotmail.con'), 'Sam.Lee@hotmail.com');
  assert.equal(s.context.emailTypoFix('sam@yahoo.co'), 'sam@yahoo.com');
  for (const fine of ['sam@gmail.com', 'sam@yahoo.co.uk', 'sam@hotmail.co.uk', 'sam@example.com', 'sam', '@gmial.com', '']) {
    assert.equal(s.context.emailTypoFix(fine), '', fine);
  }

  s.context.setupUsernameSuggestion();
  s.$('registerEmailSuggest').hidden = true;
  s.$('registerEmail').value = 'riley@outlok.com';
  s.$('registerEmail').listeners.blur();
  assert.equal(s.$('registerEmailSuggest').hidden, false);
  assert.equal(s.$('registerEmailFix').textContent, 'riley@outlook.com');
  s.$('registerEmailFix').listeners.click();
  assert.equal(s.$('registerEmail').value, 'riley@outlook.com');
  assert.equal(s.$('registerEmailSuggest').hidden, true);

  s.$('registerEmail').value = 'riley@outlook.com';
  s.$('registerEmail').listeners.blur();
  assert.equal(s.$('registerEmailSuggest').hidden, true, 'a correct address is never questioned');
});

test('after sign-up the card shows the inbox step with a link to the mail service', () => {
  const s = setup({ saved: [{ title: 'Dune' }, { title: 'Frieren' }] });
  s.context.showVerificationSent('riley@gmail.com');
  assert.equal(s.$('verifySentPanel').style.display, 'block');
  assert.equal(s.$('loginForm').style.display, 'none');
  assert.equal(s.$('registerForm').style.display, 'none');
  assert.equal(s.$('authTitle').textContent, 'Check your inbox');
  assert.equal(s.$('verifySentEmail').textContent, 'riley@gmail.com');
  assert.equal(s.$('verifySentInbox').hidden, false);
  assert.equal(s.$('verifySentInbox').textContent, 'Open Gmail');
  assert.match(s.$('verifySentInbox').href, /^https:\/\/mail\.google\.com\//);
  assert.match(s.$('verifySentNote').textContent, /48 hours/);
  assert.match(s.$('verifySentNote').textContent, /Your 2 saved titles will be in your library/);
  assert.equal(s.$('verifySentQuiz').hidden, false);
  assert.equal(s.$('loginUsername').value, 'riley@gmail.com', 'the log-in form is ready for later');

  s.context.showVerificationSent('riley@my-own-domain.example');
  assert.equal(s.$('verifySentInbox').hidden, true, 'no guess for mail services we do not know');
});

test('mail service links only match the services they name', () => {
  const s = setup();
  const name = email => { const link = s.context.inboxLinkFor(email); return link ? link.name : null; };
  assert.equal(name('a@gmail.com'), 'Gmail');
  assert.equal(name('a@googlemail.com'), 'Gmail');
  assert.equal(name('a@hotmail.co.uk'), 'Outlook');
  assert.equal(name('a@live.com'), 'Outlook');
  assert.equal(name('a@yahoo.fr'), 'Yahoo Mail');
  assert.equal(name('a@icloud.com'), 'iCloud Mail');
  assert.equal(name('a@proton.me'), 'Proton Mail');
  assert.equal(name('a@notgmail.com'), null);
  assert.equal(name('a@gmail.com.evil.example'), null);
  assert.equal(name(''), null);
  for (const email of ['a@gmail.com', 'a@outlook.com', 'a@yahoo.com', 'a@icloud.com', 'a@proton.me', 'a@aol.com']) {
    assert.match(s.context.inboxLinkFor(email).url, /^https:\/\//, email);
  }
});

test('the inbox step can send the email again, and hands the address to the log-in form', async () => {
  const s = setup();
  s.context.setupInboxPanel();
  s.context.showVerificationSent('riley@example.com');
  await s.$('verifySentResend').listeners.click();
  assert.equal(s.requests[0].url, '/auth/resend-verification?email=riley%40example.com');
  assert.equal(s.requests[0].options.method, 'POST');
  assert.match(s.$('verifySentStatus').textContent, /^Sent\./);
  assert.equal(s.$('verifySentResend').disabled, true, 'no second click straight away');

  s.$('loginUsername').value = '';
  s.$('verifySentLogin').listeners.click({ preventDefault() {} });
  assert.equal(s.$('loginForm').style.display, 'block');
  assert.equal(s.$('verifySentPanel').style.display, 'none');
  assert.equal(s.$('loginUsername').value, 'riley@example.com');
});

test('too many resends get a plain answer and the button back', async () => {
  const s = setup({ reply: { ok: false, status: 429, body: {} } });
  s.context.setupInboxPanel();
  s.context.showVerificationSent('riley@example.com');
  await s.$('verifySentResend').listeners.click();
  assert.match(s.$('verifySentStatus').textContent, /few tries/);
  assert.equal(s.$('verifySentResend').disabled, false);
});

test('confirming in another tab updates the waiting tab', () => {
  const s = setup();
  s.context.showVerificationSent('riley@example.com');
  s.windowListeners.storage({ key: 'omnitrackr_user', newValue: '{"id":5,"username":"riley"}' });
  assert.equal(s.$('authTitle').textContent, 'Your email is confirmed');
  assert.equal(s.$('verifySentInbox').hidden, false);
  assert.equal(s.$('verifySentInbox').textContent, 'Open my library');
  assert.equal(s.$('verifySentInbox').href, '/');
  assert.equal(s.$('verifySentResend').hidden, true);
});

test('a sign-in in another tab leaves the other forms alone', () => {
  const s = setup();
  s.context.showLoginForm(false);
  s.windowListeners.storage({ key: 'omnitrackr_user', newValue: '{"id":5,"username":"riley"}' });
  assert.equal(s.$('authTitle').textContent, 'Log in to OmniTrackr');
});

test('asking for a reset link ends on the inbox step, without a resend button', async () => {
  const s = setup();
  const forgotForm = s.form('forgotPasswordFormElement');
  s.context.setupAuthHandlers();
  s.context.setupInboxPanel();
  s.$('forgotPasswordEmail').value = 'riley@yahoo.com';
  await forgotForm.listeners.submit({ preventDefault() {}, target: forgotForm });
  assert.equal(s.requests[0].url, '/auth/request-password-reset?email=riley%40yahoo.com');
  assert.equal(s.$('verifySentPanel').style.display, 'block');
  assert.equal(s.$('verifySentBefore').textContent, 'If ');
  assert.equal(s.$('verifySentEmail').textContent, 'riley@yahoo.com');
  assert.match(s.$('verifySentNote').textContent, /one hour/);
  assert.equal(s.$('verifySentResend').hidden, true);
  assert.equal(s.$('verifySentQuiz').hidden, true);
  assert.equal(s.$('verifySentInbox').textContent, 'Open Yahoo Mail');

  s.$('verifySentRestart').listeners.click({ preventDefault() {} });
  assert.equal(s.$('forgotPasswordForm').style.display, 'block');
  assert.equal(s.$('verifySentPanel').style.display, 'none');
});

test('a new password needs one box, and saving it leads straight to the log-in form', async () => {
  const s = setup({ reply: { ok: true, body: { message: 'ok' } } });
  const resetForm = s.form('resetPasswordFormElement');
  resetForm.dataset.resetToken = 'tok';
  s.context.setupAuthHandlers();
  s.$('newPassword').value = 'a long new phrase';
  await resetForm.listeners.submit({ preventDefault() {}, target: resetForm });
  assert.equal(s.requests[0].url, '/auth/reset-password');
  assert.deepEqual(JSON.parse(s.requests[0].options.body), { token: 'tok', new_password: 'a long new phrase' });
  assert.equal(s.$('loginForm').style.display, 'block');
  assert.equal(s.$('authSuccess').textContent, 'Your new password is saved. Log in with it below.');
});

test('an expired reset link says where to get a new one', async () => {
  const s = setup({ reply: { ok: false, status: 400, body: { detail: 'Invalid or expired reset token' } } });
  const resetForm = s.form('resetPasswordFormElement');
  resetForm.dataset.resetToken = 'old';
  s.context.setupAuthHandlers();
  s.$('newPassword').value = 'a long new phrase';
  await resetForm.listeners.submit({ preventDefault() {}, target: resetForm });
  assert.match(s.$('authError').textContent, /expired or was already used/);
  assert.match(s.$('authError').textContent, /Forgot password\?/);
});

test('an expired confirmation link lands on the log-in form with the resend box open', async () => {
  const s = setup({ reply: { ok: false, status: 400, body: { detail: 'This verification link has expired or was already used.' } } });
  s.$('resendVerificationEmailField').hidden = true;
  await s.context.handleEmailVerification('old');
  assert.equal(s.$('loginForm').style.display, 'block');
  assert.equal(s.$('authStatusPanel').style.display, 'none');
  assert.equal(s.$('authError').textContent, 'This verification link has expired or was already used.');
  assert.equal(s.$('resendVerificationContainer').style.display, 'block');
  assert.equal(s.$('resendVerificationEmailField').hidden, false);
});

test('every form change hides the inbox step and the wait', () => {
  const s = setup();
  for (const show of ['showLoginForm', 'showRegisterForm', 'showForgotPasswordForm', 'showResetPasswordForm', 'showTwoFactorForm']) {
    s.context.showVerificationSent('riley@example.com');
    s.context.showAuthStatus('Confirming your email', 'This takes a second.');
    assert.equal(s.$('authStatusPanel').style.display, 'block');
    assert.equal(s.$('verifySentPanel').style.display, 'none');
    s.context[show](false);
    assert.equal(s.$('authStatusPanel').style.display, 'none', show);
    assert.equal(s.$('verifySentPanel').style.display, 'none', show);
  }
});
