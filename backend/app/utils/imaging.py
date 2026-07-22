"""Image decoding helpers for frames arriving over the WebSocket."""

import base64
from io import BytesIO

import cv2
import numpy as np
from PIL import Image


def base64_to_image(base64_str: str) -> np.ndarray:
    """Decode a base64 data URL (or bare base64 payload) into a BGR numpy array."""
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]

    img_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(img_data))
    img_array = np.array(image)
    return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
