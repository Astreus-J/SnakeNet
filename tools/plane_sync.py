#!/usr/bin/env python3
"""Create the SnakeNet cycles and issues in Plane from project-management/plane/plan.json.

Dry run by default. To apply:
    export PLANE_API_KEY=... PLANE_BASE_URL=http://localhost:80 \
           PLANE_WORKSPACE_SLUG=<workspace> PLANE_PROJECT_IDENTIFIER=<existing project identifier>
    python tools/plane_sync.py --apply

Use a project dedicated to SnakeNet: the script creates/updates cycles and issues matched by NAME in the
project you point it at, and never creates projects. The key is read from the environment, never printed or stored.
Same variable names and API calls as JuriSense's scripts/plane/bootstrap.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "project-management" / "plane" / "plan.json"
STATE_GROUP = {"done": "completed", "todo": "unstarted"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="really call the Plane API (default: dry run)")
    args = ap.parse_args()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))

    if not args.apply:
        print(f"DRY RUN: would sync {len(plan['cycles'])} cycles and {len(plan['issues'])} issues")
        for c in plan["cycles"]:
            print(f"\n{c['name']}  ({c['start_date']} -> {c['end_date']})")
            for i in plan["issues"]:
                if i["cycle"] == c["key"]:
                    flag = " [needs human]" if i["needs_human"] else ""
                    print(f"  [{i['state']:4}] {i['title']}{flag}")
        return 0

    missing = [v for v in ("PLANE_API_KEY", "PLANE_BASE_URL", "PLANE_WORKSPACE_SLUG", "PLANE_PROJECT_IDENTIFIER") if not os.environ.get(v)]
    if missing:
        print("Missing environment variables: " + ", ".join(missing), file=sys.stderr)
        return 1
    key, base = os.environ["PLANE_API_KEY"], os.environ["PLANE_BASE_URL"].rstrip("/")
    ws, ident = os.environ["PLANE_WORKSPACE_SLUG"], os.environ["PLANE_PROJECT_IDENTIFIER"]
    api = f"{base}/api/v1"

    def call(method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(api + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("X-API-Key", key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                time.sleep(0.6)  # stay under Plane's rate limit
                return r.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def list_all(path: str) -> list[dict]:
        out, cursor = [], None
        while True:
            sep = "&" if "?" in path else "?"
            status, body = call("GET", path + (f"{sep}cursor={cursor}" if cursor else ""))
            if status != 200:
                sys.exit(f"cannot list {path}: {status} {body}")
            out += body["results"]
            if not body.get("next_page_results"):
                return out
            cursor = body["next_cursor"]

    projects = list_all(f"/workspaces/{ws}/projects/")
    project = next((p for p in projects if p["identifier"] == ident), None)
    if project is None:
        sys.exit(f"project '{ident}' not found in workspace '{ws}' (create it in Plane first)")
    base_path = f"/workspaces/{ws}/projects/{project['id']}"

    states = list_all(base_path + "/states/")
    def state_id(kind: str) -> str:
        group = STATE_GROUP[kind]
        wanted = {"done": "done", "todo": "todo"}[kind]
        for s in states:
            if s["name"].lower() == wanted:
                return s["id"]
        return next(s["id"] for s in states if s["group"] == group)

    cycles = {c["name"]: c for c in list_all(base_path + "/cycles/")}
    cycle_ids: dict[str, str] = {}
    for c in plan["cycles"]:
        payload = {k: c[k] for k in ("name", "description", "start_date", "end_date")}
        if c["name"] in cycles:
            call("PATCH", f"{base_path}/cycles/{cycles[c['name']]['id']}/", payload)
            cycle_ids[c["key"]] = cycles[c["name"]]["id"]
        else:
            status, body = call("POST", base_path + "/cycles/", payload)
            if status != 201:
                sys.exit(f"cycle '{c['name']}' failed: {status} {body}")
            cycle_ids[c["key"]] = body["id"]
        print(f"cycle ok: {c['name']}")

    existing = {i["name"]: i for i in list_all(base_path + "/issues/")}
    links: dict[str, list[str]] = {}
    for i in plan["issues"]:
        payload = {"name": i["title"], "description_html": f"<p>{i['description']}</p>",
                   "priority": i["priority"], "state": state_id(i["state"])}
        if i["title"] in existing:
            issue_id = existing[i["title"]]["id"]
            call("PATCH", f"{base_path}/issues/{issue_id}/", payload)
        else:
            status, body = call("POST", base_path + "/issues/", payload)
            if status != 201:
                print(f"issue '{i['title']}' failed: {status} {body}", file=sys.stderr)
                continue
            issue_id = body["id"]
        links.setdefault(cycle_ids[i["cycle"]], []).append(issue_id)
        print(f"issue ok: {i['title']}")
    for cycle_id, ids in links.items():
        status, _ = call("POST", f"{base_path}/cycles/{cycle_id}/cycle-issues/", {"issues": ids})
        print(f"cycle {cycle_id}: linked {len(ids)} issues -> {'ok' if status == 200 else f'FAILED ({status})'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
