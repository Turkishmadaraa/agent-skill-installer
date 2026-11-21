#!/usr/bin/env python3
"""
Agent Skill Installer
=====================

Finds and installs agent skills (folders containing a SKILL.md) for many AI coding
agents: Abacus.AI, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode,
Windsurf, Cline, Amp, Goose, Kiro, Qwen Code, Roo Code, Trae and the universal
~/.agents/skills location. Pure standard library, Python 3.8+, Linux/macOS/Windows.

Sources:
  https://github.com/owner/repo[/tree/<ref>/<path>]   owner/repo   owner/repo@skill
  https://example.com   (well-known: /.well-known/agent-skills/index.json)
  --find "<query>"      (skills.sh search)      --profile  (curated packs)

Examples:
  python3 auto_install.py anthropics/skills@pdf
  python3 auto_install.py https://github.com/anthropics/skills --skill xlsx --agent claude-code
  python3 auto_install.py anthropics/skills@pdf --agent all --project
  python3 auto_install.py --agents          # show supported / detected agents

Security model: nothing downloaded is ever executed. Only HTTPS is used, archives are
extracted with traversal/symlink/size/count limits, GitHub tokens are sent only to
GitHub hosts and never across redirects, and skills containing high-risk patterns
(pipe-to-shell, credential paths, prompt-injection phrases, binaries) are refused
unless --allow-risky is given.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

VERSION = "2.0.1"
USER_AGENT = f"agent-skill-installer/{VERSION}"
SEARCH_API = "https://skills.sh"
TIMEOUT = 30
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
MAX_EXTRACT_BYTES = 300 * 1024 * 1024
MAX_ARCHIVE_FILES = 20000
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_SKILL = 1000
MAX_SCAN_BYTES = 1024 * 1024
MIN_INSTALLS_DEFAULT = 1000
WELL_KNOWN_PATHS = (".well-known/agent-skills", ".well-known/skills")
GITHUB_HOSTS = {"github.com", "api.github.com", "codeload.github.com", "raw.githubusercontent.com"}
SKIP_NAMES = {".git", ".github", "node_modules", "__pycache__", ".DS_Store",
              "README.md", "CHANGELOG.md", "SUMMARY.md", "OVERVIEW.md", "INSTALLATION_GUIDE.md"}
TRUSTED_OWNERS = {"anthropics", "vercel-labs", "microsoft", "openai", "google", "github",
                  "composiohq", "huggingface", "cloudflare", "supabase", "stripe"}
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")

# ----------------------------------------------------------------------------
# Supported agents: key -> (display name, global dir, project dir, detection paths)
# Paths follow the `skills` CLI (vercel-labs/skills) agent table.
# ----------------------------------------------------------------------------

HOME = Path.home()
XDG = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME / ".claude")
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or HOME / ".codex")
ABACUS_DIR = Path("/home/ubuntu/skills")

AGENTS = {
    "abacus":         ("Abacus.AI",       ABACUS_DIR,                         None,               [ABACUS_DIR]),
    "claude-code":    ("Claude Code",     CLAUDE_HOME / "skills",             ".claude/skills",   [CLAUDE_HOME]),
    "codex":          ("Codex",           HOME / ".agents/skills",            ".agents/skills",   [CODEX_HOME]),
    "cursor":         ("Cursor",          HOME / ".cursor/skills",            ".agents/skills",   [HOME / ".cursor"]),
    "gemini-cli":     ("Gemini CLI",      HOME / ".gemini/skills",            ".agents/skills",   [HOME / ".gemini"]),
    "github-copilot": ("GitHub Copilot",  HOME / ".copilot/skills",           ".agents/skills",   [HOME / ".copilot"]),
    "opencode":       ("OpenCode",        XDG / "opencode/skills",            ".agents/skills",   [XDG / "opencode"]),
    "windsurf":       ("Windsurf",        HOME / ".codeium/windsurf/skills",  ".windsurf/skills", [HOME / ".codeium/windsurf"]),
    "cline":          ("Cline",           HOME / ".agents/skills",            ".agents/skills",   [HOME / ".cline"]),
    "amp":            ("Amp",             XDG / "agents/skills",              ".agents/skills",   [XDG / "amp"]),
    "goose":          ("Goose",           XDG / "goose/skills",               ".goose/skills",    [XDG / "goose"]),
    "kiro-cli":       ("Kiro CLI",        HOME / ".kiro/skills",              ".kiro/skills",     [HOME / ".kiro"]),
    "qwen-code":      ("Qwen Code",       HOME / ".qwen/skills",              ".qwen/skills",     [HOME / ".qwen"]),
    "roo":            ("Roo Code",        HOME / ".roo/skills",               ".roo/skills",      [HOME / ".roo"]),
    "trae":           ("Trae",            HOME / ".trae/skills",              ".trae/skills",     [HOME / ".trae"]),
    "universal":      ("Universal (.agents)", HOME / ".agents/skills",        ".agents/skills",   []),
}
AGENT_ALIASES = {"claude": "claude-code", "copilot": "github-copilot", "gemini": "gemini-cli",
                 "kiro": "kiro-cli", "qwen": "qwen-code", "abacusai": "abacus", "agents": "universal"}

# Curated packs for --profile ("owner/repo@skill", ordered by preference).
PROFILE = {
    "Ofis Belgeleri": {
        "curated": ["anthropics/skills@xlsx", "anthropics/skills@docx", "anthropics/skills@pdf", "anthropics/skills@pptx"],
        "queries": ["excel", "docx"], "keywords": ["xlsx", "excel", "docx", "pdf", "pptx"]},
    "Turizm / Seyahat": {
        "curated": ["ailabs-393/ai-labs-claude-skills@travel-planner"],
        "queries": ["travel", "hotel"], "keywords": ["travel", "hotel", "itinerary", "tour", "flight"]},
    "Araç Filosu / Lojistik": {
        "curated": ["affaan-m/ecc@logistics-exception-management"],
        "queries": ["logistics", "fleet"], "keywords": ["logistic", "fleet", "route", "vehicle", "transport"]},
    "Oyun Geliştirme": {
        "curated": ["wshobson/agents@godot-gdscript-patterns", "wshobson/agents@unity-ecs-patterns"],
        "queries": ["game development", "unity"], "keywords": ["game", "unity", "godot", "unreal", "roblox"]},
    "Kripto": {
        "curated": ["binance/binance-skills-hub@crypto-market-rank", "claude-office-skills/skills@crypto-report"],
        "queries": ["crypto", "blockchain"], "keywords": ["crypto", "blockchain", "defi", "token", "binance"]},
    "Hisse Senedi / Finans": {
        "curated": ["gracefullight/stock-checker@stock-analysis", "claude-office-skills/skills@stock-analysis"],
        "queries": ["stock analysis", "trading"], "keywords": ["stock", "trading", "finance", "financial", "market"]},
}
DOMAIN_ALIASES = {"ofis": "Ofis", "office": "Ofis", "turizm": "Turizm", "seyahat": "Turizm", "travel": "Turizm",
                  "filo": "Filosu", "arac": "Filosu", "araç": "Filosu", "lojistik": "Filosu", "fleet": "Filosu",
                  "oyun": "Oyun", "game": "Oyun", "kripto": "Kripto", "crypto": "Kripto",
                  "hisse": "Hisse", "borsa": "Hisse", "finans": "Finans", "stock": "Hisse"}

# High-risk content patterns. A match blocks installation unless --allow-risky.
RISK_PATTERNS = [
    (re.compile(r"\b(curl|wget|iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]{0,300}\|\s*(sudo\s+)?(ba|z|da)?sh\b", re.I), "internetten indirilen kodu kabukta çalıştırma"),
    (re.compile(r"\b(curl|wget|iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]{0,300}\|\s*(iex|Invoke-Expression|python3?|node|perl|ruby)\b", re.I), "internetten indirilen kodu yorumlayıcıda çalıştırma"),
    (re.compile(r"base64\s+(-d|--decode)[^\n|]{0,100}\|\s*(ba|z)?sh\b", re.I), "gizlenmiş (base64) kabuk komutu"),
    (re.compile(r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(--no-preserve-root\s+)?(/|~|\$HOME)(\s|$|/\*)", re.I), "kök/ev dizinini silme"),
    (re.compile(r"(~|\$HOME|%USERPROFILE%)[/\\]\.(ssh|aws|gnupg|kube|docker)[/\\]", re.I), "kimlik bilgisi dosyalarına erişim"),
    (re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|prompts)", re.I), "prompt injection ifadesi"),
    (re.compile(r"\b(nc|ncat|netcat)\b[^\n]{0,80}\s-e\s", re.I), "reverse shell"),
]
BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".scr", ".com", ".bat", ".cmd", ".jar"}
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]")

# ----------------------------------------------------------------------------
# Output helpers
# ----------------------------------------------------------------------------

def clean(text) -> str:
    """Strip terminal control / bidi characters from untrusted text before printing."""
    return CTRL_RE.sub("", str(text))


def say(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:  # legacy Windows consoles
        print(msg.encode("ascii", "replace").decode(), flush=True)


def warn(msg: str) -> None:
    say(f"  [uyarı] {msg}")

# ----------------------------------------------------------------------------
# HTTPS-only networking
# ----------------------------------------------------------------------------

class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme != "https":
            raise urllib.error.HTTPError(newurl, code, "HTTPS olmayan yönlendirme engellendi", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnlyRedirect())


def http_get(url: str, accept: str | None = None, limit: int = MAX_DOWNLOAD_BYTES) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"Yalnızca HTTPS desteklenir: {clean(url)}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    if accept:
        req.add_header("Accept", accept)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and (parsed.hostname or "").lower() in GITHUB_HOSTS:
        req.add_unredirected_header("Authorization", f"Bearer {token}")  # never forwarded on redirect
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError(f"İndirme boyutu sınırı aşıldı: {clean(url)}")
    return data


def http_json(url: str):
    return json.loads(http_get(url, accept="application/json", limit=5 * 1024 * 1024).decode("utf-8"))

# ----------------------------------------------------------------------------
# SKILL.md / frontmatter
# ----------------------------------------------------------------------------

FM_RE = re.compile(r"^\ufeff?---\s*\r?\n(.*?)\r?\n---\s*(\r?\n|$)", re.S)


def parse_frontmatter(text: str) -> dict:
    """Minimal YAML frontmatter parser for `key: value` (incl. quoted / folded values)."""
    m = FM_RE.match(text)
    if not m:
        return {}
    out, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv and not line.startswith((" ", "\t")):
            key, val = kv.group(1), kv.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                val = ""
            out[key] = val.strip("'\"")
        elif key and line.strip():
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def sanitize_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", str(name).lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64] or "skill"


DROP_KEYS = {"name", "description", "allowed-tools", "allowed_tools"}


def normalize_skill_md(text: str, name: str, description: str) -> str:
    """Rewrite name/description safely, keep other metadata (license, metadata...), and drop
    `allowed-tools` so a third-party skill can never pre-approve tools (e.g. Bash) in Claude Code."""
    m = FM_RE.match(text)
    body = text[m.end():] if m else text
    kept, keep = [], False
    for line in (m.group(1).splitlines() if m else []):
        kv = re.match(r"^([A-Za-z0-9_-]+):", line)
        if kv and not line.startswith((" ", "\t")):
            keep = kv.group(1).lower() not in DROP_KEYS
        if keep:
            kept.append(clean(line))
    desc = clean(description).replace("\n", " ").strip()[:1024] or f"Skill {name}."
    desc = json.dumps(desc, ensure_ascii=False)  # always quoted -> valid YAML, no key injection
    extra = "".join(f"{line}\n" for line in kept)
    return f"---\nname: {name}\ndescription: {desc}\n{extra}---\n{body.lstrip(chr(10))}"


def list_installed(skills_dir: Path) -> dict:
    result = {}
    if not skills_dir.is_dir():
        return result
    for child in sorted(skills_dir.iterdir()):
        if child.name.startswith("."):
            continue
        md = child / "SKILL.md"
        if child.is_dir() and md.is_file():
            fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            result[child.name] = fm.get("description", "")
    return result

# ----------------------------------------------------------------------------
# Safe archive extraction
# ----------------------------------------------------------------------------

def _safe_rel(name: str) -> PurePosixPath | None:
    s = str(name).replace("\\", "/")
    if not s or "\x00" in s or re.match(r"^[A-Za-z]:", s):
        return None
    p = PurePosixPath(s)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    return p


def _bounded_copy(src, dst, budget: list) -> None:
    """Copy stream while enforcing the real (not declared) total size."""
    while True:
        chunk = src.read(64 * 1024)
        if not chunk:
            return
        budget[0] -= len(chunk)
        if budget[0] < 0:
            raise RuntimeError("Arşiv açılmış boyut sınırını aşıyor (zip bomb?)")
        dst.write(chunk)


def extract_archive(data: bytes, dest: Path) -> None:
    budget, count = [MAX_EXTRACT_BYTES], 0
    dest_resolved = dest.resolve()

    def target_for(rel: PurePosixPath) -> Path:
        t = dest / Path(*rel.parts)
        if dest_resolved not in t.resolve().parents:
            raise RuntimeError("Arşivde güvensiz yol")
        return t

    if data[:2] == b"\x1f\x8b" or data[257:262] == b"ustar":
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for m in tf:
                rel = _safe_rel(m.name)
                if rel is None or not (m.isfile() or m.isdir()):
                    continue  # symlinks, hardlinks, devices, traversal are skipped
                count += 1
                if count > MAX_ARCHIVE_FILES:
                    raise RuntimeError("Arşivde çok fazla dosya")
                target = target_for(rel)
                if m.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with src, open(target, "wb") as dst:
                    _bounded_copy(src, dst, budget)
    elif data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                rel = _safe_rel(info.filename)
                if rel is None or info.is_dir():
                    continue
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue  # symlink entry
                count += 1
                if count > MAX_ARCHIVE_FILES:
                    raise RuntimeError("Arşivde çok fazla dosya")
                target = target_for(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    _bounded_copy(src, dst, budget)
    else:
        raise RuntimeError("Desteklenmeyen arşiv formatı (yalnızca tar.gz / zip)")

# ----------------------------------------------------------------------------
# Skill discovery, risk scan and copying
# ----------------------------------------------------------------------------

def discover_skills(root: Path) -> list[dict]:
    """Find every SKILL.md under root; nested SKILL.md files inside another skill are ignored."""
    found = []
    for md in sorted(root.rglob("SKILL.md"), key=lambda p: len(p.parts)):
        if md.is_symlink() or any(part in SKIP_NAMES for part in md.relative_to(root).parts):
            continue
        folder = md.parent
        if any(folder != s["path"] and s["path"] in folder.parents for s in found):
            continue
        fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        name = fm.get("name") or folder.name
        if any(sanitize_name(s["name"]) == sanitize_name(name) for s in found):
            continue
        found.append({"path": folder, "name": name, "description": fm.get("description", "")})
    return found


def skill_files(src: Path) -> list[Path]:
    return [p for p in src.rglob("*") if p.is_file() and not p.is_symlink()
            and not any(part in SKIP_NAMES for part in p.relative_to(src).parts)]


def scan_risks(src: Path) -> list[str]:
    """Static scan of a skill folder. Returns human-readable findings (empty = clean)."""
    findings = []
    for p in skill_files(src):
        rel = p.relative_to(src).as_posix()
        if p.suffix.lower() in BINARY_EXTS:
            findings.append(f"{rel}: çalıştırılabilir/ikili dosya")
            continue
        try:
            if p.stat().st_size > MAX_SCAN_BYTES:
                continue
            raw = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            if raw[:4] in (b"\x7fELF", b"MZ\x90\x00") or raw[:2] == b"MZ":
                findings.append(f"{rel}: çalıştırılabilir ikili içerik")
            continue
        text = raw.decode("utf-8", errors="replace")
        for rx, label in RISK_PATTERNS:
            if rx.search(text):
                findings.append(f"{rel}: {label}")
    return findings


def copy_skill(src: Path, skills_dir: Path, folder: str, description: str, force: bool) -> str:
    """Atomically copy skill folder into skills_dir/<folder>. Returns status."""
    target = skills_dir / folder
    if (target.exists() or target.is_symlink()) and not force:
        return "exists"
    files = skill_files(src)
    if len(files) > MAX_FILES_PER_SKILL:
        raise RuntimeError(f"{folder}: çok fazla dosya ({len(files)})")
    if sum(p.stat().st_size for p in files) > MAX_UNPACKED_BYTES:
        raise RuntimeError(f"{folder}: skill klasörü 50 MB sınırını aşıyor")
    skills_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{folder}-", dir=skills_dir))
    try:
        for p in files:
            dst = staging / p.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dst)  # content only: no permission bits (no setuid / exec flags)
        md = staging / "SKILL.md"
        md.write_text(normalize_skill_md(md.read_text(encoding="utf-8", errors="replace"), folder, description),
                      encoding="utf-8")
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return "installed"


def install_skill(path: Path, name: str, desc: str, targets: list, args, source: str) -> dict:
    """Scan once, then copy the skill into every target directory."""
    folder = sanitize_name(name)
    res = {"name": folder, "description": clean(desc), "source": source, "targets": {}}
    risks = scan_risks(path)
    if risks:
        say(f"  ⚠️  {folder}: güvenlik taramasında {len(risks)} bulgu:")
        for r in risks[:10]:
            say(f"       - {clean(r)}")
        if not args.allow_risky:
            res["status"] = "blocked"
            return res
        warn("--allow-risky verildi, yine de kuruluyor.")
    if args.dry_run:
        res["status"] = "dry-run"
        return res
    for agent, d in targets:
        res["targets"][agent] = copy_skill(path, d, folder, desc, args.force)
    statuses = set(res["targets"].values())
    res["status"] = "installed" if "installed" in statuses else "exists"
    return res

# ----------------------------------------------------------------------------
# Target resolution (which agents / directories)
# ----------------------------------------------------------------------------

def detected_agents() -> list[str]:
    return [k for k, (_, _, _, det) in AGENTS.items() if det and any(Path(p).exists() for p in det)]


def resolve_targets(args) -> list[tuple[str, Path]]:
    if args.skills_dir:
        return [("custom", Path(args.skills_dir).expanduser().resolve())]
    env = os.environ.get("SKILLS_DIR")
    if env and not args.agent:
        return [("custom", Path(env).expanduser().resolve())]
    wanted = []
    for a in args.agent or ["auto"]:
        for part in a.split(","):
            key = AGENT_ALIASES.get(part.strip().lower(), part.strip().lower())
            if key in ("auto", "all"):
                det = detected_agents()
                wanted += det or ["universal"]
            elif key in AGENTS:
                wanted.append(key)
            elif key:
                raise ValueError(f"Bilinmeyen ajan: {clean(part)}  (desteklenenler için --agents)")
    out, seen = [], set()
    for key in dict.fromkeys(wanted):
        _, gdir, pdir, _ = AGENTS[key]
        if args.project:
            if pdir is None:
                continue  # Abacus.AI has no project-level dir
            d = (Path.cwd() / pdir).resolve()
        else:
            d = Path(gdir).expanduser()
        if d.as_posix() in seen:
            continue
        seen.add(d.as_posix())
        out.append((key, d))
    if not out:
        raise ValueError("Hedef klasör bulunamadı (--project ile Abacus.AI desteklenmez).")
    return out


def cmd_agents() -> None:
    det = set(detected_agents())
    say("Desteklenen ajanlar (✔ = bu bilgisayarda bulundu):\n")
    for key, (disp, gdir, pdir, _) in AGENTS.items():
        mark = "✔" if key in det else " "
        say(f"  {mark} {key:<15} {disp:<22} global: {Path(gdir).as_posix():<40} proje: {pdir or '-'}")

# ----------------------------------------------------------------------------
# Source parsing (GitHub / well-known)
# ----------------------------------------------------------------------------

GH_URL_RE = re.compile(r"^https://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)(?:/(?:tree|blob)/([^/\s?#]+)(?:/([^?#]*))?)?/?$")
SHORTHAND_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]+?)(?:@([A-Za-z0-9._-]+))?$")


def parse_source(src: str) -> dict:
    src = src.strip().strip("<>\"'")
    if src.startswith("http://"):
        raise ValueError("Güvenlik nedeniyle yalnızca https:// linkleri kabul edilir.")
    m = GH_URL_RE.match(src)
    if m:
        owner, repo, ref, sub = m.groups()
        repo = repo[:-4] if repo.endswith(".git") else repo
        if sub and sub.endswith("SKILL.md"):
            sub = sub[: -len("SKILL.md")].rstrip("/")
        spec = {"type": "github", "owner": owner, "repo": repo, "ref": ref, "subpath": sub or "", "skill": None}
    else:
        m = SHORTHAND_RE.match(src)
        if m:
            owner, repo, skill = m.groups()
            spec = {"type": "github", "owner": owner, "repo": repo, "ref": None, "subpath": "", "skill": skill}
        elif src.startswith("https://"):
            return {"type": "wellknown", "url": src}
        else:
            raise ValueError(f"Kaynak anlaşılamadı: {clean(src)}  (örnek: https://github.com/sahip/repo veya sahip/repo)")
    if not OWNER_RE.match(spec["owner"]) or not REPO_RE.match(spec["repo"]) or spec["repo"] in (".", ".."):
        raise ValueError("Geçersiz GitHub sahip/repo adı.")
    if spec["ref"] and (not REF_RE.match(spec["ref"]) or ".." in spec["ref"]):
        raise ValueError("Geçersiz dal/etiket adı.")
    if spec["subpath"] and _safe_rel(urllib.parse.unquote(spec["subpath"])) is None:
        raise ValueError("Geçersiz repo içi yol.")
    return spec


def fetch_github(owner: str, repo: str, ref: str | None, workdir: Path) -> Path:
    ref = ref or "HEAD"
    url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{urllib.parse.quote(ref, safe='')}"
    say(f"  ↓ GitHub'dan indiriliyor: {owner}/{repo} ({ref})")
    try:
        data = http_get(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Repo bulunamadı veya özel (private): {owner}/{repo}. "
                               f"Özel repo için GITHUB_TOKEN ortam değişkenini ayarlayın.")
        raise
    extract_archive(data, workdir)
    roots = [p for p in workdir.iterdir() if p.is_dir()]
    return roots[0] if len(roots) == 1 else workdir


def install_from_github(spec: dict, targets: list, args, only: set | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="skill-dl-") as tmp:
        root = fetch_github(spec["owner"], spec["repo"], spec["ref"], Path(tmp))
        base = root
        if spec["subpath"]:
            base = (root / Path(*_safe_rel(urllib.parse.unquote(spec["subpath"])).parts)).resolve()
            if base != root.resolve() and root.resolve() not in base.parents:
                raise RuntimeError("Repo içi yol kök dışına çıkıyor.")
        if not base.is_dir():
            raise RuntimeError(f"Repo içinde yol bulunamadı: {clean(spec['subpath'])}")
        skills = discover_skills(base)
        if not skills:
            raise RuntimeError("Bu kaynakta SKILL.md içeren bir skill bulunamadı.")
        wanted = set(only or set())
        if spec.get("skill"):
            wanted.add(spec["skill"])
        if args.skill:
            wanted.update(args.skill)
        if wanted:
            wl = {sanitize_name(w) for w in wanted}
            skills = [s for s in skills if sanitize_name(s["name"]) in wl or sanitize_name(s["path"].name) in wl]
            if not skills:
                raise RuntimeError(f"İstenen skill bulunamadı: {clean(', '.join(sorted(wanted)))}")
        source = f"{spec['owner']}/{spec['repo']}"
        return [install_skill(s["path"], s["name"], s["description"], targets, args, source) for s in skills]


def install_from_wellknown(url: str, targets: list, args) -> list[dict]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("Yalnızca https:// well-known adresleri desteklenir.")
    base_path = parsed.path.rstrip("/")
    origin = f"https://{parsed.netloc}"
    candidates = []
    for wk in WELL_KNOWN_PATHS:
        candidates.append(f"{origin}{base_path}/{wk}")
        if base_path:
            candidates.append(f"{origin}/{wk}")
    index, base = None, None
    for b in candidates:
        try:
            data = http_json(f"{b}/index.json")
            if isinstance(data, dict) and isinstance(data.get("skills"), list):
                index, base = data, b
                break
        except Exception:
            continue
    if not index:
        raise RuntimeError(f"Well-known skill listesi bulunamadı: {clean(url)}")
    say(f"  ✓ Well-known index bulundu: {base}/index.json ({len(index['skills'])} skill)")
    results = []
    wanted = {sanitize_name(s) for s in (args.skill or [])}
    for entry in index["skills"][:200]:
        if not isinstance(entry, dict):
            continue
        name = sanitize_name(str(entry.get("name", "")).strip() or "skill")
        if wanted and name not in wanted:
            continue
        with tempfile.TemporaryDirectory(prefix="skill-wk-") as tmp:
            d = Path(tmp) / name
            d.mkdir()
            try:
                if "files" in entry:  # v0.1.0: list of files
                    files = entry["files"]
                    if not isinstance(files, list) or len(files) > MAX_FILES_PER_SKILL:
                        raise RuntimeError("geçersiz dosya listesi")
                    for f in files:
                        rel = _safe_rel(str(f))
                        if rel is None:
                            continue
                        t = d / Path(*rel.parts)
                        t.parent.mkdir(parents=True, exist_ok=True)
                        t.write_bytes(http_get(f"{base}/{urllib.parse.quote(name)}/"
                                               + "/".join(urllib.parse.quote(x) for x in rel.parts)))
                else:  # v0.2.0: single artifact + sha256 digest
                    art_url = urllib.parse.urljoin(base + "/", str(entry["url"]))
                    blob = http_get(art_url)
                    digest = str(entry.get("digest", ""))
                    if digest.startswith("sha256:") and hashlib.sha256(blob).hexdigest() != digest[7:].lower():
                        raise RuntimeError("sha256 özeti uyuşmuyor")
                    if entry.get("type") == "archive":
                        extract_archive(blob, d)
                        found = discover_skills(d)
                        if found:
                            d = found[0]["path"]
                    else:
                        (d / "SKILL.md").write_bytes(blob)
                if not (d / "SKILL.md").is_file():
                    raise RuntimeError("SKILL.md yok")
                results.append(install_skill(d, name, str(entry.get("description", "")), targets, args,
                                             parsed.hostname))
            except Exception as e:
                warn(f"{name} atlandı: {clean(e)}")
    return results

# ----------------------------------------------------------------------------
# skills.sh search & profile mode
# ----------------------------------------------------------------------------

def search_skills(query: str) -> list[dict]:
    try:
        data = http_json(f"{SEARCH_API}/api/search?" + urllib.parse.urlencode({"q": query}))
        return [s for s in data.get("skills", []) if isinstance(s, dict) and s.get("source") and s.get("skillId")]
    except Exception as e:
        warn(f"skills.sh araması başarısız ({clean(query)}): {clean(e)}")
        return []


def is_trusted(item: dict, min_installs: int) -> bool:
    owner = str(item["source"]).split("/")[0].lower()
    try:
        installs = int(item.get("installs") or 0)
    except (TypeError, ValueError):
        installs = 0
    return owner in TRUSTED_OWNERS or installs >= min_installs


def cmd_find(query: str, installed: dict, min_installs: int) -> None:
    say(f"\n🔎 skills.sh üzerinde aranıyor: \"{clean(query)}\"\n")
    res = search_skills(query)
    if not res:
        say("  Sonuç bulunamadı.")
        return
    for s in res[:15]:
        sid = clean(s["skillId"])
        mark = "✅ kurulu" if sanitize_name(sid) in installed else ("⭐" if is_trusted(s, min_installs) else "⚠️ az kurulum")
        say(f"  • {sid:<34} {clean(s.get('installs', 0)):>8} kurulum  {mark}")
        say(f"      kur: python3 auto_install.py {clean(s['source'])}@{sid}")
    say(f"\nDaha fazlası: {SEARCH_API}")


def pick_profile_skills(installed: dict, per_domain: int, min_installs: int,
                        domains: list | None, live_search: bool) -> list:
    picks, seen = [], set(installed)
    for domain, cfg in PROFILE.items():
        if domains and not any(d.lower() in domain.lower() for d in domains):
            continue
        ranked = []
        for ref in cfg["curated"]:
            source, skill_id = ref.split("@", 1)
            ranked.append({"source": source, "skillId": skill_id, "installs": "seçili"})
        if live_search:
            pool = {}
            for q in cfg["queries"]:
                for s in search_skills(q):
                    if "/" in s["source"] and any(k in s["skillId"].lower() for k in cfg["keywords"]):
                        pool.setdefault(f"{s['source']}@{s['skillId']}", s)
            ranked += sorted((s for s in pool.values() if is_trusted(s, min_installs)),
                             key=lambda s: -int(s.get("installs") or 0))
        count = 0
        for s in ranked:
            key = sanitize_name(s["skillId"])
            if key in seen:
                continue
            seen.add(key)
            picks.append((domain, s))
            count += 1
            if count >= per_domain:
                break
    return picks

# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def report(results: list, targets: list) -> None:
    say("\n" + "=" * 64)
    say("📦 KURULUM ÖZETİ")
    say("=" * 64)
    for agent, d in targets:
        say(f"  🎯 {AGENTS.get(agent, ('Özel klasör',))[0]:<22} {d.as_posix()}")
    icons = {"installed": "✅ Kuruldu     ", "exists": "⏭️  Zaten kurulu", "dry-run": "🧪 Kurulacaktı ",
             "blocked": "⛔ Engellendi  "}
    for r in results:
        say(f"  {icons[r['status']]}: {r['name']}  ({clean(r['source'])})")
        if r["status"] == "installed" and r["description"]:
            say(f"                   {r['description'][:150]}")
    if not results:
        say("  Hiçbir skill kurulmadı.")
    if any(r["status"] == "exists" for r in results):
        say("  (üzerine yazmak için --force)")
    if any(r["status"] == "blocked" for r in results):
        say("  ⛔ Engellenen skill'leri içeriğini inceledikten sonra --allow-risky ile kurabilirsiniz.")
    installed = [r for r in results if r["status"] == "installed" and r["targets"].get("abacus") == "installed"]
    if installed:
        manifest = [{"skill_name": r["name"], "description": (r["description"] or f"Skill {r['name']}.")[:1024]}
                    for r in installed]
        try:
            (ABACUS_DIR / ".pending_registration.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        say("\n🔔 ABACUS.AI KAYIT ADIMI (ajan için): her skill için ayrı bir adımda")
        say("   `create_skill` aracını şu argümanlarla çağırın:")
        for m in manifest:
            say("   create_skill(" + json.dumps(m, ensure_ascii=False) + ")")
        say("\nREGISTRATION_JSON=" + json.dumps(manifest, ensure_ascii=False))
    if any(a != "abacus" for a, _ in targets) and any(r["status"] == "installed" for r in results):
        say("\nℹ️  Claude Code / Codex / Cursor vb. yeni skill'leri yeni oturumda otomatik görür.")
    say("=" * 64)

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Çok ajanlı skill kurulum aracı (Abacus.AI, Claude Code, Codex, Cursor...)")
    ap.add_argument("sources", nargs="*", help="GitHub linki, sahip/repo, sahip/repo@skill veya https well-known URL")
    ap.add_argument("--skill", action="append", help="Kaynaktan yalnızca bu skill'i kur (tekrarlanabilir)")
    ap.add_argument("--agent", "-a", action="append",
                    help="Hedef ajan(lar): auto (vars.), all, abacus, claude-code, codex, cursor, gemini-cli, "
                         "github-copilot, opencode, windsurf, cline, amp, goose, kiro-cli, qwen-code, roo, trae, universal")
    ap.add_argument("--project", action="store_true", help="Global yerine mevcut proje klasörüne kur (.claude/skills, .agents/skills...)")
    ap.add_argument("--agents", action="store_true", help="Desteklenen ve bulunan ajanları listele")
    ap.add_argument("--find", metavar="SORGU", help="skills.sh üzerinde skill ara")
    ap.add_argument("--profile", action="store_true", help="Seçili paketleri kur (ofis, turizm, filo, oyun, kripto, hisse)")
    ap.add_argument("--domain", action="append", help="--profile ile yalnızca bu alan(lar)")
    ap.add_argument("--search", action="store_true", help="--profile: canlı skills.sh araması da yap")
    ap.add_argument("--max", type=int, default=1, help="--profile: alan başına en fazla skill (vars: 1)")
    ap.add_argument("--min-installs", type=int, default=MIN_INSTALLS_DEFAULT, help="Güvenilir sayılmak için en az kurulum")
    ap.add_argument("--list", action="store_true", help="Hedef klasörlerdeki kurulu skill'leri listele")
    ap.add_argument("--skills-dir", help="Belirli bir klasöre kur (ajan seçimini geçersiz kılar)")
    ap.add_argument("--force", action="store_true", help="Var olan skill'in üzerine yaz")
    ap.add_argument("--dry-run", action="store_true", help="Kurmadan ne yapılacağını göster")
    ap.add_argument("--allow-risky", action="store_true", help="Güvenlik taramasında bulgu olan skill'leri de kur")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    say(f"🧩 Agent Skill Installer v{VERSION}")
    if args.agents:
        cmd_agents()
        return 0
    try:
        targets = resolve_targets(args)
    except ValueError as e:
        say(f"❌ {e}")
        return 2
    installed: dict = {}
    for _, d in targets:
        installed.update(list_installed(d))
    for agent, d in targets:
        say(f"🎯 Hedef: {AGENTS.get(agent, ('Özel klasör',))[0]} → {d.as_posix()}")
    say(f"📋 Kurulu skill sayısı: {len(installed)}")

    if args.list:
        for name, desc in installed.items():
            say(f"  • {name}: {clean(desc)[:120]}")
        return 0
    if args.find:
        cmd_find(args.find, installed, args.min_installs)
        return 0
    if args.domain or args.search:
        args.profile = True
    if not args.sources and not args.profile:
        ap.print_help()
        return 0

    results, errors = [], 0
    for src in args.sources:
        say(f"\n▶ Kaynak: {clean(src)}")
        try:
            spec = parse_source(src)
            if spec["type"] == "github":
                results += install_from_github(spec, targets, args)
            else:
                results += install_from_wellknown(spec["url"], targets, args)
        except Exception as e:
            errors += 1
            say(f"  ❌ Hata: {clean(e)}")

    if args.profile:
        domains = [DOMAIN_ALIASES.get(d.lower(), d) for d in (args.domain or [])] or None
        say(f"\n▶ Profil modu, alan başına en fazla {args.max} eksik skill:")
        by_source: dict = {}
        for domain, s in pick_profile_skills(installed, args.max, args.min_installs, domains, args.search):
            say(f"  • {domain:<24} → {clean(s['skillId'])} ({clean(s['source'])})")
            by_source.setdefault(s["source"], set()).add(s["skillId"])
        for source, names in by_source.items():
            try:
                if "/" not in source:
                    saved, args.skill = args.skill, sorted(names)
                    try:
                        results += install_from_wellknown(f"https://{source}", targets, args)
                    finally:
                        args.skill = saved
                    continue
                owner, repo = source.split("/", 1)
                spec = parse_source(f"{owner}/{repo}")
                results += install_from_github(spec, targets, args, only=names)
            except Exception as e:
                errors += 1
                say(f"  ❌ {clean(source)}: {clean(e)}")

    report(results, targets)
    if any(r["status"] == "blocked" for r in results):
        return 3
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
