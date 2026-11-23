// Supporter gifts: /supporters/gift, /gift/<code> and the giver's card page. Copy and share buttons,
// printing the card, "Lost the email?" and counting Ko-fi presses. Everything works without it except those.
(function () {
  'use strict';

  function beacon(url, body) {
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(url, new Blob([JSON.stringify(body)], { type: 'application/json' }));
    } catch (error) { /* counting is optional */ }
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let done = false;
    try { done = document.execCommand('copy'); } catch (error) { done = false; }
    area.remove();
    return done;
  }

  function resendMessage(status, data) {
    if (status === 429) return 'That was a lot of tries. Wait an hour and try again, or write to us from the Contact page.';
    if (data && typeof data.message === 'string') return data.message;
    if (data && typeof data.detail === 'string') return data.detail;
    return 'Could not send that. Please try again.';
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { resendMessage };
    return;
  }

  document.querySelectorAll('[data-gm-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      const status = button.parentElement && button.parentElement.querySelector('.gm-copy__status');
      let ok = false;
      try { ok = await copyText(button.getAttribute('data-gm-copy') || ''); } catch (error) { ok = false; }
      if (status) status.textContent = ok ? 'Copied' : 'Select it and copy it by hand';
      window.setTimeout(() => { if (status) status.textContent = ''; }, 2500);
    });
  });

  const share = document.querySelector('[data-gm-share]');
  const link = document.querySelector('[data-gm-copy^="https://"]');
  if (share && link && typeof navigator.share === 'function') {
    share.hidden = false;
    share.addEventListener('click', () => {
      navigator.share({ title: 'A gift for you on OmniTrackr', url: link.getAttribute('data-gm-copy') }).catch(() => {});
    });
  }

  const printIt = document.querySelector('[data-gm-printit]');
  if (printIt) printIt.addEventListener('click', () => window.print());

  document.querySelectorAll('[data-kofi]').forEach(button => {
    button.addEventListener('click', () => beacon('/api/support/event', { event: 'page_kofi', place: 'gift' }));
  });

  const form = document.querySelector('[data-gm-resend]');
  const formStatus = document.querySelector('[data-gm-resend-status]');
  if (form && formStatus) {
    let sending = false;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (sending) return;
      const input = form.querySelector('input[name="email"]');
      const email = input ? input.value.trim() : '';
      if (!email) {
        formStatus.textContent = 'Type the email you used on Ko-fi.';
        return;
      }
      sending = true;
      formStatus.textContent = 'Sending…';
      try {
        const response = await fetch('/api/gift/resend', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await response.json().catch(() => ({}));
        formStatus.textContent = resendMessage(response.status, data);
      } catch (error) {
        formStatus.textContent = 'Could not send that. Check your connection and try again.';
      } finally {
        sending = false;
      }
    });
  }

  const opened = document.querySelector('[data-gm-opened] h2[tabindex]');
  if (opened && /[?&]opened=1/.test(window.location.search)) {
    opened.focus();
    try { window.history.replaceState(null, '', window.location.pathname); } catch (error) { /* keep the address */ }
  }
})();
