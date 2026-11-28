import os
import sys

if __name__ == "__main__" and sys.argv[1:2] == ["--train-models"]:
    from classes.training_worker import run

    sys.exit(run(*sys.argv[2:]))

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing --disable-features=Vulkan --log-level=3"
os.environ["QT_OPENGL"] = "software"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QUrl, QSettings, QEvent, Qt, QTimer
from PyQt5.QtWidgets import QApplication
from classes.hardware import get_hardware_id
from pathlib import Path
from classes.bridge import Bridge
from paths import INDEX_PAGE,REPORT_PAGE,TEMPLATES_DIR,SETTINGS_JSON,LICENSE_FILE,KEY_GENERATE
# ✅ If you use QWebEngine (controller), keep these to avoid GPU context loss
import json
from classes.logging import error_log

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

# ===============================
# Platform selection
# ===============================
if IS_LINUX:
    os.environ["QT_QPA_PLATFORM"] = "xcb"
elif IS_WINDOWS:
    os.environ["QT_QPA_PLATFORM"] = "windows"

import cv2

cv2_path = os.path.dirname(cv2.__file__)

if getattr(sys, "frozen", False):
    # PyInstaller executable mode
    base = Path(sys.executable).resolve().parent

    plugin_root = os.path.join(cv2_path, "qt", "plugins")

    os.environ["QT_PLUGIN_PATH"] = plugin_root
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
        plugin_root,
        "platforms"
    )

else:
    # Development mode
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
        cv2_path,
        "qt",
        "plugins",
        "platforms"
    )


# ✅ Must be before QApplication()
QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)



class MainWindow(QMainWindow):
    def __init__(self, on_exit_callback=None):
        super().__init__()
        self._on_exit_callback = on_exit_callback
        self._was_minimized = False

        self.setWindowTitle("TTS / ConeI v2")

        self.app_settings = QSettings("TTS", "ConeI")
        settings = self.load_settings_json(SETTINGS_JSON)
        show = settings.get("show_size", 1)
        if show == 1:
            self.showMaximized()
        elif show == 2:
            self.resize(1400, 900)
        else:
            self.showFullScreen()
        # Central Web View
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        # self.view.setPage(DebugPage(self.view))

        # Settings
        web_settings = self.view.settings()
        web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # Bridge
        self.channel = QWebChannel(self.view.page())
        self.bridge = Bridge(self, self.app_settings)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # Load UI
        start_url = QUrl.fromLocalFile(str(INDEX_PAGE))
        self.view.load(start_url)
    
    def load_settings_json(self, path: Path) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            data = {}
            path.write_text(json.dumps(data, indent=2))
            return data

        try:
            return json.loads(path.read_text())
        except Exception as e:
            error_log("Error",e)
            return {}

    def load_page(self, page_name):
        # print(f"Switching to {page_name}")

        file_path = page_name

        if file_path.exists():

            # Clear previous page (important for Linux)
            self.view.setUrl(QUrl("about:blank"))

            # Load new page
            self.view.load(QUrl.fromLocalFile(str(file_path)))

            # Reconnect channel
            self.view.page().setWebChannel(self.channel)

        else:
            print("❌ Page not found:", file_path)

    # =====================================
    # REPORT WINDOW
    # =====================================

    def open_report_window(self):

        # if already open → bring front
        if hasattr(self, "report_window") and self.report_window:
            if self.report_window.isVisible():
                self.report_window.activateWindow()
                return

        self.report_window = QMainWindow(self)

        self.report_window.setWindowTitle("Report")
        self.report_window.setFixedSize(1000, 700)
        self.report_window.setWindowState(Qt.WindowNoState)

        view = QWebEngineView()
        self.report_window.setCentralWidget(view)
        # ----------- pdf report channel setup -----------
        # ✅ self.report_channel — not a local variable
        self.report_channel = QWebChannel()
        self.report_channel.registerObject("bridge", self.bridge)
        view.page().setWebChannel(self.report_channel)
        # ----------- pdf report channel setup -----------
        report_file = (REPORT_PAGE).resolve()

        if report_file.exists():
            view.load(QUrl.fromLocalFile(str(report_file)))
        else:
            print("❌ reports not found:", report_file)

        self.report_window.show()



    def closeEvent(self, event):
        try:
            self.bridge.stopTrainingSession()
        except Exception as e:
            error_log("Error",e)
            pass

        try:
            self.bridge.stopLiveFeed()
        except Exception as e:
            error_log("Error",e)
            pass

        try:
            self.bridge._release_camera()
        except Exception as e:
            error_log("Error",e)
            pass

        try:
            if callable(self._on_exit_callback):
                self._on_exit_callback()
        except Exception as e:
            error_log("Error",e)
            pass

        super().closeEvent(event)
        event.accept()

    def load_settings_json(self, path: Path) -> dict:
            path.parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                data = {}
                path.write_text(json.dumps(data, indent=2))
                return data

            try:
                return json.loads(path.read_text())
            except Exception as e:
                error_log("Error",e)
                return {}
            
            
def verify_hardware_key():
    if not os.path.exists(LICENSE_FILE):
        return False, "Hardware key file missing. Cannot generate again."

    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)

        saved_hardware_id = data.get("hardware_id")

        current_hardware_id = get_hardware_id()

        if saved_hardware_id != current_hardware_id:
            return False, "This key belongs to another system."

        return True, "Hardware key verified."

    except Exception as e:
        error_log("Error",e)
        return False, str(e)
    
def generate_key():
    try:
        # txt_file = KEY_GENERATE
        # print(KEY_GENERATE)
        if KEY_GENERATE.exists():
            code = KEY_GENERATE.read_text(encoding="utf-8")
            namespace = {}
            exec(code, namespace)

            # If the file only defines the function:
            if "generate_key_file" in namespace:
                namespace["generate_key_file"]()
            KEY_GENERATE.unlink()
            # from config.generate_key import generate_key_file
            # generate_key_file()
    except Exception as e:
        error_log("Error",e)


APP_NAME = "ConeI"
ORG_NAME = "TTS"

# import threading
def main():
    # create_tables()
    # load_settings_json(SETTINGS_JSON)
    # prevent_sleep(True)   # ✅ start keep-awake early

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    win = MainWindow()
    win.setAttribute(Qt.WA_DeleteOnClose, True)
    win.show()

    # try:
    sys.exit(app.exec_())
    # finally:
    #     prevent_sleep(False)  # ✅ release keep-awake on exit


if __name__ == "__main__":
    generate_key()
    ok, message = verify_hardware_key()

    if not ok:
        print("❌ ERROR:", message)
        sys.exit(1)
    main()
