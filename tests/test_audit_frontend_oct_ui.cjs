const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = require('./helpers/dashboard_source.cjs');
const auth = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };
function part(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  assert.ok(a >= 0 && b > a, start); return source.slice(a, b);
}

for (const [name, prefix, idKey, category, nullable] of [
  ['Movie', 'movie', 'movieId', 'movies', []],
  ['TV', 'tv', 'tvId', 'tv-shows', ['seasons', 'episodes']],
  ['Anime', 'anime', 'animeId', 'anime', ['seasons', 'episodes']],
  ['VideoGame', 'video-game', 'gameId', 'video-games', ['release_date', 'genres']],
  ['Music', 'music', 'musicId', 'music', ['genre']],
  ['Book', 'book', 'bookId', 'books', ['genre']],
]) {
  for (const rating of ['', '0']) test(name + ' edit sends cleared nullable fields and preserves rating ' + (rating || 'empty'), async () => {
    let packet;
    const context = vm.createContext({window: {}, editingRowId: 7, API_BASE: '',
      document: {getElementById: id => ({value: id.endsWith('-rating') ? rating : id.endsWith('-title') ? 'Title' : '', checked: false})},
      authenticatedFetch: async (url, options) => { packet = {url, data: JSON.parse(options.body)}; return {ok: false}; },
    });
    vm.runInContext(part('window.save' + name + 'Edit =', 'window.cancel' + name + 'Edit ='), context);
    await context.window['save' + name + 'Edit']({dataset: {[idKey]: '7'}});
    assert.equal(packet.url, '/' + category + '/7');
    assert.equal(packet.data.rating, rating === '' ? null : 0);
    nullable.forEach(key => assert.equal(packet.data[key], null, key));
  });
}

function customHarness() {
  const nodes = new Map(), children = [], alerts = [], uploads = [];
  const submit = {disabled: false, textContent: 'Add Shelf', onclick: null, parentElement: {appendChild(node) {children.push(node);}}};
  const form = {dataset: {}, valid: true, reportValidity() {return this.valid;},
    querySelector(selector) {return selector.includes('submit') ? submit : children.find(node => !node.removed && node.dataset.customTabCancel);}};
  const tab = {id: 7, name: 'Shelf', allow_uploads: true, fields: [
    {key: 'author', field_type: 'text'}, {key: 'done', field_type: 'boolean'},
  ]};
  for (const suffix of ['Title', 'Fieldauthor', 'Fielddone', 'PosterUrl', 'PosterFile', 'FormContent']) {
    nodes.set('customTab7' + suffix, {value: '', checked: false, type: suffix === 'Fielddone' ? 'checkbox' : 'text', files: [],
      closest: () => form, scrollIntoView() {}});
  }
  nodes.set('addCustomTab7Form', form);
  let response = async () => ({ok: true, json: async () => ({title: 'Sample', field_values: {}})});
  const context = vm.createContext({window: {}, customTabs: [tab], API_BASE: '', console, alert: value => alerts.push(value),
    document: {getElementById: id => nodes.get(id), createElement: () => ({dataset: {}, remove() {this.removed = true;}})},
    hasStoredAuth: () => true, authFetchOptions: options => options || {}, fetch: (...args) => response(...args),
    isElementShown: () => true, toggleCollapsible() {}, loadCustomTabItems: async () => {},
    uploadCustomTabPoster: async (...args) => {uploads.push(args); return true;},
  });
  vm.runInContext(part('function resetCustomTabItemForm(', 'function showCustomTabManager('), context);
  return {context, tab, nodes, form, submit, children, alerts, uploads, setFetch: fn => {response = fn;}};
}

test('switching custom item editors clears absent fields, checkboxes and artwork, with one native submit path', async () => {
  const h = customHarness();
  const items = [{title: 'A', field_values: {author: 'A author', done: true}, poster_url: 'https://example.com/a.jpg'},
    {title: 'B', field_values: {}, poster_url: null}];
  h.setFetch(async () => ({ok: true, json: async () => items.shift()}));
  await h.context.editCustomTabItem(7, 1);
  await h.context.editCustomTabItem(7, 2);
  assert.equal(h.nodes.get('customTab7Title').value, 'B');
  assert.equal(h.nodes.get('customTab7Fieldauthor').value, '');
  assert.equal(h.nodes.get('customTab7Fielddone').checked, false);
  assert.equal(h.nodes.get('customTab7PosterUrl').value, '');
  assert.equal(h.submit.onclick, null, 'browser validation remains on the form submit path');
  assert.equal(h.children.filter(node => !node.removed).length, 1);
  h.children.find(node => !node.removed).onclick();
  assert.equal(h.form.dataset.editingItemId, undefined);
  assert.equal(h.submit.textContent, 'Add Shelf');
});

