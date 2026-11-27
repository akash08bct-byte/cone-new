import cv2
import numpy as np


def largest_contour(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise RuntimeError("No object found - check the thresholds")
    return max(cnts, key=cv2.contourArea)


def detect_circles(img):
    """Return outer yarn circle and core circle as ((cx, cy), r)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    # Outer edge: bright yarn against dark background (Otsu threshold)
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, yarn = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yarn = cv2.morphologyEx(yarn, cv2.MORPH_OPEN, kernel)
    outer_cnt = largest_contour(yarn)
    outer = cv2.minEnclosingCircle(cv2.convexHull(outer_cnt))
    (ox, oy), outer_r = outer

    # Core (any colour): the central area that looks different from the yarn.
    # First learn the yarn colour from a band that contains only yarn.
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    dist = np.hypot(xx - ox, yy - oy)
    band = (dist > outer_r * 0.45) & (dist < outer_r * 0.80)
    yarn_color = np.median(lab[band], axis=0)

    # Colour and brightness difference of every pixel from the yarn
    diff = np.linalg.norm(lab - yarn_color, axis=2)
    # Threshold sits above the normal variation of the yarn itself
    limit = max(18.0, float(np.percentile(diff[band], 99.5)))
    roi = dist < outer_r * 0.45
    other = ((diff > limit) & roi).astype(np.uint8) * 255
    other = cv2.morphologyEx(other, cv2.MORPH_OPEN, kernel)
    other = cv2.morphologyEx(other, cv2.MORPH_CLOSE, kernel)

    core_cnt = largest_contour(other)
    core = cv2.minEnclosingCircle(cv2.convexHull(core_cnt))
    (cx, cy), core_r = core

    # Reject results that cannot be a real core
    fill = cv2.contourArea(cv2.convexHull(core_cnt)) / (np.pi * core_r ** 2)
    if (fill < 0.85 or np.hypot(cx - ox, cy - oy) > outer_r * 0.12
            or not outer_r * 0.08 < core_r < outer_r * 0.43):
        raise RuntimeError("Core not found reliably - check this image")
    return outer, core


def cut(img, mask, center, radius):
    """Black out everything outside the mask and crop around the circle."""
    out = cv2.bitwise_and(img, img, mask=mask)
    (x, y), rad = center, int(radius)
    return out[max(y - rad, 0):y + rad + 1, max(x - rad, 0):x + rad + 1].copy()


def split_thread_tip(img):
    """
    img : BGR image as a NumPy array (from cv2.imread or a camera)
    returns [thread, tip] : two BGR NumPy arrays, black outside each part
    """
    if img is None:
        raise ValueError("Image is empty - check the image path or camera")

    ((ox, oy), R), ((cx, cy), r) = detect_circles(img)
    package_center = (int(round(ox)), int(round(oy)))
    tip_center = (int(round(cx)), int(round(cy)))
    R = int(round(R - 3))  # exclude background pixels
    r = int(round(r))

    tip_mask = np.zeros(img.shape[:2], np.uint8)
    cv2.circle(tip_mask, tip_center, r, 255, -1)

    thread_mask = np.zeros(img.shape[:2], np.uint8)
    cv2.circle(thread_mask, package_center, R, 255, -1)
    thread_mask[tip_mask > 0] = 0  # remove the tip from the thread

    thread = cut(img, thread_mask, package_center, R)
    tip = cut(img, tip_mask, tip_center, r)
    return [thread, tip]


if __name__ == "__main__":
    image = cv2.imread(r"tip_image_20260106_120856_602.bmp")  # change to your image path
    thread, tip = split_thread_tip(image)
    cv2.imwrite(r"thread.png", thread)  # change to your desired output path
    cv2.imwrite(r"tip.png", tip)  # change to your desired output path
    print("Thread:", thread.shape, thread.dtype)
    print("Tip   :", tip.shape, tip.dtype)