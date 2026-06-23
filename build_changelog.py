#!/usr/bin/env python3
"""
Generate the public changelog (changelog.mdx) from the upstream cx-management-apis
CHANGELOG.md, unifying entries by *docs release date* instead of upstream date.

Upstream records released changes under section headers — either a bare `## YYYY-MM-DD`
or a versioned `## vX.Y.Z - YYYY-MM-DD` (reverse-chronological), with verbatim bullet
entries. In both forms the trailing `YYYY-MM-DD` is the section date. A `## Unreleased`
staging section (and any other non-date/non-version `## ` header) is deliberately ignored
so unreleased entries never reach the public docs. When a facade sync ships released
changes to the public docs, every upstream entry newer than what we've already published
collapses into a single section dated the release day.

State lives in changelog.data.json:
  - "published": hashes of every upstream bullet already accounted for. This is the dedup
    key — tracking bullet *content* (not just dates) so a new bullet appended under an
    already-published section is still picked up on the next sync, and re-heading existing
    dated sections under a version header republishes nothing (identical bullet text).
  - "releases": the rendered history, newest-first.
Bootstrap seeds "published" from the full current upstream so adoption doesn't dump history.

Usage:
  python3 build_changelog.py \
    --upstream <path/to/CHANGELOG.md> \
    --release-date <YYYY-MM-DD> \
    --cx-sha <sha> \
    --data changelog.data.json \
    --out changelog.mdx \
    [--bootstrap]
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATE_HEADER = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")
# Versioned release header, e.g. "## v5.0.1 - 2026-06-30". The trailing date is the
# section date used for grouping; the version itself is not rendered.
VERSION_HEADER = re.compile(r"^##\s+v\d+\.\d+\.\d+\s+-\s+(\d{4}-\d{2}-\d{2})\s*$")
# Any other H2 (e.g. "## Unreleased") opens a non-published section: its bullets are
# deliberately skipped so unreleased entries never reach the public docs.
OTHER_H2 = re.compile(r"^##\s+")
BULLET = re.compile(r"^-\s+")
# A cx-management-apis release tag, e.g. "v5.0.1". When --cx-sha is a tag (the
# normal flow), it labels the rendered release block alongside the docs date;
# a bare commit SHA (manual sync) leaves the block date-only.
RELEASE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")

FRONTMATTER = """---
title: Changelog
description: "Public API changes, grouped by release version and the date it shipped."
---

