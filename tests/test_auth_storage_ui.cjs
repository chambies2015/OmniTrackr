const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const preauth = fs.readFileSync(path.join(__dirname, '../app/static/preauth.js'), 'utf8');
const deferred = () => {let resolve; const promise = new Promise(r => {resolve=r;}); return {promise,resolve};};

function harness({dashboard=false, readDenied=true, writeDenied=true, sessionDenied=true,
  session=new Map(), local=new Map(), user={id:7,username:'reader'}}={}) {
  const requests=[],redirects=[],elements=new Map(),listeners=new Map(),timers=new Map();
  let readBlocked=readDenied,writeBlocked=writeDenied,fetchImpl;
  const location={protocol:'https:',origin:'https://omnitrackr.xyz',pathname:'/',search:'',hash:'',
    assign:value=>redirects.push(value),reload(){this.reloads=(this.reloads||0)+1;}};
  const get=id=>{
    if(id==='mainContainer'&&!dashboard)return null;
    if(!elements.has(id))elements.set(id,{id,style:{},dataset:{},value:'',textContent:'',reset(){},focus(){},addEventListener(){}});
    return elements.get(id);
  };
  const context=vm.createContext({URLSearchParams,AbortController,console,location,confirm:()=>true,
    document:{readyState:'loading',documentElement:{dataset:{publicShell:String(!dashboard)},classList:{add(){}}},
      getElementById:get,addEventListener(){},querySelector:()=>({scrollIntoView(){}})},
    localStorage:{getItem(key){if(readBlocked)throw new Error('Storage denied');return local.get(key)??null;},
      setItem(key,value){if(writeBlocked)throw new Error('Storage denied');local.set(key,value);},
      removeItem(key){if(writeBlocked)throw new Error('Storage denied');local.delete(key);}},
    sessionStorage:{getItem(key){if(sessionDenied)throw new Error('Session storage denied');return session.get(key)??null;},
      setItem(key,value){if(sessionDenied)throw new Error('Session storage denied');session.set(key,value);},
      removeItem(key){if(sessionDenied)throw new Error('Session storage denied');session.delete(key);}},
    fetch:(...args)=>{requests.push({url:args[0],options:args[1]});return fetchImpl(...args);},
    setTimeout:callback=>{const id=timers.size+1;timers.set(id,callback);return id;},clearTimeout:id=>timers.delete(id),
    addEventListener:(name,callback)=>listeners.set(name,callback),history:{replaceState(){}},
  });
  context.window=context;
  fetchImpl=async url=>({ok:true,status:200,json:async()=>url==='/auth/login'?{access_token:'cookie-response-token',user}:user});
  vm.runInContext(source,context);
  context.setupAuthHandlers=()=>{};
  context.showAuthModal=()=>{context.authShown=(context.authShown||0)+1;};
  context.showMainUI=()=>{context.mainShown=(context.mainShown||0)+1;};
  context.updateUserDisplay=()=>{context.displayUpdates=(context.displayUpdates||0)+1;};
  context.showRegisterForm=()=>{};
  for(const name of ['loadCustomTabs','openDashboardTargetFromLocation','bootstrapReturnDeck'])context[name]=()=>{context[name+'Calls']=(context[name+'Calls']||0)+1;};
  return {context,requests,redirects,elements,timers,session,local,location,listeners,
    setFetch:fn=>{fetchImpl=fn;},enableReads:()=>{readBlocked=false;},denyWrites:()=>{writeBlocked=true;}};
}

