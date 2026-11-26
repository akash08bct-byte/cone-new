import cv2
import numpy as np
import json
from pathlib import Path
from paths import SETTINGS_JSON
from classes.logging import error_log

_ARENA_OK = True
try:
    from arena_api.system import system
    from arena_api.buffer import BufferFactory
    print("✅ Arena SDK loaded.")
except Exception as e:
    error_log("Error",e)
    _ARENA_OK = False


class LucidCamera:
    def __init__(self):
        self.device = None
        self.devices = None
        self.is_running = False
    
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

    def open(self,exposure=None):
        if not _ARENA_OK:
            print("❌ Arena SDK not available on this machine.")
            return False
        try:
            settings = self.load_settings_json(SETTINGS_JSON)
            save_exposure = settings.get("exposure", 50000.00)
            self.devices = system.create_device()
            if not self.devices:
                print("❌ No Lucid camera found.")
                return False

            self.device = self.devices[0]
            nodemap = self.device.nodemap

            # Best-effort resolution
            try:
                nodemap["Width"].value = min(4000, nodemap["Width"].max)
            except Exception as e:
                error_log("Error",e)
            try:
                nodemap["Height"].value = min(3000, nodemap["Height"].max)
            except Exception as e:
                error_log("Error",e)

            # Exposure
            try:
                nodemap["ExposureAuto"].value = "Off"
                desired_exposure = float(exposure) if exposure else float(save_exposure) # us
                min_exp = float(nodemap["ExposureTime"].min)
                max_exp = float(nodemap["ExposureTime"].max)
                exposure_to_set = float(np.clip(desired_exposure, min_exp, max_exp))
                nodemap["ExposureTime"].value = exposure_to_set
                
                details = {
                        "camera": "lucid",
                        "current": exposure_to_set,
                        "min": min_exp,
                        "max": max_exp
                    }
                # print(details,"chwecking")
                if min_exp and max_exp:   # optional safety
                    settings["camera_details"] = details
                    SETTINGS_JSON.write_text(json.dumps(settings, indent=2))
                    
                print(f"✅ Exposure set: {exposure_to_set:.2f} µs")
            except Exception as e:
                error_log("Error",e)

            # PixelFormat (try BGR8; if not supported, convert will fail)
            try:
                nodemap["PixelFormat"].value = "BayerRG8"
                print("✅ PixelFormat set to BayerRG8")
            except Exception as e:
                error_log("Error",e)

            self.device.start_stream()
            self.is_running = True
            print("✅ Lucid Camera streaming")
            return True
        except Exception as e:
            error_log("Error",e)
            self.device = None
            self.devices = None
            self.is_running = False
            return False

    def check_connection(self):
        return bool(self.device) and bool(self.is_running)

    def close(self):
        try:
            if self.device and self.is_running:
                try:
                    self.device.stop_stream()
                except Exception as e:
                    error_log("Error",e)
                    pass
            if self.devices:
                try:
                    system.destroy_device(self.devices)
                except Exception as e:
                    error_log("Error",e)
                    # some arena versions accept no args
                    try:
                        system.destroy_device()
                    except Exception as e:
                        error_log("Error",e)
                        pass
            print("✅ Camera closed")
        finally:
            self.device = None
            self.devices = None
            self.is_running = False

    def capture_raw_image(self):
        """Return one BGR frame (numpy array)"""
        if not self.check_connection():
            return None

        buf = None
        converted = None
        try:
            buf = self.device.get_buffer()
            # converted = BufferFactory.convert(buf, "BayerRG8")

            # frame = np.frombuffer(bytes(converted.data), dtype=np.uint8).reshape(
            #     (converted.height, converted.width, 3)
            # )
            frame = np.ctypeslib.as_array(
                buf.pdata,shape=(buf.height,buf.width)
            )
            # self.device.requeue_buffer(buf)
            # frame = cv2.cvtColor(frame,cv2.COLOR_BAYER_BG2BGR)
            frame = cv2.cvtColor(frame,cv2.COLOR_BAYER_BG2BGR)
            return frame.copy()

        except Exception as e:
            error_log("Error",e)
            return None

        finally:
            # Important: destroy converted buffer + requeue original buffer
            # try:
            #     if converted is not None:
            #         BufferFactory.destroy(converted)
            # except Exception:
            #     pass
            try:
                if buf is not None:
                    self.device.requeue_buffer(buf)
            except Exception as e:
                error_log("Error",e)
                pass



# def live_view():
#     cam = LucidCamera()
#     if not cam.open():
#         return

#     win = "LUCID LIVE VIEW  (Q/ESC=Quit, S=Save)"
#     cv2.namedWindow(win, cv2.WINDOW_NORMAL)

#     # Optional: set window size (doesn't change camera resolution)
#     cv2.resizeWindow(win, 1280, 720)

#     save_count = 0
#     t0 = time.time()
#     frames = 0

#     try:
#         while True:
#             frame = cam.capture_raw_image()
#             if frame is None:
#                 # if temporary glitch, continue
#                 key = cv2.waitKey(1) & 0xFF
#                 if key in (27, ord("q")):
#                     break
#                 continue

#             frames += 1
#             dt = time.time() - t0
#             if dt >= 1.0:
#                 fps = frames / dt
#                 frames = 0
#                 t0 = time.time()
#             else:
#                 fps = None

#             # Show FPS text
#             # if fps is not None:
#             #     cv2.putText(
#             #         frame, f"FPS: {fps:.1f}", (20, 50),
#             #         cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2, cv2.LINE_AA
#             #     )

#             cv2.imshow(win, frame)

#             key = cv2.waitKey(1) & 0xFF
#             if key in (27, ord("q")):
#                 break
#             if key == ord("s"):
#                 ts = time.time()
#                 save_path = f"input/lucid_frame_{ts}.bmp"
#                 cv2.imwrite(save_path, frame)
#                 print("✅ Saved:", save_path)
#                 save_count += 1

#     finally:
#         cam.close()
#         cv2.destroyAllWindows()


# if __name__ == "__main__":
#     live_view()
