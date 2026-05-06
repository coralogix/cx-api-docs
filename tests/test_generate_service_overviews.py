"""Tests for generate_service_overviews."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Allow importing the script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_service_overviews as gso


def write_spec(path: Path, tags: list[dict]) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "", "version": "1.0.0"},
        "tags": tags,
        "paths": {},
    }
    path.write_text(yaml.safe_dump(spec))
    return path


# ---------------------------------------------------------------- Tag.key


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Actions Service", "actions-service"),
        ("IP Access Service", "ip-access-service"),
        ("Alert Scheduler Rule service", "alert-scheduler-rule-service"),
        ("  Foo   Bar  ", "foo-bar"),
        ("SLOs Service", "slos-service"),
    ],
)
def test_tag_key_kebabcases(name: str, expected: str) -> None:
    assert gso.Tag(name=name, description="x").key == expected


# ---------------------------------------------------------------- frontmatter


class TestParseFrontmatter:
    def test_no_frontmatter(self) -> None:
        assert gso.parse_frontmatter("# just markdown\n\nbody") == {}

    def test_empty_frontmatter(self) -> None:
        assert gso.parse_frontmatter("---\n---\nbody") == {}

    def test_managed_flag_true(self) -> None:
        text = "---\ngenerated: true\nservice: foo\n---\n# Foo\n"
        assert gso.parse_frontmatter(text) == {"generated": True, "service": "foo"}

    def test_managed_flag_false(self) -> None:
        assert gso.parse_frontmatter("---\ngenerated: false\n---\n") == {"generated": False}

    def test_malformed_yaml_returns_empty(self) -> None:
        # Unclosed quote = YAMLError; we should swallow and return {}.
        assert gso.parse_frontmatter("---\nfoo: 'unterminated\n---\n") == {}

    def test_frontmatter_must_open_with_delimiter(self) -> None:
        # A file with `---` only mid-content is not frontmatter.
        assert gso.parse_frontmatter("# Title\n---\ngenerated: true\n---\n") == {}


class TestIsManaged:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert gso.is_managed(tmp_path / "nope.mdx") is False

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "x.mdx"
        p.write_text("# Hand-written\n")
        assert gso.is_managed(p) is False

    def test_generated_true(self, tmp_path: Path) -> None:
        p = tmp_path / "x.mdx"
        p.write_text("---\ngenerated: true\n---\n# x\n")
        assert gso.is_managed(p) is True

    def test_generated_false_is_not_managed(self, tmp_path: Path) -> None:
        p = tmp_path / "x.mdx"
        p.write_text("---\ngenerated: false\n---\n# x\n")
        assert gso.is_managed(p) is False


# ---------------------------------------------------------------- generate()


class TestGenerate:
    def test_creates_new_files(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [
                {"name": "Foo Service", "description": "Manage foos."},
                {"name": "Bar Service", "description": "Manage bars."},
            ],
        )
        out = tmp_path / "service-overviews"

        created, updated, skipped = gso.generate(spec, out)

        assert sorted(created) == sorted(
            [out / "foo-service-overview.mdx", out / "bar-service-overview.mdx"]
        )
        assert updated == []
        assert skipped == []

    def test_generated_content_shape(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo Service", "description": "Manage foos."}],
        )
        out = tmp_path / "service-overviews"

        gso.generate(spec, out)

        content = (out / "foo-service-overview.mdx").read_text()
        assert content == (
            "---\n"
            "generated: true\n"
            "service: foo-service\n"
            "---\n"
            "# Foo Service\n"
            "\n"
            "Manage foos.\n"
        )

    def test_skips_human_authored_file(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo Service", "description": "Spec says X."}],
        )
        out = tmp_path / "service-overviews"
        out.mkdir()
        existing = out / "foo-service-overview.mdx"
        existing.write_text("# Foo Service\n\nHuman-authored content.\n")

        created, updated, skipped = gso.generate(spec, out)

        assert created == []
        assert updated == []
        assert skipped == [existing]
        assert "Human-authored content." in existing.read_text()

    def test_skips_file_with_generated_false(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo Service", "description": "Spec says X."}],
        )
        out = tmp_path / "service-overviews"
        out.mkdir()
        existing = out / "foo-service-overview.mdx"
        existing.write_text("---\ngenerated: false\n---\n# Foo\n\nLocked.\n")

        created, updated, skipped = gso.generate(spec, out)

        assert created == []
        assert updated == []
        assert skipped == [existing]
        assert "Locked." in existing.read_text()

    def test_updates_managed_when_stale(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo Service", "description": "New description."}],
        )
        out = tmp_path / "service-overviews"
        out.mkdir()
        existing = out / "foo-service-overview.mdx"
        existing.write_text(
            "---\ngenerated: true\nservice: foo-service\n---\n"
            "# Foo Service\n\nOld description.\n"
        )

        created, updated, skipped = gso.generate(spec, out)

        assert created == []
        assert updated == [existing]
        assert skipped == []
        text = existing.read_text()
        assert "New description." in text
        assert "Old description." not in text

    def test_skips_tag_without_description(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [
                {"name": "Foo Service"},  # no description -> filtered out
                {"name": "Bar Service", "description": "Manage bars."},
            ],
        )
        out = tmp_path / "service-overviews"

        created, updated, skipped = gso.generate(spec, out)

        assert created == [out / "bar-service-overview.mdx"]
        assert not (out / "foo-service-overview.mdx").exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo", "description": "Manage foos."}],
        )
        out = tmp_path / "service-overviews"

        gso.generate(spec, out)
        created, updated, skipped = gso.generate(spec, out)

        assert created == []
        assert updated == []
        assert skipped == [out / "foo-overview.mdx"]

    def test_output_dir_created_when_missing(self, tmp_path: Path) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo", "description": "x"}],
        )
        out = tmp_path / "deep" / "nested" / "service-overviews"
        assert not out.exists()

        gso.generate(spec, out)

        assert out.is_dir()
        assert (out / "foo-overview.mdx").exists()


# ---------------------------------------------------------------- CLI


class TestMain:
    def test_returns_1_on_missing_spec(self, tmp_path: Path, capsys) -> None:
        rc = gso.main(
            [
                "--spec",
                str(tmp_path / "missing.yaml"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        assert rc == 1
        assert "spec file not found" in capsys.readouterr().err

    def test_smoke_creates_files_and_summarizes(
        self, tmp_path: Path, capsys
    ) -> None:
        spec = write_spec(
            tmp_path / "spec.yaml",
            [{"name": "Foo Service", "description": "Manage foos."}],
        )
        out = tmp_path / "out"

        rc = gso.main(["--spec", str(spec), "--output-dir", str(out)])

        assert rc == 0
        stdout = capsys.readouterr().out
        assert "1 created" in stdout
        assert (out / "foo-service-overview.mdx").exists()
