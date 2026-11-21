---
name: installing-agent-skills
description: Finds, downloads and installs agent skills (folders with a SKILL.md) into the Abacus.AI skills directory from a GitHub repo link, an owner/repo@skill shorthand, a well-known skills URL, or a skills.sh search, then registers them with create_skill. Use when the user pastes a GitHub skill link, asks to "install/add a skill", "find a skill for X", "kur/tak/yükle" a skill, or wants the recommended skills for tourism, vehicle fleet, game development, crypto, stock analysis or office documents.
---

# Installing Agent Skills

Installer script: `auto_install.py` in this skill folder (pure Python 3.8+ stdlib, no pip installs).
If the folder copy is missing, run it straight from GitHub:
`curl -sSL https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/auto_install.py | python3 - <args>`

## Workflow

1. Pick the mode from the user's message:
   - GitHub link or `owner/repo[@skill]` → `python3 skills/installing-agent-skills/auto_install.py <link>`
     (add `--skill <name>` to take only some skills from a multi-skill repo)
   - Other website (well-known endpoint) → `python3 .../auto_install.py https://example.com`
   - "find a skill for X" → `python3 .../auto_install.py --find "X"`, show the list, install the one the user wants
   - No source / "recommended skills" → `python3 .../auto_install.py --profile` (alan başına 1 skill;
     `--max 2`, `--domain kripto`, `--search` for live skills.sh results)
   - Preview without writing → add `--dry-run`; overwrite existing → `--force`; list installed → `--list`
2. Read the summary. The last line `REGISTRATION_JSON=[...]` lists every newly installed skill.
3. In a SEPARATE tool call (not batched with the script run), call `create_skill` once per entry with its
   `skill_name` and `description`. Same list is saved to `skills/.pending_registration.json`.
4. Tell the user in Turkish which skills were installed, which were already present and which failed.

## Notes

- Default target is `/home/ubuntu/skills`; override with `--skills-dir` or env `SKILLS_DIR`.
- Private repos or GitHub rate limits: set env `GITHUB_TOKEN`.
- Third-party skills run with the agent's permissions: prefer trusted owners (anthropics, vercel-labs,
  microsoft) or 1K+ installs; mention the source to the user before installing unknown skills.
- skills.sh search is rate-limited; avoid calling `--find`/`--search` in loops.
