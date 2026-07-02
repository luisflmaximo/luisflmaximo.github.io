(function () {
  'use strict';

  function getHomeHref() {
    var path = window.location.pathname || '';
    if (/\/secret\/estudio(?:\/|$)/i.test(path)) return '../../pt/';
    return '../pt/';
  }

  var unlocked = false;
  try {
    unlocked = sessionStorage.getItem('secretUnlocked') === '1';
  } catch (_) {}

  if (!unlocked) {
    window.location.replace(getHomeHref());
  }
})();
