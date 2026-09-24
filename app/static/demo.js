(() => {
  'use strict';

  const categories = {
    movie: {label: 'Movie', plural: 'movies', finished: 'Watched', artwork: 'AN IMAGINED FILM'},
    tv_show: {label: 'TV show', plural: 'TV shows', finished: 'Watched', artwork: 'AN IMAGINED SERIES'},
    anime: {label: 'Anime', plural: 'anime', finished: 'Watched', artwork: 'AN IMAGINED ANIME'},
    video_game: {label: 'Game', plural: 'games', finished: 'Played', artwork: 'AN IMAGINED GAME'},
    music: {label: 'Music', plural: 'music', finished: 'Listened', artwork: 'AN IMAGINED ALBUM'},
    book: {label: 'Book', plural: 'books', finished: 'Read', artwork: 'AN IMAGINED BOOK'},
  };
  const originals = [
    {id: 'lantern-atlas', title: 'The Lantern Atlas', cover: 'THE\nLANTERN\nATLAS', category: 'movie', description: 'A cartographer follows a trail of lights through a city that changes after sunset.', finished: true, rating: 9, note: 'A world I would happily get lost in again.'},
    {id: 'northbound', title: 'Northbound', cover: 'NORTH\nBOUND', category: 'tv_show', description: 'Night-shift strangers find their stories crossing on the last train home.', finished: false, rating: null, note: '', progress: {unit: 'episode', position: 4, season: 1, note: 'Next time: the station reunion.'}},
    {id: 'quiet-observatory', title: 'The Quiet Observatory', cover: 'THE QUIET\nOBSERVATORY', category: 'anime', description: 'Two apprentices map a sky where each constellation holds a forgotten story.', finished: true, rating: 8, note: 'Loved the quiet moments between adventures.', progress: {unit: 'episode', position: 12, season: 1, note: ''}},
    {id: 'garden-circuit', title: 'Garden Circuit', cover: 'GARDEN\nCIRCUIT', category: 'video_game', description: 'Bring a sleeping greenhouse to life, one small mechanical puzzle at a time.', finished: false, rating: null, note: ''},
    {id: 'after-rain', title: 'After the Rain', cover: 'AFTER\nTHE RAIN', category: 'music', description: 'Warm piano, soft percussion, and a little breathing room for a slow Sunday.', finished: true, rating: 8.5, note: 'The soundtrack for an unhurried morning.'},
    {id: 'letters-tomorrow', title: 'Letters from Tomorrow', cover: 'LETTERS FROM\nTOMORROW', category: 'book', description: 'A bookshop owner receives letters dated one day ahead and has to decide what to change.', finished: false, rating: null, note: '', progress: {unit: 'page', position: 84, season: null, note: 'Pick up at the second letter.'}},
  ];
  const catalog = [
    {id: 'last-lighthouse', title: 'The Last Lighthouse', cover: 'THE LAST\nLIGHTHOUSE', category: 'movie', description: 'An unlikely crew keeps a coastal light shining through one extraordinary winter.'},
    {id: 'midnight-diner', title: 'Midnight on Maple Street', cover: 'MIDNIGHT ON\nMAPLE STREET', category: 'tv_show', description: 'A neighborhood diner becomes the meeting place for a new story each night.'},
    {id: 'paper-moons', title: 'Paper Moons', cover: 'PAPER\nMOONS', category: 'anime', description: 'A young inventor builds tiny worlds from the sketches in an old notebook.'},
    {id: 'tideline', title: 'Tideline', cover: 'TIDE\nLINE', category: 'video_game', description: 'Explore a quiet island and piece together the paths left behind by the tide.'},
    {id: 'small-hours', title: 'The Small Hours', cover: 'THE\nSMALL HOURS', category: 'music', description: 'An imagined collection of gentle guitar melodies for the end of a long day.'},
    {id: 'borrowed-summer', title: 'A Borrowed Summer', cover: 'A BORROWED\nSUMMER', category: 'book', description: 'Two old friends trade houses for a season and find a new way to see home.'},
  ];
  const get = id => document.getElementById(id);
  if (!get('demoCards') || !get('demoEditForm')) return;
  const freshSamples = () => originals.map(item => ({...item, progress: item.progress ? {...item.progress} : null}));
  let items = freshSamples();
  let filter = 'all';
  let editingId = null;
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const announce = text => { get('demoStatus').textContent = text; };
  const focusCard = id => {
    const button = get(`demoEdit-${id}`);
    if (button) button.focus();
    else get('demoAdd').focus();
  };
  const hideEditor = () => { get('demoEditor').hidden = true; editingId = null; };
  const hideCatalog = () => {
    get('demoCatalog').hidden = true;
    get('demoAdd').setAttribute('aria-expanded', 'false');
  };
  const supportsProgress = item => ['tv_show', 'anime', 'book'].includes(item.category);
  const progressSummary = progress => {
    if (!progress) return 'No checkpoint yet';
    if (progress.unit === 'episode') {
      const season = progress.season === null ? '' : `season ${progress.season}, `;
      return `Last watched: ${season}episode ${progress.position}`;
    }
    return `Last read: ${progress.unit} ${progress.position}`;
  };

  function renderStats() {
    const finished = items.filter(item => item.finished).length;
    const rated = items.filter(item => item.rating !== null);
    const average = rated.length ? (rated.reduce((sum, item) => sum + item.rating, 0) / rated.length).toFixed(1) : '—';
    get('demoTotal').textContent = String(items.length);
    get('demoFinished').textContent = String(finished);
    get('demoNext').textContent = String(items.length - finished);
    const averageNode = get('demoAverage');
    averageNode.textContent = average;
    if (rated.length) averageNode.append(element('span', 'demo-stat-unit', ' / 10'));
  }

  function renderCards() {
    const cards = get('demoCards');
    cards.replaceChildren();
    items.forEach((item, index) => {
      if (filter !== 'all' && item.category !== filter) return;
      const category = categories[item.category];
      const card = element('article', 'demo-card');
      card.dataset.sampleId = item.id;
      const cover = element('div', `demo-cover demo-cover-${item.category}`);
      cover.setAttribute('aria-hidden', 'true');
      cover.append(element('span', '', String(index + 1).padStart(2, '0')), element('b', '', item.cover), element('i', '', category.artwork));
      const body = element('div', 'demo-card-body');
      body.append(element('span', 'demo-category', category.label), element('h3', '', item.title), element('p', 'demo-card-description', item.description));
      const facts = element('div', 'demo-card-facts');
      facts.append(element('span', item.finished ? 'demo-complete' : '', item.finished ? category.finished : 'Not finished'), element('span', 'demo-card-rating', item.rating === null ? 'Unrated' : `${item.rating} / 10`));
      body.append(facts, element('p', item.note ? 'demo-note' : 'demo-note demo-note-empty', item.note || 'No note yet. What would you remember?'));
      if (supportsProgress(item)) {
        const progress = element('div', 'demo-card-progress');
        progress.append(element('span', 'demo-progress-label', 'YOUR CHECKPOINT'), element('p', '', progressSummary(item.progress)));
        if (item.progress?.note) progress.append(element('p', 'demo-progress-reminder', item.progress.note));
        body.append(progress);
      }
      const edit = element('button', 'demo-card-edit', 'Edit sample →');
      edit.type = 'button';
      edit.id = `demoEdit-${item.id}`;
      edit.setAttribute('aria-label', `Edit sample: ${item.title}`);
      edit.setAttribute('aria-controls', 'demoEditor');
      edit.addEventListener('click', () => openEditor(item.id));
      card.append(cover, body, edit);
      cards.append(card);
    });
  }

  function renderFilters() {
    get('demoFilters').querySelectorAll('button').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.category === filter));
    });
  }

  function renderCatalog() {
    const list = get('demoCatalogItems');
    list.replaceChildren();
    catalog.forEach(sample => {
      const exists = items.some(item => item.id === sample.id);
      const row = element('article', 'demo-catalog-item');
      const copy = element('div');
      copy.append(element('span', 'demo-category', categories[sample.category].label), element('h4', '', sample.title));
      const add = element('button', 'demo-button demo-button-quiet', exists ? 'Added' : '+ Add');
      add.id = `demoCatalogAdd-${sample.id}`;
      add.type = 'button';
      add.disabled = exists;
      add.setAttribute('aria-label', exists ? `${sample.title} is in the sample library` : `Add sample: ${sample.title}`);
      add.addEventListener('click', () => addSample(sample.id));
      row.append(copy, add);
      list.append(row);
    });
  }

  function openEditor(id) {
    const item = items.find(entry => entry.id === id);
    if (!item) return;
    hideCatalog();
    editingId = id;
    get('demoEditorHeading').textContent = item.title;
    get('demoEditFinished').checked = item.finished;
    get('demoEditFinishedLabel').textContent = `${categories[item.category].finished} / finished`;
    get('demoEditRating').value = item.rating === null ? '' : String(item.rating);
    get('demoEditNote').value = item.note;
    populateProgress(item);
    get('demoEditError').hidden = true;
    get('demoEditor').hidden = false;
    get('demoEditFinished').focus();
  }

  function populateProgress(item) {
    get('demoProgressForm').hidden = !supportsProgress(item);
    const book = item.category === 'book';
    get('demoProgressUnitField').hidden = !book;
    get('demoProgressSeasonField').hidden = book;
    get('demoProgressUnit').value = book ? (item.progress?.unit || 'page') : 'episode';
    get('demoProgressPositionLabel').textContent = book ? `Last read ${item.progress?.unit || 'page'}` : 'Last watched episode';
    get('demoProgressPosition').value = item.progress ? String(item.progress.position) : '';
    get('demoProgressSeason').value = item.progress?.season === null || item.progress?.season === undefined ? '' : String(item.progress.season);
    get('demoProgressNote').value = item.progress?.note || '';
    get('demoProgressClear').disabled = !item.progress;
    get('demoProgressError').hidden = true;
  }

  get('demoProgressUnit').addEventListener('change', () => {
    const unit = get('demoProgressUnit').value;
    if (['page', 'chapter'].includes(unit)) get('demoProgressPositionLabel').textContent = `Last read ${unit}`;
  });

  get('demoProgressForm').addEventListener('submit', event => {
    event.preventDefault();
    const item = items.find(entry => entry.id === editingId);
    if (!item || !supportsProgress(item)) return;
    const book = item.category === 'book';
    const positionInput = get('demoProgressPosition');
    const seasonInput = get('demoProgressSeason');
    const rawPosition = positionInput.value.trim();
    const rawSeason = seasonInput.value.trim();
    const note = get('demoProgressNote').value.trim();
    const unit = book ? get('demoProgressUnit').value : 'episode';
    const invalid = (message, input) => {
      get('demoProgressError').textContent = message;
      get('demoProgressError').hidden = false;
      input.focus();
    };
    if (!/^\d+$/.test(rawPosition) || positionInput.validity?.badInput || Number(rawPosition) < 1 || Number(rawPosition) > 1000000) {
      invalid('Enter a whole episode, page, or chapter number from 1 to 1,000,000.', positionInput);
      return;
    }
    if (!book && (seasonInput.validity?.badInput || (rawSeason !== '' && (!/^\d+$/.test(rawSeason) || Number(rawSeason) > 10000)))) {
      invalid('Use a whole season number from 0 to 10,000, or leave it blank. Season 0 is for specials.', seasonInput);
      return;
    }
    if (book && !['page', 'chapter'].includes(unit)) {
      invalid('Choose pages or chapters for this book.', get('demoProgressUnit'));
      return;
    }
    if (note.length > 300) {
      invalid('Keep your checkpoint reminder to 300 characters or fewer.', get('demoProgressNote'));
      return;
    }
    item.progress = {unit, position: Number(rawPosition), season: book || rawSeason === '' ? null : Number(rawSeason), note};
    populateProgress(item);
    renderCards();
    announce(`Checkpoint updated for “${item.title}”. Completion, rating, and your other note are unchanged.`);
  });
  get('demoProgressClear').addEventListener('click', () => {
    const item = items.find(entry => entry.id === editingId);
    if (!item || !supportsProgress(item)) return;
    item.progress = null;
    populateProgress(item);
    renderCards();
    get('demoProgressPosition').focus();
    announce(`Checkpoint cleared for “${item.title}”. Completion, rating, and your other note are unchanged.`);
  });

  function addSample(id) {
    const sample = catalog.find(entry => entry.id === id);
    if (!sample || items.some(item => item.id === id)) return;
    items.push({...sample, finished: false, rating: null, note: ''});
    // Show the new title even when a different category was selected.
    filter = sample.category;
    hideEditor();
    hideCatalog();
    renderFilters();
    renderStats();
    renderCards();
    announce(`Added “${sample.title}” to your sample library. Try Edit sample to give it a rating.`);
    focusCard(id);
  }

  get('demoEditForm').addEventListener('submit', event => {
    event.preventDefault();
    const item = items.find(entry => entry.id === editingId);
    if (!item) return;
    const ratingInput = get('demoEditRating');
    const raw = ratingInput.value.trim();
    const rating = raw === '' ? null : Number(raw);
    const error = get('demoEditError');
    if (ratingInput.validity?.badInput || (rating !== null && (!Number.isFinite(rating) || rating < 0 || rating > 10 || Math.abs(rating * 10 - Math.round(rating * 10)) > 1e-8))) {
      error.textContent = 'Use a rating from 0 to 10 with up to one decimal, or leave it blank.';
      error.hidden = false;
      ratingInput.focus();
      return;
    }
    const note = get('demoEditNote').value;
    if (note.length > 500) {
      error.textContent = 'Keep your practice note to 500 characters or fewer.';
      error.hidden = false;
      get('demoEditNote').focus();
      return;
    }
    const id = item.id;
    item.finished = get('demoEditFinished').checked;
    item.rating = rating;
    item.note = note.trim();
    hideEditor();
    renderStats();
    renderCards();
    announce(`Updated “${item.title}”. These changes are only in this demo.`);
    focusCard(id);
  });
  get('demoEditCancel').addEventListener('click', () => {
    const id = editingId;
    hideEditor();
    focusCard(id);
  });
  get('demoAdd').addEventListener('click', () => {
    if (!get('demoCatalog').hidden) { hideCatalog(); return; }
    hideEditor();
    renderCatalog();
    get('demoCatalog').hidden = false;
    get('demoAdd').setAttribute('aria-expanded', 'true');
    get('demoCatalogHeading').focus();
  });
  get('demoCatalogClose').addEventListener('click', () => {
    hideCatalog();
    get('demoAdd').focus();
  });
  get('demoFilters').querySelectorAll('button').forEach(button => {
    button.addEventListener('click', () => {
      const selected = button.dataset.category;
      if (selected !== 'all' && !Object.hasOwn(categories, selected)) return;
      filter = selected;
      hideEditor();
      hideCatalog();
      renderFilters();
      renderCards();
      const visible = items.filter(item => filter === 'all' || item.category === filter).length;
      const group = filter === 'all' ? 'All media' : categories[filter].plural[0].toUpperCase() + categories[filter].plural.slice(1);
      announce(`${group}: ${visible} sample ${visible === 1 ? 'title' : 'titles'}. Statistics still cover the whole sample library.`);
    });
  });
  get('demoReset').addEventListener('click', () => {
    items = freshSamples();
    filter = 'all';
    hideEditor();
    hideCatalog();
    renderFilters();
    renderStats();
    renderCards();
    announce('Demo reset. Your original six sample titles are ready to try again.');
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!get('demoEditor').hidden) {
      const id = editingId;
      hideEditor();
      focusCard(id);
    } else if (!get('demoCatalog').hidden) {
      hideCatalog();
      get('demoAdd').focus();
    }
  });
  renderCards();
  renderStats();
  get('demoToolbar').hidden = false;
  get('demoFilters').hidden = false;
})();
