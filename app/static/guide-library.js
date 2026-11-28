// The /guides library: filter every guide by format, or find one by name, without a reload.
// The server already renders the full list (and a filtered one for ?format=), so the page
// works without this file; it only makes the chips and the search box answer instantly.
(function () {
  'use strict';
  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var tools = document.querySelector('[data-gl-tools]');
    if (!tools) return;
    var rows = Array.prototype.slice.call(document.querySelectorAll('.gl-row'));
    var shelves = Array.prototype.slice.call(document.querySelectorAll('[data-gl-shelf]'));
    var chips = Array.prototype.slice.call(tools.querySelectorAll('.gl-chip'));
    var count = tools.querySelector('[data-gl-count]');
    var find = tools.querySelector('[data-gl-find]');
    var input = tools.querySelector('[data-gl-search]');
    var empty = document.querySelector('[data-gl-empty]');
    var heading = document.getElementById('guide-library-heading');
    var total = rows.length;
    var current = '';

    chips.forEach(function (chip) {
      if (chip.getAttribute('aria-current') === 'true') current = chip.getAttribute('data-format') || '';
    });
    if (find) find.hidden = false;

    function chipFor(kind) {
      for (var i = 0; i < chips.length; i++) {
        if ((chips[i].getAttribute('data-format') || '') === kind) return chips[i];
      }
      return null;
    }

    // On phones the chips are one sideways row; keep the chosen one in view.
    function revealChip() {
      var chip = chipFor(current);
      var row = chip && chip.parentNode;
      if (!row || row.scrollWidth <= row.clientWidth) return;
      row.scrollLeft = Math.max(0, chip.offsetLeft - row.offsetLeft - 16);
    }

    function matches(row, query) {
      if (current && (' ' + row.getAttribute('data-formats') + ' ').indexOf(' ' + current + ' ') === -1) return false;
      return !query || (row.getAttribute('data-name') || '').indexOf(query) !== -1;
    }

    function apply() {
      var query = input ? input.value.trim().toLowerCase() : '';
      var shown = 0;
      rows.forEach(function (row) {
        var ok = matches(row, query);
        row.hidden = !ok;
        if (ok) shown += 1;
      });
      shelves.forEach(function (shelf) {
        var visible = shelf.querySelectorAll('.gl-row:not([hidden])').length;
        shelf.hidden = visible === 0;
        var badge = shelf.querySelector('[data-gl-shelf-count]');
        if (badge) badge.textContent = String(visible);
      });
      if (empty) empty.hidden = shown > 0;
      var chip = chipFor(current);
      var plural = chip ? chip.getAttribute('data-plural') : '';
      var text;
      if (query) {
        text = (shown === 1 ? 'One guide' : shown + ' guides') + (current ? ' covering ' + plural : '')
          + (shown === 1 ? ' matches.' : ' match.');
      } else if (current) {
        text = 'Showing ' + shown + ' of ' + total + ' guides that cover ' + plural + '.';
      } else {
        text = 'Showing all ' + total + ' guides.';
      }
      if (count) count.textContent = text;
    }

    function choose(kind, scroll) {
      current = kind || '';
      chips.forEach(function (chip) {
        if ((chip.getAttribute('data-format') || '') === current) chip.setAttribute('aria-current', 'true');
        else chip.removeAttribute('aria-current');
      });
      var chip = chipFor(current);
      var slug = chip ? chip.getAttribute('data-slug') : '';
      try {
        history.replaceState(null, '', location.pathname + (slug ? '?format=' + encodeURIComponent(slug) : '') + '#guide-library-heading');
      } catch (e) { /* the filter still works without the address change */ }
      apply();
      revealChip();
      if (scroll && heading) heading.scrollIntoView({ block: 'start' });
    }

    chips.forEach(function (chip) {
      chip.addEventListener('click', function (event) {
        event.preventDefault();
        choose(chip.getAttribute('data-format'), false);
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.gl-desk__all[data-format]'), function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        if (input) input.value = '';
        choose(link.getAttribute('data-format'), true);
      });
    });
    if (input) input.addEventListener('input', apply);
    revealChip();
  });
})();
