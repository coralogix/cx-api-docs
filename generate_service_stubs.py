#!/usr/bin/env python3
"""
Detect new v5 services that mintlify-scrape already wrote, and optionally
generate a stub service-overview from the matching OpenAPI tag.

Phase 1 of CX-53340 (option D): this is the reusable generator. It does not
edit V5_SERVICES, introduction-v5.mdx, or the facade-sync workflow. Existing
human-owned overviews are never overwritten.

Usage:
  python3 generate_service_stubs.py              # dry-run
  python3 generate_service_stubs.py --write      # write missing stubs
"""

from __future__ import annotations

import argparse
import sys
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from build_navigation_file import V5_SERVICES

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")


AUTH_DOCS = (
    "https://coralogix.com/docs/user-guides/account-management/api-keys/api-keys/"
)


def tag_slug(name: str) -> str:
    """Mintlify-scrape directory name for an OpenAPI tag."""
    return name.lower().replace(" ", "-")


def load_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tags_by_slug(spec: dict) -> Dict[str, dict]:
    return {tag_slug(tag["name"]): tag for tag in spec.get("tags") or [] if tag.get("name")}


def operations_by_tag(spec: dict) -> Dict[str, List[dict]]:
    """Map tag slug → list of {method, path, summary, permissions, errors}."""
    out: Dict[str, List[dict]] = {}
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict) or method.startswith("x-"):
                continue
            for tag in op.get("tags") or []:
                slug = tag_slug(tag)
                responses = op.get("responses") or {}
                errors = sorted(
                    code for code in responses if str(code).isdigit() and int(code) >= 400
                )
                out.setdefault(slug, []).append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "summary": (op.get("summary") or "").strip(),
                        "permissions": list(op.get("x-coralogixPermissions") or []),
                        "errors": errors,
                    }
                )
    for ops in out.values():
        ops.sort(key=lambda o: (o["path"], o["method"]))
    return out


def status_label(code: str) -> str:
    try:
        phrase = HTTPStatus(int(code)).phrase
    except (ValueError, TypeError):
        phrase = ""
    return f"`{code} {phrase}`".rstrip() if phrase else f"`{code}`"


def render_stub(tag: dict, operations: Iterable[dict]) -> str:
    name = tag["name"]
    description = " ".join((tag.get("description") or "").split())
    external = tag.get("externalDocs") or {}
    docs_url = (external.get("url") or "").strip()

    ops = list(operations)
    permissions = sorted({p for op in ops for p in op["permissions"]})
    errors = sorted({e for op in ops for e in op["errors"]}, key=lambda c: int(c))

    lines = [f"# {name} overview", ""]
    if description:
        lines += [description, ""]
    if docs_url:
        lines += [f"Learn more in our [documentation]({docs_url}).", ""]

    if ops:
        lines += [
            "## Methods",
            "",
            "| Method | Path | Description |",
            "|--------|------|-------------|",
        ]
        for op in ops:
            lines.append(f"| `{op['method']}` | `{op['path']}` | {op['summary']} |")
        lines.append("")

    if permissions:
        lines += [
            "## Authentication and permissions",
            "",
            f"To use the {name} API you need to [create a personal or team API key]({AUTH_DOCS}). "
            "The key needs one of the following permissions.",
            "",
            "| Permission |",
            "|------------|",
        ]
        for perm in permissions:
            lines.append(f"| `{perm}` |")
        lines.append("")

    if errors:
        lines += [
            "## Common error response codes",
            "",
            "| Status Code | Description |",
            "|-------------|-------------|",
        ]
        for code in errors:
            lines.append(f"| {status_label(code)} | Response code {code} |")
        lines.append("")

    return "\n".join(lines)


def discover(
    api_ref: Path,
    overviews: Path,
    spec: dict,
) -> Tuple[List[str], List[Tuple[str, Path, str]]]:
    """Return (proposed V5_SERVICES entries, stubs to write)."""
    on_disk = sorted(p.name for p in api_ref.iterdir() if p.is_dir())
    tags = tags_by_slug(spec)
    ops = operations_by_tag(spec)

    proposed: List[str] = []
    stubs: List[Tuple[str, Path, str]] = []

    for slug in on_disk:
        if slug not in V5_SERVICES:
            display = (tags.get(slug) or {}).get("name") or slug
            proposed.append(f"    {slug!r}: {display!r},")

        dest = overviews / f"{slug}-overview.mdx"
        if dest.exists():
            continue
        if slug in V5_SERVICES:
            # Already visible in nav; do not invent overviews for older gaps.
            continue
        tag = tags.get(slug)
        if not tag:
            print(f"Warning: no OpenAPI tag for {slug}; skipping stub", file=sys.stderr)
            continue
        stubs.append((slug, dest, render_stub(tag, ops.get(slug, []))))

    return proposed, stubs


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("openapi_v5.yaml"),
        help="OpenAPI spec to read tags and operations from",
    )
    parser.add_argument(
        "--api-ref",
        type=Path,
        default=Path("api-reference/v5"),
        help="Scraped v5 service directories",
    )
    parser.add_argument(
        "--overviews",
        type=Path,
        default=Path("service-overviews"),
        help="Human-owned overview directory",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write missing stubs. Default is dry-run.",
    )
    args = parser.parse_args(argv)

    spec = load_spec(args.spec)
    proposed, stubs = discover(args.api_ref, args.overviews, spec)

    if proposed:
        print("Proposed V5_SERVICES entries (not written):")
        for line in proposed:
            print(line)
        print()
    else:
        print("No scraped v5 services are missing from V5_SERVICES.")
        print()

    if not stubs:
        print("No missing overviews to generate for new services.")
        return 0

    for slug, dest, body in stubs:
        action = "Writing" if args.write else "Would write"
        print(f"{action} {dest} ({slug})")
        if args.write:
            dest.write_text(body, encoding="utf-8")

    if not args.write:
        print("\nDry-run. Re-run with --write to create the files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
