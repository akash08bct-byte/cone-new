from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from classes.split_thread import split_thread_tip


def training_image_paths(image_dir):
    folder = Path(image_dir)
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    paths = sorted(
        path for path in folder.rglob("*")
        if path.suffix.lower() in extensions and path.is_file()
    )
    if not paths:
        raise RuntimeError(f"No training images found in {folder.name}.")
    return paths


def load_thread_image(path):
    try:
        with Image.open(path) as image:
            image_bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        thread, _ = split_thread_tip(image_bgr)
        return Image.fromarray(cv2.cvtColor(thread, cv2.COLOR_BGR2RGB))
    except (OSError, ValueError, RuntimeError, cv2.error) as exc:
        raise RuntimeError(
            f"Cannot train with {path.parent.name}/{path.name}. "
            f"{exc}. Replace this capture with a clear, centered image of the cone."
        ) from exc
