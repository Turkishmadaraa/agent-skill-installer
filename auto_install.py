#!/usr/bin/env python3
"""
Abacus.AI Skill Auto-Installer
==============================

Finds and installs agent skills (folders containing a SKILL.md) into the
Abacus.AI skills directory. Pure standard library, works on Linux / macOS /
Windows with Python 3.8+.

Sources supported (mirrors the provider model of the `skills` CLI):
  * GitHub repo links   https://github.com/owner/repo
                        https://github.com/owner/repo/tree/<branch>/<path>
                        owner/repo   |   owner/repo@skill-name
  * Well-known endpoints https://example.com  (/.well-known/agent-skills/index.json,
                        falls back to /.well-known/skills/index.json; v0.1 + v0.2 schemas)
  * skills.sh search    --find "<query>"   (same API as `npx skills find`)
  * Profile mode        --profile           (searches skills.sh for the user's domains
                        and installs the most popular missing skills)

Usage examples:
  python3 auto_install.py https://github.com/anthropics/skills
  python3 auto_install.py anthropics/skills@pdf
  python3 auto_install.py --find "stock analysis"
  python3 auto_install.py --profile --max 2
  python3 auto_install.py --list

After installing, new skills must be registered in Abacus.AI with the agent tool
`create_skill(skill_name, description)`. The script prints the exact calls.
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

VERSION = "1.0.0"
USER_AGENT = f"abacus-skill-installer/{VERSION}"
SEARCH_API = os.environ.get("SKILLS_API_URL", "https://skills.sh").rstrip("/")
TIMEOUT = 30
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_FILES_PER_SKILL = 1000
MIN_INSTALLS_DEFAULT = 1000
WELL_KNOWN_PATHS = (".well-known/agent-skills", ".well-known/skills")
# Files that Abacus.AI conventions say must not live inside a skill folder.
SKIP_NAMES = {".git", ".github", "node_modules", "__pycache__", ".DS_Store",
              "README.md", "CHANGELOG.md", "SUMMARY.md", "OVERVIEW.md", "INSTALLATION_GUIDE.md"}
TRUSTED_OWNERS = {"anthropics", "vercel-labs", "microsoft", "openai", "google", "github",
                  "composiohq", "huggingface", "cloudflare", "supabase", "stripe"}

# Domain profile of this user (tourism, vehicle fleet, game dev, crypto, stocks, office docs).
# "curated": hand-checked picks from skills.sh (ordered by preference, "owner/repo@skill").
# "queries"/"keywords": used only with --search (live skills.sh search; results must contain a keyword).
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

# ----------------------------------------------------------------------------
# Output helpers (Turkish user-facing text)
# ----------------------------------------------------------------------------

def say(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:  # old Windows consoles
        print(msg.encode("ascii", "replace").decode(), flush=True)


def warn(msg: str) -> None:
    say(f"  [uyarı] {msg}")


# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------

def detect_skills_dir(explicit: str | None) -> Path:
    """Abacus.AI VM uses /home/ubuntu/skills; elsewhere fall back to ./skills or ~/skills."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    for cand in (Path("/home/ubuntu/skills"), Path.cwd() / "skills", Path.home() / "skills"):
        if cand.is_dir():
            return cand.resolve()
    if Path("/home/ubuntu").is_dir():
        return Path("/home/ubuntu/skills")
    return (Path.cwd() / "skills").resolve()


def http_get(url: str, accept: str | None = None, limit: int = MAX_DOWNLOAD_BYTES) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    host = urllib.parse.urlparse(url).hostname or ""
    if token and host.endswith("github.com"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError(f"İndirme boyutu sınırı aşıldı: {url}")
    return data


def http_json(url: str):
    return json.loads(http_get(url, accept="application/json").decode("utf-8"))


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
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64] or "skill"


def normalize_skill_md(text: str, name: str, description: str) -> str:
    """Ensure SKILL.md starts with Abacus-style frontmatter (name + description only)."""
    m = FM_RE.match(text)
    body = text[m.end():] if m else text
    desc = description.replace("\n", " ").strip()[:1024] or f"Skill {name}."
    if any(c in desc for c in ":#\"'") or desc.startswith(("-", "[", "{", "*", "&", "!", "|", ">")):
        desc = json.dumps(desc, ensure_ascii=False)
    return f"---\nname: {name}\ndescription: {desc}\n---\n{body.lstrip(chr(10))}"


