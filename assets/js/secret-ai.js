(function () {
  'use strict';

  const config = Object.assign({
    enabled: true,
    endpoint: '',
    model: 'gemini-3.1-flash-lite-preview',
  }, window.SECRET_AI_CONFIG || {});

  if (!config.enabled) return;

  const refs = {
    root: document.getElementById('secretAi'),
    panel: document.getElementById('secretAiPanel'),
    backdrop: document.getElementById('secretAiBackdrop'),
    fab: document.getElementById('secretAiFab'),
    close: document.getElementById('secretAiClose'),
    messages: document.getElementById('secretAiMessages'),
    form: document.getElementById('secretAiForm'),
    input: document.getElementById('secretAiInput'),
    hint: document.getElementById('secretAiHint'),
    submit: document.getElementById('secretAiSubmit'),
    chips: document.getElementById('secretAiChips'),
    attachBtn: document.getElementById('secretAiAttachBtn'),
    fileInput: document.getElementById('secretAiFileInput'),
    imagePreview: document.getElementById('secretAiImagePreview'),
    imageThumbnail: document.getElementById('secretAiImageThumbnail'),
    imageRemoveBtn: document.getElementById('secretAiImageRemoveBtn'),
  };

  if (!refs.root || !refs.panel || !refs.backdrop || !refs.fab || !refs.close || !refs.messages || !refs.form || !refs.input || !refs.submit || !refs.hint || !refs.chips || !refs.attachBtn || !refs.fileInput || !refs.imagePreview || !refs.imageThumbnail || !refs.imageRemoveBtn) {
    return;
  }

  const mobileQuery = (window.matchMedia && typeof window.matchMedia === 'function')
    ? window.matchMedia('(max-width: 640px)')
    : { matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
  const STOP_WORDS = new Set([
    'a', 'ao', 'aos', 'as', 'com', 'como', 'da', 'das', 'de', 'do', 'dos',
    'e', 'em', 'eu', 'la', 'mais', 'me', 'mostra', 'na', 'nas', 'no', 'nos', 'o', 'os',
    'ou', 'para', 'por', 'pra', 'preciso', 'procuro', 'quero', 'que', 'recomenda',
    'sem', 'ser', 'site', 'sites', 'sugere', 'um', 'uma', 'uns', 'umas',
    'the', 'and', 'for', 'with', 'use', 'using', 'need', 'want', 'show', 'tell', 'recommend',
  ]);
  const SHORT_QUERY_TOKENS = new Set(['ai', 'ia', 'ui', 'ux', 'vr', 'ar', 'cv', '2d', '3d', 'pdf', 'api']);
  const TOKEN_ALIASES = {
    multiplayer: ['multiplayer', 'multijogador', 'co-op', 'coop', 'co op', 'cooperative', 'cooperativo'],
    multijogador: ['multiplayer', 'multijogador', 'co-op', 'coop', 'co op', 'cooperative', 'cooperativo'],
    'co-op': ['co-op', 'coop', 'co op', 'cooperative', 'cooperativo', 'multiplayer'],
    'co op': ['co-op', 'coop', 'co op', 'cooperative', 'cooperativo', 'multiplayer'],
    coop: ['co-op', 'coop', 'co op', 'cooperative', 'cooperativo', 'multiplayer'],
    singleplayer: ['singleplayer', 'single-player', 'single player', 'solo'],
    'single-player': ['singleplayer', 'single-player', 'single player', 'solo'],
    'single player': ['singleplayer', 'single-player', 'single player', 'solo'],
    solo: ['solo', 'singleplayer', 'single-player', 'single player'],
  };

  const state = {
    open: false,
    busy: false,
    history: [],
    catalog: [],
    cardMap: Object.create(null),
    filters: {
      categoryId: null,
      categoryLabel: '',
      sectionId: null,
      sectionLabel: '',
    },
    toolsApi: null,
    typingNode: null,
    closeTimer: null,
    attachedImage: null, // Stores { mimeType, data (base64) }
  };

  function normalizeText(value) {
    const text = String(value || '').trim().toLowerCase();
    if (!text) return '';

    if (typeof text.normalize === 'function') {
      return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }

    return text;
  }

  function tokenize(text) {
    return normalizeText(text)
      .split(/[^a-z0-9]+/i)
      .filter((token) => (token.length > 2 || SHORT_QUERY_TOKENS.has(token)) && !STOP_WORDS.has(token));
  }

  function uniqueTextList(values) {
    const seen = new Set();

    return values.filter((value) => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function buildTokenVariants(token) {
    const normalized = normalizeText(token);
    const variants = [normalized];

    if (normalized.length > 4 && normalized.endsWith('s')) {
      variants.push(normalized.slice(0, -1));
    } else if (normalized.length > 3) {
      variants.push(normalized + 's');
    }

    if (normalized.length > 5 && normalized.endsWith('es')) {
      variants.push(normalized.slice(0, -2));
    }

    if (TOKEN_ALIASES[normalized]) {
      variants.push.apply(variants, TOKEN_ALIASES[normalized]);
    }

    return uniqueTextList(variants.map((value) => normalizeText(value)));
  }

  function buildQuerySignals(queryNorm, tokens) {
    const normalizedTokens = uniqueTextList(tokens.map((token) => normalizeText(token)));

    Object.keys(TOKEN_ALIASES).forEach((token) => {
      if (queryNorm.includes(token) && !normalizedTokens.includes(token)) {
        normalizedTokens.push(token);
      }
    });

    return normalizedTokens
      .map((token) => ({
        token,
        variants: buildTokenVariants(token),
      }));
  }

  function getCandidateMatchText(item) {
    if (!item) return '';

    const badges = Array.isArray(item.badges)
      ? item.badges.map((badge) => typeof badge === 'string' ? badge : badge && badge.label ? badge.label : '').join(' ')
      : '';

    return normalizeText([
      item.title,
      item.desc,
      item.search,
      item.categoryId,
      item.categoryLabel,
      item.sectionId,
      item.sectionLabel,
      badges,
    ].join(' '));
  }

  function getCandidateHighSignalText(item) {
    if (!item) return '';

    const badges = Array.isArray(item.badges)
      ? item.badges.map((badge) => typeof badge === 'string' ? badge : badge && badge.label ? badge.label : '').join(' ')
      : '';

    return normalizeText([
      item.title,
      item.categoryId,
      item.categoryLabel,
      item.sectionId,
      item.sectionLabel,
      badges,
    ].join(' '));
  }

  function countSignalMatches(text, signals) {
    return signals.reduce((total, signal) => {
      return total + (signal.variants.some((variant) => text.includes(variant)) ? 1 : 0);
    }, 0);
  }

  function getCandidateCoverage(item, signals) {
    if (!signals.length) {
      return {
        highHits: 0,
        fullHits: 0,
      };
    }

    const highSignalText = getCandidateHighSignalText(item);
    const fullSignalText = getCandidateMatchText(item);

    return {
      highHits: countSignalMatches(highSignalText, signals),
      fullHits: countSignalMatches(fullSignalText, signals),
    };
  }

  function passesCoverageGate(coverage, signalCount) {
    if (!signalCount) return true;
    if (signalCount === 1) return coverage.fullHits >= 1;
    return coverage.fullHits >= Math.min(2, signalCount);
  }

  function clampText(value, maxLength) {
    const text = String(value || '').trim();
    if (text.length <= maxLength) return text;
    return text.slice(0, Math.max(0, maxLength - 1)).trim() + '…';
  }

  function isMobileSheet() {
    return mobileQuery.matches;
  }

  function submitPromptForm() {
    if (typeof refs.form.requestSubmit === 'function') {
      refs.form.requestSubmit();
      return;
    }

    refs.form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
  }

  function autoResizeInput() {
    refs.input.style.height = 'auto';
    refs.input.style.height = Math.min(refs.input.scrollHeight, 136) + 'px';
  }

  function scrollMessagesToBottom() {
    refs.messages.scrollTop = refs.messages.scrollHeight;
  }

  function revealMessage(node, role) {
    if (!node) return;

    window.requestAnimationFrame(() => {
      window.setTimeout(() => {
        node.classList.add('secret-ai__message--visible');
      }, role === 'assistant' ? 70 : 0);
    });
  }

  function createMessageShell(role, bubbleClassName) {
    const item = document.createElement('article');
    item.className = 'secret-ai__message secret-ai__message--' + role;

    const roleLabel = document.createElement('span');
    roleLabel.className = 'secret-ai__role';
    roleLabel.textContent = role === 'assistant' ? 'IA' : 'Tu';

    const bubble = document.createElement('div');
    bubble.className = 'secret-ai__bubble' + (bubbleClassName ? ' ' + bubbleClassName : '');

    item.appendChild(roleLabel);
    item.appendChild(bubble);
    refs.messages.appendChild(item);
    revealMessage(item, role);

    return {
      item,
      bubble,
    };
  }

  function appendParagraphs(container, text) {
    String(text || '')
      .split(/\n{2,}|\r\n\r\n/)
      .map((part) => part.trim())
      .filter(Boolean)
      .forEach((part) => {
        const paragraph = document.createElement('p');
        paragraph.textContent = part;
        container.appendChild(paragraph);
      });
  }

  function appendTextMessage(role, text, options) {
    const message = createMessageShell(role, options && options.bubbleClassName);
    appendParagraphs(message.bubble, text);
    scrollMessagesToBottom();
    return message.item;
  }

  function appendAssistantRecommendations(answer, recommendations) {
    const message = createMessageShell('assistant', 'secret-ai__bubble--assistant');

    if (answer) {
      const summary = document.createElement('div');
      summary.className = 'secret-ai__answer';
      appendParagraphs(summary, answer);
      message.bubble.appendChild(summary);
    }

    if (recommendations.length) {
      const list = document.createElement('div');
      list.className = 'secret-ai__recommendations';

      recommendations.forEach((entry, index) => {
        const card = state.cardMap[entry.id];
        if (!card) return;

        const article = document.createElement('article');
        article.className = 'secret-ai__rec';

        const titleRow = document.createElement('div');
        titleRow.className = 'secret-ai__rec-title-row';

        const title = document.createElement('p');
        title.className = 'secret-ai__rec-title';
        title.textContent = card.title;

        const ranking = document.createElement('span');
        ranking.className = 'secret-ai__rec-index';
        ranking.textContent = String(index + 1);

        titleRow.appendChild(title);
        titleRow.appendChild(ranking);

        const meta = document.createElement('p');
        meta.className = 'secret-ai__rec-meta';
        meta.textContent = card.categoryLabel + (card.sectionLabel ? ' · ' + card.sectionLabel : '') + (card.domain ? ' · ' + card.domain : '');

        const reason = document.createElement('p');
        reason.className = 'secret-ai__rec-reason';
        reason.textContent = clampText(entry.reason || card.desc || 'Parece ajustar-se bem ao que pediste.', 160);

        const link = document.createElement('a');
        link.className = 'secret-ai__rec-link';
        link.href = card.href;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'Abrir site';

        article.appendChild(titleRow);
        article.appendChild(meta);
        article.appendChild(reason);
        article.appendChild(link);
        list.appendChild(article);
      });

      if (list.childElementCount) {
        message.bubble.appendChild(list);
      }
    }

    scrollMessagesToBottom();
    return message.item;
  }

  function showTypingMessage() {
    const message = createMessageShell('assistant', 'secret-ai__bubble--muted');
    const row = document.createElement('div');
    row.className = 'secret-ai__typing';

    for (let index = 0; index < 3; index += 1) {
      const dot = document.createElement('span');
      dot.className = 'secret-ai__typing-dot';
      row.appendChild(dot);
    }

    message.bubble.appendChild(row);
    scrollMessagesToBottom();
    state.typingNode = message.item;
  }

  function removeTypingMessage() {
    if (state.typingNode && state.typingNode.parentNode) {
      state.typingNode.parentNode.removeChild(state.typingNode);
    }
    state.typingNode = null;
  }

  function setBusy(isBusy) {
    state.busy = isBusy;
    refs.submit.disabled = isBusy;
    refs.submit.textContent = isBusy ? 'A pensar…' : 'Perguntar';
    refs.input.readOnly = isBusy;
  }

  function setOpen(nextOpen) {
    window.clearTimeout(state.closeTimer);
    state.open = Boolean(nextOpen);

    refs.root.classList.toggle('secret-ai--open', state.open);
    refs.panel.setAttribute('aria-hidden', state.open ? 'false' : 'true');
    refs.fab.setAttribute('aria-expanded', state.open ? 'true' : 'false');
    refs.backdrop.hidden = !state.open;
    document.body.classList.toggle('secret-ai-body-lock', state.open && isMobileSheet());

    if (state.open) {
      window.requestAnimationFrame(() => {
        try {
          refs.input.focus({ preventScroll: true });
        } catch (_) {
          refs.input.focus();
        }
        scrollMessagesToBottom();
      });
      return;
    }

    state.closeTimer = window.setTimeout(() => {
      if (!state.open) refs.backdrop.hidden = true;
    }, 240);
  }

  function updateHint() {
    const filters = state.filters || {};
    if (filters.sectionLabel) {
      refs.hint.textContent = 'Categoria ativa: ' + filters.categoryLabel + ' · ' + filters.sectionLabel;
      return;
    }

    if (filters.categoryLabel) {
      refs.hint.textContent = 'Categoria ativa: ' + filters.categoryLabel;
      return;
    }

    refs.hint.textContent = 'A IA só recomenda sites já presentes neste catálogo.';
  }

  function pushHistory(role, text) {
    state.history.push({
      role,
      text: clampText(text, 500),
    });

    if (state.history.length > 12) {
      state.history = state.history.slice(-12);
    }
  }

  function hydrateCatalogItem(card) {
    const badges = Array.isArray(card.badges) ? card.badges : [];
    const badgeLabels = badges
      .map((badge) => badge && badge.label ? String(badge.label).trim() : '')
      .filter(Boolean);

    const sourceLabel = card.source && card.source.label ? String(card.source.label).trim() : '';
    const title = String(card.title || '').trim();
    const domain = String(card.domain || '').trim();
    const desc = String(card.desc || '').trim();
    const categoryLabel = String(card.categoryLabel || '').trim();
    const sectionLabel = String(card.sectionLabel || '').trim();
    const search = String(card.search || '').trim();

    return {
      id: String(card.id || '').trim(),
      title,
      href: String(card.href || '').trim(),
      desc,
      domain,
      badges: badgeLabels,
      source: card.source ? {
        href: String(card.source.href || '').trim(),
        label: sourceLabel,
      } : null,
      categoryId: String(card.categoryId || '').trim(),
      categoryLabel,
      sectionId: String(card.sectionId || '').trim(),
      sectionLabel,
      titleNorm: normalizeText(title),
      domainNorm: normalizeText(domain),
      descNorm: normalizeText(desc),
      categoryNorm: normalizeText(categoryLabel),
      sectionNorm: normalizeText(sectionLabel),
      badgesNorm: normalizeText(badgeLabels.join(' ')),
      searchNorm: normalizeText(search),
      matchText: normalizeText([
        title,
        domain,
        desc,
        categoryLabel,
        sectionLabel,
        badgeLabels.join(' '),
        sourceLabel,
        search,
      ].join(' ')),
    };
  }

  function syncCatalogFromTools() {
    if (!state.toolsApi) return;

    state.catalog = state.toolsApi.getCatalog().map(hydrateCatalogItem);
    state.cardMap = Object.create(null);
    state.catalog.forEach((card) => {
      state.cardMap[card.id] = card;
    });
    state.filters = Object.assign({}, state.toolsApi.getActiveFilters());
    updateHint();
  }

  function scoreCandidate(card, queryNorm, tokens, signals) {
    let score = 0;
    const coverage = getCandidateCoverage(card, signals);

    if (state.filters.categoryId && card.categoryId === state.filters.categoryId) score += 18;
    if (state.filters.sectionId && card.sectionId === state.filters.sectionId) score += 28;

    if (signals.length) {
      score += coverage.highHits * 34;
      score += Math.max(0, coverage.fullHits - coverage.highHits) * 12;

      if (coverage.fullHits === signals.length) {
        score += 42;
      } else if (coverage.fullHits >= Math.min(2, signals.length)) {
        score += 18;
      }

      if (signals.length >= 2 && coverage.fullHits <= 1) {
        score -= 120;
      }

      if (signals.length >= 2 && coverage.highHits === 0 && coverage.fullHits < signals.length) {
        score -= 32;
      }
    }

    if (queryNorm) {
      if (card.titleNorm === queryNorm) score += 120;
      if (card.domainNorm === queryNorm) score += 90;
      if (card.titleNorm.includes(queryNorm)) score += 74;
      if (card.domainNorm.includes(queryNorm)) score += 64;
      if (card.sectionNorm.includes(queryNorm)) score += 34;
      if (card.categoryNorm.includes(queryNorm)) score += 24;
      if (card.badgesNorm.includes(queryNorm)) score += 22;
      if (card.descNorm.includes(queryNorm)) score += 18;
      if (card.searchNorm.includes(queryNorm)) score += 16;
    }

    tokens.forEach((token) => {
      if (card.titleNorm.includes(token)) score += 16;
      if (card.domainNorm.includes(token)) score += 10;
      if (card.badgesNorm.includes(token)) score += 10;
      if (card.sectionNorm.includes(token)) score += 8;
      if (card.categoryNorm.includes(token)) score += 6;
      if (card.descNorm.includes(token)) score += 5;
      if (card.searchNorm.includes(token)) score += 4;
    });

    if (tokens.length && tokens.every((token) => card.matchText.includes(token))) {
      score += 14;
    }

    return {
      score,
      coverage,
    };
  }

  function toWorkerCandidate(card) {
    return {
      id: card.id,
      title: card.title,
      href: card.href,
      desc: clampText(card.desc, 320),
      domain: card.domain,
      badges: card.badges.slice(0, 5),
      categoryLabel: card.categoryLabel,
      sectionLabel: card.sectionLabel,
    };
  }

  function appendUniqueCards(target, seen, cards) {
    (Array.isArray(cards) ? cards : []).forEach((card) => {
      if (!card || !card.id || seen.has(card.id) || target.length >= 30) return;
      seen.add(card.id);
      target.push(card);
    });
  }

  function pickCandidates(query) {
    const queryNorm = normalizeText(query);
    const tokens = tokenize(query);
    const signals = buildQuerySignals(queryNorm, tokens);

    const ranked = state.catalog
      .map((card) => {
        const result = scoreCandidate(card, queryNorm, tokens, signals);
        return {
          card,
          score: result.score,
          coverage: result.coverage,
        };
      })
      .filter((entry) => entry.score > 0)
      .sort((left, right) => right.score - left.score || left.card.title.localeCompare(right.card.title));

    const preferredRanked = ranked.filter((entry) => passesCoverageGate(entry.coverage, signals.length));
    const effectiveRanked = preferredRanked.length ? preferredRanked : ranked;

    const selected = [];
    const seen = new Set();
    const scopedFallback = state.filters.sectionId
      ? state.catalog.filter((card) => card.sectionId === state.filters.sectionId)
      : state.filters.categoryId
        ? state.catalog.filter((card) => card.categoryId === state.filters.categoryId)
        : state.catalog.slice();

    appendUniqueCards(selected, seen, effectiveRanked.map((entry) => entry.card));

    if (effectiveRanked.length) {
      const lead = effectiveRanked[0].card;
      const relatedCards = state.catalog
        .filter((card) => (
          (lead.sectionId && card.sectionId === lead.sectionId) ||
          (lead.categoryId && card.categoryId === lead.categoryId)
        ))
        .sort((left, right) => left.title.localeCompare(right.title));

      appendUniqueCards(selected, seen, relatedCards);
    }

    appendUniqueCards(selected, seen, scopedFallback);

    return selected.slice(0, 30).map(toWorkerCandidate);
  }

  function buildRequestPayload(query) {
    const payload = {
      query: clampText(query, 500),
      history: state.history.slice(-6).map((entry) => ({
        role: entry.role,
        text: entry.text,
      })),
      activeCategory: state.filters.categoryId ? {
        id: state.filters.categoryId,
        label: state.filters.categoryLabel,
      } : null,
      activeSection: state.filters.sectionId ? {
        id: state.filters.sectionId,
        label: state.filters.sectionLabel,
      } : null,
      candidates: pickCandidates(query),
    };

    if (state.attachedImage) {
      payload.image = state.attachedImage;
    }

    return payload;
  }

  function normalizeRecommendations(recommendations) {
    const seen = new Set();

    return (Array.isArray(recommendations) ? recommendations : [])
      .map((entry) => ({
        id: String(entry && entry.id || '').trim(),
        reason: clampText(entry && entry.reason || '', 180),
      }))
      .filter((entry) => {
        if (!entry.id || seen.has(entry.id) || !state.cardMap[entry.id]) return false;
        seen.add(entry.id);
        return true;
      })
      .slice(0, 6);
  }

  function buildFallbackRecommendation(candidate) {
    const hint = clampText(candidate && candidate.desc || '', 180);

    return {
      id: String(candidate && candidate.id || '').trim(),
      reason: hint || 'Boa opcao dentro do catalogo para este pedido.',
    };
  }

  function rankFallbackCandidates(candidates, query) {
    const queryNorm = normalizeText(query);
    const tokens = tokenize(query);
    const signals = buildQuerySignals(queryNorm, tokens);
    const list = Array.isArray(candidates) ? candidates.slice() : [];

    if (!signals.length) return list;

    const ranked = list
      .map((candidate, index) => ({
        candidate,
        index,
        coverage: getCandidateCoverage(candidate, signals),
      }))
      .sort((left, right) => (
        right.coverage.fullHits - left.coverage.fullHits ||
        right.coverage.highHits - left.coverage.highHits ||
        left.index - right.index
      ));

    const preferred = ranked.filter((entry) => passesCoverageGate(entry.coverage, signals.length));
    return (preferred.length ? preferred : ranked).map((entry) => entry.candidate);
  }

  function fillRecommendations(recommendations, candidates, query) {
    const filled = Array.isArray(recommendations) ? recommendations.slice(0, 6) : [];
    const seen = new Set(filled.map((entry) => entry.id));

    rankFallbackCandidates(candidates, query).forEach((candidate) => {
      const id = String(candidate && candidate.id || '').trim();
      if (!id || seen.has(id) || filled.length >= 6) return;

      seen.add(id);
      filled.push(buildFallbackRecommendation(candidate));
    });

    return filled.slice(0, 6);
  }

  async function requestRecommendations(query) {
    const payload = buildRequestPayload(query);

    if (!payload.candidates.length) {
      return {
        answer: 'Ainda não encontrei candidatos suficientes no catálogo para responder com confiança.',
        recommendations: [],
      };
    }

    const response = await fetch(config.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    let body = null;

    try {
      body = await response.json();
    } catch (_) {
      body = null;
    }

    if (!response.ok) {
      const errorMessage = body && body.error ? String(body.error) : 'Falha ao pedir recomendações.';
      throw new Error(errorMessage);
    }

    const recommendations = fillRecommendations(
      normalizeRecommendations(body && body.recommendations),
      payload.candidates,
      query,
    );
    const answer = clampText(body && body.answer || '', 500) || (
      recommendations.length
        ? 'Estas parecem ser as opções mais adequadas dentro do catálogo atual.'
        : 'Não encontrei um match claro no catálogo com base no que pediste.'
    );

    return {
      answer,
      recommendations,
    };
  }

  function showSetupMessage() {
    appendTextMessage('assistant',
      'O chat já está montado, mas ainda falta ligar o endpoint da IA.\n\n' +
      'Para ativar isto tens só de publicar o Worker da Cloudflare, definir o segredo GROQ_API_KEY e colar o URL final em assets/js/secret-ai-config.js.',
      { bubbleClassName: 'secret-ai__bubble--muted' });
  }

  function showCatalogUnavailableMessage() {
    appendTextMessage('assistant',
      'O catálogo ainda está a carregar. Tenta outra vez dentro de um instante.',
      { bubbleClassName: 'secret-ai__bubble--muted' });
  }

  async function handleSubmit(event) {
    if (event) event.preventDefault();

    const query = refs.input.value.trim();
    if ((!query && !state.attachedImage) || state.busy) return;

    if (state.attachedImage) {
      const message = createMessageShell('user');
      const img = document.createElement('img');
      img.src = 'data:' + state.attachedImage.mimeType + ';base64,' + state.attachedImage.data;
      img.style.maxHeight = '120px';
      img.style.borderRadius = '6px';
      img.style.display = 'block';
      img.style.marginBottom = '6px';
      message.bubble.appendChild(img);
      if (query) {
        const p = document.createElement('p');
        p.textContent = query;
        message.bubble.appendChild(p);
      }
      scrollMessagesToBottom();
    } else {
      appendTextMessage('user', query);
    }

    const savedQuery = query;
    refs.input.value = '';
    state.attachedImage = null;
    refs.imagePreview.hidden = true;
    refs.imageThumbnail.src = '';
    refs.fileInput.value = '';
    autoResizeInput();

    if (!config.endpoint) {
      showSetupMessage();
      return;
    }

    if (!state.catalog.length) {
      showCatalogUnavailableMessage();
      return;
    }

    setBusy(true);
    showTypingMessage();

    try {
      const result = await requestRecommendations(savedQuery || 'Analisa esta imagem em relação aos sites.');
      removeTypingMessage();
      appendAssistantRecommendations(result.answer, result.recommendations);
      pushHistory('user', savedQuery || 'Imagem enviada');
      pushHistory('assistant', result.answer);
    } catch (error) {
      removeTypingMessage();
      appendTextMessage('assistant',
        error && error.message
          ? error.message
          : 'Não consegui obter uma resposta da IA neste momento.',
        { bubbleClassName: 'secret-ai__bubble--error' });
    } finally {
      setBusy(false);
    }
  }

  function seedWelcomeMessage() {
    appendTextMessage('assistant',
      'Diz-me o que precisas e eu sugiro os sites mais adequados desta aba.',
      { bubbleClassName: 'secret-ai__bubble--muted' });
  }

  function handleImageFile(file) {
    if (!file || !file.type.startsWith('image/')) return;

    const reader = new FileReader();
    reader.onload = function (e) {
      const base64Data = e.target.result.split(',')[1];
      state.attachedImage = {
        mimeType: file.type,
        data: base64Data,
      };
      refs.imageThumbnail.src = e.target.result;
      refs.imagePreview.hidden = false;
    };
    reader.readAsDataURL(file);
  }

  function bindEvents() {
    refs.fab.addEventListener('click', () => {
      setOpen(true);
    });

    refs.close.addEventListener('click', () => {
      setOpen(false);
    });

    refs.backdrop.addEventListener('click', () => {
      setOpen(false);
    });

    refs.form.addEventListener('submit', handleSubmit);

    refs.input.addEventListener('input', autoResizeInput);

    refs.input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitPromptForm();
      }
    });

    refs.chips.addEventListener('click', (event) => {
      const chip = event.target.closest('.secret-ai__chip');
      if (!chip) return;
      const prompt = chip.dataset.prompt;
      if (prompt) {
        refs.input.value = prompt;
        autoResizeInput();
        refs.input.focus();
      }
    });

    refs.attachBtn.addEventListener('click', () => {
      refs.fileInput.click();
    });

    refs.fileInput.addEventListener('change', (event) => {
      const file = event.target.files[0];
      handleImageFile(file);
    });

    refs.imageRemoveBtn.addEventListener('click', () => {
      state.attachedImage = null;
      refs.imagePreview.hidden = true;
      refs.imageThumbnail.src = '';
      refs.fileInput.value = '';
    });

    refs.input.addEventListener('paste', (event) => {
      const items = (event.clipboardData || event.originalEvent.clipboardData).items;
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const file = items[i].getAsFile();
          handleImageFile(file);
          break;
        }
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && state.open) {
        setOpen(false);
      }
    });

    if (typeof mobileQuery.addEventListener === 'function') {
      mobileQuery.addEventListener('change', () => {
        document.body.classList.toggle('secret-ai-body-lock', state.open && isMobileSheet());
      });
      return;
    }

    if (typeof mobileQuery.addListener === 'function') {
      mobileQuery.addListener(() => {
        document.body.classList.toggle('secret-ai-body-lock', state.open && isMobileSheet());
      });
    }
  }

  function connectToSecretTools(attempt) {
    const api = window.SecretToolsAI;

    if (api && typeof api.getCatalog === 'function' && typeof api.subscribe === 'function') {
      state.toolsApi = api;
      syncCatalogFromTools();
      api.subscribe(() => {
        syncCatalogFromTools();
      });
      return;
    }

    if (attempt >= 20) {
      appendTextMessage('assistant',
        'Não consegui ligar o assistente ao catálogo desta página.',
        { bubbleClassName: 'secret-ai__bubble--error' });
      return;
    }

    window.setTimeout(() => {
      connectToSecretTools(attempt + 1);
    }, 180);
  }

  seedWelcomeMessage();
  bindEvents();
  autoResizeInput();
  updateHint();
  connectToSecretTools(0);
})();
