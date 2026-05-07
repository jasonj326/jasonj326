# seed-grow Worker

Cloudflare Worker that receives a POST from iOS Shortcut (or other client) and
commits a new seed `.md` file to `seeds/posts/` via the GitHub Contents API.
GitHub Actions then auto-rebuilds `seeds/seeds.json`.

```
iPhone Shortcut  →  this Worker  →  GitHub Contents API
                          ↓                    ↓
                    validates secret      writes .md
                    builds .md            triggers Actions
                                                ↓
                                          builds seeds.json
                                                ↓
                                          live on jasonjlai.net
```

## Deploy

1. Cloudflare Dashboard → **Workers & Pages** → Create → name `seed-grow`
2. **Quick Edit** → paste `seed-grow.js` contents → **Save and Deploy**
3. **Settings → Variables and Secrets** add:

| Name | Type | Value |
|------|------|-------|
| `GITHUB_TOKEN` | Secret | PAT with `repo` scope |
| `SEED_SECRET` | Secret | random passcode (e.g. `openssl rand -hex 16`) |
| `GITHUB_OWNER` | Variable | `jasonj326` |
| `GITHUB_REPO` | Variable | `jasonj326` |
| `GITHUB_BRANCH` | Variable | `main` |

4. Note the worker URL (`https://seed-grow.<subdomain>.workers.dev`) — needed
   for the iOS Shortcut.

## API contract

`POST /` with JSON body:

```json
{
  "secret":       "...",          // required, must match SEED_SECRET
  "body":         "seed text",    // required
  "ts":           "2026-05-07T22:15:30+08:00",  // optional, defaults to Taipei now
  "tags":         "humor, philosophy",          // optional, string or array
  "derived_from": "2021-12-31-mrps365"          // optional, parent seed id
}
```

The worker always adds `y<YYYY>` (year tag) automatically. ID = date + HHMMSS.

Success (201):
```json
{ "ok": true, "id": "2026-05-07-221530", "path": "seeds/posts/2026-05-07-221530.md", "commit_url": "..." }
```

Error (400/401/502):
```json
{ "ok": false, "error": "..." }
```

`GET /` returns `{ ok: true, worker: "seed-grow", version: "..." }` for
liveness checks.

## Local test

```bash
curl -X POST https://seed-grow.<subdomain>.workers.dev \
  -H 'Content-Type: application/json' \
  -d '{"secret":"<your-secret>","body":"test seed from curl","tags":"meta"}'
```

## Update / iterate

Edit `seed-grow.js`, paste into Cloudflare Quick Edit, Save and Deploy. Bump
the `VERSION` constant on functional changes for traceability.