def list_installed(skills_dir: Path) -> dict:
    """Return {folder_name: description} for every installed skill."""
    result = {}
    if not skills_dir.is_dir():
        return result
    for child in sorted(skills_dir.iterdir()):
        if child.name.startswith("."):
            continue  # shared skills (.shared__*) and hidden folders
        md = child / "SKILL.md"
        if child.is_dir() and md.is_file():
            fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            result[child.name] = fm.get("description", "")
    return result


# ----------------------------------------------------------------------------
# Safe archive extraction
# ----------------------------------------------------------------------------

def _safe_rel(name: str) -> PurePosixPath | None:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    return p


def extract_archive(data: bytes, dest: Path) -> None:
    total = 0
    if data[:2] == b"\x1f\x8b" or data[:5] == b"ustar":
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for m in tf.getmembers():
                rel = _safe_rel(m.name)
                if rel is None or not (m.isfile() or m.isdir()):
                    continue  # skip symlinks, devices, traversal
                target = dest / Path(*rel.parts)
                if m.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += m.size
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("Arşiv çok büyük")
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(m) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    elif data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                rel = _safe_rel(info.filename)
                if rel is None or info.is_dir():
                    continue
                total += info.file_size
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("Arşiv çok büyük")
                target = dest / Path(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    else:
        raise RuntimeError("Desteklenmeyen arşiv formatı (yalnızca tar.gz / zip)")


# ----------------------------------------------------------------------------
# Skill discovery inside a directory tree
# ----------------------------------------------------------------------------

def discover_skills(root: Path) -> list[dict]:
    """Find every SKILL.md under root; a nested SKILL.md inside another skill is ignored."""
    found = []
    for md in sorted(root.rglob("SKILL.md"), key=lambda p: len(p.parts)):
        if any(part in SKIP_NAMES for part in md.relative_to(root).parts):
            continue
        folder = md.parent
        if any(folder != s["path"] and s["path"] in folder.parents for s in found):
            continue
        fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
        name = fm.get("name") or folder.name
        if any(sanitize_name(s["name"]) == sanitize_name(name) for s in found):
            continue  # same skill mirrored in several folders: keep the shallowest copy
        found.append({"path": folder, "name": name, "description": fm.get("description", "")})
    return found


def copy_skill(src: Path, skills_dir: Path, name: str, description: str, force: bool) -> tuple[str, str]:
    """Copy skill folder into skills_dir/<name>. Returns (status, folder_name)."""
    folder = sanitize_name(name)
    target = skills_dir / folder
    if target.exists() and not force:
        return "exists", folder
    files = [p for p in src.rglob("*") if p.is_file()
             and not any(part in SKIP_NAMES for part in p.relative_to(src).parts)]
    if len(files) > MAX_FILES_PER_SKILL:
        raise RuntimeError(f"{name}: çok fazla dosya ({len(files)})")
    if sum(p.stat().st_size for p in files) > MAX_UNPACKED_BYTES:
        raise RuntimeError(f"{name}: skill klasörü 50 MB sınırını aşıyor")
    staging = Path(tempfile.mkdtemp(prefix=f".{folder}-", dir=skills_dir))
    try:
        for p in files:
            dst = staging / p.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        md = staging / "SKILL.md"
        md.write_text(normalize_skill_md(md.read_text(encoding="utf-8", errors="replace"),
                                         folder, description), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return "installed", folder


# ----------------------------------------------------------------------------
# Source parsing (GitHub / well-known)
# ----------------------------------------------------------------------------

GH_URL_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)(?:/(?:tree|blob)/([^/\s]+)(?:/(.*))?)?/?$")
SHORTHAND_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]+?)(?:@([A-Za-z0-9._-]+))?$")


