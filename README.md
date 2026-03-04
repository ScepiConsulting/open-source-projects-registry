# Self-Hosted Knowledge Registry

This repository builds a structured knowledge base from `selfhst/cdn` and can optionally:
- publish to GitHub Pages
- ingest into Supabase (`registry_apps`)

## What it does

- Pulls source JSON files from `selfhst/cdn` (`directory/*.json` + `directory/integrations/trala.json`)
- Normalizes apps and repo relations
- Fetches README files from repo URLs (GitHub API first, non-GitHub HTTP fallback)
- Uses cached ETag/hash state for incremental refreshes
- Writes static output under `site/knowledge/` for GitHub Pages

## Repository layout

- `config.yaml`: pipeline settings (chunk size, workers, rate/retry limits)
- `scripts/harvest_knowledge.py`: main pipeline
- `scripts/requirements.txt`: Python deps
- `.github/workflows/knowledge-weekly.yml`: weekly run + optional Supabase ingest + optional Pages deploy
- `data/state/readme_state.json`: incremental fetch state
- `site/knowledge/`: generated static knowledge output
- `scripts/ingest_registry_to_supabase.py`: ingests generated manifest/chunks/readmes to Supabase
- `supabase/migrations/*.sql`: table + search function migrations
- `supabase/functions/registry-search/index.ts`: public edge function for search API

## Configuration

Adjust in `config.yaml`:

- `output.apps_chunk_size` (default `50`)
- `output.chunk_max_bytes` (default `2000000`)
- `fetch.max_workers`
- `fetch.github_min_remaining`
- `fetch.retry_*`

## GitHub secrets

Set in repository settings:

- `GH_PAT` (recommended, fine-grained token for GitHub API)
- `SUPABASE_URL` (required for ingest)
- `SUPABASE_SECRET_KEY` (required for ingest; Supabase secret key from API Keys page)
- `EMBEDDING_API_KEY` (optional)
- `SUPABASE_ACCESS_TOKEN` (optional; only if auto-deploying edge functions)
- `SUPABASE_PROJECT_REF` (optional; only if auto-deploying edge functions)

Fallback behavior:
- If `GH_PAT` is missing, Actions will use `GITHUB_TOKEN`.

Optional repository variables:
- `ENABLE_SUPABASE_INGEST=true` (scheduled runs)
- `ENABLE_PAGES_DEPLOY=true` (scheduled runs)
- `ENABLE_DEPLOY_REGISTRY_SEARCH_FUNCTION=true` (scheduled runs)
- `PAGES_CUSTOM_DOMAIN=...` (used when custom domain flag is on)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/harvest_knowledge.py
python scripts/ingest_registry_to_supabase.py --manifest site/knowledge/manifest.json
```

## Workflow flags (manual run)

- `publish_to_pages` (default `false`)
- `use_custom_domain` (default `false`)
- `ingest_to_supabase` (default `true`)
- `deploy_registry_search_function` (default `false`)

## Supabase setup

1. Run migrations:
- `supabase/migrations/202603041900_registry_apps.sql`
- `supabase/migrations/202603041910_registry_search.sql`
2. (Optional) deploy edge function:
- `supabase/functions/registry-search/index.ts`

## Output for ChatGPT Project knowledge

Entry point:

- `site/knowledge/manifest.json`

From there:

- chunked apps: `site/knowledge/apps/apps-*.json`
- chunked repos: `site/knowledge/repos/repos-*.json`
- indexes: `site/knowledge/index/by-tag/*.json`, `site/knowledge/index/by-license/*.json`
- readmes: `site/knowledge/readmes/*.md`
- fetch report: `site/knowledge/meta/fetch_report.json`