"""


def parse_upstream(text: str) -> List[Tuple[str, List[str]]]:
    """Parse upstream CHANGELOG.md into ordered (date, [bullets]) preserving file order.

    Bullets may span multiple lines; continuation lines (indented or non-empty,
    non-header, non-bullet) are folded into the current bullet verbatim.
    """
    sections: List[Tuple[str, List[str]]] = []
    cur_date: Optional[str] = None
    cur_bullets: List[str] = []
    cur_bullet: Optional[List[str]] = None

    def flush_bullet():
        nonlocal cur_bullet
        if cur_bullet is not None:
            cur_bullets.append("\n".join(cur_bullet).rstrip())
            cur_bullet = None

    def flush_section():
        nonlocal cur_date, cur_bullets
        flush_bullet()
        if cur_date is not None:
            sections.append((cur_date, cur_bullets))
        cur_date = None
        cur_bullets = []

    for line in text.splitlines():
        m = DATE_HEADER.match(line) or VERSION_HEADER.match(line)
        if m:
            flush_section()
            cur_date = m.group(1)
            cur_bullets = []
            continue
        if OTHER_H2.match(line):
            # e.g. "## Unreleased" — close any open section; bullets here are skipped.
            flush_section()
            continue
        if cur_date is None:
            continue  # skip the top-level "# Changelog" header and any preamble
        if BULLET.match(line):
            flush_bullet()
            cur_bullet = [BULLET.sub("", line, count=1).rstrip()]
        elif line.strip() == "":
            flush_bullet()
        elif cur_bullet is not None:
            cur_bullet.append(line.strip())
        # else: stray text outside a bullet -> ignore

    flush_section()
    return sections


def bullet_hash(bullet: str) -> str:
    return hashlib.sha1(bullet.encode("utf-8")).hexdigest()


def load_data(path: Path) -> Dict:
    if not path.exists():
        return {"published": [], "releases": [], "last_cx_sha": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("published", [])
    data.setdefault("releases", [])
    data.setdefault("last_cx_sha", "")
    return data


def collect_new(
    sections: List[Tuple[str, List[str]]], published: set
) -> Tuple[List[str], List[str]]:
    """Return (new_bullets in upstream order, sorted unique dates that contributed).

    "New" is decided by bullet content, not date: any upstream bullet whose hash is not
    already in `published` is new — including bullets appended under a date we've already
    published.
    """
    new_bullets: List[str] = []
    new_dates: List[str] = []
    seen = set(published)  # also dedup repeats within this single upstream pass
    for dt, bullets in sections:
        contributed = False
        for b in bullets:
            h = bullet_hash(b)
            if h not in seen:
                seen.add(h)
                new_bullets.append(b)
                contributed = True
        if contributed:
            new_dates.append(dt)
    return new_bullets, sorted(set(new_dates), reverse=True)


def fmt_label(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")


def release_label(rec: Dict) -> str:
    """Heading for a release block: "vX.Y.Z — <date>" when versions are known,
    otherwise just the docs release date (older blocks, or manual SHA syncs)."""
    date = fmt_label(rec["release_date"])
    versions = rec.get("versions") or []
    if versions:
        return f"{', '.join(versions)} — {date}"
    return date


def render(data: Dict) -> str:
    out = [FRONTMATTER]
    for rec in data["releases"]:
        if not rec.get("bullets"):
            continue
        out.append(f'<Update label="{release_label(rec)}">\n')
        for b in rec["bullets"]:
            # Keep multi-line bullets readable under the markdown list item.
            lines = b.split("\n")
            out.append(f"  - {lines[0]}")
            for cont in lines[1:]:
                out.append(f"    {cont}")
        out.append("\n</Update>\n")
    if data.get("last_cx_sha"):
        out.append(
            f"\n{{/* Generated by build_changelog.py from "
            f"cx-management-apis@{data['last_cx_sha']} */}}\n"
        )
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--release-date", default=date.today().isoformat())
    ap.add_argument("--cx-sha", default="")
    ap.add_argument("--data", default="changelog.data.json", type=Path)
    ap.add_argument("--out", default="changelog.mdx", type=Path)
    ap.add_argument(
        "--bootstrap",
        action="store_true",
        help="Seed `published` from current upstream without emitting a release.",
    )
    args = ap.parse_args()

    sections = parse_upstream(args.upstream.read_text(encoding="utf-8"))
    data = load_data(args.data)

    if args.bootstrap:
        if data["published"] or data["releases"]:
            print("Data file already populated; refusing to bootstrap over it.", file=sys.stderr)
            return 1
        all_bullets = [b for _, bullets in sections for b in bullets]
        data["published"] = sorted({bullet_hash(b) for b in all_bullets})
        data["last_cx_sha"] = args.cx_sha
        args.data.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if not args.out.exists():
            args.out.write_text(render(data), encoding="utf-8")
        print(f"Bootstrapped: {len(data['published'])} upstream bullets marked as published.")
        return 0

    published = set(data["published"])
    new_bullets, new_dates = collect_new(sections, published)

    if not new_bullets:
        print("No new upstream entries since last release; nothing to do.")
        return 0

    data["published"] = sorted(published | {bullet_hash(b) for b in new_bullets})
    data["last_cx_sha"] = args.cx_sha

    # When --cx-sha is a release tag, label the block with it; a bare commit SHA
    # (manual sync) yields no version and the block stays date-only.
    version = args.cx_sha if RELEASE_TAG.match(args.cx_sha or "") else None

    releases = data["releases"]
    if releases and releases[0].get("release_date") == args.release_date:
        rec = releases[0]
        rec["bullets"] = new_bullets + rec.get("bullets", [])
        rec["upstream_dates"] = sorted(
            set(rec.get("upstream_dates", [])) | set(new_dates), reverse=True
        )
        if version and version not in rec.get("versions", []):
            # Same-day syncs of multiple releases collapse into one block; list
            # each version, newest first.
            rec["versions"] = [version] + rec.get("versions", [])
        print(f"Merged {len(new_bullets)} entries into existing {args.release_date} release.")
    else:
        releases.insert(
            0,
            {
                "release_date": args.release_date,
                "versions": [version] if version else [],
                "upstream_dates": new_dates,
                "bullets": new_bullets,
            },
        )
        print(f"Added {args.release_date} release with {len(new_bullets)} entries.")

    args.data.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    args.out.write_text(render(data), encoding="utf-8")
    print(f"Wrote {args.out} and {args.data}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