def parse_source(src: str) -> dict:
    src = src.strip().strip("<>\"'")
    m = GH_URL_RE.match(src)
    if m:
        owner, repo, ref, sub = m.groups()
        repo = repo[:-4] if repo.endswith(".git") else repo
        if sub and sub.endswith("SKILL.md"):
            sub = sub[: -len("SKILL.md")].rstrip("/")
        return {"type": "github", "owner": owner, "repo": repo, "ref": ref, "subpath": sub or "", "skill": None}
    m = SHORTHAND_RE.match(src)
    if m and not src.startswith(("http://", "https://")):
        owner, repo, skill = m.groups()
        return {"type": "github", "owner": owner, "repo": repo, "ref": None, "subpath": "", "skill": skill}
    if src.startswith(("http://", "https://")):
        return {"type": "wellknown", "url": src}
    raise ValueError(f"Kaynak anlaşılamadı: {src}  (örnek: https://github.com/sahip/repo veya sahip/repo)")


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


def install_from_github(spec: dict, skills_dir: Path, args, only: set | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="skill-dl-") as tmp:
        root = fetch_github(spec["owner"], spec["repo"], spec["ref"], Path(tmp))
        base = root / spec["subpath"] if spec["subpath"] else root
        if not base.exists():
            raise RuntimeError(f"Repo içinde yol bulunamadı: {spec['subpath']}")
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
                raise RuntimeError(f"İstenen skill bulunamadı: {', '.join(sorted(wanted))}")
        source = f"{spec['owner']}/{spec['repo']}"
        return [_do_copy(s["path"], s["name"], s["description"], skills_dir, args, source) for s in skills]


def _do_copy(path: Path, name: str, desc: str, skills_dir: Path, args, source: str) -> dict:
    folder = sanitize_name(name)
    if args.dry_run:
        return {"name": folder, "description": desc, "status": "dry-run", "source": source}
    status, folder = copy_skill(path, skills_dir, name, desc, args.force)
    return {"name": folder, "description": desc, "status": status, "source": source}


def install_from_wellknown(url: str, skills_dir: Path, args) -> list[dict]:
    parsed = urllib.parse.urlparse(url)
    base_path = parsed.path.rstrip("/")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates = []
    for wk in WELL_KNOWN_PATHS:
        candidates.append((f"{origin}{base_path}/{wk}", f"{origin}{base_path}/{wk}/index.json"))
        if base_path:
            candidates.append((f"{origin}/{wk}", f"{origin}/{wk}/index.json"))
    index, base = None, None
    for b, idx_url in candidates:
        try:
            data = http_json(idx_url)
            if isinstance(data, dict) and isinstance(data.get("skills"), list):
                index, base = data, b
                break
        except Exception:
            continue
    if not index:
        raise RuntimeError(f"Well-known skill listesi bulunamadı: {url}")
    say(f"  ✓ Well-known index bulundu: {base}/index.json ({len(index['skills'])} skill)")
    results = []
    wanted = {sanitize_name(s) for s in (args.skill or [])}
    for entry in index["skills"]:
        name = str(entry.get("name", "")).strip()
        if not name or (wanted and sanitize_name(name) not in wanted):
            continue
        with tempfile.TemporaryDirectory(prefix="skill-wk-") as tmp:
            d = Path(tmp) / sanitize_name(name)
            d.mkdir()
            try:
                if "files" in entry:  # v0.1.0: directory of files
                    for f in entry["files"]:
                        rel = _safe_rel(f)
                        if rel is None:
                            continue
                        t = d / Path(*rel.parts)
                        t.parent.mkdir(parents=True, exist_ok=True)
                        t.write_bytes(http_get(f"{base}/{name}/{rel.as_posix()}"))
                else:  # v0.2.0: single artifact with sha256 digest
                    art_url = urllib.parse.urljoin(base + "/", entry["url"])
                    blob = http_get(art_url)
                    digest = str(entry.get("digest", ""))
                    if digest.startswith("sha256:") and hashlib.sha256(blob).hexdigest() != digest[7:]:
                        raise RuntimeError("digest uyuşmuyor")
                    if entry.get("type") == "archive":
                        extract_archive(blob, d)
                        found = discover_skills(d)
                        if found:
                            d = found[0]["path"]
                    else:
                        (d / "SKILL.md").write_bytes(blob)
                if not (d / "SKILL.md").is_file():
                    raise RuntimeError("SKILL.md yok")
                results.append(_do_copy(d, name, entry.get("description", ""), skills_dir, args, parsed.netloc))
            except Exception as e:
                warn(f"{name} atlandı: {e}")
    return results