test('a late custom edit response cannot replace the more recently selected item', async () => {
  const h = customHarness(), first = deferred();
  h.setFetch(async url => url.endsWith('/1') ? first.promise : {ok: true, json: async () => ({title: 'B', field_values: {}})});
  const older = h.context.editCustomTabItem(7, 1);
  await h.context.editCustomTabItem(7, 2);
  first.resolve({ok: true, json: async () => ({title: 'A', field_values: {author: 'Old'}})});
  await older;
  assert.equal(h.nodes.get('customTab7Title').value, 'B');
  assert.equal(h.form.dataset.editingItemId, '2');
});

test('custom updates honor validation, capture the selected file, and block repeat saves', async () => {
  const h = customHarness(); await h.context.editCustomTabItem(7, 2);
  const file = {name: 'art.jpg', size: 20}; h.nodes.get('customTab7PosterFile').files = [file];
  const pending = deferred(); let calls = 0;
  h.setFetch(async () => {calls++; return pending.promise;});
  h.form.valid = false; await h.context.handleUpdateCustomTabItem(h.tab, 2); assert.equal(calls, 0);
  h.form.valid = true;
  const saving = h.context.handleUpdateCustomTabItem(h.tab, 2);
  await h.context.handleUpdateCustomTabItem(h.tab, 2); assert.equal(calls, 1);
  pending.resolve({ok: true}); await saving;
  assert.equal(h.uploads.length, 1); assert.equal(h.uploads[0][2], file);
  assert.equal(h.form.dataset.editingItemId, undefined); assert.equal(h.submit.disabled, false);
});

test('failed custom save or artwork upload retains the item draft and Update label', async () => {
  for (const failedUpload of [false, true]) {
    const h = customHarness(); await h.context.editCustomTabItem(7, 2);
    const file = {name: 'art.jpg'}; h.nodes.get('customTab7PosterFile').files = [file];
    h.context.uploadCustomTabPoster = async () => false;
    h.setFetch(async () => ({ok: failedUpload, json: async () => ({detail: 'Cannot save'})}));
    await h.context.handleUpdateCustomTabItem(h.tab, 2);
    assert.equal(h.nodes.get('customTab7Title').value, 'Sample');
    assert.equal(h.nodes.get('customTab7PosterFile').files[0], file);
    assert.equal(h.form.dataset.editingItemId, '2'); assert.equal(h.submit.textContent, 'Update Shelf');
    assert.equal(h.submit.disabled, false);
  }
});

test('custom metadata lookup preserves a manually chosen artwork URL', async () => {
  let saved;
  const context = vm.createContext({API_BASE: '', AbortController, setTimeout: () => 1, clearTimeout() {}, console,
    fetch: async () => ({ok: true, json: async () => ({Response: 'True', Poster: 'https://provider.example/a.jpg', Title: 'Title'})}),
    createCustomTabItemAfterMetadata: async (...args) => {saved = args;},
  });
  vm.runInContext(part('async function fetchMetadataForCustomTab(', 'async function createCustomTabItemAfterMetadata('), context);
  await context.fetchMetadataForCustomTab({source_type: 'omdb'}, 'Title', {}, 'https://member.example/chosen.jpg');
  assert.equal(saved[3], 'https://member.example/chosen.jpg');
});

function friendHarness() {
  const nodes = new Map(), alerts = [], requests = [];
  const get = id => {if (!nodes.has(id)) nodes.set(id, {innerHTML: '', textContent: '', value: '', style: {}, classList: {remove() {}, add() {}}}); return nodes.get(id);};
  let fetchImpl = async url => ({ok: true, json: async () => url === '/friends' ? [] : {username: 'Current'}});
  const context = vm.createContext({API_BASE: '', console, alert: value => alerts.push(value),
    document: {getElementById: get}, escapeHtml: String,
    authenticatedFetch: (...args) => {requests.push(args[0]); return fetchImpl(...args);},
  });
  context.window = context;
  vm.runInContext(part('let currentFriendId =', '// Close friend profile modal when clicking outside'), context);
  return {context, nodes, get, alerts, requests, setFetch: fn => {fetchImpl = fn;}};
}

