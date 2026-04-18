"""Deterministic LAB-median color extraction.

Takes the channel-wise median of the preprocessed image in LAB space, then
converts back to sRGB. LAB is perceptually uniform, so the median is close
to the middle color a human sees. Works well on clean swatches; fails
predictably on heavy texture (that's why vision is the primary method).
"""

from __future__ import annotations

import numpy as np

import image_utils
from models import AlgorithmicResult


def extract(preprocessed_rgb: np.ndarray) -> AlgorithmicResult:
    lab = image_utils.rgb_to_lab(preprocessed_rgb)
    flat = lab.reshape(-1, 3)
    median = np.median(flat, axis=0)
    hex_value = image_utils.rgb_to_hex(image_utils.lab_to_rgb(median))
    std_dev = float(np.std(flat[:, 0]))  # L-channel spread = uniformity proxy
    return AlgorithmicResult(hex=hex_value, std_dev=std_dev)
