# GitBroom — PROJECT_PLAN.md
## Claude Code Adım Adım Geliştirme Planı

---

> **Nasıl kullanılır:**
> Bu dosyayı Claude Code'a ver. Her adımı sırayla uygulasın.
> Bir adım bitmeden bir sonrakine geçme.
> Her adım sonunda `pytest` çalıştır, testler geçmeden devam etme.

---

## FAZA 0 — Proje Altyapısı

### Adım 0.1 — Proje İskeleti

Aşağıdaki dosya ve klasör yapısını oluştur:

```
gitbroom/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── README.md
└── src/
    └── gitbroom/
        ├── __init__.py       (version = "0.1.0")
        ├── main.py
        ├── core/
        │   └── __init__.py
        ├── gitlab/
        │   └── __init__.py
        ├── ui/
        │   ├── __init__.py
        │   └── theme/
        │       └── __init__.py
        └── config/
            └── __init__.py
```

**pyproject.toml içeriği:**
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "gitbroom"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "PyQt6>=6.6",
    "gitpython>=3.1",
    "python-gitlab>=4.0",
    "tomli>=2.0; python_version < '3.11'",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-qt>=4.2",
    "ruff>=0.1",
    "mypy>=1.5",
]

[project.scripts]
gitbroom = "gitbroom.main:main"
```

**Beklenen çıktı:** `pip install -e ".[dev]"` başarıyla çalışmalı.

---

### Adım 0.2 — Core Veri Modelleri

`src/gitbroom/core/models.py` dosyasını oluştur.

İçermesi gerekenler:
- `RiskLevel` enum: `GREEN`, `YELLOW`, `ORANGE`, `RED`
- `RiskScore` dataclass: `level`, `label`, `icon`, `reasons: list[str]`
- `MergeType` enum: `STANDARD`, `SQUASH`, `REBASE`, `UNKNOWN`, `NOT_MERGED`
- `BranchInfo` dataclass: CLAUDE.md'deki tanıma göre
- `DeletionResult` dataclass: `branch_name`, `local_deleted`, `remote_deleted`, `backup_tag`, `errors`
- `AppSettings` dataclass: SKILLS.md'deki Settings tanımına göre

Tüm field'lara type hint ekle. Default değerler mantıklı olsun.

**Test:** `tests/core/test_models.py` yaz — dataclass'ların instantiate edilip edilemediğini test et.

---

### Adım 0.3 — Settings Yönetimi

`src/gitbroom/config/settings.py` dosyasını oluştur.

- TOML okuma/yazma (Python 3.11+ `tomllib` kullan)
- Config dizini: `~/.gitbroom/config.toml`
- `AppSettings.load()` → dosya yoksa default değerler dönsün
- `AppSettings.save()` → TOML formatında kaydet
- `GITBROOM_GITLAB_TOKEN` env variable desteği

**Test:** `tests/config/test_settings.py` — load/save round-trip test et.

---

## FAZA 1 — Core Git Motoru

### Adım 1.1 — Repo Yönetimi

`src/gitbroom/core/repo.py` dosyasını oluştur.

```python
class RepoManager:
    def load(self, path: str) -> Repo
    def validate(self, repo: Repo) -> list[str]   # uyarı listesi döner
    def get_default_branch(self, repo: Repo) -> str
    def get_remotes(self, repo: Repo) -> list[str]
    def fetch_remote(self, repo: Repo, remote: str = "origin") -> bool
```

- `search_parent_directories=True` kullan
- Bare repo kontrolü ekle
- Default branch tespiti: önce `origin/HEAD`, sonra `main`, `master`, `develop` sıralaması

**Test:** Gerçek bir git reposu oluşturarak test et (pytest `tmp_path` fixture kullan).

---

### Adım 1.2 — Branch Toplayıcı

`src/gitbroom/core/branch.py` dosyasına `BranchCollector` sınıfını ekle.

```python
class BranchCollector:
    def get_branches(self, repo: Repo, default_branch: str) -> list[dict]
```

- Local branch'leri topla
- Remote branch'leri topla (origin/ prefix'ini temizle)
- `HEAD` ve default branch'i listeden çıkar
- Her branch için: `name`, `is_local`, `is_remote`, `commit`, `tracking_remote` bilgilerini topla
- Local + remote eşleşmelerini birleştir (aynı branch local'de de remote'da da olabilir)

**Test:** Birden fazla branch içeren test reposu oluştur.

---

### Adım 1.3 — Branch Analizörü

`src/gitbroom/core/branch.py` dosyasına `BranchAnalyzer` sınıfını ekle.

```python
class BranchAnalyzer:
    def analyze(self, branch_dict: dict, repo: Repo, default_branch_ref) -> BranchInfo
    def _get_merge_status(self, ...) -> tuple[bool, MergeType, datetime | None]
    def _detect_squash_merge(self, ...) -> bool
    def _detect_rebase_merge(self, ...) -> bool
    def _get_ahead_behind(self, ...) -> tuple[int, int]