test('preauth startup tolerates denied localStorage and preserves stored sign-in styling',()=>{
  const added=[],timers=[];
  const context=vm.createContext({localStorage:{getItem(){throw new Error('denied');}},
    document:{documentElement:{classList:{add(value){added.push(value);},remove(value){added.splice(added.indexOf(value),1);}}}},
    setTimeout:(callback,delay)=>{timers.push({callback,delay});}});
  assert.doesNotThrow(()=>vm.runInContext(preauth,context));assert.equal(added.length,0);assert.equal(timers.length,0);
  context.localStorage.getItem=key=>key==='omnitrackr_token'?'legacy':null;
  vm.runInContext(preauth,context);assert.deepEqual(added,['authenticated','dashboard-settling']);
  assert.equal(timers[0].delay,3000);timers[0].callback();assert.deepEqual(added,['authenticated']);
});

test('denied storage cannot turn a successful cookie login into an error or store a bearer token',async()=>{
  const h=harness();await h.context.login('reader','password');
  assert.deepEqual(h.redirects,['/']);assert.equal(h.context.getUser().id,7);assert.equal(h.context.isAuthenticated(),true);
  assert.equal(h.context.getToken(),null);assert.equal(h.local.size,0);
  await h.context.authenticatedFetch('/movies/');
  const request=h.requests.at(-1);assert.equal(request.options.credentials,'same-origin');
  assert.equal(request.options.headers.Authorization,undefined);
});

test('denied credential removal cannot reuse an old bearer after a new login or logout',async()=>{
  const h=harness({readDenied:false,local:new Map([['omnitrackr_token','old-account-token'],['omnitrackr_user','{"id":1,"username":"old"}']])});
  await h.context.login('reader','password');assert.equal(h.context.getUser().id,7);assert.equal(h.context.getToken(),null);
  await h.context.logout();assert.equal(h.context.getUser(),null);assert.equal(h.context.getToken(),null);
  assert.equal(h.context.isAuthenticated(),false);assert.equal(h.location.reloads,1);
  assert.equal(h.requests.at(-1).url,'/auth/logout');assert.equal(h.requests.at(-1).options.credentials,'same-origin');
  await assert.rejects(h.context.authenticatedFetch('/movies/'),/Not authenticated/);
});

test('private bootstrap and API reads coalesce cookie recovery when all browser storage is denied',async()=>{
  const h=harness({dashboard:true}),reply=deferred();
  h.setFetch(async url=>url==='/account/me'?reply.promise:{ok:true,status:200,json:async()=>[]});
  const loading=h.context.authenticatedFetch('/movies/');
  const startup=h.context.initAuth();
  assert.deepEqual(h.requests.map(request=>request.url),['/account/me']);
  reply.resolve({ok:true,json:async()=>({id:7,username:'reader'})});await Promise.all([loading,startup]);
  assert.deepEqual(h.requests.map(request=>request.url),['/account/me','/movies/']);
  assert.equal(h.requests[0].options.credentials,'same-origin');assert.equal(h.requests[0].options.cache,'no-store');
  assert.equal(h.context.getUser().id,7);assert.equal(h.context.mainShown,1);assert.equal(h.context.displayUpdates,1);
  assert.equal(h.context.loadCustomTabsCalls,1);assert.equal(h.context.openDashboardTargetFromLocationCalls,1);
  assert.equal(h.requests[1].options.headers.Authorization,undefined);
});

test('public bootstrap never treats a denied storage read as a reason to open private UI',async()=>{
  const h=harness();h.context.initAuth();assert.equal(h.context.authShown,1);assert.equal(h.requests.length,0);
  await assert.rejects(h.context.authenticatedFetch('/movies/'),/Not authenticated/);
  assert.equal(h.requests.length,0);assert.equal(h.context.mainShown,undefined);
});

test('an expired cookie or failed recovery leaves the private shell at sign-in',async()=>{
  for(const failure of ['unauthorized','network','invalid']){
    const h=harness({dashboard:true});h.setFetch(async()=>{
      if(failure==='network')throw new Error('offline');
      return {ok:failure!=='unauthorized',status:401,json:async()=>failure==='invalid'?{id:0,username:'bad'}:null};
    });
    await h.context.initAuth();assert.equal(h.context.isAuthenticated(),false,failure);
    assert.equal(h.context.mainShown,undefined,failure);assert.equal(h.context.authShown,1,failure);
  }
});

