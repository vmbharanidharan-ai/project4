#!/usr/bin/env python3
"""
Puzzle reconnaissance and claim helper for carlodoroff.com.

What this script does:
1) Fetches likely puzzle routes and stores raw responses.
2) Extracts clues from HTML/JS comments and common encodings.
3) Discovers explicit __puzzle.claim(...) / __puzzle.mark(...) references.
4) Optionally probes /api/puzzle/claim with candidate level/answer pairs.
5) Optionally sends a dry-run guestbook payload to discover missing levels.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin

import requests


BASE_URL = "https://carlodoroff.com"
DEFAULT_PATHS = ["/", "/rabbit", "/cra-0004", "/signal", "/signal.json"]
STATE_KEY = "cd_puzzle_state_v1"

CLAIM_REGEX = re.compile(
    r"__puzzle\.claim\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
)
MARK_REGEX = re.compile(r"__puzzle\.mark\(\s*['\"]([^'\"]+)['\"]\s*\)")
ROUTE_REGEX = re.compile(r"(?<![A-Za-z0-9_])/(?:[a-z0-9][a-z0-9\-_./]*)", re.I)
HTML_COMMENT_REGEX = re.compile(r"<!--(.*?)-->", re.S)
BASE64_REGEX = re.compile(r"\b[A-Za-z0-9+/]{20,}={0,2}\b")
HEX_REGEX = re.compile(r"\b[0-9a-fA-F]{24,}\b")


@dataclass(frozen=True)
class ClaimPair:
    level: str
    answer: str


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def sanitize_path_for_filename(route: str) -> str:
    route = route.strip("/")
    if not route:
        return "root"
    return route.replace("/", "__")


def fetch_paths(session: requests.Session, base_url: str, paths: Sequence[str], out_dir: Path) -> dict[str, str]:
    fetched: dict[str, str] = {}
    pages_dir = out_dir / "pages"
    ensure_dir(pages_dir)

    for route in paths:
        url = urljoin(base_url, route)
        resp = session.get(url, timeout=20)
        name = sanitize_path_for_filename(route)
        ext = ".html" if "text/html" in resp.headers.get("content-type", "") else ".txt"
        out_file = pages_dir / f"{name}{ext}"
        save_text(out_file, resp.text)
        fetched[route] = resp.text
        print(f"[fetch] {route:<12} -> {resp.status_code} ({len(resp.text)} chars) -> {out_file}")
    return fetched


def decode_possible_base64(candidate: str) -> str | None:
    # cheap entropy guard to avoid decoding regular words
    if len(candidate) % 4 != 0:
        return None
    try:
        raw = base64.b64decode(candidate, validate=True)
    except Exception:
        return None
    if not raw:
        return None
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(ch.isprintable() for ch in txt):
        return txt.strip()
    return None


def extract_clues(route: str, text: str) -> dict[str, list[str]]:
    comments = [c.strip() for c in HTML_COMMENT_REGEX.findall(text) if c.strip()]
    routes = sorted(set(r for r in ROUTE_REGEX.findall(text) if not r.startswith("//")))
    claims = [f"{m.group(1)}::{m.group(2)}" for m in CLAIM_REGEX.finditer(text)]
    marks = [m.group(1) for m in MARK_REGEX.finditer(text)]
    b64_hits = BASE64_REGEX.findall(text)
    b64_decoded = []
    for hit in b64_hits:
        decoded = decode_possible_base64(hit)
        if decoded and len(decoded) >= 3:
            b64_decoded.append(f"{hit[:24]}... => {decoded[:120]}")
    hex_hits = HEX_REGEX.findall(text)
    return {
        "route": [route],
        "claims": sorted(set(claims)),
        "marks": sorted(set(marks)),
        "comments": comments[:50],
        "routes": routes[:200],
        "b64_decoded": sorted(set(b64_decoded))[:100],
        "hex_strings": sorted(set(hex_hits))[:100],
    }


def write_report(out_dir: Path, report: dict[str, dict[str, list[str]]]) -> None:
    report_path = out_dir / "report.json"
    ensure_dir(out_dir)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[report] wrote {report_path}")

    md_lines = ["# Puzzle Recon Report", ""]
    all_claims = set()
    all_marks = set()
    for route, data in report.items():
        md_lines.append(f"## {route}")
        claims = data.get("claims", [])
        marks = data.get("marks", [])
        all_claims.update(claims)
        all_marks.update(marks)
        md_lines.append(f"- claims found: {len(claims)}")
        for c in claims[:20]:
            md_lines.append(f"  - `{c}`")
        md_lines.append(f"- marks found: {len(marks)}")
        for m in marks[:20]:
            md_lines.append(f"  - `{m}`")
        route_hits = data.get("routes", [])
        md_lines.append(f"- interesting routes: {len(route_hits)}")
        for r in route_hits[:20]:
            md_lines.append(f"  - `{r}`")
        md_lines.append("")

    md_lines.append("## Aggregate")
    md_lines.append(f"- total claim pairs: {len(all_claims)}")
    for c in sorted(all_claims):
        md_lines.append(f"  - `{c}`")
    md_lines.append(f"- total mark keys: {len(all_marks)}")
    for m in sorted(all_marks):
        md_lines.append(f"  - `{m}`")
    md_lines.append("")

    report_md = out_dir / "report.md"
    report_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[report] wrote {report_md}")


def parse_extra_claim_pairs(pairs: Sequence[str]) -> list[ClaimPair]:
    parsed: list[ClaimPair] = []
    for pair in pairs:
        if ":" not in pair:
            raise ValueError(f"Invalid --probe pair '{pair}'. Expected LEVEL:ANSWER format.")
        level, answer = pair.split(":", 1)
        level = level.strip()
        answer = answer.strip()
        if not level or not answer:
            raise ValueError(f"Invalid --probe pair '{pair}'. Empty level or answer.")
        parsed.append(ClaimPair(level=level, answer=answer))
    return parsed


def collect_claim_pairs(report: dict[str, dict[str, list[str]]], extra_pairs: Sequence[ClaimPair]) -> list[ClaimPair]:
    found: set[ClaimPair] = set(extra_pairs)
    for route_data in report.values():
        for item in route_data.get("claims", []):
            level, answer = item.split("::", 1)
            found.add(ClaimPair(level=level, answer=answer))
    return sorted(found, key=lambda x: (x.level, x.answer))


def probe_claims(session: requests.Session, base_url: str, pairs: Iterable[ClaimPair], out_dir: Path) -> list[dict[str, object]]:
    endpoint = urljoin(base_url, "/api/puzzle/claim")
    results: list[dict[str, object]] = []
    for pair in pairs:
        payload = {"level": pair.level, "answer": pair.answer}
        try:
            resp = session.post(endpoint, json=payload, timeout=20)
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:800]}
            row = {
                "level": pair.level,
                "answer": pair.answer,
                "status": resp.status_code,
                "response": body,
            }
            results.append(row)
            print(f"[claim] {pair.level}:{pair.answer} -> {resp.status_code} {body}")
        except Exception as exc:
            row = {
                "level": pair.level,
                "answer": pair.answer,
                "status": "error",
                "response": {"error": str(exc)},
            }
            results.append(row)
            print(f"[claim] {pair.level}:{pair.answer} -> error {exc}")

    out_file = out_dir / "claim_probe.json"
    save_text(out_file, json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[claim] wrote {out_file}")
    return results


def probe_guestbook(session: requests.Session, base_url: str, out_dir: Path) -> dict[str, object]:
    endpoint = urljoin(base_url, "/api/guestbook")
    payload = {
        "name": "solver_probe",
        "github": None,
        "message": "probe",
        "solution": "probe",
        "steps_completed": [],
        "time_to_complete": 0,
        "tokens": {},
    }
    resp = session.post(endpoint, json=payload, timeout=20)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:1200]}
    result = {"status": resp.status_code, "response": body}
    save_text(out_dir / "guestbook_probe.json", json.dumps(result, indent=2, ensure_ascii=False))
    print(f"[guestbook] -> {resp.status_code} {body}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recon + claim helper for the carlodoroff puzzle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python3 puzzle_solver.py --probe-claims --probe-guestbook
              python3 puzzle_solver.py --path /rabbit --path /signal --probe L1_foo:bar
            """
        ),
    )
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Route to fetch. Repeat for multiple. Defaults to /, /rabbit, /signal.",
    )
    parser.add_argument("--out-dir", default="project3/out", help="Output directory for artifacts.")
    parser.add_argument("--probe", action="append", default=[], help="Extra LEVEL:ANSWER pair(s) to test.")
    parser.add_argument("--probe-claims", action="store_true", help="POST discovered claim pairs to /api/puzzle/claim.")
    parser.add_argument("--probe-guestbook", action="store_true", help="POST a minimal payload to /api/guestbook.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "project3-puzzle-solver/0.1",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        }
    )

    paths = args.path if args.path else DEFAULT_PATHS
    fetched = fetch_paths(session, args.base_url, paths, out_dir)

    report: dict[str, dict[str, list[str]]] = {}
    for route, text in fetched.items():
        report[route] = extract_clues(route, text)
    write_report(out_dir, report)

    extra_pairs = parse_extra_claim_pairs(args.probe)
    discovered_pairs = collect_claim_pairs(report, extra_pairs)
    print(f"[info] discovered {len(discovered_pairs)} claim candidate pair(s).")
    if discovered_pairs:
        for pair in discovered_pairs:
            print(f"       - {pair.level}:{pair.answer}")

    if args.probe_claims and discovered_pairs:
        probe_claims(session, args.base_url, discovered_pairs, out_dir)
    elif args.probe_claims:
        print("[claim] no discovered pairs; use --probe LEVEL:ANSWER")

    if args.probe_guestbook:
        probe_guestbook(session, args.base_url, out_dir)

    print(f"[done] artifacts in {out_dir}")
    print(f"[done] local state key on site is '{STATE_KEY}' (for browser-side checks).")


if __name__ == "__main__":
    main()
