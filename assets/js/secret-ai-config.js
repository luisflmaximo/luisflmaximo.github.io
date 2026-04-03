(function () {
  'use strict';

  window.SECRET_AI_CONFIG = Object.assign({
    enabled: true,
    endpoint: 'https://secret-ai.luisflmaximo.workers.dev/recommend',
    model: 'gemini-3.1-flash-lite-preview',
  }, window.SECRET_AI_CONFIG || {});
})();