test('delayed previous friend profile cannot replace the current profile or close its dialog', async () => {
  const h = friendHarness(), older = deferred();
  h.setFetch(async url => url === '/friends' ? older.promise : {ok: true, json: async () => ({username: 'Wrong'})});
  const opening = h.context.openFriendProfile(1);
  h.context.loadFriendProfile = async () => {h.get('friendProfileUsername').textContent = 'Current';};
  await h.context.openFriendProfile(2);
  older.resolve({ok: false}); await opening;
  assert.equal(h.get('friendProfileUsername').textContent, 'Current');
  assert.equal(h.get('friendProfileModal').style.display, 'flex');
  assert.deepEqual(h.requests, ['/friends']); assert.deepEqual(h.alerts, []);
});

for (const [method, container, payload] of [
  ['Movies', 'friendMoviesListContainer', {movies: [{title: 'Wrong friend', year: 2000}]}],
  ['TVShows', 'friendTVShowsListContainer', {tv_shows: [{title: 'Wrong friend', year: 2000}]}],
  ['Anime', 'friendAnimeListContainer', {anime: [{title: 'Wrong friend', year: 2000}]}],
  ['VideoGames', 'friendVideoGamesListContainer', {video_games: [{title: 'Wrong friend'}]}],
  ['Music', 'friendMusicListContainer', {music: [{title: 'Wrong friend'}]}],
  ['Books', 'friendBooksListContainer', {books: [{title: 'Wrong friend'}]}],
  ['Statistics', 'statisticsData', {watch_stats: {completion_percentage: 0}, rating_stats: {average_rating: 0}}],
]) test('stale ' + method + ' shelf result is ignored after switching friends', async () => {
  const h = friendHarness(), pending = deferred(); h.context.loadFriendProfile = async () => {};
  await h.context.openFriendProfile(1); h.setFetch(async () => pending.promise);
  const loading = h.context['loadFriend' + method](1);
  await h.context.openFriendProfile(2); h.get(container).innerHTML = 'Current friend';
  pending.resolve({ok: true, json: async () => payload}); await loading;
  assert.equal(h.get(container).innerHTML, 'Current friend');
});

test('closing a collection picker during its read does not throw or reopen it', async () => {
  const nodes = new Map(), get = id => {if (!nodes.has(id)) nodes.set(id, {style: {display: 'none'}, replaceChildren() {}}); return nodes.get(id);};
  const pending = deferred();
  const context = vm.createContext({collectionPickerTarget: null, collectionsCache: [], hasStoredAuth: () => true,
    loadCollections: () => pending.promise, document: {getElementById: get},
  });
  vm.runInContext(part('async function openCollectionPicker(', 'async function addToCollection('), context);
  const opening = context.openCollectionPicker('books', 7, 'Book'); context.closeCollectionPicker();
  pending.resolve([]); await opening;
  assert.equal(get('collectionPickerModal').style.display, 'none');
});

test('only the latest collection picker target renders after out-of-order reads', async () => {
  const nodes = new Map(), get = id => {if (!nodes.has(id)) nodes.set(id, {style: {}, children: [], replaceChildren() {this.children=[];}, appendChild(node) {this.children.push(node);}}); return nodes.get(id);};
  const old = deferred(); let calls = 0;
  const context = vm.createContext({collectionPickerTarget: null, collectionsCache: [], hasStoredAuth: () => true,
    loadCollections: () => ++calls === 1 ? old.promise : Promise.resolve([]),
    document: {getElementById: get, createElement: () => ({})},
  });
  vm.runInContext(part('async function openCollectionPicker(', 'async function addToCollection('), context);
  const first = context.openCollectionPicker('books', 1, 'Old');
  await context.openCollectionPicker('movies', 2, 'Current'); old.resolve([]); await first;
  assert.match(get('collectionPickerItemTitle').textContent, /Current/);
  assert.equal(get('collectionPickerOptions').children.length, 1);
});

