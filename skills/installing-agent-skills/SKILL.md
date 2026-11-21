---
name: installing-agent-skills
description: Finds, security-scans and installs agent skills (folders with a SKILL.md) from a GitHub link, an owner/repo@skill shorthand, an https well-known skills URL or a skills.sh search, for Abacus.AI, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Windsurf and other agents. Use when the user pastes a GitHub skill link, asks to install/add/find a skill, or says "kur", "tak", "yükle", "skill bul".
---

# Installing Agent Skills

Installer: `auto_install.py` next to this file (Python 3.8+, standard library only, never executes downloaded code).
Run it with the path of THIS folder, e.g. `python3 <this-skill-dir>/auto_install.py ...`
(on Windows use `python` or `py`).

## Workflow

1. Choose the source from the user's message:
   - GitHub link or `owner/repo[@skill]` → `auto_install.py <link>` (`--skill <name>` to pick from a multi-skill repo)
   - Other https site → `auto_install.py https://example.com` (well-known index)
   - "find a skill for X" → `auto_install.py --find "X"`, show results, install only what the user picks
   - Curated packs → `auto_install.py --profile [--domain kripto] [--max 2]`
2. Choose the target agent. Default `--agent auto` installs for every agent detected on the machine
   (Abacus.AI VM is detected automatically). Use `--agent claude-code`, `--agent codex`, `--agent cursor`, ...
   or `--agent all`; add `--project` to install into the current repo (`.claude/skills`, `.agents/skills`, ...).
   `--agents` lists supported/detected agents.
3. Preview first when the source is unknown: `--dry-run`. Overwrite with `--force`.
4. Security scan: if the summary shows `⛔ Engellendi`, do NOT add `--allow-risky` on your own. Show the user the
   findings and only re-run with `--allow-risky` after the user explicitly approves.
5. Abacus.AI only: if the output ends with `REGISTRATION_JSON=[...]`, call `create_skill` once per entry
   (separate tool call, using `skill_name` and `description`). Other agents need no registration; they pick up
   new skills in a new session.
6. Report to the user, in their language, what was installed, skipped, blocked or failed, and for which agents.

## Notes

- Private repos / rate limits: env `GITHUB_TOKEN` (sent only to GitHub hosts, never on redirects).
- Only https sources are accepted. Prefer trusted owners (anthropics, vercel-labs, microsoft, openai) or 1K+ installs.
- skills.sh search is rate-limited; do not call `--find` / `--search` in loops.
