# RepIQ RAG API (Render-ready)

This is the backend "brain" for **The Collective**. It hosts the RepIQ API that your Lovable app calls.

## Deploy on Render (no coding)

1) In Render, click **New → Web Service** and choose **Upload Folder/ZIP**. Upload this folder or the `repiq-api.zip` you downloaded.
2) Render will create a Postgres database from `render.yaml` and inject `DATABASE_URL` automatically.
3) Add these *Environment Variables* in the service:
   - `OPENAI_API_KEY` = your OpenAI key
   - `API_BEARER_TOKEN` = secret for Lovable (default in render.yaml: `supersecrettoken`)
   - `ALLOWED_ORIGINS` = `https://thecollective.lovable.app,http://localhost:3000`
   - `EMBED_MODEL` = `text-embedding-3-large`
   - `EMBED_DIM` = `3072`
4) Deploy and copy the public URL (e.g., `https://repiq-api.onrender.com`).

## Load the packaged NFLPA corpus

Run this one-time command to ingest the CBA/policies from `data/chunks.jsonl` into your DB:

```bash
curl -X POST https://YOUR-RENDER-URL/admin/ingest   -H "Authorization: Bearer supersecrettoken"
```

Then find the workspace UUID:
```sql
SELECT id,name FROM workspaces WHERE name='NFLPA-Prod';
```

Use that `id` as `workspace_id` in `/query`.

## Test /query quickly

```bash
curl -s -X POST https://YOUR-RENDER-URL/query   -H "Authorization: Bearer supersecrettoken"   -H "Content-Type: application/json"   -d '{"workspace_id":"<UUID from workspaces>", "question":"Which article covers Injury Protection?"}'
```