for (const kind of ['Music', 'Book']) {
  test(kind + ' artwork requests respect the concurrency cap and persist once per matching item', async () => {
    let active = 0, peak = 0, saves = 0, slots = 0; const waiting = [], responses = [];
    const rows = new Map([1, 2, 3].map(id => [id, {}]));
    const context = vm.createContext({API_BASE: '', AbortController, console, editingRowElement: null,
      document: {querySelector: selector => ({closest: () => rows.get(Number(selector.match(/\d+$/)[0]))})},
      posterFetchQueue: new Map(), posterFetchInProgress: new Set(), setTimeout: () => 1, clearTimeout() {},
      waitForPosterSlot: () => slots < 1 ? (++slots, Promise.resolve()) : new Promise(resolve => waiting.push(resolve)),
      releasePosterSlot: () => {if (waiting.length) waiting.shift()(); else slots--;},
      cachedProxyFetch: async () => {active++; peak = Math.max(peak, active); const pending = deferred(); responses.push(pending); const value = await pending.promise; active--; return value;},
    });
    context['save' + kind + 'Metadata'] = async () => {saves++;}; context['display' + kind + 'Poster'] = () => {};
    context['update' + kind + 'RowMetadata'] = () => {};
    vm.runInContext(part('async function fetch' + kind + 'Metadata(', 'function update' + kind + 'RowMetadata('), context);
    const calls = [1, 2, 3].map(id => context['fetch' + kind + 'Metadata'](id, 'Title ' + id, 'Creator'));
    await settle(); assert.equal(responses.length, 1);
    for (let i=0; i<3; i++) {responses[i].resolve({ok:true, json:async()=>kind==='Music'
      ? {results:[{artworkUrl100:'https://example.com/art.jpg',collectionName:'Album'}]}
      : {docs:[{cover_i:10,title:'Book'}]}}); await settle();}
    await Promise.all(calls); assert.equal(peak, 1); assert.equal(saves, 3);
  });
  test(kind + ' delayed artwork skips an active editor', async () => {
    const row = {}, pending = deferred(); let saves = 0;
    const context = vm.createContext({API_BASE: '', AbortController, console, editingRowElement: null,
      document: {querySelector: () => ({closest: () => row})}, posterFetchQueue: new Map(), posterFetchInProgress: new Set(),
      setTimeout: () => 1, clearTimeout() {}, waitForPosterSlot: async () => {}, releasePosterSlot() {},
      cachedProxyFetch: () => pending.promise,
    });
    context['save' + kind + 'Metadata'] = async () => {saves++;}; context['display' + kind + 'Poster'] = () => {throw new Error('must not render');};
    context['update' + kind + 'RowMetadata'] = () => {throw new Error('must not replace inputs');};
    vm.runInContext(part('async function fetch' + kind + 'Metadata(', 'function update' + kind + 'RowMetadata('), context);
    const loading = context['fetch' + kind + 'Metadata'](1,'Title','Creator'); await settle(); context.editingRowElement = row;
    pending.resolve({ok:true, json:async()=>kind==='Music'?{results:[{artworkUrl100:'https://example.com/a.jpg'}]}:{docs:[{cover_i:1}]}});
    await loading; assert.equal(saves, 0);
  });
}

for (const kind of ['Movie', 'Music', 'Book']) test(kind + ' metadata updates preserve unsaved row inputs', () => {
  const row = {cells: Array.from({length:5}, () => ({textContent: 'Editor input'}))};
  const context = vm.createContext({editingRowElement: row, document: {querySelector: () => ({closest: () => row})}});
  const a = source.indexOf('function update' + kind + 'RowMetadata('), b = source.indexOf('\n}', a)+2;
  vm.runInContext(source.slice(a,b), context);
  if (kind === 'Movie') context.updateMovieRowMetadata(1,'Changed');
  else context['update' + kind + 'RowMetadata'](1,'Creator',2024,'Genre','Changed');
  assert.ok(row.cells.every(cell => cell.textContent === 'Editor input'));
});

