import json
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QThread, QTimer, QUrl
import time
import threading
import cv2
import base64
# from classes.plc import plc_check, white_light_signal, uv_light_signal
from classes.Plc_connection import machine_status, uv_light_signal, white_light_signal, uv_light_result, white_light_result
# Project Imports
from paths import (
    TRAINING_PAGE , CONTROLLER_PAGE, INDEX_PAGE, SETTINGS_PAGE, SETTINGS_JSON, TRAINING_IMG, MODELS_DIR
)


# ✅ CHANGED: Import HikRobotCamera instead of BaslerCamera
from classes.webcam import Webcam
from classes.logging import error_log


def j(d):
    try:
        return json.dumps(d, separators=(",", ":"))
    except Exception as e:
        error_log("J()",e)
        return json.dumps({"ok": False, "message": f"JSON error: {e}"})



class CameraGrabWorker(QObject):

    frame_signal = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, cam_factory_func, view=None,
                 mode="live", trigger_event=None):
        super().__init__()

        self._cam_factory = cam_factory_func
        self._running = False
        self._cam = None
        self.view = view

        self.mode = mode
        self.trigger_event = trigger_event
        self.latest_frame = None
        self.frame_lock = threading.Lock() 

        self._previous_trigger = False

    @pyqtSlot()
    def start(self):

        if self._running:
            return

        self._running = True

        try:
            self._cam = self._cam_factory()

            if self._cam is None:
                self.status.emit("Camera open failed")
                return

            self.status.emit(f"{self.mode} camera started")

            while self._running:

                try:
                    frame = self._cam.capture_raw_image()
                    # image = cv2.imread("LUCID_TRI122S-C_263900056__20261128121401111_image0.jpg")
                    # frame = image.copy()
                    if frame is None:
                        QThread.msleep(5)
                        continue
                    # Always update the latest frame
                    with self.frame_lock:
                        self.latest_frame = frame.copy()

                    should_emit = False

                    if self.mode == "live":
                        # Live mode: continuously emit frames
                        should_emit = True

                    elif self.mode == "training":

                        trigger = self.trigger_event.is_set()

                        # Emit only on PLC rising edge
                        if trigger and not self._previous_trigger:
                            should_emit = True

                        self._previous_trigger = trigger

                    if should_emit:

                        success, buffer = cv2.imencode(
                            ".jpg", frame
                        )

                        if success:
                            base64_data = base64.b64encode(
                                buffer.tobytes()
                            ).decode("utf-8")

                            self.frame_signal.emit(base64_data)

                except Exception as e:
                    self.status.emit(f"Grab error: {e}")
                    error_log("CameraGrabWorker", e)
                    QThread.msleep(50)

                QThread.msleep(30)

        except Exception as e:
            error_log("Camera Worker", e)
            self.status.emit(f"Camera error: {e}")

        finally:

            self._running = False

            try:
                if self._cam:
                    self._cam.close()

            except Exception as e:
                error_log("Camera Close", e)

            self._cam = None
            self.status.emit("Camera grabbing stopped")

    @pyqtSlot()
    def stop(self):
        self._running = False

