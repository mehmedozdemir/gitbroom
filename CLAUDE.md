# GitBroom — Git Branch Temizleme Aracı
## CLAUDE.md — Claude Code Proje Rehberi

---

## Proje Özeti

**GitBroom**, geliştiricilerin Git repolarındaki branch karmaşasını temizlemesine yardımcı olan bir masaüstü uygulamasıdır. Hangi branch'lerin merge edildiğini, ne zaman merge edildiğini, kimin tarafından açıldığını gösterir; güvenli silme önerileri sunar.

---

## Teknoloji Stack

| Katman | Teknoloji |
|---|---|
| UI | PyQt6 |
| Git Core | gitpython + pygit2 |
| GitLab (opsiyonel) | python-gitlab |
| Config | TOML (tomllib / tomli) |
| Paketleme | PyInstaller |
| Test | pytest + pytest-qt |
| Linting | ruff + mypy |

---

## Proje Yapısı

```
gitbroom/
├── CLAUDE.md                  ← Bu dosya
├── SKILLS.md                  ← Geliştirme becerileri
├── PROJECT_PLAN.md            ← Adım adım geliştirme planı
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
│
├── src/
│   └── gitbroom/
│       ├── __init__.py
│       ├── main.py            ← Uygulama giriş noktası
│       │
│       ├── core/              ← İş mantığı (UI bağımsız)
│       │   ├── __init__.py
│       │   ├── repo.py        ← Repo yükleme ve yönetim
│       │   ├── branch.py      ← Branch analiz motoru
│       │   ├── scorer.py      ← Risk skoru hesaplama
│       │   ├── cleaner.py     ← Güvenli silme işlemleri
│       │   └── models.py      ← Veri modelleri (dataclass)
│       │
│       ├── gitlab/            ← Opsiyonel GitLab katmanı
│       │   ├── __init__.py
│       │   ├── client.py
│       │   └── enricher.py    ← Branch bilgilerini MR verisiyle zenginleştir
│       │
│       ├── ui/                ← PyQt6 UI katmanı
│       │   ├── __init__.py
│       │   ├── app.py         ← QApplication setup
│       │   ├── main_window.py ← Ana pencere
│       │   ├── widgets/
│       │   │   ├── repo_selector.py
│       │   │   ├── branch_table.py
│       │   │   ├── branch_detail.py
│       │   │   ├── delete_dialog.py
│       │   │   └── settings_dialog.py
│       │   ├── models/
│       │   │   └── branch_table_model.py  ← QAbstractTableModel
│       │   └── theme/
│       │       ├── style.qss              ← Global stylesheet
│       │       └── theme.py              ← Dark/Light tema yönetimi
│       │
│       └── config/
│           ├── __init__.py
│           └── settings.py    ← Kullanıcı ayarları (TOML)
│
├── tests/
│   ├── core/
│   ├── gitlab/
│   └── ui/
│
└── assets/
    ├── icons/
    └── screenshots/
```

---

## Temel Veri Modeli

```python
# src/gitbroom/core/models.py içinde tanımlanacak

@dataclass
class BranchInfo:
    name: str
    is_local: bool
    is_remote: bool
    last_commit_sha: str
    last_commit_date: datetime
    last_commit_author: str       # "B seçeneği" — son commit author'ı
    last_commit_message: str
    is_merged: bool
    merge_type: str               # "merge" | "squash" | "rebase" | "unknown"
    merged_at: datetime | None
    merged_into: str | None       # hangi branch'e merge edildi
    ahead_count: int              # default branch'e göre
    behind_count: int
    risk_score: RiskScore         # GREEN | YELLOW | ORANGE | RED
    risk_reasons: list[str]       # neden bu skoru aldığı
    # GitLab enrichment (opsiyonel)
    gitlab_mr_id: int | None = None
    gitlab_mr_state: str | None = None
    gitlab_mr_author: str | None = None

@dataclass
class RiskScore:
    level: str        # "green" | "yellow" | "orange" | "red"
    label: str        # "Güvenli Sil" | "Gözden Geçir" | "Bekle" | "Dokunma"
    icon: str         # "🟢" | "🟡" | "🟠" | "🔴"
```

---

## Risk Skoru Mantığı

