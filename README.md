# 🧩 Agent Skill Installer

**Tek link yapıştır, skill kurulsun.** Abacus.AI, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot,
OpenCode, Windsurf, Cline, Amp, Goose, Kiro, Qwen Code, Roo Code, Trae ve evrensel `~/.agents/skills` için
skill (SKILL.md paketleri) bulur, **güvenlik taramasından geçirir** ve kurar.
Sadece Python 3.8+ gerekir, ek kütüphane yok. Windows, macOS ve Linux'ta çalışır.

*English below.*

---

## ⚡ Hızlı başlangıç

### Sohbete yapıştırın (Abacus.AI, Claude Code, Codex, Cursor...)

```
https://github.com/Turkishmadaraa/agent-skill-installer bu skill'i kur
```

Kurucu bir kez eklendikten sonra herhangi bir skill linkini yapıştırıp **"bunu kur"** demeniz yeterli:

```
https://github.com/anthropics/skills/tree/main/skills/pdf bunu kur
```

### Claude Code eklentisi olarak

```
/plugin marketplace add Turkishmadaraa/agent-skill-installer
/plugin install skill-installer@agent-skill-installer
```

### `skills` CLI ile (tüm ajanlar)

```bash
npx skills add Turkishmadaraa/agent-skill-installer
```

### Terminalden

**Linux / macOS**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.sh)
# belirli bir skill:
bash <(curl -fsSL https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.sh) anthropics/skills@pdf
```

**Windows PowerShell**

```powershell
irm https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.ps1 | iex
```

> Uzaktan script çalıştırmadan önce içeriğini okumanızı öneririz. Sabit bir sürüm için
> `SKILL_INSTALLER_REF=v2.0.1` ortam değişkenini ayarlayın.

---

## 🎯 Hangi ajana kurulur?

Varsayılan `--agent auto`: bilgisayarda bulunan **tüm** ajanlara kurar (hiçbiri yoksa `~/.agents/skills`).

| `--agent` | Global klasör | Proje klasörü (`--project`) |
|---|---|---|
| `abacus` | `/home/ubuntu/skills` | – |
| `claude-code` | `~/.claude/skills` | `.claude/skills` |
| `codex` | `~/.agents/skills` | `.agents/skills` |
| `cursor` | `~/.cursor/skills` | `.agents/skills` |
| `gemini-cli` | `~/.gemini/skills` | `.agents/skills` |
| `github-copilot` | `~/.copilot/skills` | `.agents/skills` |
| `opencode` | `~/.config/opencode/skills` | `.agents/skills` |
| `windsurf` | `~/.codeium/windsurf/skills` | `.windsurf/skills` |
| `cline`, `amp`, `goose`, `kiro-cli`, `qwen-code`, `roo`, `trae`, `universal` | `python3 auto_install.py --agents` ile görün | |

Örnekler: `--agent claude-code`, `-a codex -a cursor`, `--agent all --project`.

---

## 📚 Komutlar

Script: `skills/installing-agent-skills/auto_install.py`

| Komut | Ne yapar |
|---|---|
| `auto_install.py <github-linki>` | Repodaki tüm skill'leri kurar |
| `auto_install.py sahip/repo@skill` | Tek skill kurar |
| `auto_install.py <link> --skill a --skill b` | Seçilen skill'leri kurar |
| `auto_install.py https://site.com` | Well-known (`/.well-known/agent-skills/`) sitesinden kurar |
| `auto_install.py --find "stock analysis"` | skills.sh'de arar |
| `auto_install.py --profile [--domain kripto] [--max 2]` | Seçili paketler (ofis, turizm, filo, oyun, kripto, hisse) |
| `auto_install.py --agents` | Desteklenen / bulunan ajanlar |
| `auto_install.py --list` | Kurulu skill'ler |
| `--dry-run` / `--force` / `--project` / `--skills-dir YOL` | Önizleme / üzerine yaz / projeye kur / özel klasör |
| `--allow-risky` | Güvenlik bulgusu olan skill'i **bilerek** kur |

---

## 🔒 Güvenlik

- İndirilen hiçbir kod **çalıştırılmaz**, sadece dosya olarak kopyalanır (çalıştırma izinleri de kopyalanmaz).
- Yalnızca **HTTPS**. HTTP'ye yönlendirmeler engellenir.
- `GITHUB_TOKEN` yalnızca GitHub sunucularına gönderilir, yönlendirmelerde asla iletilmez.
- Arşivler güvenli açılır: yol aşımı (`../`), mutlak yollar, sembolik/sabit bağlantılar engellenir,
  zip-bomb'a karşı gerçek boyut, dosya sayısı ve indirme sınırı uygulanır.
- Repo/dal/yol adları sıkı doğrulanır; terminal kaçış karakterleri temizlenir.
- **İçerik taraması:** pipe-to-shell (`curl … | sh`, `irm … | iex`), base64 ile gizlenmiş komut, `rm -rf /`,
  `~/.ssh` / `~/.aws` erişimi, reverse shell, prompt injection ifadeleri ve ikili/çalıştırılabilir dosyalar
  bulunan skill'ler **engellenir** (`--allow-risky` ile bilerek kurulabilir).
- Claude Code'da araç izinlerini önceden onaylayan `allowed-tools` alanı kurulumda silinir.
- `well-known` v0.2 paketlerinde sha256 özeti doğrulanır.

Statik tarama her kötü niyetli içeriği yakalayamaz. Bilinmeyen kaynakları önce `--dry-run` ile inceleyin.
Açık bildirmek için: [SECURITY.md](SECURITY.md).

---

## English

**Paste a link, get the skill installed** for Abacus.AI, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot,
OpenCode, Windsurf and more. Python 3.8+ stdlib only.

```bash
# any agent, auto-detected
bash <(curl -fsSL https://raw.githubusercontent.com/Turkishmadaraa/agent-skill-installer/main/install.sh) anthropics/skills@pdf
# Claude Code plugin
/plugin marketplace add Turkishmadaraa/agent-skill-installer
# skills CLI
npx skills add Turkishmadaraa/agent-skill-installer
```

Key options: `--agent <name|all|auto>`, `--project`, `--skill`, `--find`, `--dry-run`, `--force`, `--allow-risky`.
Downloaded content is never executed; HTTPS only; safe extraction; tokens scoped to GitHub; risky skills
(pipe-to-shell, credential access, prompt injection, binaries) are blocked by default; `allowed-tools` is stripped.
CLI messages are in Turkish.

## 📁 Repo

| Yol | Açıklama |
|---|---|
| `skills/installing-agent-skills/SKILL.md` | Skill tanımı (tüm ajanlar) |
| `skills/installing-agent-skills/auto_install.py` | Kurulum motoru |
| `.claude-plugin/marketplace.json` | Claude Code eklenti pazarı |
| `install.sh` / `install.ps1` | Tek satır kurulum |

Lisans: [MIT](LICENSE)
