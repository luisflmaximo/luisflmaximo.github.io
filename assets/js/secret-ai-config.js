(function () {
  'use strict';

  window.SECRET_AI_CONFIG = Object.assign({
    enabled: true,
    endpoint: 'https://secret-ai.luisflmaximo.workers.dev/recommend',
  }, window.SECRET_AI_CONFIG || {});
})();
