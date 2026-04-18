"""Shared image pre-processing and color-space math.

Applied identically to both vision and algorithmic extraction so the two
methods see the same pixels.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image

CENTER_CROP_FRACTION = 0.65
DOWNSCALE_LONG_EDGE = 512


def load_and_preprocess(path: Path) -> np.ndarray:
    """Load image, center-crop to the middle 65%, downscale to 512px long edge.

    Returns an HxWx3 uint8 numpy array in sRGB.
    """
    image = Image.open(path).convert("RGB")
    image = _center_crop(image, CENTER_CROP_FRACTION)
    image = _downscale(image, DOWNSCALE_LONG_EDGE)
    return np.asarray(image, dtype=np.uint8)


def encode_jpeg(arr: np.ndarray, quality: int = 90) -> bytes:
    """Encode the preprocessed array back to JPEG for the vision API."""
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _center_crop(image: Image.Image, fraction: float) -> Image.Image:
    w, h = image.size
    cw, ch = int(w * fraction), int(h * fraction)
    left, top = (w - cw) // 2, (h - ch) // 2
    return image.crop((left, top, left + cw, top + ch))


def _downscale(image: Image.Image, long_edge: int) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= long_edge:
        return image
    scale = long_edge / longest
    return image.resize(
        (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
    )


# -----------------------------------------------------------------------------
# sRGB <-> LAB (D65). Hand-rolled to avoid a colormath dependency.
# -----------------------------------------------------------------------------

_D65_XYZ = np.array([0.95047, 1.0, 1.08883])


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert an HxWx3 uint8 sRGB array to HxWx3 float LAB."""
    srgb = rgb.astype(np.float64) / 255.0
    linear = np.where(
        srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4
    )
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ]
    )
    xyz = linear @ m.T
    xyz_n = xyz / _D65_XYZ
    f = np.where(
        xyz_n > (6 / 29) ** 3,
        np.cbrt(xyz_n),
        (xyz_n * (29 / 6) ** 2 / 3) + 4 / 29,
    )
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """Convert a 3-element or ...x3 LAB array back to uint8 sRGB."""
    lab = np.asarray(lab, dtype=np.float64)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    delta = 6 / 29

    def finv(t: np.ndarray) -> np.ndarray:
        return np.where(t > delta, t ** 3, 3 * delta ** 2 * (t - 4 / 29))

    xyz = np.stack([finv(fx), finv(fy), finv(fz)], axis=-1) * _D65_XYZ
    m_inv = np.array(
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.9692660, 1.8760108, 0.0415560],
            [0.0556434, -0.2040259, 1.0572252],
        ]
    )
    linear = xyz @ m_inv.T
    srgb = np.where(
        linear <= 0.0031308,
        12.92 * linear,
        1.055 * np.power(np.clip(linear, 0, None), 1 / 2.4) - 0.055,
    )
    return np.clip(np.round(srgb * 255), 0, 255).astype(np.uint8)


def hex_to_rgb(hex_str: str) -> np.ndarray:
    s = hex_str.lstrip("#")
    return np.array(
        [int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)], dtype=np.uint8
    )


def rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(x) for x in rgb.reshape(-1)[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def delta_e_76(hex_a: str, hex_b: str) -> float:
    """CIE76 ΔE between two hex colors. Good enough for our bucket thresholds."""
    lab_a = rgb_to_lab(hex_to_rgb(hex_a).reshape(1, 1, 3))[0, 0]
    lab_b = rgb_to_lab(hex_to_rgb(hex_b).reshape(1, 1, 3))[0, 0]
    return float(math.sqrt(float(np.sum((lab_a - lab_b) ** 2))))