test('late cookie recovery cannot sign the user back in after logout',async()=>{
  const h=harness({dashboard:true}),reply=deferred();
  h.setFetch(async url=>url==='/account/me'?reply.promise:{ok:true,json:async()=>({})});
  const startup=h.context.initAuth();await h.context.logout();
  reply.resolve({ok:true,json:async()=>({id:7,username:'reader'})});await startup;
  assert.equal(h.context.isAuthenticated(),false);assert.equal(h.context.getUser(),null);assert.equal(h.context.mainShown,undefined);
});

test('late recovery cannot replace a user who completed a newer explicit login',async()=>{
  const h=harness({dashboard:true}),reply=deferred();
  h.setFetch(async url=>url==='/account/me'?reply.promise:{ok:true,json:async()=>({user:{id:9,username:'new-reader'}})});
  const startup=h.context.initAuth();await h.context.login('new-reader','password');
  reply.resolve({ok:true,json:async()=>({id:7,username:'old-reader'})});await startup;
  assert.equal(h.context.getUser().id,9);assert.deepEqual(h.redirects,['/']);assert.equal(h.context.authShown,undefined);
});

test('a stalled storage-denied session check times out and releases bootstrap',async()=>{
  const h=harness({dashboard:true});h.setFetch(()=>new Promise(()=>{}));
  const startup=h.context.initAuth();assert.equal(h.timers.size,1);
  h.timers.values().next().value();await startup;
  assert.equal(h.context.isAuthenticated(),false);assert.equal(h.context.authShown,1);assert.equal(h.timers.size,0);
});

test('write-denied localStorage uses session storage across reload and clears it on logout',async()=>{
  const session=new Map(),local=new Map([['omnitrackr_token','old-account-token']]);
  const first=harness({readDenied:false,sessionDenied:false,session,local});await first.context.login('reader','password');
  const reloaded=harness({dashboard:true,readDenied:false,sessionDenied:false,session,local});
  reloaded.context.initAuth();assert.equal(reloaded.context.getUser().id,7);assert.equal(reloaded.context.getToken(),null);
  assert.equal(reloaded.context.mainShown,1);assert.equal(reloaded.requests.length,0);
  await reloaded.context.logout();assert.equal(reloaded.context.isAuthenticated(),false);assert.equal(session.size,0);
});

test('ordinary legacy bearer sessions and later stored profile updates retain their behavior',async()=>{
  const h=harness({dashboard:true,readDenied:false,writeDenied:false,sessionDenied:false,
    local:new Map([['omnitrackr_token','legacy-token']])});
  await h.context.authenticatedFetch('/movies/');assert.equal(h.requests[0].options.headers.Authorization,'Bearer legacy-token');
  await h.context.login('reader','password');assert.equal(h.context.getToken(),null);
  h.local.set('omnitrackr_user','{"id":7,"username":"renamed"}');assert.equal(h.context.getUser().username,'renamed');
});

test('cross-tab credential changes invalidate this tab\'s fallback identity',async()=>{
  const h=harness({readDenied:false});await h.context.login('reader','password');assert.equal(h.context.getUser().id,7);
  h.local.set('omnitrackr_user','{"id":9,"username":"other-tab"}');
  h.listeners.get('storage')({key:'omnitrackr_user'});assert.equal(h.context.getUser().id,9);
});


test('read-denied storage remains usable after cookie recovery even when writes succeed',async()=>{
  const h=harness({dashboard:true,readDenied:true,writeDenied:false,sessionDenied:true});
  await h.context.initAuth();assert.equal(h.context.isAuthenticated(),true);assert.equal(h.context.getUser().id,7);
  await h.context.authenticatedFetch('/movies/');assert.equal(h.requests.at(-1).url,'/movies/');
});
