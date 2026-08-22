#!/usr/bin/env python3
"""Validate the repository catalog and self-contained skill directories."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"[a-z0-9-]{1,64}")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s|$)")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_frontmatter(path: Path, errors: list[str]) -> tuple[str | None, set[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        fail(errors, f"{path.relative_to(ROOT)}: missing opening frontmatter marker")
        return None, set()

    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(errors, f"{path.relative_to(ROOT)}: missing closing frontmatter marker")
        return None, set()

    frontmatter = lines[1:end]
    keys: set[str] = set()
    name: str | None = None
    for line in frontmatter:
        if line.startswith((" ", "\t")):
            continue
        match = FRONTMATTER_KEY_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        keys.add(key)
        if key == "name":
            name = line.split(":", 1)[1].strip().strip("'\"")

    if keys != {"name", "description"}:
        fail(
            errors,
            f"{path.relative_to(ROOT)}: frontmatter keys must be name and description, got {sorted(keys)}",
        )
    if "description:" not in "\n".join(frontmatter):
        fail(errors, f"{path.relative_to(ROOT)}: missing description")
    if len(lines) > 500:
        fail(errors, f"{path.relative_to(ROOT)}: SKILL.md exceeds 500 lines")
    return name, keys


def validate_local_links(errors: list[str]) -> None:
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            file_part = unquote(target.split("#", 1)[0])
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                fail(
                    errors,
                    f"{path.relative_to(ROOT)}: broken local link {raw_target}",
                )


def validate_skill_is_self_contained(skill_dir: Path, errors: list[str]) -> None:
    skill_root = skill_dir.resolve()
    for path in skill_dir.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            file_part = unquote(target.split("#", 1)[0])
            resolved = (path.parent / file_part).resolve()
            if not resolved.is_relative_to(skill_root):
                fail(
                    errors,
                    f"{path.relative_to(ROOT)}: skill link escapes its directory: {raw_target}",
                )


def main() -> int:
    errors: list[str] = []
    catalog_path = ROOT / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"catalog.json: {exc}", file=sys.stderr)
        return 1

    if catalog.get("schema_version") != 1:
        fail(errors, "catalog.json: schema_version must be 1")

    records = catalog.get("skills")
    if not isinstance(records, list):
        fail(errors, "catalog.json: skills must be a list")
        records = []

    required = {"name", "display_name", "path", "status", "source_url", "docs", "evals"}
    names: set[str] = set()
    catalog_paths: set[Path] = set()

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            fail(errors, f"catalog.json: skills[{index}] must be an object")
            continue
        if set(record) != required:
            fail(errors, f"catalog.json: skills[{index}] has unexpected fields")
            continue

        name = record["name"]
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            fail(errors, f"catalog.json: invalid skill name {name!r}")
            continue
        if name in names:
            fail(errors, f"catalog.json: duplicate skill name {name}")
        names.add(name)

        skill_dir = ROOT / record["path"]
        catalog_paths.add(skill_dir.resolve())
        if skill_dir != ROOT / "skills" / name:
            fail(errors, f"{name}: path must be skills/{name}")
        if not skill_dir.is_dir():
            fail(errors, f"{name}: missing directory {record['path']}")
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            fail(errors, f"{name}: missing SKILL.md")
            continue
        frontmatter_name, _ = read_frontmatter(skill_md, errors)
        if frontmatter_name != name:
            fail(errors, f"{name}: folder, catalog and frontmatter names differ")
        if (skill_dir / "README.md").exists():
            fail(errors, f"{name}: README.md must live outside the installable skill")
        validate_skill_is_self_contained(skill_dir, errors)

        for key in ("docs", "evals"):
            target = ROOT / record[key]
            if not target.is_file():
                fail(errors, f"{name}: missing {key} file {record[key]}")

        source_url = record["source_url"]
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            fail(errors, f"{name}: source_url must use https")

    actual_paths = {
        path.parent.resolve()
        for path in (ROOT / "skills").glob("*/SKILL.md")
        if path.is_file()
    }
    for unlisted in sorted(actual_paths - catalog_paths):
        fail(errors, f"unlisted skill directory: {unlisted.relative_to(ROOT)}")
    for missing in sorted(catalog_paths - actual_paths):
        fail(errors, f"catalog points to missing skill: {missing.relative_to(ROOT)}")

    validate_local_links(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: validated {len(records)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
