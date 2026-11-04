(function () {
  const MEASUREMENT_ID = 'G-7EJ4ZGHNV1';

  function prefersLimitedTracking() {
    return navigator.globalPrivacyControl === true ||
      navigator.doNotTrack === '1' ||
      window.doNotTrack === '1';
  }

  if (
    !document.documentElement.hasAttribute('data-public-shell') ||
    prefersLimitedTracking() ||
    document.getElementById('omnitrackr-google-analytics')
  ) {
    return;
  }

  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };
  window.gtag('js', new Date());
  window.gtag('config', MEASUREMENT_ID, {
    anonymize_ip: true,
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
  });

  // gtag.js is about 200 KB of script that ran while the page was still
  // starting up and held the main thread for a third of a second on phones.
  // The calls above wait in dataLayer, so loading it once the page has
  // finished (and the browser is idle) still records the visit.
  function load() {
    if (document.getElementById('omnitrackr-google-analytics')) return;
    const script = document.createElement('script');
    script.id = 'omnitrackr-google-analytics';
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
    document.head.appendChild(script);
  }

  function whenIdle() {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(load, { timeout: 2000 });
    } else {
      window.setTimeout(load, 200);
    }
  }

  if (document.readyState === 'complete') {
    whenIdle();
  } else {
    window.addEventListener('load', whenIdle, { once: true });
  }
})();
