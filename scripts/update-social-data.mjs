import { readFile, writeFile } from "node:fs/promises";

const dataPath = new URL("../assets/data/social.json", import.meta.url);
const data = JSON.parse(await readFile(dataPath, "utf8"));
const now = new Date().toISOString();

const instagramProjects = [
  {
    key: "politiza-te",
    userIdEnv: "IG_USER_ID_POLITIZA_TE",
    tokenEnv: "IG_ACCESS_TOKEN_POLITIZA_TE",
  },
  {
    key: "troca-resposta",
    userIdEnv: "IG_USER_ID_TROCA_RESPOSTA",
    tokenEnv: "IG_ACCESS_TOKEN_TROCA_RESPOSTA",
  },
  {
    key: "noticias-de-ontem",
    userIdEnv: "IG_USER_ID_NOTICIAS_DE_ONTEM",
    tokenEnv: "IG_ACCESS_TOKEN_NOTICIAS_DE_ONTEM",
  },
  {
    key: "politometro",
    userIdEnv: "IG_USER_ID_POLITOMETRO",
    tokenEnv: "IG_ACCESS_TOKEN_POLITOMETRO",
  },
];

async function updateInstagramProject(project) {
  const userId = process.env[project.userIdEnv]?.trim();
  const accessToken =
    process.env[project.tokenEnv]?.trim() ||
    process.env.META_ACCESS_TOKEN?.trim();

  if (!userId || !accessToken) {
    console.log(`[instagram] ${project.key}: credenciais não configuradas; valor anterior preservado.`);
    return;
  }

  const url = new URL(`https://graph.facebook.com/v23.0/${encodeURIComponent(userId)}`);
  url.searchParams.set("fields", "followers_count,username");
  url.searchParams.set("access_token", accessToken);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Meta Graph devolveu HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (!Number.isInteger(payload.followers_count) || payload.followers_count < 0) {
    throw new Error("followers_count em falta ou inválido");
  }

  const current = data.instagram.projects[project.key];
  current.followers = payload.followers_count;
  current.username = payload.username || current.username;
  current.updatedAt = now;
  console.log(`[instagram] ${project.key}: métricas atualizadas.`);
}

function linkedInPostFromApi(post) {
  const id = typeof post.id === "string" ? post.id : "";
  if (!/^urn:li:(?:ugcPost|share):\d+$/.test(id)) return null;
  return {
    id,
    url: `https://www.linkedin.com/feed/update/${id}/`,
    embedUrl: `https://www.linkedin.com/embed/feed/update/${id}`,
    publishedAt:
      typeof post.publishedAt === "number"
        ? new Date(post.publishedAt).toISOString()
        : null,
  };
}

async function updateLinkedIn() {
  const accessToken = process.env.LINKEDIN_ACCESS_TOKEN?.trim();
  const authorUrn = process.env.LINKEDIN_AUTHOR_URN?.trim();
  if (!accessToken || !authorUrn) {
    console.log("[linkedin] credenciais não configuradas; publicações anteriores preservadas.");
    return;
  }

  const url = new URL("https://api.linkedin.com/rest/posts");
  url.searchParams.set("q", "author");
  url.searchParams.set("author", authorUrn);
  url.searchParams.set("sortBy", "LAST_MODIFIED");
  url.searchParams.set("count", "5");
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "LinkedIn-Version": process.env.LINKEDIN_API_VERSION || "202506",
      "X-Restli-Protocol-Version": "2.0.0",
    },
  });
  if (!response.ok) {
    throw new Error(`LinkedIn devolveu HTTP ${response.status}`);
  }

  const payload = await response.json();
  const posts = Array.isArray(payload.elements)
    ? payload.elements.map(linkedInPostFromApi).filter(Boolean)
    : [];
  if (!posts.length) throw new Error("a API não devolveu publicações incorporáveis");

  data.linkedin.posts = posts;
  data.linkedin.updatedAt = now;
  console.log(`[linkedin] ${posts.length} publicações atualizadas.`);
}

for (const project of instagramProjects) {
  try {
    await updateInstagramProject(project);
  } catch (error) {
    console.warn(`[instagram] ${project.key}: atualização falhou; valor anterior preservado (${error.message}).`);
  }
}

try {
  await updateLinkedIn();
} catch (error) {
  console.warn(`[linkedin] atualização falhou; publicações anteriores preservadas (${error.message}).`);
}

await writeFile(dataPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
