/**
 * seed-grow Worker — receives a POST from iOS Shortcut (or other client),
 * authenticates with a shared secret, then commits a new seed .md file
 * to seeds/posts/ via the GitHub Contents API.
 *
 * Required env / secrets (set in Cloudflare Dashboard → Settings → Variables):
 *   GITHUB_TOKEN  (secret) — PAT with `repo` scope
 *   SEED_SECRET   (secret) — shared passcode required from caller
 *   GITHUB_OWNER          — e.g. "jasonj326"
 *   GITHUB_REPO           — e.g. "jasonj326"
 *   GITHUB_BRANCH         — e.g. "main"
 *
 * Request body (JSON):
 *   {
 *     secret:        string  (required — must match SEED_SECRET)
 *     body:          string  (required — seed body markdown)
 *     ts:            string  (optional — ISO timestamp; defaults to "now" in Taipei TZ)
 *     tags:          string | string[]  (optional — comma/space-separated or array;
 *                                         year tag y<YYYY> is always added automatically)
 *     derived_from:  string  (optional — parent seed ID like "2021-12-31-mrps365")
 *   }
 *
 * Success response (201):
 *   { ok: true, id, path, commit_url }
 *
 * Error responses (400/401/405/502):
 *   { ok: false, error }
 */

const VERSION = "1.0.0";

export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return jsonOk({ ok: true, worker: "seed-grow", version: VERSION });
    }
    if (request.method !== "POST") {
      return jsonError(405, "Method not allowed — use POST");
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return jsonError(400, "Invalid JSON body");
    }

    if (!payload.secret || payload.secret !== env.SEED_SECRET) {
      return jsonError(401, "Invalid or missing secret");
    }

    const body = String(payload.body || "").trim();
    if (!body) {
      return jsonError(400, "Missing 'body' field");
    }

    // Timestamp + ID (date + HHMMSS for human-readability + collision avoidance)
    const ts = isValidIso(payload.ts) ? payload.ts : taipeiNow();
    const date = ts.slice(0, 10);                 // YYYY-MM-DD
    const time = ts.slice(11, 19).replace(/:/g, ""); // HHMMSS
    const id = `${date}-${time}`;
    const path = `seeds/posts/${id}.md`;

    // Tags: always include y<year>, plus user-supplied (deduped)
    const year = date.slice(0, 4);
    const userTags = parseTagsInput(payload.tags);
    const tags = [`y${year}`, ...userTags.filter((t) => t !== `y${year}`)];

    // Frontmatter + body
    const fm = ["---", `id: ${id}`, `ts: ${ts}`, "tags:"];
    for (const t of tags) fm.push(`  - ${t}`);
    const derivedFrom = String(payload.derived_from || "").trim();
    if (derivedFrom) fm.push(`derived_from: ${derivedFrom}`);
    fm.push("---", "", body, "");
    const fileContent = fm.join("\n");

    // PUT to GitHub Contents API
    const owner = env.GITHUB_OWNER;
    const repo = env.GITHUB_REPO;
    const branch = env.GITHUB_BRANCH || "main";
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;

    const ghRes = await fetch(apiUrl, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "seed-grow-worker",
      },
      body: JSON.stringify({
        message: `Grow: seed ${id}`,
        content: utf8ToBase64(fileContent),
        branch,
      }),
    });

    if (!ghRes.ok) {
      const errText = await ghRes.text();
      return jsonError(
        502,
        `GitHub API ${ghRes.status}: ${errText.slice(0, 300)}`,
      );
    }
    const result = await ghRes.json();
    return new Response(
      JSON.stringify({
        ok: true,
        id,
        path,
        commit_url: result.commit && result.commit.html_url,
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    );
  },
};

function jsonError(status, message) {
  return new Response(JSON.stringify({ ok: false, error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function jsonOk(obj) {
  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function isValidIso(s) {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(s);
}

// Format current time as ISO with Taipei (UTC+8) offset
function taipeiNow() {
  const now = new Date();
  const tp = new Date(now.getTime() + 8 * 3600 * 1000);
  const Y = tp.getUTCFullYear();
  const M = String(tp.getUTCMonth() + 1).padStart(2, "0");
  const D = String(tp.getUTCDate()).padStart(2, "0");
  const h = String(tp.getUTCHours()).padStart(2, "0");
  const m = String(tp.getUTCMinutes()).padStart(2, "0");
  const s = String(tp.getUTCSeconds()).padStart(2, "0");
  return `${Y}-${M}-${D}T${h}:${m}:${s}+08:00`;
}

// Accept tags as array or comma/space-separated string
function parseTagsInput(input) {
  if (!input) return [];
  const arr = Array.isArray(input)
    ? input
    : String(input).split(/[,\s]+/);
  return arr.map((s) => String(s).trim()).filter(Boolean);
}

// UTF-8 safe base64 encoding (handles CJK)
function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
