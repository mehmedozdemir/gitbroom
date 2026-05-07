# GitBroom — SKILLS.md
## Claude Code Geliştirme Becerileri ve Kalıplar

---

## 1. PyQt6 Geliştirme Becerileri

### QAbstractTableModel Kullanımı
Branch listesi için custom model yaz — asla `QTableWidget` kullanma.

```python
class BranchTableModel(QAbstractTableModel):
    COLUMNS = ["", "Branch", "Author", "Son Commit", "Merge", "Risk", "Konum"]
    
    def __init__(self, branches: list[BranchInfo]):
        super().__init__()
        self._branches = branches
        self._filtered = branches  # filtreleme için ayrı liste tut
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._filtered)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        branch = self._filtered[index.row()]
        col = index.column()
        
        if role == Qt.ItemDataRole.DisplayRole:
            # Her kolon için doğru veriyi döndür
            ...
        
        if role == Qt.ItemDataRole.DecorationRole:
            # Risk ikonu için
            ...
        
        if role == Qt.ItemDataRole.CheckStateRole and col == 0:
            # Checkbox için
            ...
    
    def filter(self, text: str, show_merged: bool, show_stale: bool):
        """Filtreleme sonrası beginResetModel/endResetModel çağır."""
        self.beginResetModel()
        self._filtered = [b for b in self._branches if self._matches(b, text, show_merged, show_stale)]
        self.endResetModel()
```

### Worker Thread Pattern (Git İşlemleri İçin)
Git işlemleri UI thread'ini **asla** bloklamamalı.

```python
class BranchAnalyzerWorker(QThread):
    progress = pyqtSignal(int, int)          # current, total
    branch_ready = pyqtSignal(BranchInfo)    # her branch hazır olduğunda
    finished = pyqtSignal(list)              # tüm branch'ler hazır
    error = pyqtSignal(str)                  # hata mesajı
    
    def __init__(self, repo_path: str, settings: Settings):
        super().__init__()
        self.repo_path = repo_path
        self.settings = settings
        self._cancelled = False
    
    def run(self):
        try:
            analyzer = BranchAnalyzer(self.repo_path, self.settings)
            branches = analyzer.get_all_branches()
            for i, branch in enumerate(branches):
                if self._cancelled:
                    return
                info = analyzer.analyze(branch)
                self.branch_ready.emit(info)
                self.progress.emit(i + 1, len(branches))
            self.finished.emit([...])
        except Exception as e:
            self.error.emit(str(e))
    
    def cancel(self):
        self._cancelled = True
```

### QSS Theming
`assets/style.qss` dosyasında merkezi stil tanımla:

```css
/* Dark Theme */
QMainWindow {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QTableView {
    background-color: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 8px;
}

QTableView::item:selected {
    background-color: #45475a;
}

QPushButton#dangerButton {
    background-color: #f38ba8;
    color: #1e1e2e;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton#dangerButton:hover {
    background-color: #eba0ac;
}
```

---

## 2. gitpython Kullanım Kalıpları

### Repo Yükleme

```python
from git import Repo, InvalidGitRepositoryError

def load_repo(path: str) -> Repo:
    try:
        repo = Repo(path, search_parent_directories=True)
        if repo.bare:
            raise ValueError("Bare repo desteklenmiyor")
        return repo
    except InvalidGitRepositoryError:
        raise ValueError(f"{path} geçerli bir git reposu değil")
```

### Branch Analizi

```python
def get_all_branches(repo: Repo) -> list[dict]:
    branches = []
    
    # Local branches
    for ref in repo.heads:
        branches.append({
            "name": ref.name,
            "is_local": True,
            "is_remote": False,
            "commit": ref.commit
        })
    
    # Remote branches (local tracking'i olmayan)
    local_names = {b["name"] for b in branches}
    for ref in repo.remote().refs:
        name = ref.name.split("/", 1)[1]  # "origin/main" → "main"
        if name not in ("HEAD",) and name not in local_names:
            branches.append({
                "name": name,
                "is_local": False,
                "is_remote": True,
                "commit": ref.commit
            })
    
    return branches

def is_merged_into(branch_commit, target_branch, repo: Repo) -> bool:
    """Branch'in target'a merge edilip edilmediğini kontrol et."""
    try:
        merge_base = repo.merge_base(branch_commit, target_branch.commit)
        return merge_base[0] == branch_commit
    except Exception:
        return False
```

### Squash Merge Tespiti

```python
def detect_squash_merge(branch, default_branch, repo: Repo) -> bool:
    """
    Squash merge tespiti için branch'in commit tree'sini
    default branch'teki commit'lerle karşılaştır.
    Performans için max 200 commit kontrol et.
    """
    try:
        tree1 = branch.commit.tree
        # Default branch'teki son 200 commit'in tree'leri
        for commit in default_branch.commit.iter_items(repo, default_branch, max_count=200):
            if commit.tree == tree1:
                return True
        return False
    except Exception:
        return False
```

---

## 3. Güvenli Silme İşlemi

