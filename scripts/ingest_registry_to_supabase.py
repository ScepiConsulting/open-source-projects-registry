#!/usr/bin/env python3
import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


def utc_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SupabaseIngestor:
    def __init__(self, manifest_path: Path, batch_size: int = 50):
        self.manifest_path = manifest_path
        self.batch_size = batch_size

        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if not self.supabase_url or not self.secret_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

        self.embedding_api_key = os.environ.get("EMBEDDING_API_KEY", "").strip()
        self.embedding_api_url = os.environ.get("EMBEDDING_API_URL", "https://api.openai.com/v1/embeddings")
        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_timeout_sec = int(os.environ.get("EMBEDDING_TIMEOUT_SEC", "30"))

        self.headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

        self.logger = logging.getLogger("supabase-ingest")
        self.stats: Dict[str, Any] = {
            "started_at": utc_ts(),
            "apps_seen": 0,
            "apps_upserted": 0,
            "readme_found": 0,
            "readme_missing": 0,
            "embed_attempted": 0,
            "embed_success": 0,
            "embed_error": 0,
            "upsert_error": 0,
            "chunks_processed": 0,
            "duration_sec": 0,
        }

    def run(self) -> int:
        t0 = time.time()
        manifest = self._load_json(self.manifest_path)
        site_root = self.manifest_path.parent.parent
        app_files = manifest.get("files", {}).get("apps", [])
        if not app_files:
            raise RuntimeError("No app chunk files found in manifest.files.apps")

        self.logger.info("Ingest start: chunks=%s, manifest=%s", len(app_files), self.manifest_path)

        for rel in app_files:
            chunk_path = (site_root / rel).resolve()
            self._process_chunk(chunk_path, site_root)

        self._flush([])
        self.stats["duration_sec"] = int(time.time() - t0)
        self.stats["finished_at"] = utc_ts()
        self.logger.info("Ingest done: %s", json.dumps(self.stats, ensure_ascii=False))
        return 0

    def _process_chunk(self, chunk_path: Path, site_root: Path) -> None:
        chunk = self._load_json(chunk_path)
        items = chunk.get("items", [])
        if not isinstance(items, list):
            return

        self.stats["chunks_processed"] += 1
        self.logger.info("Processing chunk: %s items=%s", chunk_path.name, len(items))

        batch: List[Dict[str, Any]] = []
        for app in items:
            self.stats["apps_seen"] += 1
            row = self._transform_row(app, site_root)
            batch.append(row)

            if len(batch) >= self.batch_size:
                self._flush(batch)
                batch = []

        if batch:
            self._flush(batch)

    def _transform_row(self, app: Dict[str, Any], site_root: Path) -> Dict[str, Any]:
        readme_text = None
        readme_path = app.get("readme_path")
        if readme_path:
            p = (site_root / readme_path).resolve()
            if p.exists() and p.is_file():
                readme_text = p.read_text(encoding="utf-8", errors="replace")
                self.stats["readme_found"] += 1
            else:
                self.stats["readme_missing"] += 1
        else:
            self.stats["readme_missing"] += 1

        embedding = None
        if self.embedding_api_key:
            self.stats["embed_attempted"] += 1
            try:
                embedding = self._embed(app, readme_text)
                if embedding is not None:
                    self.stats["embed_success"] += 1
            except Exception as exc:
                self.stats["embed_error"] += 1
                self.logger.warning("Embedding failed for %s: %s", app.get("reference"), exc)

        row = {
            "id": str(app.get("reference") or "").strip(),
            "name": app.get("name"),
            "description": app.get("description"),
            "tags": app.get("tags") or [],
            "license": app.get("license"),
            "repo_url": app.get("repo_url"),
            "homepage_url": app.get("website"),
            "readme": readme_text,
            "raw": app,
            "updated_at": utc_ts(),
        }

        if embedding is not None:
            # vector input accepted by pgvector/PostgREST as text literal
            row["embedding"] = self._vector_literal(embedding)

        return row

    def _embed(self, app: Dict[str, Any], readme_text: Optional[str]) -> Optional[List[float]]:
        text = "\n\n".join(
            [
                app.get("name") or "",
                app.get("description") or "",
                readme_text or "",
            ]
        ).strip()
        if not text:
            return None

        # Keep payload size bounded
        if len(text) > 20000:
            text = text[:20000]

        body = {
            "model": self.embedding_model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self.embedding_api_url, headers=headers, json=body, timeout=self.embedding_timeout_sec)
        if resp.status_code != 200:
            raise RuntimeError(f"embedding_http_{resp.status_code}: {resp.text[:300]}")
        payload = resp.json()
        data = payload.get("data") or []
        if not data:
            return None
        emb = data[0].get("embedding")
        if not isinstance(emb, list):
            return None
        return [float(x) for x in emb]

    def _flush(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return

        url = f"{self.supabase_url}/rest/v1/registry_apps?on_conflict=id"
        headers = dict(self.headers)
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        resp = requests.post(url, headers=headers, data=json.dumps(rows, ensure_ascii=False), timeout=60)
        if resp.status_code not in (200, 201, 204):
            self.stats["upsert_error"] += len(rows)
            raise RuntimeError(f"upsert_http_{resp.status_code}: {resp.text[:500]}")
        self.stats["apps_upserted"] += len(rows)

    @staticmethod
    def _vector_literal(values: List[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in values) + "]"

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest generated knowledge registry into Supabase")
    p.add_argument(
        "--manifest",
        default="site/knowledge/manifest.json",
        help="Path to generated knowledge manifest",
    )
    p.add_argument("--batch-size", type=int, default=50, help="Upsert batch size")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    ingestor = SupabaseIngestor(Path(args.manifest), batch_size=max(1, args.batch_size))
    return ingestor.run()


if __name__ == "__main__":
    raise SystemExit(main())
