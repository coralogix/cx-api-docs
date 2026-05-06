#!/usr/bin/env python3
"""Generate or update service-overview MDX files from openapi_v5.yaml tag descriptions.

Policy: a file is *managed* by this script iff its frontmatter contains
``generated: true``. Files without that flag are left untouched (human-authored
overviews stay human-owned). Tags without a description are skipped — we don't
create empty stubs.

Run via ``make generate-overviews`` (or directly: ``python3 generate_service_overviews.py``).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_SPEC = Path("openapi_v5.yaml")
DEFAULT_OUTPUT_DIR = Path("service-overviews")


@dataclass(frozen=True)
class Tag:
    name: str
    description: str

    @property
    def key(self) -> str:
        # Mintlify-scrape derives directory names by lowercasing the tag and
        # collapsing whitespace runs into single hyphens. Match that exactly so
        # the generated overview filename pairs with the api-reference dir.
        return re.sub(r"\s+", "-", self.name.lower().strip())


def load_tags(spec_path: Path) -> list[Tag]:
    with spec_path.open() as f:
        spec = yaml.safe_load(f)
    tags = []
    for raw in spec.get("tags") or []:
        name = (raw.get("name") or "").strip()
        description = (raw.get("description") or "").strip()
        if name and description:
            tags.append(Tag(name=name, description=description))
    return tags


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter delimited by ``---`` lines. ``{}`` if absent or malformed."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def is_managed(path: Path) -> bool:
    if not path.exists():
        return False
    return parse_frontmatter(path.read_text()).get("generated") is True


def render_overview(tag: Tag) -> str:
    return (
        "---\n"
        "generated: true\n"
        f"service: {tag.key}\n"
        "---\n"
        f"# {tag.name}\n"
        "\n"
        f"{tag.description}\n"
    )


def generate(
    spec_path: Path, output_dir: Path
) -> tuple[list[Path], list[Path], list[Path]]:
    """Returns ``(created, updated, skipped)``.

    - ``created``: files that didn't exist and were written.
    - ``updated``: managed files whose contents changed.
    - ``skipped``: human-authored files left alone, plus managed files already in sync.
    """
    tags = load_tags(spec_path)
    created: list[Path] = []
    updated: list[Path] = []
    skipped: list[Path] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    for tag in tags:
        target = output_dir / f"{tag.key}-overview.mdx"
        new_content = render_overview(tag)

        if not target.exists():
            target.write_text(new_content)
            created.append(target)
            continue

        if not is_managed(target):
            skipped.append(target)
            continue

        if target.read_text() != new_content:
            target.write_text(new_content)
            updated.append(target)
        else:
            skipped.append(target)

    return created, updated, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if not args.spec.exists():
        print(f"error: spec file not found: {args.spec}", file=sys.stderr)
        return 1

    created, updated, skipped = generate(args.spec, args.output_dir)

    for p in created:
        print(f"created: {p}")
    for p in updated:
        print(f"updated: {p}")
    print(
        f"\nGenerated overviews: {len(created)} created, {len(updated)} updated, "
        f"{len(skipped)} unchanged (incl. human-managed)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