```python
class SafeDeleter:
    def __init__(self, repo: Repo, settings: Settings):
        self.repo = repo
        self.settings = settings
    
    def delete_branch(
        self,
        branch_name: str,
        delete_local: bool,
        delete_remote: bool,
        create_backup_tag: bool
    ) -> DeletionResult:
        
        # Güvenlik kontrolleri
        self._safety_checks(branch_name)
        
        # Yedek tag oluştur
        if create_backup_tag:
            tag_name = self._create_backup_tag(branch_name)
        
        errors = []
        
        # Local sil
        if delete_local:
            try:
                self.repo.delete_head(branch_name, force=False)
            except Exception as e:
                errors.append(f"Local silme hatası: {e}")
        
        # Remote sil
        if delete_remote:
            try:
                self.repo.remote().push(f":refs/heads/{branch_name}")
            except Exception as e:
                errors.append(f"Remote silme hatası: {e}")
        
        # Log kaydı
        self._log_deletion(branch_name, delete_local, delete_remote, errors)
        
        return DeletionResult(
            branch=branch_name,
            local_deleted=delete_local and not errors,
            remote_deleted=delete_remote and not errors,
            backup_tag=tag_name if create_backup_tag else None,
            errors=errors
        )
    
    def _safety_checks(self, branch_name: str):
        default = self.settings.default_branch
        if branch_name == default:
            raise ValueError(f"Default branch ({default}) silinemez!")
        if branch_name == self.repo.active_branch.name:
            raise ValueError("Aktif branch (HEAD) silinemez!")
    
    def _create_backup_tag(self, branch_name: str) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        tag_name = f"backup/{branch_name}-{date_str}"
        self.repo.create_tag(tag_name)
        return tag_name
```

---

## 4. Settings (TOML Config)

```python
# ~/.gitbroom/config.toml
[general]
default_branch = "main"
stale_days_green = 90
stale_days_yellow = 30
stale_days_red = 14
theme = "dark"
language = "tr"

[gitlab]
enabled = false
url = "https://gitlab.com"
token = ""  # env var GITBROOM_GITLAB_TOKEN tercih edilir

[behavior]
create_backup_tag = true
confirm_remote_delete = true
show_merged_by_default = true
```

```python
@dataclass
class Settings:
    default_branch: str = "main"
    stale_days_green: int = 90
    stale_days_yellow: int = 30
    stale_days_red: int = 14
    theme: str = "dark"
    gitlab_enabled: bool = False
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    create_backup_tag: bool = True
    confirm_remote_delete: bool = True
    
    @classmethod
    def load(cls) -> "Settings":
        config_path = Path.home() / ".gitbroom" / "config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            return cls(**_flatten(data))
        return cls()
    
    def save(self):
        config_path = Path.home() / ".gitbroom" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # toml write...
```

---

## 5. GitLab Entegrasyon Kalıbı

```python
import gitlab
from typing import Optional

class GitLabClient:
    def __init__(self, url: str, token: str):
        self._gl = gitlab.Gitlab(url, private_token=token)
        self._project: Optional[object] = None
    
    def connect(self, remote_url: str) -> bool:
        """Remote URL'den proje bul ve bağlan."""
        try:
            self._gl.auth()
            project_path = self._extract_project_path(remote_url)
            self._project = self._gl.projects.get(project_path)
            return True
        except Exception as e:
            logging.warning(f"GitLab bağlantısı başarısız: {e}")
            return False
    
    def get_branch_mr(self, branch_name: str) -> Optional[dict]:
        """Branch için açık MR bilgisi getir."""
        if not self._project:
            return None
        try:
            mrs = self._project.mergerequests.list(
                source_branch=branch_name,
                state="opened"
            )
            if mrs:
                mr = mrs[0]
                return {
                    "id": mr.iid,
                    "state": mr.state,
                    "author": mr.author["username"],
                    "title": mr.title
                }
        except Exception:
            return None
    
    def _extract_project_path(self, remote_url: str) -> str:
        # "git@gitlab.com:group/project.git" → "group/project"
        # "https://gitlab.com/group/project.git" → "group/project"
        ...
```

---

## 6. Hata Yönetimi Prensipleri

```python
# Kullanıcıya gösterilen hata mesajları teknik değil, anlaşılır olmalı
ERROR_MESSAGES = {
    "InvalidGitRepositoryError": "Seçilen klasör geçerli bir Git reposu değil.",
    "NoRemoteError": "Bu repoda remote tanımlı değil.",
    "GitCommandError": "Git komutu çalıştırılırken hata oluştu. Remote'a erişiminiz olduğundan emin olun.",
    "AuthenticationError": "GitLab token geçersiz veya süresi dolmuş.",
}

def user_friendly_error(exception: Exception) -> str:
    class_name = type(exception).__name__
    return ERROR_MESSAGES.get(class_name, f"Beklenmeyen hata: {exception}")
```

---

## 7. Test Yazma Kalıpları

```python
# tests/core/test_scorer.py
import pytest
from datetime import datetime, timedelta
from gitbroom.core.scorer import RiskScorer
from gitbroom.core.models import BranchInfo

@pytest.fixture
def scorer(default_settings):
    return RiskScorer(default_settings)

def test_merged_old_branch_is_green(scorer):
    branch = make_branch(
        is_merged=True,
        days_old=100
    )
    assert scorer.score(branch).level == "green"

def test_active_branch_is_red(scorer):
    branch = make_branch(
        is_merged=False,
        days_old=5
    )
    assert scorer.score(branch).level == "red"

def test_unmerged_stale_is_yellow(scorer):
    branch = make_branch(
        is_merged=False,
        days_old=65
    )
    assert scorer.score(branch).level == "yellow"
```

---

## 8. Performance İpuçları

- **Büyük repolar için:** Branch analizi stream edilmeli, `branch_ready` signal'i her branch için emit edilmeli
- **Squash merge tespiti:** Sonuçları cache'le (branch SHA → merge status)
- **Remote fetch:** Sadece kullanıcı istediğinde yap, otomatik yapma
- **UI freeze:** Her git işlemi `QThread` içinde çalışmalı, hiçbir zaman main thread'de değil