# ----------------------------------------------------------------------------
# skills.sh search & profile mode
# ----------------------------------------------------------------------------

def search_skills(query: str) -> list[dict]:
    try:
        data = http_json(f"{SEARCH_API}/api/search?" + urllib.parse.urlencode({"q": query}))
        return [s for s in data.get("skills", []) if s.get("source") and s.get("skillId")]
    except Exception as e:
        warn(f"skills.sh araması başarısız ({query}): {e}")
        return []


def is_trusted(item: dict, min_installs: int) -> bool:
    owner = item["source"].split("/")[0].lower()
    return owner in TRUSTED_OWNERS or int(item.get("installs") or 0) >= min_installs


def cmd_find(query: str, installed: dict, min_installs: int) -> None:
    say(f"\n🔎 skills.sh üzerinde aranıyor: \"{query}\"\n")
    res = search_skills(query)
    if not res:
        say("  Sonuç bulunamadı.")
        return
    for s in res[:15]:
        mark = "✅ kurulu" if sanitize_name(s["skillId"]) in installed else ("⭐" if is_trusted(s, min_installs) else "⚠️ az kurulum")
        say(f"  • {s['skillId']:<34} {s.get('installs', 0):>8} kurulum  {mark}")
        say(f"      kur: python3 auto_install.py {s['source']}@{s['skillId']}")
    say(f"\nDaha fazlası: {SEARCH_API}")


def pick_profile_skills(installed: dict, per_domain: int, min_installs: int,
                        domains: list[str] | None, live_search: bool) -> list[tuple[str, dict]]:
    """Pick missing skills per domain: curated list first, optional live search as fallback."""
    picks, seen = [], set(installed)
    for domain, cfg in PROFILE.items():
        if domains and not any(d.lower() in domain.lower() for d in domains):
            continue
        ranked = []
        for ref in cfg["curated"]:
            source, skill_id = ref.split("@", 1)
            ranked.append({"id": ref, "source": source, "skillId": skill_id, "installs": "seçili"})
        if live_search:
            pool = {}
            for q in cfg["queries"]:
                for s in search_skills(q):
                    if "/" in s["source"] and any(k in s["skillId"].lower() for k in cfg["keywords"]):
                        pool.setdefault(s["id"], s)
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

