# SPDX-License-Identifier: Apache-2.0
"""Validate .claude/ agent setup for structural correctness.

The .claude/ directory is checked into the repo and affects how AI
assistants interact with the codebase. Broken SKILL.md frontmatter,
missing hook scripts, or dangling settings.json references silently
degrade the developer experience.

Validation patterns adapted from harness-eval-lab inspection rules
(frontmatter, structural, hooks, cross-type checks).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_DIR = ROOT / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"


def _discover_skills() -> list[Path]:
    """Return all skill directories under .claude/skills/."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir() and d.name != "__pycache__")


def _skill_id(path: Path) -> str:
    return path.name


def _parse_yaml_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


SKILL_DIRS = _discover_skills()

REQUIRED_FRONTMATTER_FIELDS = ("name", "description")


class TestSkillFrontmatter:
    """Validate SKILL.md files have correct YAML frontmatter."""

    @pytest.mark.parametrize(
        "skill_dir", SKILL_DIRS, ids=[_skill_id(d) for d in SKILL_DIRS]
    )
    def test_skill_md_exists(self, skill_dir: Path) -> None:
        """Each skill directory must contain a SKILL.md file."""
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), (
            f"Skill '{skill_dir.name}' is missing SKILL.md. "
            "Every skill directory must contain a SKILL.md file."
        )

    @pytest.mark.parametrize(
        "skill_dir", SKILL_DIRS, ids=[_skill_id(d) for d in SKILL_DIRS]
    )
    def test_skill_has_valid_frontmatter(self, skill_dir: Path) -> None:
        """SKILL.md must have parseable YAML frontmatter."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("SKILL.md missing (covered by test_skill_md_exists)")

        content = skill_md.read_text()
        fm = _parse_yaml_frontmatter(content)
        assert fm is not None, (
            f"Skill '{skill_dir.name}' has no YAML frontmatter. "
            "SKILL.md must start with ---\\n<yaml>\\n---"
        )

    @pytest.mark.parametrize(
        "skill_dir", SKILL_DIRS, ids=[_skill_id(d) for d in SKILL_DIRS]
    )
    def test_skill_has_required_fields(self, skill_dir: Path) -> None:
        """Frontmatter must include name and description."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("SKILL.md missing")

        fm = _parse_yaml_frontmatter(skill_md.read_text())
        if fm is None:
            pytest.skip("No frontmatter (covered by other test)")

        for field in REQUIRED_FRONTMATTER_FIELDS:
            assert field in fm, (
                f"Skill '{skill_dir.name}' frontmatter missing '{field}'. "
                f"Required fields: {', '.join(REQUIRED_FRONTMATTER_FIELDS)}"
            )
            value = fm[field]
            assert isinstance(value, str) and value.strip(), (
                f"Skill '{skill_dir.name}' frontmatter field '{field}' is empty."
            )


class TestSettingsJson:
    """Validate .claude/settings.json structure and references."""

    def test_settings_json_exists(self) -> None:
        """settings.json must exist if .claude/ directory exists."""
        if not CLAUDE_DIR.exists():
            pytest.skip("No .claude/ directory")
        assert SETTINGS_PATH.exists(), ".claude/settings.json is missing."

    def test_settings_json_is_valid(self) -> None:
        """settings.json must be valid JSON."""
        if not SETTINGS_PATH.exists():
            pytest.skip("settings.json missing")

        content = SETTINGS_PATH.read_text()
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            pytest.fail(f"settings.json is not valid JSON: {e}")


class TestHooks:
    """Validate hook scripts referenced in settings.json."""

    @staticmethod
    def _extract_hook_commands() -> list[str]:
        """Extract all hook command paths from settings.json."""
        if not SETTINGS_PATH.exists():
            return []
        data = json.loads(SETTINGS_PATH.read_text())
        hooks_config = data.get("hooks", {})
        commands: list[str] = []
        for _event, hook_list in hooks_config.items():
            if not isinstance(hook_list, list):
                continue
            for entry in hook_list:
                inner_hooks = entry.get("hooks", [])
                for hook in inner_hooks:
                    cmd = hook.get("command", "")
                    if cmd:
                        commands.append(cmd)
        return commands

    def test_hook_scripts_exist(self) -> None:
        """All hook commands in settings.json must point to existing files."""
        commands = self._extract_hook_commands()
        if not commands:
            pytest.skip("No hook commands in settings.json")

        missing = []
        for cmd in commands:
            script_path = ROOT / cmd
            if not script_path.exists():
                missing.append(cmd)

        assert not missing, (
            f"settings.json references {len(missing)} missing hook script(s):\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_hook_scripts_are_executable(self) -> None:
        """Hook scripts must have the executable bit set."""
        commands = self._extract_hook_commands()
        if not commands:
            pytest.skip("No hook commands in settings.json")

        not_executable = []
        for cmd in commands:
            script_path = ROOT / cmd
            if script_path.exists() and not os.access(script_path, os.X_OK):
                not_executable.append(cmd)

        assert not not_executable, (
            f"{len(not_executable)} hook script(s) are not executable:\n"
            + "\n".join(f"  - {s}" for s in not_executable)
            + "\nFix with: chmod +x <script>"
        )


class TestSkillCrossReferences:
    """Validate that skills referencing other skills by name point to skills that exist."""

    @staticmethod
    def _get_skill_names() -> set[str]:
        """Get all skill directory names."""
        return {d.name for d in SKILL_DIRS}

    @pytest.mark.parametrize(
        "skill_dir", SKILL_DIRS, ids=[_skill_id(d) for d in SKILL_DIRS]
    )
    def test_skill_references_resolve(self, skill_dir: Path) -> None:
        """Skills that reference other skills via backtick notation must reference existing skills."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("SKILL.md missing")

        content = skill_md.read_text()
        known_skills = self._get_skill_names()

        # Match patterns like: invoke the `skill-name` skill
        # or: consult the `skill-name` skill
        refs = re.findall(r"`([a-z][a-z0-9-]+)`\s+skill", content)

        broken = [ref for ref in refs if ref not in known_skills]
        assert not broken, (
            f"Skill '{skill_dir.name}' references {len(broken)} "
            f"non-existent skill(s): {', '.join(broken)}"
        )
