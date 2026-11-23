#!/usr/bin/env python3

# os.environ["PYLON_ROOT"] = "/opt/pylon"
# # ================== BASLER PYLON (FIRST) ==================
# os.environ["PYLON_ROOT"] = "/opt/pylon"
# os.environ["LD_LIBRARY_PATH"] = "/opt/pylon/lib64"
# os.environ["GENICAM_GENTL64_PATH"] = "/opt/pylon/lib64/gentlproducer"
# os.environ["GENICAM_ROOT_V3_1"] = "/opt/pylon/lib64/genicam"
# # ==========================================================

# ================== QT SETUP ===============================
# from pypylon import pylon
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from classes.bridge import Bridge
from paths import *

from PyQt5.QtCore import QUrl, QCoreApplication
import sys
from classes.database import init_db,load_settings
import os
import traceback

#!/usr/bin/env python3

# os.environ["PYLON_ROOT"] = "/opt/pylon"
# # ================== BASLER PYLON (FIRST) ==================
# os.environ["PYLON_ROOT"] = "/opt/pylon"
# os.environ["LD_LIBRARY_PATH"] = "/opt/pylon/lib64"
# os.environ["GENICAM_GENTL64_PATH"] = "/opt/pylon/lib64/gentlproducer"
# os.environ["GENICAM_ROOT_V3_1"] = "/opt/pylon/lib64/genicam"
# # ==========================================================

# ================== QT SETUP ===============================
# from pypylon import pylon
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from classes.bridge import Bridge
from paths import *

from PyQt5.QtCore import QUrl
import sys
from classes.database import init_db,load_settings
import os

if os.name == 'nt':  # Windows
    os.environ["PYLON_ROOT"] = "C:\\Program Files\\Basler\\pylon"
    os.environ["GENICAM_GENTL64_PATH"] = "C:\\Program Files\\Basler\\pylon\\Runtime\\x64\\genicam\\bin\\Win64_x64"
else:  # Linux/Unix
    os.environ["PYLON_ROOT"] = "/opt/pylon"
    os.environ["GENICAM_GENTL64_PATH"] = "/opt/pylon/lib/gentl"

if os.name == 'nt':  # Windows
    os.environ["QT_QPA_PLATFORM"] = "windows"
else:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

if getattr(sys, "frozen", False):
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
        sys._MEIPASS, "cv2", "qt", "plugins", "platforms"
    )
    print("execute1 (frozen)")
else:
    import PyQt5
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
        os.path.dirname(PyQt5.__file__), "qt", "plugins", "platforms"
    )
    print("execute2 (dev)")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller_window = None
        self.setting_window = None
        self.report_window = None
        self.setWindowTitle("Cone Inspection")
        self.resize(1280, 800)

        # WebEngineView setup
        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        # Bridge and Channel
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        
        # Load local HTML
        self.view.load(QUrl.fromLocalFile(str(INDEX_HTML.resolve())))

    def load_main_page(self, html_path):
        self.view.load(QUrl.fromLocalFile(str(html_path.resolve())))

    def open_home_page(self):
        self.load_main_page(INDEX_HTML)

    # Controller Window
    def open_controller_window(self):
        self.load_main_page(CONTROLLER_HTML)

    def open_training_window(self):
        self.load_main_page(TRAINING_HTML)

    # Setting Window
    def open_setting_window(self):
        self.load_main_page(SETTING_HTML)

    # Report Window
    def open_report_window(self):
        if self.report_window is not None:
            self.report_window.raise_()
            self.report_window.activateWindow()
            self.report_window.showNormal()
            return
        self.report_window = QMainWindow(self)
        self.report_window.setWindowTitle("Report Window")
        self.report_window.resize(900, 700)

        self.report_view = QWebEngineView()
        self.report_window.setCentralWidget(self.report_view)

        self.report_channel = QWebChannel()
        self.report_bridge = Bridge(self)
        self.report_channel.registerObject("bridge", self.report_bridge)
        self.report_view.page().setWebChannel(self.report_channel)

        self.report_view.load(QUrl.fromLocalFile(str(REPORTS_HTML.resolve())))
        self.report_window.show()
        

    def shutdown(self):
        print("[MainWindow] shutdown called")
        try:
            if hasattr(self, "bridge") and self.bridge is not None:
                # Stop live loop + process thread
                try:
                    self.bridge.stopCamera()
                except Exception as e:
                    print("stopCamera on controller close error:", e)

                # Turn OFF all Modbus outputs
                try:
                    self.bridge.all_channels_off()
                except Exception as e:
                    print("all_channels_off error on controller close:", e)

                # Finally close Basler camera
                try:
                    self.bridge._close_camera()
                except Exception as e:
                    print("_close_camera on controller close error:", e)
        except Exception as e:
            print("Controller close handler error:", e)
       

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)



if __name__ == "__main__":
    init_db()
    load_settings()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        ret = app.exec_()
        window.shutdown()
        sys.exit(ret)
    else:
        window = MainWindow()
        window.show()
