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

  const script = document.createElement('script');
  script.id = 'omnitrackr-google-analytics';
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
  document.head.appendChild(script);
})();
