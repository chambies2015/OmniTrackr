// Binge calculator (/binge-calculator): totals and a finish date, worked out in the browser.
// Title lookups use the public title search and a cache-only length endpoint.
(function () {
  const tool = document.getElementById('bingeTool');
  if (!tool) return;
  const form = tool.querySelector('[data-binge-form]');
  const screenFields = tool.querySelector('[data-binge-screen]');
  const bookFields = tool.querySelector('[data-binge-book]');
  const skip = form.elements.skip.closest('label');
  const out = {
    name: tool.querySelector('[data-binge-name]'),
    hours: tool.querySelector('[data-binge-hours]'),
    finish: tool.querySelector('[data-binge-finish]'),
    detail: tool.querySelector('[data-binge-detail]'),
  };
  const searchInput = document.getElementById('bcSearch');
  const results = tool.querySelector('[data-binge-results]');
  const SKIP_MINUTES = 2;
  let name = 'Breaking Bad';

  function todayIso() {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function number(field) {
    const value = Number(form.elements[field].value);
    return Number.isFinite(value) && value > 0 ? value : 0;
  }

  function formatHours(hours) {
    return hours < 10 ? hours.toFixed(1).replace(/\.0$/, '') : Math.round(hours).toLocaleString();
  }

  function finishDate(start, viewingDays, daysPerWeek) {
    // Viewing days fall on the chosen weekdays: every day, Mon to Fri, Sat and Sun, or Mon, Wed and Fri.
    const allowed = {7: [0, 1, 2, 3, 4, 5, 6], 5: [1, 2, 3, 4, 5], 2: [0, 6], 3: [1, 3, 5]}[daysPerWeek] || [0, 1, 2, 3, 4, 5, 6];
    const date = new Date(`${start}T12:00:00`);
    let counted = 0;
    for (let guard = 0; guard < 40000; guard += 1) {
      if (allowed.includes(date.getDay())) {
        counted += 1;
        if (counted >= viewingDays) return date;
      }
      date.setDate(date.getDate() + 1);
    }
    return null;
  }

  function mode() {
    return form.elements.kind.value === 'book' ? 'book' : 'screen';
  }

  function update() {
    const isBook = mode() === 'book';
    screenFields.hidden = isBook;
    bookFields.hidden = !isBook;
    skip.hidden = isBook;
    let minutes = 0;
    let detail = '';
    if (isBook) {
      const pages = number('pages');
      const pace = number('pace');
      minutes = pace ? (pages / pace) * 60 : 0;
      detail = `${pages.toLocaleString()} pages at ${pace} pages an hour.`;
    } else {
      const episodes = number('episodes');
      const perEpisode = Math.max(1, number('minutes') - (form.elements.skip.checked ? SKIP_MINUTES : 0));
      minutes = episodes * perEpisode;
      detail = `${episodes.toLocaleString()} episodes at ${perEpisode} minutes each.`;
    }
    const daily = number('hours');
    out.name.textContent = name || (isBook ? 'Your book' : 'Your show');
    out.detail.textContent = detail;
    if (!minutes || !daily) {
      out.hours.textContent = '0';
      out.finish.textContent = 'Fill in the length and how many hours a day you have.';
      return;
    }
    const totalHours = minutes / 60;
    const days = Math.ceil(minutes / (daily * 60));
    const week = Number(form.elements.week.value) || 7;
    const start = form.elements.start.value || todayIso();
    const end = finishDate(start, days, week);
    const dayWord = days === 1 ? 'day' : 'days';
    const pace = `${formatHours(daily)} hour${daily === 1 ? '' : 's'} a day`;
    const when = end ? end.toLocaleDateString(undefined, {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'}) : '';
    out.hours.textContent = formatHours(totalHours);
    out.finish.textContent = week === 7
      ? `At ${pace}, that's ${days.toLocaleString()} ${dayWord}. Start ${start === todayIso() ? 'today' : 'then'} and you'd finish on ${when}.`
      : `At ${pace} on ${days.toLocaleString()} ${isBook ? 'reading' : 'viewing'} ${dayWord}, you'd finish on ${when}.`;
  }

  function load(values) {
    if (values.kind === 'book') {
      form.elements.kind.value = 'book';
      if (values.pages) form.elements.pages.value = values.pages;
    } else {
      form.elements.kind.value = 'screen';
      if (values.episodes) form.elements.episodes.value = values.episodes;
      if (values.minutes) form.elements.minutes.value = values.minutes;
    }
    name = values.name || '';
    update();
  }

  form.addEventListener('input', event => {
    if (['episodes', 'minutes', 'pages'].includes(event.target.name)) name = '';
    update();
  });
  form.addEventListener('submit', event => event.preventDefault());

  document.querySelectorAll('[data-binge-example]').forEach(button => {
    button.addEventListener('click', () => {
      load({kind: button.dataset.kind, name: button.dataset.name, episodes: button.dataset.episodes,
        minutes: button.dataset.minutes, pages: button.dataset.pages});
      tool.scrollIntoView({behavior: 'smooth', block: 'start'});
    });
  });

  let searchTimer = null;
  let searchToken = 0;
  function closeResults() {
    results.hidden = true;
    results.textContent = '';
  }

  async function pick(entry) {
    closeResults();
    searchInput.value = entry.title;
    const params = new URLSearchParams({kind: entry.kind, title: entry.title});
    if (entry.year) params.set('year', entry.year);
    out.finish.textContent = `Looking up ${entry.title}…`;
    try {
      const response = await fetch(`/api/binge-calculator/length?${params}`);
      const data = response.ok ? await response.json() : {};
      const label = entry.year ? `${entry.title} (${entry.year})` : entry.title;
      load({kind: entry.kind === 'book' ? 'book' : 'screen', name: label, episodes: data.episodes,
        minutes: data.minutes, pages: data.pages});
      const missing = entry.kind === 'book' ? !data.pages : !(data.episodes && data.minutes);
      if (missing) out.detail.textContent += ' We don\'t have every number for this one yet, so check the boxes above.';
    } catch (error) {
      update();
    }
  }

  async function search(text) {
    const token = ++searchToken;
    if (text.trim().length < 2) return closeResults();
    try {
      const response = await fetch(`/api/titles/search?q=${encodeURIComponent(text)}`);
      const data = response.ok ? await response.json() : {results: []};
      if (token !== searchToken) return;
      const found = (data.results || []).filter(entry => ['tv', 'anime', 'book'].includes(entry.kind)).slice(0, 6);
      results.textContent = '';
      if (!found.length) {
        const empty = document.createElement('p');
        empty.className = 'muted';
        empty.textContent = 'No shows or books with that name yet. Type the numbers in instead.';
        results.append(empty);
      }
      found.forEach(entry => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'bc-search__result';
        const title = document.createElement('strong');
        title.textContent = entry.title;
        const meta = document.createElement('span');
        meta.textContent = [entry.label, entry.year].filter(Boolean).join(' · ');
        button.append(title, meta);
        button.addEventListener('click', () => pick(entry));
        results.append(button);
      });
      results.hidden = false;
    } catch (error) {
      closeResults();
    }
  }

  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => search(searchInput.value), 250);
  });
  searchInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeResults();
  });

  form.elements.start.value = todayIso();
  update();
}());
