import cv2
import os

# =========================================================
# 3. WEBCAM CLASS (Fallback)
# =========================================================

class Webcam:
    def __init__(self, index=1):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(index)
        if not self.cap or not self.cap.isOpened():
            print("❌ Webcam Initialization Failed")
            self.cap = None
        else:
            print("✅ Webcam Initialized Successfully")

    def open(self,exposer = None):
        return self.check_connection()

    def check_connection(self):
        return self.cap is not None and self.cap.isOpened()

    def close(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            print("✅ Webcam closed")
        self.cap = None

    def __del__(self):
        self.close()

    def capture_raw_image(self):
        if not self.check_connection():
            return None
        ok, frame = self.cap.read()
        return frame.copy() if ok else None