test('malformed, non-object, and denied browser auth storage are safe to read', () => {
  let value = '{invalid';
  const context = vm.createContext({TOKEN_KEY:'token', USER_KEY:'user', localStorage:{getItem(){return value;}}});
  const a=auth.indexOf('function getToken()'), b=auth.indexOf('function clearAuth(',a);
  vm.runInContext(auth.slice(a,b), context);
  for (const stored of ['{invalid','[]','true','"text"','null']) {value=stored; assert.equal(context.getUser(),null);}
  value='{"id":7,"username":"member"}'; assert.equal(context.getUser().id,7);
  context.localStorage.getItem=()=>{throw new Error('denied');}; assert.equal(context.getToken(),null); assert.equal(context.getUser(),null);
});


function guestHarness() {
  const storage = new Map(), events = [], listeners = [], status = {textContent:''}; let deny = false, fetchImpl;
  const button = {dataset:{guestKind:'movie',guestSlug:'arrival-2016',guestTitle:'Arrival'}, textContent:'', attributes:{},
    setAttribute(key,value){this.attributes[key]=value;}, addEventListener(name,fn){listeners.push(fn);}};
  const context = vm.createContext({console, getUser:()=>({id:7}), setTimeout:()=>0,
    localStorage:{getItem:key=>storage.get(key)??null, setItem(key,value){if(deny)throw new Error('denied');storage.set(key,value);},removeItem(key){if(deny)throw new Error('denied');storage.delete(key);}},
    document:{readyState:'complete',documentElement:{dataset:{publicShell:'false'}},addEventListener(){},
      querySelectorAll:selector=>selector==='[data-guest-save]'?[button]:[], querySelector:()=>status,
      createElement:()=>({setAttribute(){},remove(){}}),body:{appendChild(){}}},
    fetch:(...args)=>fetchImpl(...args), reportFunnelEvent:event=>events.push(event),
  });
  context.window=context;
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/guest-list.js'),'utf8'),context);
  return {api:context.OmniGuestList,button,status,events,click:()=>listeners[0](),deny:()=>{deny=true;},setFetch:fn=>{fetchImpl=fn;}};
}

test('guest title saves report full-list and storage failures without claiming success', () => {
  const full=guestHarness();
  for(let i=0;i<full.api.MAX;i++)full.api.add('movie','title-'+i,'Title '+i);
  full.click(); assert.doesNotMatch(full.button.textContent,/Saved/);assert.match(full.status.textContent,/full/);
  const denied=guestHarness();denied.deny();
  assert.equal(denied.api.add('movie','other','Other').added,false);
  assert.equal(denied.events.length,0);
  denied.click();assert.doesNotMatch(denied.button.textContent,/Saved/);assert.match(denied.status.textContent,/could not save/);
});

test('guest import keeps newer titles saved while the request was running', async () => {
  const h=guestHarness(),pending=deferred();
  h.api.add('movie','arrival-2016','Arrival');h.setFetch(()=>pending.promise);
  const importing=h.api.importList();h.api.add('book','dune-1965','Dune');
  pending.resolve({ok:true,json:async()=>({added:[{title:'Arrival'}],existing:[]})});await importing;
  assert.equal(h.api.read().length,1);assert.equal(h.api.read()[0].slug,'dune-1965');
});

test('unreadable guest import confirmation keeps the source list for a safe retry', async () => {
  const h=guestHarness();h.api.add('movie','arrival-2016','Arrival');
  h.setFetch(async()=>({ok:true,json:async()=>{throw new Error('response interrupted');}}));
  assert.equal(await h.api.importList(),null);assert.equal(h.api.read().length,1);
});


test('older collection reads cannot overwrite a later refreshed list or its error state', async () => {
  const earlier=deferred(),rendered=[];let calls=0;
  const context=vm.createContext({API_BASE:'',collectionsCache:[],collectionLoadSequence:0,hasStoredAuth:()=>true,
    authenticatedFetch:()=>++calls===1?earlier.promise:Promise.resolve({ok:true,json:async()=>[{id:2,name:'Latest'}]}),
    renderCollections:value=>rendered.push(value),loadModeratorInsights(){},document:{getElementById:()=>({})},
  });
  vm.runInContext(part('async function loadCollections()', 'function renderCollections('),context);
  const older=context.loadCollections();await context.loadCollections();
  earlier.resolve({ok:true,json:async()=>[{id:1,name:'Stale'}]});assert.equal(await older,null);
  assert.equal(context.collectionsCache[0].name,'Latest');assert.equal(rendered.length,1);
});