```

SKILLS.md'deki squash/rebase tespit algoritmalarını uygula.
Performans için: squash tespitinde max 200 commit kontrol et.

**Test:** Standart merge, squash merge, rebase merge, ve merge edilmemiş branch senaryolarını test et.

---

### Adım 1.4 — Risk Skoru Hesaplayıcı

`src/gitbroom/core/scorer.py` dosyasını oluştur.

```python
class RiskScorer:
    def __init__(self, settings: AppSettings):
        ...
    
    def score(self, branch: BranchInfo) -> RiskScore:
        """
        Kural önceliği (yukarıdan aşağıya, ilk eşleşen kazanır):
        1. Son 14 gün içinde aktif → RED
        2. Açık MR var → RED  
        3. Merged + 90+ gün → GREEN
        4. Merged + 30-90 gün → YELLOW
        5. Merged + 30 gün içinde → ORANGE
        6. Unmerged + 60+ gün → YELLOW
        7. Default → ORANGE
        """
```

Eşik değerleri `AppSettings`'ten alınsın.
`RiskScore.reasons` alanına neden o skoru aldığını açıklayan Türkçe metinler ekle.

**Test:** Her kural için ayrı test yaz. Edge case'leri test et (tam sınır değerler).

---

### Adım 1.5 — Güvenli Silici

`src/gitbroom/core/cleaner.py` dosyasını oluştur.

```python
class SafeDeleter:
    def delete_branches(
        self,
        branches: list[str],
        repo: Repo,
        delete_local: bool,
        delete_remote: bool,
        create_backup: bool,
        remote_name: str = "origin"
    ) -> list[DeletionResult]
    
    def _safety_check(self, branch_name: str, repo: Repo) -> None
    def _create_backup_tag(self, branch_name: str, repo: Repo) -> str