```
🟢 Güvenli Sil   → merged=True  AND son commit 90+ gün önce
🟡 Gözden Geçir  → merged=True  AND son commit 30-90 gün önce
                   VEYA merged=False AND son commit 60+ gün önce
🟠 Bekle         → merged=True  AND son commit 30 gün içinde
🔴 Dokunma       → son 14 günde aktif commit
                   VEYA açık MR var (GitLab bağlıysa)
                   VEYA default branch ile aynı
```

Eşik değerleri kullanıcı tarafından Ayarlar'dan değiştirilebilir.

---

## Squash/Rebase Merge Tespiti

Standart `git branch --merged` komutu squash ve rebase merge'leri tespit edemez.
`branch.py` içinde şu strateji kullanılacak:

```python
def detect_merge_type(branch, default_branch, repo):
    # 1. Önce standart merge kontrolü
    if is_standard_merged(branch, default_branch, repo):
        return "merge"
    
    # 2. Squash merge tespiti:
    #    Branch'in tüm commit'lerinin diff'ini al,
    #    default branch'te aynı diff'e sahip bir commit ara
    if has_matching_squash_commit(branch, default_branch, repo):
        return "squash"
    
    # 3. Rebase merge tespiti:
    #    Branch commit'lerinin patch-id'lerini default branch ile karşılaştır
    if has_matching_patch_ids(branch, default_branch, repo):
        return "rebase"
    
    return None  # merge edilmemiş
```

---

## UI/UX Prensipleri

1. **Tema:** Dark mode varsayılan, light mode seçenek
2. **Renk paleti:** Sober, profesyonel — mavi/gri ağırlıklı
3. **Tablo:** Sıralanabilir, filtrelenebilir, seçilebilir (checkbox)
4. **Destructive aksiyonlar:** Her zaman onay dialogu + özet
5. **Yedekleme:** Silmeden önce otomatik `git tag` oluşturma seçeneği
6. **Loading state:** Büyük repolar için progress göstergesi
7. **Hata mesajları:** Teknik değil, anlaşılır Türkçe/İngilizce

---

## Güvenlik Kuralları

- Default branch **asla** listede gösterilmez, silinemez
- `HEAD` olan branch silinemez
- Açık MR olan branch kırmızı işaretlenir (GitLab bağlıysa)
- Remote silme işlemi **ayrıca onaylanır**
- Silme öncesi `git tag backup/BRANCHNAME-YYYYMMDD` oluşturulabilir
- Tüm işlemler log dosyasına kaydedilir

---

## Geliştirme Kuralları

### Genel
- Python 3.11+ syntax kullan
- Type hint'leri her yerde kullan (mypy strict)
- Docstring: Google style
- Satır uzunluğu: 100 karakter

### Core Katman
- Core katman **hiçbir PyQt6 import'u içermez**
- İş mantığı UI'dan tamamen bağımsız olmalı
- Her public fonksiyon için unit test yaz

### UI Katmanı
- `QThread` kullan — Git işlemleri UI thread'ini bloklamamalı
- Signal/Slot pattern'ini doğru kullan
- Widget'lar birbirinden bağımsız olmalı

### GitLab Katmanı
- Her zaman `try/except` ile wrap et
- Token yoksa veya bağlantı başarısızsa uygulama çalışmaya devam etmeli
- Rate limiting'e karşı retry logic ekle

---

## Komutlar

```bash
# Geliştirme ortamı kurulumu
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Uygulamayı çalıştır
python -m gitbroom

# Testleri çalıştır
pytest tests/ -v

# Linting
ruff check src/
mypy src/

# Paketleme (PyInstaller)
pyinstaller gitbroom.spec
```

---

## Ortam Değişkenleri

```env
GITBROOM_GITLAB_TOKEN=glpat-xxxx    # GitLab personal access token (opsiyonel)
GITBROOM_LOG_LEVEL=INFO             # DEBUG | INFO | WARNING | ERROR
GITBROOM_CONFIG_DIR=~/.gitbroom     # Config ve log dizini
```

---

## Kısıtlamalar ve Bilinen Sınırlar

- Squash merge tespiti büyük repolarda yavaş olabilir → cache mekanizması ekle
- Remote branch silme için write access gerekli → açıkça belirt
- GitLab self-hosted için custom URL desteği gerekli
- SSH key authentication gitpython tarafından destekleniyor, HTTPS de
