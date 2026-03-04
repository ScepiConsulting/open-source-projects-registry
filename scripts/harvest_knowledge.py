#!/usr/bin/env python3
import concurrent.futures
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import requests
import yaml


@dataclasses.dataclass
class RepoTask:
    repo_key: str
    repo_url: str
    host: str
    owner: str
    repo: str


class Harvester:
    def __init__(self, config: Dict[str, Any]):
        self.cfg = config
        self.fetch_cfg = config["fetch"]
        self.output_cfg = config["output"]
        self.schema_cfg = config["schema"]
        self.state_cfg = config["state"]
        self.user_agent = self.fetch_cfg.get("user_agent", "selfhst-knowledge-harvester")
        self.timeout = int(self.fetch_cfg.get("timeout_sec", 25))
        self.max_workers = int(self.fetch_cfg.get("max_workers", 6))
        self.retry_max = int(self.fetch_cfg.get("retry_max", 5))
        self.retry_base = float(self.fetch_cfg.get("retry_base_sec", 1.5))
        self.retry_max_sec = int(self.fetch_cfg.get("retry_max_sec", 90))
        self.github_min_remaining = int(self.fetch_cfg.get("github_min_remaining", 120))
        self.github_max_pause = int(self.fetch_cfg.get("github_max_pause_sec", 900))
        self.include_readme_text = bool(self.fetch_cfg.get("include_readme_text_in_repo", True))
        self.write_pretty_json = bool(self.output_cfg.get("write_pretty_json", True))

        self.github_token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
        self.rate_lock = threading.Lock()
        self.rate_resume_at = 0.0

        self.source_cache: Dict[str, Any] = {}
        self.repo_state = self._load_state()
        self.fetch_results: Dict[str, Dict[str, Any]] = {}

        self.knowledge_root = Path(self.output_cfg["knowledge_root"])
        self.site_root = Path(self.output_cfg["site_root"])
        self.readmes_root = self.knowledge_root / "readmes"
        self.apps_root = self.knowledge_root / "apps"
        self.repos_root = self.knowledge_root / "repos"
        self.index_root = self.knowledge_root / "index"
        self.meta_root = self.knowledge_root / "meta"
        self.logger = logging.getLogger("harvester")

    def run(self) -> int:
        self._log("Starting knowledge harvest")
        self._ensure_dirs()
        self._write_text(self.site_root / ".nojekyll", "")

        self._log("Loading source JSON files")
        source = self._load_sources()
        self._log("Normalizing source data")
        normalized = self._normalize(source)
        repo_tasks = self._build_repo_tasks(normalized["repos"])
        self._log(
            f"Prepared normalized dataset: apps={len(normalized['apps'])}, repos={len(repo_tasks)}, "
            f"github_token={'yes' if bool(self.github_token) else 'no'}"
        )
        self._log("Fetching README files")
        self.fetch_results = self._fetch_all_readmes(repo_tasks)

        self._log("Building static site payload")
        site_payload = self._build_site_payload(normalized)
        self._log("Writing static output files")
        self._write_site(site_payload)
        self._log("Persisting state/report")
        self._write_state()
        self._write_report(site_payload)
        self._log("Harvest finished")
        return 0

    def _ensure_dirs(self) -> None:
        for path in [
            self.site_root,
            self.knowledge_root,
            self.readmes_root,
            self.apps_root,
            self.repos_root,
            self.index_root / "by-tag",
            self.index_root / "by-license",
            self.meta_root,
            Path(self.state_cfg["file"]).parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        state_path = Path(self.state_cfg["file"])
        if not state_path.exists():
            return {"repos": {}, "updated_at": None}
        with state_path.open("r", encoding="utf-8") as f:
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                return {"repos": {}, "updated_at": None}
        if "repos" not in state or not isinstance(state["repos"], dict):
            state["repos"] = {}
        return state

    def _write_state(self) -> None:
        self.repo_state["updated_at"] = utc_now()
        self._write_json(Path(self.state_cfg["file"]), self.repo_state)

    def _load_sources(self) -> Dict[str, Any]:
        base_url = self.cfg["source"]["base_raw_url"].rstrip("/")
        files = self.cfg["source"]["files"]
        loaded: Dict[str, Any] = {}
        for rel in files:
            url = f"{base_url}/{rel}"
            self._log(f"Loading source: {rel}")
            loaded[rel] = self._get_json(url)
        self.source_cache = loaded
        return loaded

    def _get_json(self, url: str) -> Any:
        res = self._request("GET", url, headers={"Accept": "application/json"}, provider="generic")
        return res.json()

    def _normalize(self, source: Dict[str, Any]) -> Dict[str, Any]:
        software = source.get("software.json", [])
        tags = source.get("tags.json", [])
        licenses = source.get("licenses.json", [])
        trala = source.get("integrations/trala.json", [])

        tags_map = self._build_id_map(tags)
        license_map = self._build_id_map(licenses)
        trala_map = self._build_trala_tag_map(trala)

        apps: List[Dict[str, Any]] = []
        repos: Dict[str, Dict[str, Any]] = {}

        for row in software:
            app = self._normalize_software_row(row, tags_map, license_map, trala_map)
            if not app:
                continue
            apps.append(app)

            repo_key = app.get("repo_key")
            if repo_key:
                repo = repos.setdefault(
                    repo_key,
                    {
                        "repo_key": repo_key,
                        "repo_url": app.get("repo_url"),
                        "host": app.get("repo_host"),
                        "owner": app.get("repo_owner"),
                        "repo": app.get("repo_name"),
                        "app_references": [],
                    },
                )
                repo["app_references"].append(app.get("reference"))

        apps.sort(key=lambda x: (x.get("name") or "").lower())
        for repo in repos.values():
            repo["app_references"] = sorted(set(repo["app_references"]))

        return {
            "apps": apps,
            "repos": sorted(repos.values(), key=lambda x: x["repo_key"]),
            "tags": tags,
            "licenses": licenses,
            "languages": source.get("languages.json", []),
            "activitypub": source.get("activitypub.json", []),
            "alternatives": source.get("alternatives.json", []),
            "companions": source.get("companions.json", []),
            "companion_software": source.get("companion-software.json", []),
            "trala": trala,
        }

    def _build_id_map(self, rows: Any) -> Dict[int, Dict[str, Any]]:
        out: Dict[int, Dict[str, Any]] = {}
        if isinstance(rows, dict):
            for key, value in rows.items():
                rid = safe_int(key)
                if rid is None:
                    continue
                if isinstance(value, dict):
                    out[rid] = {"id": rid, "name": value.get("name") or str(rid), "raw": value}
                else:
                    out[rid] = {"id": rid, "name": str(value), "raw": value}
            return out
        if not isinstance(rows, list):
            return out
        for r in rows:
            if isinstance(r, list) and r:
                rid = safe_int(r[0])
                if rid is not None:
                    out[rid] = {"id": rid, "name": r[1] if len(r) > 1 else str(rid), "raw": r}
            elif isinstance(r, dict):
                rid = safe_int(r.get("id"))
                if rid is not None:
                    out[rid] = {"id": rid, "name": r.get("name") or str(rid), "raw": r}
        return out

    def _build_trala_tag_map(self, trala_rows: Any) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        if not isinstance(trala_rows, list):
            return out
        for row in trala_rows:
            if not isinstance(row, dict):
                continue
            ref = clean_text(row.get("reference"))
            if not ref:
                continue
            tags = row.get("tags")
            if not isinstance(tags, list):
                continue
            names = sorted({clean_text(tag) for tag in tags if clean_text(tag)})
            if names:
                out[ref] = names
        return out

    def _normalize_software_row(
        self,
        row: Any,
        tags_map: Dict[int, Dict[str, Any]],
        license_map: Dict[int, Dict[str, Any]],
        trala_map: Dict[str, List[str]],
    ) -> Optional[Dict[str, Any]]:
        if isinstance(row, dict):
            app = {
                "software_id": row.get("id"),
                "name": row.get("name"),
                "reference": row.get("reference"),
                "website": row.get("website"),
                "repo_url": row.get("repo") or row.get("repository") or row.get("repo_url"),
                "description": row.get("description"),
                "stars": row.get("stars"),
                "forks": row.get("forks"),
                "updated_at": row.get("updated_at") or row.get("updated"),
                "raw": row,
            }
            tag_ids = parse_tag_ids_from_value(row.get("tags"))
            license_id = safe_int(row.get("license_id") or row.get("license"))
        elif isinstance(row, list):
            cols = self.schema_cfg["software_columns"]
            opt = self.schema_cfg.get("optional_indices", {})
            app = {
                "software_id": self._row_get(row, cols.get("id")),
                "name": self._row_get(row, cols.get("name")),
                "reference": self._row_get(row, cols.get("reference")),
                "website": self._row_get(row, cols.get("website")),
                "repo_url": self._row_get(row, cols.get("repo_url")),
                "description": self._row_get(row, cols.get("description")),
                "stars": self._row_get(row, opt.get("stars")),
                "forks": self._row_get(row, opt.get("forks")),
                "updated_at": self._row_get(row, opt.get("updated_at")),
                "raw": row,
            }
            tag_ids = parse_tag_ids_from_value(self._row_get(row, opt.get("tag_ids")))
            if not tag_ids:
                tag_ids = self._guess_tag_ids(row, tags_map)
            license_id = safe_int(self._row_get(row, opt.get("license_id")))
        else:
            return None

        app["reference"] = clean_text(app.get("reference"))
        app["name"] = clean_text(app.get("name"))
        if not app["reference"] or not app["name"]:
            return None

        repo_info = parse_repo_url(clean_text(app.get("repo_url")))
        app.update(
            {
                "repo_key": repo_info["repo_key"],
                "repo_host": repo_info["host"],
                "repo_owner": repo_info["owner"],
                "repo_name": repo_info["repo"],
            }
        )

        resolved_tags = []
        for tid in tag_ids:
            t = tags_map.get(tid)
            if t:
                resolved_tags.append({"id": tid, "name": t["name"]})

        license_name = None
        if license_id is not None and license_id in license_map:
            license_name = license_map[license_id]["name"]

        app["tag_ids"] = tag_ids
        official_tags = sorted({t["name"] for t in resolved_tags})
        trala_tags = trala_map.get(app["reference"], [])
        app["tags"] = sorted(set(official_tags) | set(trala_tags))
        app["tags_source"] = (
            "official+trala"
            if official_tags and trala_tags
            else ("official" if official_tags else ("trala" if trala_tags else "none"))
        )
        app["license_id"] = license_id
        app["license_name"] = license_name
        app["stars"] = safe_int(app.get("stars"))
        app["forks"] = safe_int(app.get("forks"))
        app["description"] = clean_text(app.get("description"))
        app["website"] = clean_text(app.get("website"))
        app["repo_url"] = clean_text(app.get("repo_url"))

        app["provenance"] = {
            "source": "selfhst/cdn directory/software.json",
            "fetched_at": utc_now(),
            "row_hash": sha256_json(app.get("raw")),
        }
        return app

    def _row_get(self, row: List[Any], idx: Optional[int]) -> Any:
        if idx is None:
            return None
        if not isinstance(idx, int):
            return None
        if idx < 0 or idx >= len(row):
            return None
        return row[idx]

    def _guess_tag_ids(self, row: List[Any], tags_map: Dict[int, Dict[str, Any]]) -> List[int]:
        known_ids = set(tags_map.keys())
        best: List[int] = []
        for value in row:
            ids = parse_tag_ids_from_value(value)
            if not ids:
                continue
            if set(ids).issubset(known_ids) and len(ids) > len(best):
                best = ids
        return best

    def _build_repo_tasks(self, repos: List[Dict[str, Any]]) -> List[RepoTask]:
        tasks: List[RepoTask] = []
        for r in repos:
            if not r.get("repo_url"):
                continue
            tasks.append(
                RepoTask(
                    repo_key=r["repo_key"],
                    repo_url=r["repo_url"],
                    host=r.get("host") or "",
                    owner=r.get("owner") or "",
                    repo=r.get("repo") or "",
                )
            )
        return tasks

    def _fetch_all_readmes(self, tasks: List[RepoTask]) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        if not tasks:
            return results

        total = len(tasks)
        completed = 0
        started_at = time.time()
        self._log(f"README fetch queue started: {total} repos, workers={self.max_workers}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {pool.submit(self._fetch_readme_for_repo, task): task for task in tasks}
            pending = set(future_map.keys())

            while pending:
                done, pending = concurrent.futures.wait(
                    pending,
                    timeout=20,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                if not done:
                    elapsed = int(time.time() - started_at)
                    self._log(f"README fetch heartbeat: {completed}/{total} completed, elapsed={elapsed}s")
                    continue

                for fut in done:
                    task = future_map[fut]
                    try:
                        result = fut.result()
                    except Exception as exc:
                        result = {
                            "status": "error",
                            "error": f"worker_exception: {exc}",
                            "repo_key": task.repo_key,
                            "repo_url": task.repo_url,
                        }
                    results[task.repo_key] = result
                    completed += 1
                    if completed == total or completed % 25 == 0:
                        elapsed = int(time.time() - started_at)
                        self._log(f"README progress: {completed}/{total} completed, elapsed={elapsed}s")
        return results

    def _fetch_readme_for_repo(self, task: RepoTask) -> Dict[str, Any]:
        previous = self.repo_state["repos"].get(task.repo_key, {})
        etag = previous.get("etag")

        if task.host in {"github.com", "www.github.com"} and task.owner and task.repo:
            result = self._fetch_readme_github(task, etag)
        else:
            result = self._fetch_readme_generic(task)

        state_entry = {
            "repo_url": task.repo_url,
            "repo_key": task.repo_key,
            "host": task.host,
            "updated_at": utc_now(),
            "status": result.get("status"),
            "etag": result.get("etag") or previous.get("etag"),
            "readme_sha256": result.get("readme_sha256") or previous.get("readme_sha256"),
            "readme_path": result.get("readme_path") or previous.get("readme_path"),
            "last_error": result.get("error"),
        }
        self.repo_state["repos"][task.repo_key] = state_entry
        return result

    def _fetch_readme_github(self, task: RepoTask, etag: Optional[str]) -> Dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        if etag:
            headers["If-None-Match"] = etag

        url = f"https://api.github.com/repos/{task.owner}/{task.repo}/readme"
        resp = self._request("GET", url, headers=headers, provider="github")

        if resp.status_code == 304:
            prior = self.repo_state["repos"].get(task.repo_key, {})
            return {
                "status": "not_modified",
                "repo_key": task.repo_key,
                "repo_url": task.repo_url,
                "etag": prior.get("etag") or etag,
                "readme_path": prior.get("readme_path"),
                "readme_sha256": prior.get("readme_sha256"),
            }

        if resp.status_code != 200:
            return {
                "status": "error",
                "repo_key": task.repo_key,
                "repo_url": task.repo_url,
                "error": f"github_readme_http_{resp.status_code}",
            }

        payload = resp.json()
        readme_text = decode_github_content(payload)
        if not readme_text.strip():
            return {
                "status": "error",
                "repo_key": task.repo_key,
                "repo_url": task.repo_url,
                "error": "empty_readme",
            }

        readme_rel = self._write_readme(task.repo_key, readme_text)
        return {
            "status": "ok",
            "repo_key": task.repo_key,
            "repo_url": task.repo_url,
            "etag": resp.headers.get("ETag"),
            "readme_path": readme_rel,
            "readme_sha256": sha256_text(readme_text),
            "readme_html_url": payload.get("html_url"),
            "readme_download_url": payload.get("download_url"),
            "source": "github_api",
        }

    def _fetch_readme_generic(self, task: RepoTask) -> Dict[str, Any]:
        candidates = list(self._generic_candidate_urls(task.repo_url, task.host, task.owner, task.repo))
        for candidate in candidates:
            resp = self._request("GET", candidate, headers={"User-Agent": self.user_agent}, provider="generic")
            if resp.status_code == 200 and resp.text.strip():
                readme_rel = self._write_readme(task.repo_key, resp.text)
                return {
                    "status": "ok",
                    "repo_key": task.repo_key,
                    "repo_url": task.repo_url,
                    "readme_path": readme_rel,
                    "readme_sha256": sha256_text(resp.text),
                    "readme_download_url": candidate,
                    "source": "generic_candidate",
                }

        html_guess = self._scrape_readme_link(task.repo_url)
        if html_guess:
            resp = self._request("GET", html_guess, headers={"User-Agent": self.user_agent}, provider="generic")
            if resp.status_code == 200 and resp.text.strip():
                readme_rel = self._write_readme(task.repo_key, resp.text)
                return {
                    "status": "ok",
                    "repo_key": task.repo_key,
                    "repo_url": task.repo_url,
                    "readme_path": readme_rel,
                    "readme_sha256": sha256_text(resp.text),
                    "readme_download_url": html_guess,
                    "source": "generic_html_scrape",
                }

        return {
            "status": "error",
            "repo_key": task.repo_key,
            "repo_url": task.repo_url,
            "error": "readme_not_found",
        }

    def _generic_candidate_urls(self, repo_url: str, host: str, owner: str, repo: str) -> Iterable[str]:
        root = repo_url.rstrip("/")
        filenames = ["README.md", "Readme.md", "README.rst", "README.txt", "README"]
        branches = ["main", "master", "trunk"]

        # GitLab-style raw URLs
        for b in branches:
            for f in filenames:
                yield f"{root}/-/raw/{b}/{f}"

        # Gitea/Codeberg-like raw URLs
        for b in branches:
            for f in filenames:
                yield f"{root}/raw/{b}/{f}"

        if host == "gitlab.com" and owner and repo:
            project = quote(f"{owner}/{repo}", safe="")
            for f in filenames:
                yield f"https://gitlab.com/api/v4/projects/{project}/repository/files/{quote(f, safe='')}/raw?ref=HEAD"

    def _scrape_readme_link(self, repo_url: str) -> Optional[str]:
        try:
            resp = self._request("GET", repo_url, headers={"User-Agent": self.user_agent}, provider="generic")
        except Exception:
            return None
        if resp.status_code != 200:
            return None

        html = resp.text[:500000]
        links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        for link in links:
            ll = link.lower()
            if "readme" not in ll:
                continue
            full = urljoin(repo_url, link)
            raw = to_raw_url(full)
            if raw:
                return raw
        return None

    def _write_readme(self, repo_key: str, text: str) -> str:
        safe_key = repo_key.replace("/", "__")
        path = self.readmes_root / f"{safe_key}.md"
        if self.include_readme_text:
            self._write_text(path, text)
        return str(path.relative_to(self.site_root)).replace("\\", "/")

    def _build_site_payload(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        apps = []
        repos = []

        for app in normalized["apps"]:
            repo_result = self.fetch_results.get(app.get("repo_key") or "", {})
            app_record = {
                "reference": app.get("reference"),
                "name": app.get("name"),
                "website": app.get("website"),
                "description": app.get("description"),
                "repo_url": app.get("repo_url"),
                "repo_key": app.get("repo_key"),
                "stars": app.get("stars"),
                "forks": app.get("forks"),
                "updated_at": app.get("updated_at"),
                "license": app.get("license_name"),
                "tags": app.get("tags"),
                "readme_path": repo_result.get("readme_path"),
                "readme_status": repo_result.get("status"),
                "provenance": app.get("provenance"),
            }
            apps.append(app_record)

        for repo in normalized["repos"]:
            rr = self.fetch_results.get(repo["repo_key"], {})
            repos.append(
                {
                    **repo,
                    "readme_status": rr.get("status"),
                    "readme_path": rr.get("readme_path"),
                    "readme_download_url": rr.get("readme_download_url"),
                    "readme_sha256": rr.get("readme_sha256"),
                    "error": rr.get("error"),
                }
            )

        by_tag: Dict[str, List[str]] = {}
        by_license: Dict[str, List[str]] = {}
        for a in apps:
            for t in a.get("tags") or []:
                by_tag.setdefault(t, []).append(a["reference"])
            if a.get("license"):
                by_license.setdefault(a["license"], []).append(a["reference"])

        for idx in [by_tag, by_license]:
            for key, refs in idx.items():
                idx[key] = sorted(set(refs))

        return {
            "generated_at": utc_now(),
            "apps": apps,
            "repos": repos,
            "by_tag": by_tag,
            "by_license": by_license,
            "meta": {
                "source_base": self.cfg["source"]["base_raw_url"],
                "source_files": self.cfg["source"]["files"],
                "counts": {
                    "apps": len(apps),
                    "repos": len(repos),
                    "readme_ok": sum(1 for x in self.fetch_results.values() if x.get("status") == "ok"),
                    "readme_not_modified": sum(
                        1 for x in self.fetch_results.values() if x.get("status") == "not_modified"
                    ),
                    "readme_error": sum(1 for x in self.fetch_results.values() if x.get("status") == "error"),
                },
            },
        }

    def _write_site(self, payload: Dict[str, Any]) -> None:
        chunk_size = int(self.output_cfg.get("apps_chunk_size", 50))
        chunk_max_bytes = int(self.output_cfg.get("chunk_max_bytes", 2_000_000))

        for path in self.apps_root.glob("*.json"):
            path.unlink()
        for path in self.repos_root.glob("*.json"):
            path.unlink()

        app_files = self._write_chunks(payload["apps"], self.apps_root, "apps", chunk_size, chunk_max_bytes)
        repo_files = self._write_chunks(payload["repos"], self.repos_root, "repos", chunk_size, chunk_max_bytes)

        by_tag_files = []
        for tag, refs in sorted(payload["by_tag"].items(), key=lambda x: x[0].lower()):
            slug = slugify(tag)
            p = self.index_root / "by-tag" / f"{slug}.json"
            self._write_json(p, {"tag": tag, "references": refs})
            by_tag_files.append(str(p.relative_to(self.site_root)).replace("\\", "/"))

        by_license_files = []
        for license_name, refs in sorted(payload["by_license"].items(), key=lambda x: x[0].lower()):
            slug = slugify(license_name)
            p = self.index_root / "by-license" / f"{slug}.json"
            self._write_json(p, {"license": license_name, "references": refs})
            by_license_files.append(str(p.relative_to(self.site_root)).replace("\\", "/"))

        manifest = {
            "generated_at": payload["generated_at"],
            "meta": payload["meta"],
            "files": {
                "apps": app_files,
                "repos": repo_files,
                "index_by_tag": by_tag_files,
                "index_by_license": by_license_files,
                "report": str(Path(self.state_cfg["report_file"]).relative_to(self.site_root)).replace("\\", "/"),
            },
        }
        self._write_json(self.knowledge_root / "manifest.json", manifest)

    def _write_chunks(
        self,
        rows: List[Dict[str, Any]],
        out_dir: Path,
        prefix: str,
        chunk_size: int,
        chunk_max_bytes: int,
    ) -> List[str]:
        files: List[str] = []
        chunk: List[Dict[str, Any]] = []
        chunk_idx = 1

        def flush() -> None:
            nonlocal chunk_idx, chunk
            if not chunk:
                return
            path = out_dir / f"{prefix}-{chunk_idx:04d}.json"
            payload = {
                "chunk": chunk_idx,
                "count": len(chunk),
                "generated_at": utc_now(),
                "items": chunk,
            }
            self._write_json(path, payload)
            files.append(str(path.relative_to(self.site_root)).replace("\\", "/"))
            chunk_idx += 1
            chunk = []

        for row in rows:
            row_size = len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
            chunk_size_bytes = len(json.dumps(chunk, ensure_ascii=False).encode("utf-8")) if chunk else 0
            if chunk and (len(chunk) >= chunk_size or (chunk_size_bytes + row_size) > chunk_max_bytes):
                flush()
            chunk.append(row)
        flush()
        return files

    def _write_report(self, payload: Dict[str, Any]) -> None:
        failed = []
        for repo_key, result in sorted(self.fetch_results.items()):
            if result.get("status") == "error":
                failed.append(
                    {
                        "repo_key": repo_key,
                        "repo_url": result.get("repo_url"),
                        "error": result.get("error"),
                    }
                )

        report = {
            "generated_at": payload["generated_at"],
            "summary": payload["meta"]["counts"],
            "failed_repos": failed,
        }
        self._write_json(Path(self.state_cfg["report_file"]), report)
        self._write_json(self.meta_root / "failed_repos.json", failed)

    def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        provider: str = "generic",
    ) -> requests.Response:
        headers = headers or {}
        headers.setdefault("User-Agent", self.user_agent)

        for attempt in range(self.retry_max + 1):
            self._wait_for_rate_window()
            try:
                resp = requests.request(method, url, headers=headers, timeout=self.timeout)
            except requests.RequestException:
                if attempt >= self.retry_max:
                    raise
                self._sleep_backoff(attempt)
                continue

            if provider == "github":
                self._update_rate_limit(resp)

            if resp.status_code in {429, 500, 502, 503, 504}:
                if attempt >= self.retry_max:
                    return resp
                retry_after = parse_retry_after(resp.headers.get("Retry-After"))
                if retry_after is not None:
                    time.sleep(min(retry_after, self.retry_max_sec))
                else:
                    self._sleep_backoff(attempt)
                continue
            return resp

        raise RuntimeError("unreachable")

    def _wait_for_rate_window(self) -> None:
        with self.rate_lock:
            resume = self.rate_resume_at
        if resume > time.time():
            wait_s = min(resume - time.time(), self.github_max_pause)
            if wait_s > 5:
                self._log(f"Rate-limit pause: sleeping {int(wait_s)}s")
            time.sleep(wait_s)

    def _update_rate_limit(self, resp: requests.Response) -> None:
        remaining = safe_int(resp.headers.get("X-RateLimit-Remaining"))
        reset_epoch = safe_int(resp.headers.get("X-RateLimit-Reset"))
        if remaining is None:
            return
        if remaining >= self.github_min_remaining:
            return
        pause_until = time.time() + 10
        if reset_epoch is not None:
            pause_until = min(float(reset_epoch) + 2.0, time.time() + self.github_max_pause)
        with self.rate_lock:
            self.rate_resume_at = max(self.rate_resume_at, pause_until)

    def _sleep_backoff(self, attempt: int) -> None:
        base = min(self.retry_base * (2**attempt), float(self.retry_max_sec))
        time.sleep(base + random.uniform(0.0, 0.5))

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            if self.write_pretty_json:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            else:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(text)

    def _log(self, message: str) -> None:
        self.logger.info(message)


# Helpers

def utc_now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return None
    return None


def parse_tag_ids_from_value(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, list):
        out = [safe_int(x) for x in value]
        return [x for x in out if x is not None]

    text = str(value).strip()
    if not text:
        return []
    if not re.fullmatch(r"\d+(,\d+)*", text):
        return []
    return [int(x) for x in text.split(",") if x]


def parse_repo_url(url: Optional[str]) -> Dict[str, str]:
    if not url:
        return {"repo_key": "", "host": "", "owner": "", "repo": ""}
    raw = url.strip()
    if raw.startswith("git@"):
        # git@github.com:owner/repo.git
        match = re.match(r"^git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$", raw)
        if not match:
            return {"repo_key": "", "host": "", "owner": "", "repo": ""}
        host, owner, repo = match.group(1).lower(), match.group(2), match.group(3)
    else:
        if raw.startswith("www."):
            raw = "https://" + raw
        if not raw.startswith("http"):
            raw = "https://" + raw
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            return {"repo_key": "", "host": "", "owner": "", "repo": ""}
        owner, repo = parts[0], parts[1]
    repo = repo[:-4] if repo.endswith(".git") else repo
    key = f"{host}/{owner}/{repo}"
    return {"repo_key": key, "host": host, "owner": owner, "repo": repo}


def decode_github_content(payload: Dict[str, Any]) -> str:
    encoding = payload.get("encoding")
    content = payload.get("content", "")
    if encoding == "base64" and content:
        import base64

        try:
            decoded = base64.b64decode(content)
        except Exception:
            return ""
        return decoded.decode("utf-8", errors="replace")
    return ""


def parse_retry_after(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    v = safe_int(value)
    if v is not None and v >= 0:
        return v
    return None


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def to_raw_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    if host in {"github.com", "www.github.com"}:
        # /owner/repo/blob/branch/path/to/file
        match = re.match(r"^/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", path)
        if match:
            owner, repo, branch, rel = match.groups()
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rel}"
    if host == "gitlab.com":
        # /owner/repo/-/blob/branch/path
        match = re.match(r"^/([^/]+/[^/]+)/-/blob/([^/]+)/(.+)$", path)
        if match:
            project, branch, rel = match.groups()
            return f"https://gitlab.com/{project}/-/raw/{branch}/{rel}"
    if "codeberg.org" in host or "gitea" in host:
        match = re.match(r"^/([^/]+)/([^/]+)/src/branch/([^/]+)/(.+)$", path)
        if match:
            owner, repo, branch, rel = match.groups()
            return f"https://{host}/{owner}/{repo}/raw/branch/{branch}/{rel}"

    if re.search(r"readme", path, flags=re.IGNORECASE):
        return url
    return None


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config_path = Path(os.getenv("KNOWLEDGE_CONFIG", "config.yaml"))
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}")
        return 2
    cfg = load_config(config_path)
    harvester = Harvester(cfg)
    return harvester.run()


if __name__ == "__main__":
    raise SystemExit(main())
