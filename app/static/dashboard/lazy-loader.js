// Lazy dashboard features. window.OmniDashboardChunks (written by the server
// ahead of this file) lists each chunk's files and the global functions it
// defines. Until a chunk has loaded, each of those names is a placeholder that
// loads the chunk and then calls the real function, so buttons and other code
// can keep calling them by name. Once the page is idle every chunk is fetched
// in the background, so a first click rarely has to wait.
(function () {
  'use strict';

  const config = window.OmniDashboardChunks;
  if (!config || !config.chunks) return;
  const loading = new Map();

  function loadFile(file) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `${config.base}${file}?v=${encodeURIComponent(config.version)}`;
      // Dynamic scripts with async = false still download in parallel but run in order.
      script.async = false;
      script.onload = resolve;
      script.onerror = () => {
        script.remove();
        reject(new Error(`Could not load ${file}`));
      };
      document.head.appendChild(script);
    });
  }

  function loadChunk(name) {
    const chunk = config.chunks[name];
    if (!chunk) return Promise.reject(new Error(`Unknown dashboard feature: ${name}`));
    if (!loading.has(name)) {
      const request = Promise.all(chunk.files.map(loadFile));
      // A failed download (for example while offline) can be retried on the next use.
      request.catch(() => { if (loading.get(name) === request) loading.delete(name); });
      loading.set(name, request);
    }
    return loading.get(name);
  }

  function placeholder(name, chunkName) {
    const standIn = function (...args) {
      const current = window[name];
      if (current !== standIn && typeof current === 'function') return current.apply(this, args);
      // Lazy submit handlers always cancel the browser's own submission first;
      // do that now so the form is not sent while the chunk downloads.
      const [event] = args;
      if (typeof Event === 'function' && event instanceof Event && event.type === 'submit') event.preventDefault();
      return loadChunk(chunkName).then(() => {
        const loaded = window[name];
        if (loaded === standIn || typeof loaded !== 'function') throw new Error(`${name} is unavailable`);
        return loaded.apply(this, args);
      });
    };
    return standIn;
  }

  Object.entries(config.chunks).forEach(([chunkName, chunk]) => {
    chunk.exports.forEach(name => {
      if (typeof window[name] === 'undefined') window[name] = placeholder(name, chunkName);
    });
  });

  function prefetchAll() {
    if (navigator.connection && navigator.connection.saveData) return;
    Object.keys(config.chunks).reduce(
      (previous, name) => previous.then(() => loadChunk(name).catch(() => {})),
      Promise.resolve(),
    );
  }

  function prefetchWhenIdle() {
    if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(prefetchAll, { timeout: 5000 });
    else window.setTimeout(prefetchAll, 2000);
  }

  config.load = loadChunk;
  if (document.readyState === 'complete') prefetchWhenIdle();
  else window.addEventListener('load', prefetchWhenIdle, { once: true });
})();
