# 🧩 Abacus.AI Skill Otomatik Kurucu

Abacus.AI ajanına **tek bir link yapıştırarak** skill (yetenek paketi) kurmanızı sağlar.
GitHub'daki herhangi bir skill reposunu, `sahip/repo@skill` kısayolunu, "well-known" skill sitelerini
veya [skills.sh](https://skills.sh) aramasını destekler. Ek kütüphane gerekmez (yalnızca Python 3.8+).

---

## ⚡ En hızlı kullanım: Abacus.AI sohbetine yapıştırın

Abacus.AI (web veya **Abacus AI Code** masaüstü uygulaması) sohbetine şunu yapıştırın:

```
https://github.com/Turkishmadaraa/abacus-skill-installer bu skill'i tak, sonra önerilen skill'leri de kur
```

Ajan repoyu okur, `auto_install.py`'yi çalıştırır, skill'leri `/home/ubuntu/skills/` altına kopyalar
ve `create_skill` ile Abacus.AI'ye kaydeder. Bu kurucu bir kez skill olarak eklendikten sonra
başka herhangi bir skill linkini yapıştırıp **"bunu tak"** demeniz yeterli:

```
https://github.com/anthropics/skills/tree/main/skills/pdf bunu tak
```

---

## 🖥️ Komutla kullanım

**Linux / macOS / Abacus.AI terminali:**

```bash
# Kurucuyu skill olarak ekle + önerilen skill'leri kur
curl -sSL https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.sh | bash

# Belirli bir repo / skill kur
curl -sSL https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.sh | bash -s -- anthropics/skills@pdf
```

**Windows PowerShell:**

```powershell
irm https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/install.ps1 | iex
```

**Doğrudan Python ile:**

```bash
curl -sSL https://raw.githubusercontent.com/Turkishmadaraa/abacus-skill-installer/main/auto_install.py | python3 - https://github.com/anthropics/skills --skill xlsx
```

---

## 📚 Komutlar

| Komut | Ne yapar |
|---|---|
| `python3 auto_install.py <github-linki>` | Repodaki tüm skill'leri kurar |
| `python3 auto_install.py sahip/repo@skill` | Repodan tek bir skill kurar |
| `python3 auto_install.py <link> --skill a --skill b` | Yalnızca seçilen skill'leri kurar |
| `python3 auto_install.py https://site.com` | Well-known (`/.well-known/agent-skills/`) sitesinden kurar |
| `python3 auto_install.py --find "stock analysis"` | skills.sh üzerinde arar, kurulum komutlarını listeler |
| `python3 auto_install.py --profile` | Aşağıdaki alanlar için önerilen eksik skill'leri kurar |
| `python3 auto_install.py --profile --domain kripto --max 2` | Yalnızca bir alan, alan başına 2 skill |
| `python3 auto_install.py --profile --search` | Seçili listeye ek olarak canlı skills.sh araması |
| `python3 auto_install.py --list` | Kurulu skill'leri listeler |
| `--dry-run` / `--force` / `--skills-dir YOL` | Önizleme / üzerine yaz / farklı klasör |

Kabul edilen link biçimleri:

- `https://github.com/sahip/repo`
- `https://github.com/sahip/repo/tree/main/skills/skill-adi`
- `https://github.com/sahip/repo/blob/main/skills/skill-adi/SKILL.md`
- `sahip/repo` veya `sahip/repo@skill-adi`

---

## 🎯 Önerilen profil (`--profile`)

| Alan | Seçili skill'ler |
|---|---|
| Ofis Belgeleri | `anthropics/skills` → xlsx, docx, pdf, pptx |
| Turizm / Seyahat | `ailabs-393/ai-labs-claude-skills` → travel-planner |
| Araç Filosu / Lojistik | `affaan-m/ecc` → logistics-exception-management |
| Oyun Geliştirme | `wshobson/agents` → godot-gdscript-patterns, unity-ecs-patterns |
| Kripto | `binance/binance-skills-hub` → crypto-market-rank, `claude-office-skills/skills` → crypto-report |
| Hisse Senedi / Finans | `gracefullight/stock-checker` → stock-analysis |

Zaten kurulu olan skill'ler atlanır; alan başına sıradaki eksik skill seçilir.

---

## 🔔 Abacus.AI kaydı

Script dosyaları diske yazar ve en sonda şu satırı basar:

```
REGISTRATION_JSON=[{"skill_name": "pdf", "description": "..."}]
```

Ajan bu listedeki her skill için `create_skill` aracını çağırarak kaydı tamamlar
(liste ayrıca `skills/.pending_registration.json` dosyasına kaydedilir). Sohbete link yapıştırdığınızda
bu adım otomatik yapılır.

---

## 🔒 Güvenlik

- Arşivler güvenli açılır (yol aşımı ve sembolik bağlantılar engellenir, 50 MB / 1000 dosya sınırı).
- v0.2.0 well-known paketlerinde `sha256` özeti doğrulanır.
- Üçüncü taraf skill'ler ajanın yetkileriyle çalışır: güvenilir kaynakları (anthropics, vercel-labs,
  microsoft) veya 1000+ kurulumlu skill'leri tercih edin.
- Özel repolar için `GITHUB_TOKEN` ortam değişkenini ayarlayın.

## 📁 Repo içeriği

| Dosya | Açıklama |
|---|---|
| `auto_install.py` | Asıl kurulum mantığı (Python, bağımlılıksız) |
| `SKILL.md` | Bu reponun Abacus.AI skill tanımı |
| `install.sh` | Linux/macOS tek satır kurulum |
| `install.ps1` | Windows PowerShell tek satır kurulum |
| `README.md` | Bu dosya |

Lisans: MIT
