/*
 * Small progressive-enhancement layer for the anonymous homepage.
 *
 * The private dashboard script is intentionally not loaded on public responses,
 * so this file owns only landing-page interactions. Keeping it separate reduces
 * transfer size and prevents anonymous visitors from receiving dashboard code.
 */
(function () {
  // Sign-up and log-in buttons open the form card in a pop-up instead of scrolling
  // past the whole page to it. The card is moved (not copied) so auth.js keeps
  // working on the same elements, and goes back to its section when the pop-up closes.
  var authHome = null;

  function authDialog() {
    var dialog = document.getElementById('authDialog');
    return dialog && typeof dialog.showModal === 'function' ? dialog : null;
  }

  function openAuthDialog() {
    var dialog = authDialog();
    var slot = dialog && dialog.querySelector('[data-auth-dialog-slot]');
    var card = document.querySelector('.lp-auth__card');
    if (!dialog || !slot || !card) return false;
    if (dialog.open) {
      focusAuthCard(card);
      return true;
    }
    if (!authHome) authHome = {parent: card.parentNode, next: card.nextSibling};
    slot.appendChild(card);
    try {
      dialog.showModal();
    } catch (error) {
      returnAuthCard();
      return false;
    }
    document.body.style.overflow = 'hidden';
    focusAuthCard(card);
    return true;
  }

  // Where the cursor starts when the pop-up opens or changes form. With a mouse and
  // keyboard: the first box, ready to type. On a touch screen: the title, so the
  // keyboard doesn't cover the Google button before anyone has chosen how to sign up.
  function focusAuthCard(card) {
    if (typeof card.querySelectorAll !== 'function') return;
    var finePointer = typeof window.matchMedia === 'function' && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    var target = null;
    if (finePointer) {
      var boxes = card.querySelectorAll('input:not([type="checkbox"])');
      for (var i = 0; i < boxes.length && !target; i += 1) {
        if (boxes[i].offsetParent !== null && !boxes[i].value) target = boxes[i];
      }
    }
    if (!target) target = card.querySelector('#authTitle');
    if (target && typeof target.focus === 'function') {
      try { target.focus({preventScroll: true}); } catch (error) { target.focus(); }
    }
  }

  function returnAuthCard() {
    var card = document.querySelector('.lp-auth__card');
    if (authHome && card && card.parentNode !== authHome.parent) authHome.parent.insertBefore(card, authHome.next);
    document.body.style.overflow = '';
  }

  function closeAuthDialog() {
    var dialog = authDialog();
    if (dialog && dialog.open) dialog.close();
  }

  var dialogElement = authDialog();
  if (dialogElement) {
    dialogElement.addEventListener('close', returnAuthCard);
    // A click on the dimmed backdrop lands on the dialog itself.
    dialogElement.addEventListener('click', function (event) {
      if (event.target === dialogElement) closeAuthDialog();
    });
  }
  window.OmniAuthDialog = {open: openAuthDialog, close: closeAuthDialog};

  function report(event) {
    if (typeof window.reportFunnelEvent === 'function') window.reportFunnelEvent(event);
  }

  function showForm(action) {
    if (action === 'show-register-form' && typeof window.showRegisterForm === 'function') {
      window.showRegisterForm();
    }
    if (action === 'show-login-form' && typeof window.showLoginForm === 'function') {
      window.showLoginForm();
    }
  }

  function openPreview(source, alt) {
    const modal = document.getElementById('screenshotModal');
    const image = document.getElementById('screenshotModalImage');
    const caption = document.getElementById('screenshotModalCaption');
    if (!modal || !image || !caption || !source) return;

    image.src = source;
    image.alt = alt || 'OmniTrackr dashboard preview';
    caption.textContent = alt || 'OmniTrackr dashboard preview';
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function closePreview() {
    const modal = document.getElementById('screenshotModal');
    if (!modal) return;
    modal.classList.remove('show');
    document.body.style.overflow = '';
  }

  document.addEventListener('click', function (event) {
    const action = event.target.closest('[data-action]');
    if (action) {
      const actionName = action.dataset.action;
      if (actionName === 'show-register-form' || actionName === 'show-login-form') {
        event.preventDefault();
        if (action.hasAttribute && action.hasAttribute('data-hero-signup')) report('hero_signup_clicked');
        if (action.hasAttribute && action.hasAttribute('data-home-cta')) report('home_cta_clicked');
        showForm(actionName);
        return;
      }
      if (actionName === 'close-auth-dialog') {
        event.preventDefault();
        closeAuthDialog();
        return;
      }
      if (actionName === 'close-screenshot-modal') {
        event.preventDefault();
        closePreview();
        return;
      }
    }

    if (event.target.closest('a[data-hero-signup]')) report('hero_signup_clicked');
    if (event.target.closest('a[data-home-cta]')) report('home_cta_clicked');
    if (event.target.closest('[data-home-tool]')) report('home_tool_opened');

    // "Sign up and import": remember the import intent the way /?start=import does,
    // then open the sign-up pop-up here instead of reloading the page.
    var importLink = event.target.closest('a[data-home-import]');
    if (importLink) {
      report('home_import_clicked');
      try {
        sessionStorage.setItem('omnitrackr_demo_start', JSON.stringify({source: 'import', created_at: Date.now()}));
      } catch (error) {
        return; // No storage: follow the link, which sets the intent on load.
      }
      if (typeof window.showRegisterForm === 'function') {
        event.preventDefault();
        window.showRegisterForm();
      }
      return;
    }

    // Show/Hide password buttons are handled by auth.js, which every sign-in form loads.
    if (event.target.closest('[data-password-toggle]')) return;

    const preview = event.target.closest('[data-screenshot-src]');
    if (preview) {
      event.preventDefault();
      openPreview(preview.dataset.screenshotSrc, preview.dataset.screenshotAlt);
      return;
    }

    const faqQuestion = event.target.closest('.faq-question');
    if (faqQuestion) {
      const item = faqQuestion.closest('.faq-item');
      if (item) {
        const expanded = item.classList.toggle('active');
        faqQuestion.setAttribute('aria-expanded', String(expanded));
      }
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closePreview();
  });
  // Look inside: tabs over real screens. Arrow keys move between tabs (WAI-ARIA tabs pattern).
  var canQuery = typeof document.querySelector === 'function';
  var tour = canQuery ? document.querySelector('[data-tour]') : null;
  if (tour) {
    var tabs = Array.prototype.slice.call(tour.querySelectorAll('[data-tour-tab]'));
    var tourReported = false;
    function selectTab(tab, focus) {
      tabs.forEach(function (other) {
        var selected = other === tab;
        other.setAttribute('aria-selected', String(selected));
        other.tabIndex = selected ? 0 : -1;
        var panel = document.getElementById(other.getAttribute('aria-controls'));
        if (!panel) return;
        panel.hidden = !selected;
        if (selected) {
          panel.classList.remove('is-entering');
          void panel.offsetWidth; // restart the fade
          panel.classList.add('is-entering');
        }
      });
      if (focus) tab.focus();
      if (typeof tab.scrollIntoView === 'function' && tab.parentNode.scrollWidth > tab.parentNode.clientWidth) {
        tab.scrollIntoView({block: 'nearest', inline: 'center'});
      }
      if (!tourReported) {
        tourReported = true;
        report('home_tour_opened');
      }
    }
    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () { selectTab(tab, false); });
      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length];
        if (event.key === 'ArrowLeft') next = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === 'Home') next = tabs[0];
        if (event.key === 'End') next = tabs[tabs.length - 1];
        if (next) {
          event.preventDefault();
          selectTab(next, true);
        }
      });
    });
  }

  // Binge calculator demo: series + hours a day -> days and a finish date, worked out here.
  var binge = canQuery ? document.querySelector('[data-binge-demo]') : null;
  if (binge) {
    var select = binge.querySelector('select');
    var paces = Array.prototype.slice.call(binge.querySelectorAll('[data-hours]'));
    var bingeReported = false;
    function hoursText(minutes) {
      var whole = Math.round(minutes);
      var hours = Math.floor(whole / 60);
      var mins = whole % 60;
      return hours.toLocaleString('en-US') + ' hours' + (mins && hours < 100 ? ' ' + mins + ' min' : '');
    }
    function updateBinge(fromVisitor) {
      var option = select && select.options[select.selectedIndex];
      if (!option) return;
      var pace = paces.filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; })[0];
      var hoursPerDay = pace ? Number(pace.getAttribute('data-hours')) : 2;
      var minutes = Number(option.getAttribute('data-minutes'));
      var episodes = Number(option.getAttribute('data-episodes'));
      var days = Math.ceil(minutes / (hoursPerDay * 60));
      var finish = new Date();
      finish.setDate(finish.getDate() + days - 1);
      binge.querySelector('[data-binge-days]').textContent = days.toLocaleString('en-US');
      binge.querySelector('[data-binge-days-word]').textContent = days === 1 ? 'day' : 'days';
      binge.querySelector('[data-binge-detail]').textContent = episodes.toLocaleString('en-US') + ' episodes, about ' + hoursText(minutes) + ' in all.';
      var finishLine = binge.querySelector('[data-binge-finish]');
      finishLine.textContent = '';
      finishLine.appendChild(document.createTextNode('Start today and you finish on '));
      var when = document.createElement('strong');
      when.textContent = finish.toLocaleDateString('en-US', days > 300 ? {month: 'long', day: 'numeric', year: 'numeric'} : {weekday: 'long', month: 'long', day: 'numeric'});
      finishLine.appendChild(when);
      finishLine.appendChild(document.createTextNode('.'));
      finishLine.hidden = false;
      var link = binge.querySelector('[data-binge-link]');
      // Only a guide slug goes into the link (the options are written by the server).
      if (link && /^[a-z0-9-]{1,80}$/.test(option.value)) link.setAttribute('href', '/binge-calculator/' + encodeURIComponent(option.value));
      if (fromVisitor && !bingeReported) {
        bingeReported = true;
        report('home_binge_demo_used');
      }
    }
    if (select) select.addEventListener('change', function () { updateBinge(true); });
    paces.forEach(function (button) {
      button.addEventListener('click', function () {
        paces.forEach(function (other) { other.setAttribute('aria-pressed', String(other === button)); });
        updateBinge(true);
      });
    });
    updateBinge(false);
  }
})();
