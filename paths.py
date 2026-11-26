import sys
from pathlib import Path
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
# =====================================================
# CORE PATH HELPERS
# =====================================================

def app_path() -> Path:
    """
    Read-only application path
    - Normal run   → project root
    - PyInstaller  → _MEIPASS
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def run_path() -> Path:
    """
    Read/write runtime path
    - Normal run   → project root
    - PyInstaller  → exe folder
    """
    if IS_WINDOWS:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent

        return Path.cwd()

    elif IS_LINUX:
        path = Path.home() / "Documents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    return Path.cwd()

# =====================================================
# READ-ONLY (BUNDLED) PATHS
# =====================================================

APP_DIR = app_path()
LICENSE_FILE = APP_DIR / "hardware_key.lic"
FRONT_END = APP_DIR / "frontend_files"
TEMPLATES_DIR      = FRONT_END / "templates"
ASSETS = FRONT_END / "assets"

INDEX_PAGE  = TEMPLATES_DIR / "index.html"
TRAINING_PAGE  = TEMPLATES_DIR / "training.html"
CONTROLLER_PAGE  = TEMPLATES_DIR / "controller.html"
REPORT_PAGE = TEMPLATES_DIR / "reports.html"
SETTINGS_PAGE = TEMPLATES_DIR / "settings.html"

# =====================================================
# READ / WRITE (RUNTIME) PATHS
# =====================================================

RUN_DIR = run_path()

RUN_DIR = RUN_DIR/"ConeI_Data"

RUN_DIR.mkdir(parents=True, exist_ok=True)
KEY_GENERATE = RUN_DIR/"generate_key.txt"

MODELS_DIR  = RUN_DIR / "models"
DB_PATH = RUN_DIR / "main_db.db"
SETTINGS_JSON = RUN_DIR / "settings.json"
ERROR_LOG = RUN_DIR / "error_log.txt"
TRAINING_IMG = RUN_DIR / "training_images"
# =====================================================
# ENSURE RUNTIME DIRECTORIES
# =====================================================

MODELS_DIR.mkdir(parents=True, exist_ok=True)