def report(results: list[dict], skills_dir: Path) -> None:
    installed = [r for r in results if r["status"] == "installed"]
    existed = [r for r in results if r["status"] == "exists"]
    dry = [r for r in results if r["status"] == "dry-run"]
    say("\n" + "=" * 64)
    say("📦 KURULUM ÖZETİ")
    say("=" * 64)
    say(f"Skill klasörü: {skills_dir.as_posix()}")
    for r in installed:
        say(f"  ✅ Kuruldu     : {r['name']}  ({r['source']})")
        if r["description"]:
            say(f"                   {r['description'][:150]}")
    for r in existed:
        say(f"  ⏭️  Zaten kurulu: {r['name']}  (üzerine yazmak için --force)")
    for r in dry:
        say(f"  🧪 Kurulacaktı : {r['name']}  ({r['source']})")
    if not results:
        say("  Hiçbir skill kurulmadı.")
    if installed:
        manifest = [{"skill_name": r["name"], "description": (r["description"] or f"Skill {r['name']}.")[:1024]}
                    for r in installed]
        try:
            (skills_dir / ".pending_registration.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        say("\n🔔 ABACUS.AI KAYIT ADIMI (ajan için talimat):")
        say("   Dosyalar diske yazıldı. Her skill'i Abacus.AI'ye kaydetmek için ayrı bir")
        say("   adımda `create_skill` aracını şu argümanlarla çağırın:")
        for m in manifest:
            say("   create_skill(" + json.dumps(m, ensure_ascii=False) + ")")
        say("\nREGISTRATION_JSON=" + json.dumps(manifest, ensure_ascii=False))
    say("=" * 64)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Abacus.AI skill otomatik kurulum aracı")
    ap.add_argument("sources", nargs="*", help="GitHub linki, sahip/repo, sahip/repo@skill veya well-known URL")
    ap.add_argument("--skill", action="append", help="Kaynaktan yalnızca bu skill'i kur (tekrarlanabilir)")
    ap.add_argument("--find", metavar="SORGU", help="skills.sh üzerinde skill ara")
    ap.add_argument("--profile", action="store_true", help="Kullanıcı alanlarına göre popüler skill'leri kur")
    ap.add_argument("--domain", action="append", help="--profile ile yalnızca bu alan(lar): turizm, filo, oyun, kripto, hisse, ofis")
    ap.add_argument("--search", action="store_true", help="--profile: seçili listeye ek olarak skills.sh'de canlı ara")
    ap.add_argument("--max", type=int, default=1, help="--profile: alan başına en fazla skill (vars: 1)")
    ap.add_argument("--min-installs", type=int, default=MIN_INSTALLS_DEFAULT, help="Güvenilir sayılmak için en az kurulum")
    ap.add_argument("--list", action="store_true", help="Kurulu skill'leri listele")
    ap.add_argument("--skills-dir", help="Skill klasörü (vars: /home/ubuntu/skills)")
    ap.add_argument("--force", action="store_true", help="Var olan skill'in üzerine yaz")
    ap.add_argument("--dry-run", action="store_true", help="Kurmadan ne yapılacağını göster")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    skills_dir = detect_skills_dir(args.skills_dir)
    if not args.dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)
    installed = list_installed(skills_dir)

    say(f"🧩 Abacus.AI Skill Kurucu v{VERSION}")
    say(f"📁 Skill klasörü: {skills_dir.as_posix()}")
    say(f"📋 Kurulu skill sayısı: {len(installed)}" + (f"  →  {', '.join(installed)}" if installed else ""))

    if args.list:
        for name, desc in installed.items():
            say(f"  • {name}: {desc[:120]}")
        return 0
    if args.find:
        cmd_find(args.find, installed, args.min_installs)
        return 0

    if args.domain or args.search:
        args.profile = True
    elif not args.sources and not args.profile:
        args.profile = True
        say("ℹ️  Kaynak verilmedi → profil modu (turizm, filo, oyun, kripto, hisse, ofis).")

    results: list[dict] = []
    errors = 0
    for src in args.sources:
        say(f"\n▶ Kaynak: {src}")
        try:
            spec = parse_source(src)
            if spec["type"] == "github":
                results += install_from_github(spec, skills_dir, args)
            else:
                results += install_from_wellknown(spec["url"], skills_dir, args)
        except Exception as e:
            errors += 1
            say(f"  ❌ Hata: {e}")

    if args.profile:
        domains = [DOMAIN_ALIASES.get(d.lower(), d) for d in (args.domain or [])] or None
        mode = "seçili liste + canlı skills.sh araması" if args.search else "seçili liste"
        say(f"\n▶ Profil modu ({mode}), alan başına en fazla {args.max} eksik skill:")
        picks = pick_profile_skills(installed, args.max, args.min_installs, domains, args.search)
        by_source: dict[str, set] = {}
        for domain, s in picks:
            say(f"  • {domain:<24} → {s['skillId']} ({s['source']}, {s.get('installs', 0)} kurulum)")
            by_source.setdefault(s["source"], set()).add(s["skillId"])
        for source, names in by_source.items():
            if "/" not in source:  # non-GitHub publisher (well-known endpoint)
                saved, args.skill = args.skill, sorted(names)
                try:
                    results += install_from_wellknown(f"https://{source}", skills_dir, args)
                except Exception as e:
                    errors += 1
                    say(f"  ❌ {source}: {e}")
                finally:
                    args.skill = saved
                continue
            owner, repo = source.split("/", 1)
            spec = {"type": "github", "owner": owner, "repo": repo, "ref": None, "subpath": "", "skill": None}
            try:
                results += install_from_github(spec, skills_dir, args, only=names)
            except Exception as e:
                errors += 1
                say(f"  ❌ {source}: {e}")

    report(results, skills_dir)
    return 1 if errors and not results else 0


if __name__ == "__main__":
    sys.exit(main())