```

CLAUDE.md'deki güvenlik kurallarını uygula.
Her işlemi `~/.gitbroom/deletion.log` dosyasına kaydet (JSON Lines formatı).

**Test:** Mock repo ile silme senaryolarını test et. Güvenlik kontrollerinin çalıştığını doğrula.

---

## FAZA 2 — UI Temel Yapısı

### Adım 2.1 — Tema Sistemi

`src/gitbroom/ui/theme/` klasörünü oluştur.

Dosyalar:
- `colors.py` — renk sabitleri (Catppuccin Mocha dark, Latte light)
- `style_dark.qss` — dark mode QSS
- `style_light.qss` — light mode QSS  
- `theme.py` — `ThemeManager` sınıfı (QSS yükleme, tema değiştirme)

**Dark mode renk paleti (Catppuccin Mocha):**
```
Background:  #1e1e2e
Surface:     #181825
Overlay:     #313244
Text:        #cdd6f4
Subtext:     #a6adc8
Blue:        #89b4fa
Green:       #a6e3a1
Yellow:      #f9e2af
Orange:      #fab387
Red:         #f38ba8
```

**Beklenen çıktı:** `ThemeManager().apply_dark(app)` çalışmalı.

---

### Adım 2.2 — Ana Pencere İskeleti

`src/gitbroom/ui/main_window.py` dosyasını oluştur.

Layout:
```
┌─────────────────────────────────────────────────┐
│  🧹 GitBroom              [Ayarlar] [?]         │  ← Toolbar
├─────────────────────────────────────────────────┤
│  Repo: [/path/to/repo        ▼] [Tara]          │  ← Repo seçici
├──────────────────────────────────────────────────┤
│  [Hepsi] [Benim] [Merged] [Stale]  🔍 Ara...   │  ← Filtre bar
├──────────────────────────────────────────────────┤
│                                                   │
│  Branch tablosu (placeholder)                    │  ← Ana içerik
│                                                   │
├──────────────────────────────────────────────────┤
│  Seçili: 3 branch   [Seçilileri Sil ▼]          │  ← Action bar
└──────────────────────────────────────────────────┘
```

- `QMainWindow` kullan
- Pencere boyutu: 1200x750, minimum 900x600
- Başlık: "GitBroom — Git Branch Temizleyici"
- Status bar ekle

**Beklenen çıktı:** Uygulama açılmalı, boş ama düzgün görünmeli.

---

### Adım 2.3 — Repo Seçici Widget

`src/gitbroom/ui/widgets/repo_selector.py` dosyasını oluştur.

Özellikler:
- Son kullanılan repoları dropdown'da göster (max 10)
- "Klasör Seç" butonu → `QFileDialog`
- Remote URL girişi için toggle (sonradan, şimdilik disabled)
- Repo yüklenince `repo_changed(path: str)` signal emit et
- Son kullanılan repo otomatik yüklensin

---

### Adım 2.4 — Branch Tablo Modeli

`src/gitbroom/ui/models/branch_table_model.py` dosyasını oluştur.

SKILLS.md'deki `BranchTableModel` implementasyonunu yap.

Kolonlar:
| # | Başlık | İçerik |
|---|---|---|
| 0 | ☐ | Checkbox (seçim) |
| 1 | Branch | İsim + ikon (local/remote badge) |
| 2 | Yazar | Son commit author'ı |
| 3 | Son Commit | "3 gün önce" formatında |
| 4 | Merge | ✅ Merged / ⚠️ Unmerged + merge tipi |
| 5 | Risk | Renkli badge |
| 6 | Konum | Local / Remote / Her ikisi |

- `Qt.ItemDataRole` doğru kullan
- Sıralanabilir (`QSortFilterProxyModel`)
- Filtrelenebilir (metin + filtre butonları)

**Test:** Model'in doğru satır/kolon sayısı döndürdüğünü test et.

---

### Adım 2.5 — Branch Tablosu Widget

`src/gitbroom/ui/widgets/branch_table.py` dosyasını oluştur.

- `QTableView` + custom model
- Kolon genişlikleri: otomatik + kullanıcı ayarlanabilir
- Satıra tıklayınca detay panel açılsın (sağ tarafta)
- Checkbox kolonuna tıklayınca seçim toggle
- "Hepsini Seç / Hiçbirini Seçme" header checkbox
- Sağ tık → context menu (Detaylar / Sil / Tag Oluştur)
- Risk seviyesine göre satır arka plan rengi (hafif)

---

### Adım 2.6 — Worker Thread Entegrasyonu

`src/gitbroom/ui/workers.py` dosyasını oluştur.

```python
class RepoScanWorker(QThread):
    """Repo tarama işini arka planda yürütür."""
    progress = pyqtSignal(int, int, str)    # current, total, branch_name
    branch_found = pyqtSignal(object)       # BranchInfo
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
```

Ana pencerede:
- "Tara" butonuna basınca Worker başlasın
- Progress bar göster (indeterminate → progress)
- Her `branch_found` signal'inde tablo güncelle (stream)
- Hata olunca kullanıcıya göster
- "İptal" butonu ekle

---

## FAZA 3 — Silme ve Onay Akışı

### Adım 3.1 — Branch Detay Paneli

`src/gitbroom/ui/widgets/branch_detail.py` dosyasını oluştur.

Gösterilecekler:
- Branch adı (büyük, bold)
- Risk badge'i (renkli, açıklamalı)
- Yazar avatarı yerine initials (örn. "AK")
- Son 5 commit listesi (sha kısaltılmış + mesaj + tarih)
- Merge bilgisi (merge tipi, ne zaman, hangi branch'e)
- Ahead/behind sayacı
- GitLab MR bilgisi (bağlıysa)

Sağ tarafta `QSplitter` ile açılır panel olsun.

---

### Adım 3.2 — Silme Onay Diyaloğu

`src/gitbroom/ui/widgets/delete_dialog.py` dosyasını oluştur.

```
┌─────────────────────────────────────────┐
│  ⚠️  Branch Silme Onayı                 │
├─────────────────────────────────────────┤
│  Şu branch'ler silinecek:               │
│                                          │
│  🟢 feature/login-page    (local+remote) │
│  🟡 fix/typo-header       (local)        │
│  🟠 refactor/auth         (remote)       │
│                                          │
├─────────────────────────────────────────┤
│  Silme seçenekleri:                     │
│  ☑ Local branch'leri sil               │
│  ☑ Remote branch'leri sil              │
│  ☑ Silmeden önce backup tag oluştur    │
├─────────────────────────────────────────┤
│  ⚠️ Bu işlem geri alınamaz!            │
│     (Backup tag oluşturulursa kurtarılabilir)│
├─────────────────────────────────────────┤
│          [İptal]    [Sil (3 branch)]   │
└─────────────────────────────────────────┘
```

- "Sil" butonu kırmızı, disabled → 2 saniye countdown sonra aktif
- Onay kutuları duruma göre pre-filled (seçili branch'ler local/remote durumuna göre)

---

### Adım 3.3 — Silme İşlemi ve Sonuç

Ana pencereye silme akışını entegre et:

1. "Seçilileri Sil" butonuna tıkla
2. Onay diyaloğu açılır
3. Kullanıcı onaylarsa `DeletionWorker` başlar
4. Progress gösterilir
5. Sonuç özeti: kaç tane silindi, kaç hata oldu
6. Tablo güncellenir (silinen branch'ler kaldırılır)

---

## FAZA 4 — Ayarlar ve Cilalama

### Adım 4.1 — Ayarlar Diyaloğu

`src/gitbroom/ui/widgets/settings_dialog.py` dosyasını oluştur.

Sekmeler:
1. **Genel** — default branch, stale eşikleri, tema, dil
2. **GitLab** — URL, token, bağlantı testi butonu
3. **Davranış** — backup tag, otomatik fetch, log tutma

Kaydet → `AppSettings.save()` çağır → ana pencereye `settings_changed` signal gönder.

---

### Adım 4.2 — Filtre ve Arama İyileştirmeleri

- Filtre butonları (Hepsi / Benim / Merged / Stale / Sadece Local / Sadece Remote)
- Arama: branch adı + author'da ara
- "Benim" filtresi: git config'deki `user.email` ile eşleştir
- Filtre state'i pencere kapatılınca hatırlanır

---

### Adım 4.3 — GitLab Opsiyonel Entegrasyonu

`src/gitbroom/gitlab/client.py` ve `enricher.py` dosyalarını oluştur.

SKILLS.md'deki `GitLabClient` implementasyonunu yap.

Entegrasyon akışı:
1. Ayarlarda GitLab URL ve token girilir
2. Repo yüklenince remote URL'den proje otomatik tespit edilir
3. Arka planda MR bilgileri çekilir
4. Branch listesi güncellenir (MR bilgisiyle zenginleşir)
5. Açık MR olan branch'ler kırmızı badge alır

GitLab bağlantısı başarısız olursa uygulama sorunsuz çalışmaya devam etmeli.

---

### Adım 4.4 — Hata Yönetimi ve Logging

- `~/.gitbroom/app.log` — genel uygulama logu
- `~/.gitbroom/deletion.log` — silme işlemleri (JSON Lines)
- Tüm exception'lar loglanmalı
- Kullanıcıya gösterilen hatalar teknik değil, anlaşılır olmalı
- Unhandled exception → özel hata diyaloğu + log kaydı

---

### Adım 4.5 — Son Dokunuşlar

- Keyboard shortcuts: `Ctrl+R` (tara), `Ctrl+,` (ayarlar), `Delete` (sil), `Esc` (seçimi temizle)
- Pencere boyutu ve kolon genişlikleri hatırlanır
- Uygulama ikonu ekle (`assets/icons/gitbroom.png`)
- About diyaloğu (versiyon, lisans)
- README.md güncelle

---

## FAZA 5 — Test ve Paketleme

### Adım 5.1 — Kapsamlı Test Yazımı

Hedef: core katman için %80+ coverage.

Test senaryoları:
- Boş repo
- Sadece default branch
- 100+ branch'li büyük repo
- Squash/rebase merge'leri olan repo
- Remote erişimi olmayan repo
- Bozuk git reposu

---

### Adım 5.2 — PyInstaller Paketleme

`gitbroom.spec` dosyasını oluştur:
- Windows için `.exe` (single file)
- macOS için `.app`
- Linux için tek dosya binary

```bash
pyinstaller gitbroom.spec
```

---

## Geliştirme Sıralaması Özeti

```
Faza 0: Altyapı (0.1 → 0.2 → 0.3)
   ↓
Faza 1: Core Motor (1.1 → 1.2 → 1.3 → 1.4 → 1.5)
   ↓
Faza 2: UI Temel (2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6)
   ↓
Faza 3: Silme Akışı (3.1 → 3.2 → 3.3)
   ↓
Faza 4: Ayarlar & Cilalama (4.1 → 4.2 → 4.3 → 4.4 → 4.5)
   ↓
Faza 5: Test & Paketleme (5.1 → 5.2)
```

---

## Her Adım Sonrası Kontrol Listesi

Claude Code her adım sonunda şunları yapmalı:

- [ ] `pytest tests/ -v` — tüm testler geçiyor mu?
- [ ] `ruff check src/` — linting temiz mi?
- [ ] `python -m gitbroom` — uygulama açılıyor mu?
- [ ] Adımın beklenen çıktısı doğrulandı mı?

Herhangi bir kontrol başarısız olursa bir sonraki adıma geçme, düzelt.