# ================= BRIDGE CLASS =================
class Bridge(QObject):
    frame_signal = pyqtSignal(str)  # Base64 JPEG string

    def __init__(self, main_window, settings):
        super().__init__()
        self.main_window = main_window
        self.web_view = main_window.view
        self.qt_settings = settings
        self.cam_thread = None
        self.cam_worker = None
        self.live_start = False
        self.training_start = False
        self.prediction_start = False
        self.latest_frame = None
        self.plc_status = False
        self.white_light_signal = False
        self.white_light_process = False
        self.uv_light_signal = False
        self.uv_light_process = False
        self.training_trigger = threading.Event()
        self.active_job_id = ""
        self.session_white_count = 0
        self.session_uv_count = 0
        self.job_id = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.connection_check)


    def connection_check(self):
        try:
            self.plc_status = machine_status()

            self.white_light_signal = white_light_signal()
            self.uv_light_signal = uv_light_signal()

            if self.training_start:
                if not self.white_light_signal:
                    self.white_light_process = False
                if not self.uv_light_signal:
                    self.uv_light_process = False

                frame = self.cam_worker.latest_frame if self.cam_worker else None
                if self.white_light_signal and not self.white_light_process:
                    if self.save_training_images(frame, self.job_id, "top_white", self.session_white_count + 1):
                        self.training_trigger.set()
                        self.session_white_count += 1
                        self.white_light_process = True
                        time.sleep(2.0)
                        white_light_result(1)
                elif self.uv_light_signal and not self.uv_light_process:
                    if self.save_training_images(frame, self.job_id, "top_uv", self.session_uv_count + 1):
                        self.training_trigger.set()
                        self.session_uv_count += 1
                        self.uv_light_process = True
                        time.sleep(2.0)
                        uv_light_result(1)
                else:
                    self.training_trigger.clear()

            else:
                self.training_trigger.clear()

        except Exception as e:
            self.plc_status = False
            self.white_light_signal = False
            self.training_trigger.clear()
            error_log("PLC Connection Check", e)

    def save_training_images(self, image, job_id, position, sequence):
        if image is None or image.size == 0:
            return False
        folder = TRAINING_IMG / job_id / position
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{self.capture_session_id}_{sequence:06d}.bmp"
        return cv2.imwrite(str(folder / filename), image)


    @pyqtSlot(result=str)
    def training_job_options(self):
        try:
            jobs = sorted(folder.name for folder in TRAINING_IMG.iterdir() if folder.is_dir())
        except FileNotFoundError:
            return j([])
        except OSError as exc:
            error_log("Training job folders", exc)
            return j([])

        return j([{"job_id": job} for job in jobs])

    def _saved_training_job(self, job_id):
        root = TRAINING_IMG.resolve()
        job = root / job_id
        if job.parent != root or job.resolve() != job or not job.is_dir():
            raise ValueError("The selected training job folder could not be found.")
        return job

    @pyqtSlot(str, result=str)
    def getTrainingJobFolders(self, job_id):
        try:
            job = self._saved_training_job(job_id)
            parts = job.name.rsplit("_", 2)
            material, count = parts[1:] if len(parts) == 3 else ("", "")
            return j({"ok": True, "material": material, "count": count})
        except (OSError, ValueError, RuntimeError) as exc:
            return j({"ok": False, "message": str(exc)})

    def _training_images(self, job):
        light_by_folder = {
            "top_white": "white", "white_field_white": "white",
            "top_uv": "uv", "uv_light_uv": "uv",
        }
        for folder in sorted(job.iterdir()):
            light = light_by_folder.get(folder.name.lower())
            if not light or not folder.is_dir() or folder.resolve() != folder:
                continue
            for image in sorted(folder.iterdir()):
                if image.suffix.lower() in {".bmp", ".jpg", ".jpeg", ".png", ".webp"}:
                    if image.is_file() and image.resolve() == image:
                        yield image, light

    def _training_job_totals(self, job_id):
        counts = {"white": 0, "uv": 0}
        if job_id:
            try:
                job = self._saved_training_job(job_id)
            except ValueError:
                return counts
            for _, light in self._training_images(job):
                counts[light] += 1
        return counts

    @pyqtSlot(str, result=str)
    def getTrainingCaptureStatus(self, job_id):
        job_id = job_id or self.active_job_id
        capturing = self.training_start and job_id == self.active_job_id
        try:
            return j({
                "ok": True,
                "job_id": job_id,
                "stage": "capturing" if capturing else "idle",
                "phase": "waiting" if capturing else "",
                "job_totals": self._training_job_totals(job_id),
            })
        except (OSError, RuntimeError) as exc:
            error_log("Training image counts", exc)
            return j({"ok": False})

    @pyqtSlot(str, result=str)
    def getTrainingImageItems(self, job_id):
        try:
            job = self._saved_training_job(job_id)
            items = [
                {
                    "filename": image.relative_to(job).as_posix(),
                    "light": light,
                    "url": QUrl.fromLocalFile(str(image)).toString(),
                }
                for image, light in self._training_images(job)
            ]
            return j({"ok": True, "items": items})
        except (OSError, ValueError, RuntimeError) as exc:
            error_log("Training job images", exc)
            return j({"ok": False, "items": []})

    @pyqtSlot(str, str, result=str)
    def deleteTrainingImage(self, job_id, filename):
        try:
            job = self._saved_training_job(job_id)
            for image, _ in self._training_images(job):
                if image.relative_to(job).as_posix() == filename:
                    image.unlink()
                    return j({"ok": True, "message": "Image deleted."})
            return j({"ok": False, "message": "The selected image was not found."})
        except (OSError, ValueError, RuntimeError) as exc:
            error_log("Delete training image", exc)
            return j({"ok": False, "message": "Unable to delete the selected image."})

    @pyqtSlot(result=str)
    def startCamera(self):

        if self.cam_thread and self.cam_thread.isRunning():
            return "already_running"

        self.cam_thread = QThread()

        self.cam_worker = CameraGrabWorker(
            self._create_and_open_camera_for_worker,
             mode="live"
        )

        self.cam_worker.moveToThread(self.cam_thread)

        # Worker frame -> Bridge frame
        self.cam_worker.frame_signal.connect(
            self.frame_signal.emit
        )

        self.cam_thread.started.connect(
            self.cam_worker.start
        )

        self.cam_thread.start()

        self.live_start = True

        return "ok"


    @pyqtSlot()
    def stopCamera(self):
        self.live_start = False

        if self.cam_worker:
            self.cam_worker.stop()

        if self.cam_thread:
            self.cam_thread.quit()
            self.cam_thread.wait(5000)

        self.cam_worker = None
        self.cam_thread = None


    @pyqtSlot(str, bool, str, str, result=str)
    def startTraining(self, job, select, material, count):

        try:
            if select:
                self.job_id = job
            else:
                self.job_id = f"{job}_{material}_{count}"
            

            if self.cam_thread and self.cam_thread.isRunning():
                return j({
                    "ok": False,
                    "message": "Camera is already running."
                })

            self.active_job_id = self.job_id
            self.capture_session_id = time.time_ns()
            self.session_white_count = 0
            self.session_uv_count = 0
            self.white_light_process = False
            self.uv_light_process = False

            self.training_trigger.clear()

            self.cam_thread = QThread()

            self.cam_worker = CameraGrabWorker(
                self._create_and_open_camera_for_worker,
                mode="training",
                trigger_event=self.training_trigger
            )

            self.cam_worker.moveToThread(self.cam_thread)

            self.cam_worker.frame_signal.connect(
                self.frame_signal.emit
            )

            self.cam_thread.started.connect(
                self.cam_worker.start
            )

            self.training_start = True

            if not self.timer.isActive():
                self.timer.start(20)

            self.cam_thread.start()

            return j({
                "ok": True,
                "stage": "capturing",
                "phase": "waiting",
                "job_id": self.active_job_id,
                "job_totals": self._training_job_totals(self.active_job_id),
                "message": "Waiting for PLC trigger."
            })

        except Exception as e:

            self.training_start = False
            self.training_trigger.clear()

            error_log("Start Training", e)

            return j({
                "ok": False,
                "message": str(e)
            })

    @pyqtSlot(result=str)
    def stopTraining(self):

        try:
            self.training_start = False
            self.training_trigger.clear()

            if self.timer.isActive():
                self.timer.stop()

            if self.cam_worker:
                self.cam_worker.stop()

            if self.cam_thread:
                self.cam_thread.quit()

                # Wait for camera worker to finish
                stopped = self.cam_thread.wait(5000)

                if not stopped:
                    return j({
                        "ok": False,
                        "stage": "stopping",
                        "message": "Camera is still stopping. Check camera capture timeout."
                    })

            self.cam_worker = None
            self.cam_thread = None

            self.live_start = False

            return j({
                "ok": True,
                "stage": "completed",
                "phase": "closing",
                "job_id": self.active_job_id,
                "job_totals": self._training_job_totals(self.active_job_id),
                "message": "Training capture stopped successfully."
            })

        except Exception as e:

            error_log("Stop Training", e)

            return j({
                "ok": False,
                "stage": "failed",
                "message": str(e)
            })

    
    @pyqtSlot(str, result=str)
    def startModelTraining(self, jobid):

        try:
            print("Training Job ID:", jobid)

            from classes.train import train_knn

            # ================= TOP WHITE =================

            top_white_train = TRAINING_IMG / jobid / "top_white"
            top_white_out = MODELS_DIR / jobid / "top_white.joblib"

            if not top_white_train.exists():
                return j({
                    "ok": False,
                    "stage": "failed",
                    "message": f"Top White training folder not found: {top_white_train}"
                })

            print("Training TOP WHITE model...")

            train_knn(
                top_white_train,
                top_white_out
            )

            print("TOP WHITE training completed")

            # ================= TOP UV =================

            top_uv_train = TRAINING_IMG / jobid / "top_uv"
            top_uv_out = MODELS_DIR / jobid / "top_uv.joblib"

            if not top_uv_train.exists():
                return j({
                    "ok": False,
                    "stage": "failed",
                    "message": f"Top UV training folder not found: {top_uv_train}"
                })

            print("Training TOP UV model...")

            train_knn(
                top_uv_train,
                top_uv_out
            )

            print("TOP UV training completed")

            # ================= SUCCESS =================

            return j({
                "ok": True,
                "stage": "completed",
                "message": "Both Top White and Top UV models trained successfully.",
                "job_id": jobid
            })

        except Exception as e:

            return j({
                "ok": False,
                "stage": "failed",
                "message": str(e),
                "job_id": jobid
            })


    def _new_camera_instance(self):
        """
        Always create a fresh camera object.
        Do not reuse self.cam after _release_camera(), because self.cam may be None.
        """
        try:
            self.settings = self.load_settings_json(SETTINGS_JSON)
            camera_name = str(self.settings.get("camera_name", "lucid")).strip().lower()

            if camera_name == "lucid":
                from classes.lucid import LucidCamera
                return LucidCamera()

            elif camera_name == "hikrobot":
                from classes.hikrobot import HikRobotCamera
                return HikRobotCamera()

            elif camera_name == "webcam":
                idx = int(self.settings.get("camera_index", 0))
                return Webcam(index=idx)

            else:
                print(f"⚠️ Unknown camera_name in settings.json: {camera_name}")
                return None

        except Exception as e:
            error_log("New_camera_instance error",e)
            return None

    def _create_and_open_camera_for_worker(self):
        """
        This is called inside worker thread.
        Do not use self.web_view here.
        Do not use old self.cam here.
        """
        exposure = None

        try:
            cam = self._new_camera_instance()

            if cam is not None:
                try:
                    if exposure is not None:
                        ok = cam.open(exposure)
                    else:
                        ok = cam.open()
                except TypeError as e:
                    error_log("Error",e)
                    ok = cam.open()

                if ok:
                    print("✅ Main camera opened in worker")
                    return cam

                try:
                    cam.close()
                except Exception as e:
                    error_log("Error",e)
                    pass

        except Exception as e:
            error_log("Error",e)
            

        # Fallback webcam
        try:
            idx = self.settings.get("camera_index", 0)
            cam = Webcam(index=int(idx))
            ok = cam.open()
            print(f"⚠️ Worker: Webcam.open({idx}) = {ok}")
            if ok:
                return cam
        except Exception as e:
            error_log("Webcam fallback error",e)


        return None

        

    def load_settings_json(self, path: Path) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            data = {}
            path.write_text(json.dumps(data, indent=2))
            return data

        try:
            return json.loads(path.read_text())
        except Exception as e:
            error_log("Bridge load setting",e)
            # corrupted JSON fallback
            return {}
     
        
    @pyqtSlot()
    def showTraining(self):
        self.main_window.load_page(TRAINING_PAGE)
        
    @pyqtSlot()
    def showController(self):
        self.main_window.load_page(CONTROLLER_PAGE)
        
    @pyqtSlot()
    def showReport(self):
        self.main_window.open_report_window()

    @pyqtSlot()
    def showHome(self):
        self.main_window.load_page(INDEX_PAGE)

    @pyqtSlot()
    def showSetting(self):
        self.main_window.load_page(SETTINGS_PAGE)

    @pyqtSlot(result=str)
    def openInvoiceViewer(self):
        try:
            from classes.invoice_viewer import InvoiceViewer

            parent = getattr(self.main_window, "report_window", None) or self.main_window
            viewer = InvoiceViewer(parent)
            viewer.finished.connect(viewer.deleteLater)
            viewer.open()
            return ""
        except Exception as exc:
            error_log("Open invoice viewer", exc)
            return "Could not open invoice preview"
