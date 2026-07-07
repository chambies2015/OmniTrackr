(function () {
  const AD_CLIENT = 'ca-pub-7271682066779719';
  const AD_SCRIPT_ID = 'omnitrackr-public-adsense';
  const AD_SRC = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CLIENT}`;
  const AD_ELIGIBLE_PATHS = new Set([
    '/about',
    '/faq',
    '/guides',
    '/compare',
    '/use-cases',
    '/changelog',
    '/tv-show-tracker',
    '/game-tracker',
    '/movie-tracker',
    '/anime-tracker',
    '/book-tracker',
    '/music-tracker',
    '/media-statistics',
    '/export-import-guide',
    '/media-tracker-checklist',
    '/tracking-templates',
    '/review-guidelines',
    '/sample-library',
    '/demo',
    '/media-tracking',
    '/roadmap',
    '/reviews',
  ]);

  function isAdEligiblePath() {
    return AD_ELIGIBLE_PATHS.has(window.location.pathname) ||
      /^\/reviews\/\d+$/.test(window.location.pathname);
  }

  function hasStoredAuth() {
    try {
      return Boolean(
        localStorage.getItem('omnitrackr_user') ||
        localStorage.getItem('omnitrackr_token')
      );
    } catch (error) {
      return true;
    }
  }

  function hasSessionCookie() {
    try {
      return document.cookie
        .split(';')
        .some((cookie) => cookie.trim().startsWith('omnitrackr_session='));
    } catch (error) {
      return true;
    }
  }

  function prefersLimitedTracking() {
    return (
      navigator.globalPrivacyControl === true ||
      navigator.doNotTrack === '1' ||
      window.doNotTrack === '1' ||
      (navigator.connection && navigator.connection.saveData === true)
    );
  }

  function isNoindexPage() {
    const robots = document.querySelector('meta[name="robots"]');
    return Boolean(robots && /\bnoindex\b/i.test(robots.getAttribute('content') || ''));
  }

  function appendAdScript() {
    if (document.getElementById(AD_SCRIPT_ID)) {
      return;
    }

    const script = document.createElement('script');
    script.id = AD_SCRIPT_ID;
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.src = AD_SRC;
    document.head.appendChild(script);
  }

  function scheduleAdScript() {
    const runWhenIdle = () => {
      if ('requestIdleCallback' in window) {
        window.requestIdleCallback(appendAdScript, { timeout: 2500 });
      } else {
        window.setTimeout(appendAdScript, 1200);
      }
    };

    if (document.readyState === 'complete') {
      runWhenIdle();
    } else {
      window.addEventListener('load', runWhenIdle, { once: true });
    }
  }

  if (
    !isAdEligiblePath() ||
    hasStoredAuth() ||
    hasSessionCookie() ||
    prefersLimitedTracking() ||
    isNoindexPage() ||
    document.documentElement.classList.contains('authenticated') ||
    document.getElementById(AD_SCRIPT_ID)
  ) {
    return;
  }

  scheduleAdScript();
})();
