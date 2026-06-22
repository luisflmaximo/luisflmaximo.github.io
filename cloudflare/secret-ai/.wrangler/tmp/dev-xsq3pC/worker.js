var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// worker.js
var MAX_BODY_BYTES = 1.5 * 1024 * 1024;
var MAX_QUERY_LENGTH = 500;
var MAX_HISTORY_ITEMS = 6;
var MAX_CANDIDATES = 30;
var MAX_BADGES = 5;
var MAX_ANSWER_LENGTH = 500;
var MAX_REASON_LENGTH = 320;
var DEFAULT_MODEL = "llama-3.3-70b-versatile";
var DEFAULT_VISION_MODEL = "llama-3.2-11b-vision-preview";
var worker_default = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";
    const corsOrigin = getCorsOrigin(origin, env);
    if (request.method === "OPTIONS") {
      return handleOptions(request, corsOrigin);
    }
    if (!isAllowedRoute(url.pathname)) {
      return jsonResponse({ error: "Not found." }, 404, corsOrigin);
    }
    if (origin && !corsOrigin) {
      return jsonResponse({ error: "Origin not allowed." }, 403, "");
    }
    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed." }, 405, corsOrigin);
    }
    const contentType = request.headers.get("Content-Type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      return jsonResponse({ error: "Expected application/json." }, 415, corsOrigin);
    }
    const contentLength = Number(request.headers.get("Content-Length") || 0);
    if (contentLength > MAX_BODY_BYTES) {
      return jsonResponse({ error: "Payload too large." }, 413, corsOrigin);
    }
    if (!env.GEMINI_API_KEY) {
      return jsonResponse({ error: "Missing GEMINI_API_KEY secret." }, 500, corsOrigin);
    }
    try {
      const payload = await request.json();
      const data = validatePayload(payload);
      const result = await requestGroq(data, env);
      return jsonResponse(result, 200, corsOrigin);
    } catch (error) {
      const status = error && typeof error.status === "number" ? error.status : 500;
      const message = error && error.message ? error.message : "Unexpected server error.";
      return jsonResponse({ error: message }, status, corsOrigin);
    }
  }
};
function isAllowedRoute(pathname) {
  return pathname === "/" || pathname === "/recommend";
}
__name(isAllowedRoute, "isAllowedRoute");
function getCorsOrigin(origin, env) {
  if (!origin) return "";
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin)) return origin;
  const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map((item) => item.trim()).filter(Boolean);
  return allowed.includes(origin) ? origin : "";
}
__name(getCorsOrigin, "getCorsOrigin");
function handleOptions(request, corsOrigin) {
  if ((request.headers.get("Origin") || "") && !corsOrigin) {
    return jsonResponse({ error: "Origin not allowed." }, 403, "");
  }
  return new Response(null, {
    status: 204,
    headers: buildCorsHeaders(corsOrigin)
  });
}
__name(handleOptions, "handleOptions");
function buildCorsHeaders(corsOrigin) {
  const headers = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin"
  };
  if (corsOrigin) {
    headers["Access-Control-Allow-Origin"] = corsOrigin;
  }
  return headers;
}
__name(buildCorsHeaders, "buildCorsHeaders");
function jsonResponse(body, status, corsOrigin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
      ...buildCorsHeaders(corsOrigin)
    }
  });
}
__name(jsonResponse, "jsonResponse");
function createHttpError(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}
__name(createHttpError, "createHttpError");
function clampText(value, maxLength) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return text.slice(0, Math.max(0, maxLength - 1)).trim() + "\u2026";
}
__name(clampText, "clampText");
function validateShortText(value, fieldName, maxLength, required) {
  const text = String(value || "").trim();
  if (!text && required) {
    throw createHttpError("Missing field: " + fieldName + ".", 400);
  }
  return clampText(text, maxLength);
}
__name(validateShortText, "validateShortText");
function validateOptionalScope(scope, fieldName) {
  if (!scope) return null;
  if (typeof scope !== "object") {
    throw createHttpError("Invalid field: " + fieldName + ".", 400);
  }
  const id = validateShortText(scope.id, fieldName + ".id", 120, false);
  const label = validateShortText(scope.label, fieldName + ".label", 160, false);
  if (!id && !label) return null;
  return { id, label };
}
__name(validateOptionalScope, "validateOptionalScope");
function validateHistory(history) {
  if (!Array.isArray(history)) return [];
  if (history.length > MAX_HISTORY_ITEMS) {
    throw createHttpError("History is too large.", 400);
  }
  return history.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw createHttpError("Invalid history entry at index " + index + ".", 400);
    }
    const role = String(item.role || "").trim();
    if (role !== "user" && role !== "assistant") {
      throw createHttpError("Invalid history role at index " + index + ".", 400);
    }
    return {
      role,
      text: validateShortText(item.text, "history[" + index + "].text", MAX_QUERY_LENGTH, true)
    };
  });
}
__name(validateHistory, "validateHistory");
function validateCandidates(candidates) {
  if (!Array.isArray(candidates) || !candidates.length) {
    throw createHttpError("At least one candidate is required.", 400);
  }
  if (candidates.length > MAX_CANDIDATES) {
    throw createHttpError("Too many candidates.", 400);
  }
  return candidates.map((candidate, index) => {
    if (!candidate || typeof candidate !== "object") {
      throw createHttpError("Invalid candidate at index " + index + ".", 400);
    }
    const badges = Array.isArray(candidate.badges) ? candidate.badges.slice(0, MAX_BADGES).map((badge, badgeIndex) => {
      const text = validateShortText(badge, "candidates[" + index + "].badges[" + badgeIndex + "]", 60, false);
      return text;
    }).filter(Boolean) : [];
    return {
      id: validateShortText(candidate.id, "candidates[" + index + "].id", 120, true),
      title: validateShortText(candidate.title, "candidates[" + index + "].title", 140, true),
      href: validateShortText(candidate.href, "candidates[" + index + "].href", 300, true),
      desc: validateShortText(candidate.desc, "candidates[" + index + "].desc", 360, false),
      domain: validateShortText(candidate.domain, "candidates[" + index + "].domain", 120, false),
      badges,
      categoryLabel: validateShortText(candidate.categoryLabel, "candidates[" + index + "].categoryLabel", 80, false),
      sectionLabel: validateShortText(candidate.sectionLabel, "candidates[" + index + "].sectionLabel", 100, false)
    };
  });
}
__name(validateCandidates, "validateCandidates");
function validateImage(image) {
  if (!image) return null;
  if (typeof image !== "object") {
    throw createHttpError("Invalid image parameter.", 400);
  }
  const mimeType = validateShortText(image.mimeType, "image.mimeType", 80, true);
  const data = String(image.data || "").trim();
  if (!data) {
    throw createHttpError("Missing field: image.data.", 400);
  }
  return { mimeType, data };
}
__name(validateImage, "validateImage");
function validatePayload(payload) {
  if (!payload || typeof payload !== "object") {
    throw createHttpError("Invalid JSON payload.", 400);
  }
  return {
    query: validateShortText(payload.query, "query", MAX_QUERY_LENGTH, true),
    history: validateHistory(payload.history),
    activeCategory: validateOptionalScope(payload.activeCategory, "activeCategory"),
    activeSection: validateOptionalScope(payload.activeSection, "activeSection"),
    candidates: validateCandidates(payload.candidates),
    image: validateImage(payload.image)
  };
}
__name(validatePayload, "validatePayload");
function buildPrompt(data) {
  const historyBlock = data.history.length ? data.history.map((entry, index) => {
    const role = entry.role === "assistant" ? "IA" : "Utilizador";
    return index + 1 + ". " + role + ": " + entry.text;
  }).join("\n") : "Sem hist\xF3rico anterior.";
  const categoryLabel = data.activeCategory && data.activeCategory.label ? data.activeCategory.label : "Nenhuma";
  const sectionLabel = data.activeSection && data.activeSection.label ? data.activeSection.label : "Nenhuma";
  const candidatesBlock = data.candidates.map((candidate, index) => {
    return [
      "Candidato " + (index + 1),
      "ID: " + candidate.id,
      "Nome: " + candidate.title,
      "Categoria: " + (candidate.categoryLabel || "Sem categoria"),
      "Sec\xE7\xE3o: " + (candidate.sectionLabel || "Sem sec\xE7\xE3o"),
      "Dom\xEDnio: " + (candidate.domain || "Sem dom\xEDnio"),
      "Badges: " + (candidate.badges.length ? candidate.badges.join(", ") : "Nenhuma"),
      "Descri\xE7\xE3o: " + (candidate.desc || "Sem descri\xE7\xE3o"),
      "URL: " + candidate.href
    ].join("\n");
  }).join("\n\n");
  return [
    "\xC9s um assistente de recomenda\xE7\xE3o para uma p\xE1gina privada de cat\xE1logo.",
    "Responde sempre em portugu\xEAs europeu (pt-PT).",
    "N\xE3o uses portugu\xEAs do Brasil, nem vocabul\xE1rio brasileiro.",
    "Prefere formas como utilizador, ficheiro, ecr\xE3, telem\xF3vel, registo, equipa e descarregar.",
    "S\xF3 podes recomendar itens presentes nos candidatos fornecidos abaixo.",
    "Nunca inventes sites, nomes, links, categorias ou funcionalidades fora dos candidatos.",
    "Se n\xE3o houver um match claro, admite isso e devolve uma lista vazia.",
    "Se houver candidatos relevantes suficientes, devolve 6 recomendacoes ordenadas da melhor para a menos forte.",
    "Prioriza os candidatos que cobrem mais requisitos explicitos do pedido do utilizador.",
    "Se o pedido tiver dois ou mais termos fortes, evita recomendar candidatos que so correspondam a um deles.",
    "Nao uses mencoes laterais no texto como justificacao principal; a correspondencia deve ser central no titulo, badges, categoria, secao ou descricao.",
    "D\xE1 prefer\xEAncia \xE0 categoria ou sec\xE7\xE3o ativa quando isso fizer sentido, mas escolhe o melhor fit geral.",
    "Mant\xE9m a resposta curta, \xFAtil e profissional.",
    "Devolve JSON estrito neste formato:",
    '{"answer":"texto curto","recommendations":[{"id":"candidate_id","reason":"motivo curto"}]}',
    "",
    "Categoria ativa: " + categoryLabel,
    "Sec\xE7\xE3o ativa: " + sectionLabel,
    "Hist\xF3rico recente:",
    historyBlock,
    "",
    "Pedido atual do utilizador:",
    data.query,
    "",
    "Candidatos dispon\xEDveis:",
    candidatesBlock
  ].join("\n");
}
__name(buildPrompt, "buildPrompt");
async function requestGroq(data, env) {
  let model;
  if (data.image) {
    model = String(env.GROQ_VISION_MODEL || DEFAULT_VISION_MODEL).trim() || DEFAULT_VISION_MODEL;
  } else {
    model = String(env.GROQ_MODEL || DEFAULT_MODEL).trim() || DEFAULT_MODEL;
  }
  const prompt = buildPrompt(data);
  let content;
  if (data.image) {
    content = [
      {
        type: "text",
        text: prompt
      },
      {
        type: "image_url",
        image_url: {
          url: "data:" + data.image.mimeType + ";base64," + data.image.data
        }
      }
    ];
  } else {
    content = prompt;
  }
  const messages = [
    {
      role: "user",
      content
    }
  ];
  const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + env.GEMINI_API_KEY
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.2,
      top_p: 0.9,
      max_tokens: 700,
      response_format: { type: "json_object" }
    })
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload && payload.error && payload.error.message ? String(payload.error.message) : "Groq request failed.";
    throw createHttpError(clampText(message, 260), 502);
  }
  const rawText = extractModelText(payload);
  const parsed = parseModelJson(rawText);
  return sanitizeModelResponse(parsed, data.candidates);
}
__name(requestGroq, "requestGroq");
function extractModelText(payload) {
  const choices = payload && Array.isArray(payload.choices) ? payload.choices : [];
  const firstChoice = choices[0] || {};
  const message = firstChoice.message || {};
  const text = String(message.content || "").trim();
  if (!text) {
    throw createHttpError("Groq returned an empty response.", 502);
  }
  return text;
}
__name(extractModelText, "extractModelText");
function parseModelJson(text) {
  try {
    return JSON.parse(text);
  } catch (_) {
    const match = text.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        return JSON.parse(match[0]);
      } catch (_2) {
      }
    }
  }
  throw createHttpError("Groq returned invalid JSON.", 502);
}
__name(parseModelJson, "parseModelJson");
function sanitizeModelResponse(parsed, candidates) {
  const candidateIds = new Set(candidates.map((candidate) => candidate.id));
  const seen = /* @__PURE__ */ new Set();
  const recommendations = Array.isArray(parsed && parsed.recommendations) ? parsed.recommendations.map((entry) => ({
    id: clampText(entry && entry.id || "", 120),
    reason: clampText(normalizeEuropeanPortuguese(entry && entry.reason || ""), MAX_REASON_LENGTH)
  })).filter((entry) => {
    if (!entry.id || seen.has(entry.id) || !candidateIds.has(entry.id)) return false;
    seen.add(entry.id);
    return true;
  }).slice(0, 6) : [];
  const answer = clampText(normalizeEuropeanPortuguese(parsed && parsed.answer || ""), MAX_ANSWER_LENGTH) || (recommendations.length ? "Estas parecem ser as melhores op\xE7\xF5es dentro do cat\xE1logo fornecido." : "N\xE3o encontrei um match claro no cat\xE1logo fornecido.");
  return {
    answer,
    recommendations
  };
}
__name(sanitizeModelResponse, "sanitizeModelResponse");
function normalizeEuropeanPortuguese(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.replace(/\bvoc[eê]\b/gi, "tu").replace(/\bvoc[eê]s\b/gi, "voc\xEAs").replace(/\busu[aá]rio\b/gi, "utilizador").replace(/\busu[aá]rios\b/gi, "utilizadores").replace(/\bcadastro\b/gi, "registo").replace(/\bcadastrar\b/gi, "registar").replace(/\barquivo\b/gi, "ficheiro").replace(/\barquivos\b/gi, "ficheiros").replace(/\btela\b/gi, "ecr\xE3").replace(/\btelas\b/gi, "ecr\xE3s").replace(/\bcelular\b/gi, "telem\xF3vel").replace(/\bcelulares\b/gi, "telem\xF3veis").replace(/\bbaixar\b/gi, "descarregar").replace(/\bbaixado\b/gi, "descarregado").replace(/\bbaixando\b/gi, "a descarregar").replace(/\bcurtir\b/gi, "gostar").replace(/\bônibus\b/gi, "autocarro").replace(/\btime\b/gi, "equipa").replace(/\blegal\b/gi, "\xF3timo").replace(/\bsite\b/gi, "site");
}
__name(normalizeEuropeanPortuguese, "normalizeEuropeanPortuguese");

// ../../../../AppData/Roaming/npm/node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// ../../../../AppData/Roaming/npm/node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// .wrangler/tmp/bundle-aG3Ejw/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = worker_default;

// ../../../../AppData/Roaming/npm/node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-aG3Ejw/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=worker.js.map
