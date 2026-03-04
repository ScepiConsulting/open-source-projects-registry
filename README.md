# Self-Hosted Knowledge Registry

This repository builds a static, GitHub Pages-hosted knowledge base from `selfhst/cdn`.

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
- `.github/workflows/knowledge-weekly.yml`: weekly run + Pages deploy
- `data/state/readme_state.json`: incremental fetch state
- `site/knowledge/`: generated static knowledge output

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

Fallback behavior:
- If `GH_PAT` is missing, Actions will use `GITHUB_TOKEN`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/harvest_knowledge.py
```

## Output for ChatGPT Project knowledge

Entry point:

- `site/knowledge/manifest.json`

From there:

- chunked apps: `site/knowledge/apps/apps-*.json`
- chunked repos: `site/knowledge/repos/repos-*.json`
- indexes: `site/knowledge/index/by-tag/*.json`, `site/knowledge/index/by-license/*.json`
- readmes: `site/knowledge/readmes/*.md`
- fetch report: `site/knowledge/meta/fetch_report.json`
