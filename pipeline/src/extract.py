"""Orchestrate algorithmic + (optional) vision extraction, pick final hex.

Every image is classified as a photograph or a rendered swatch first.
Rendered swatches (flat images with near-zero color variance and essentially
no edges — e.g. design-software-produced swatches like AGF Pure Solids) skip
vision and use algorithmic extraction directly. Photographs run the full
vision + algorithmic consensus.

Consensus logic for photographs (from docs/project-plan.md):

    ΔE < 3  and no warnings  -> vision_consensus, high
    ΔE < 3  and warnings      -> vision_consensus, medium
    3 <= ΔE < 7               -> vision_claude,    medium
    ΔE >= 7                   -> vision_claude,    low (review flagged)

Vision wins on disagreement: the algorithmic method fails predictably on
textured fabrics where human-perceived color differs from mathematical
median. When they disagree it's usually the algorithm that's wrong — but
confidence drops, so a human should look.
"""

from __future__ import annotations

from typing import List

import numpy as np

import extract_algorithmic
import image_utils
import vision
from models import AlgorithmicResult, ExtractionResult, ParsedColor

DELTA_E_AGREE = 3.0
DELTA_E_DISAGREE = 7.0

# Classifier v1 (calibrated 2026-04-19 on 370 Kona photos + 8 AGF swatches):
#   AGF swatches:         max_lab_std=0.00, edge_ratio=0.00
#   Smoothest Kona photo: max_lab_std=1.08, edge_ratio=0.17
# Both signals must be below threshold to classify as rendered_swatch; this
# preserves a healthy buffer on each side of the split. Bumping a threshold
# counts as a classifier version bump — see CLASSIFIER_VERSION.
CLASSIFIER_VERSION = "v1"
FLAT_LAB_STD_THRESHOLD = 0.5
FLAT_EDGE_RATIO_THRESHOLD = 0.05


def extract(parsed: List[ParsedColor]) -> List[ExtractionResult]:
    out: List[ExtractionResult] = []
    for item in parsed:
        preprocessed = image_utils.load_and_preprocess(item.image_path)
        algo = extract_algorithmic.extract(preprocessed)
        classification = _classify(algo, preprocessed)

        if classification == "rendered_swatch":
            out.append(
                ExtractionResult(
                    parsed=item,
                    algorithmic=algo,
                    classification=classification,
                    vision=None,
                    delta_e=0.0,
                    final_hex=algo.hex,
                    final_method="algorithmic",
                    final_confidence="high",
                )
            )
            continue

        jpeg = image_utils.encode_jpeg(preprocessed)
        vision_result = vision.extract(jpeg)
        delta_e = image_utils.delta_e_76(vision_result.hex, algo.hex)
        final_hex, final_method, final_confidence = _consensus(
            vision_result, delta_e
        )
        out.append(
            ExtractionResult(
                parsed=item,
                algorithmic=algo,
                classification=classification,
                vision=vision_result,
                delta_e=delta_e,
                final_hex=final_hex,
                final_method=final_method,
                final_confidence=final_confidence,
            )
        )
    return out


def _classify(algo: AlgorithmicResult, preprocessed_rgb: np.ndarray) -> str:
    max_lab_std = max(algo.std_dev, algo.std_a, algo.std_b)
    edge_ratio = _edge_ratio(preprocessed_rgb)
    if (
        max_lab_std < FLAT_LAB_STD_THRESHOLD
        and edge_ratio < FLAT_EDGE_RATIO_THRESHOLD
    ):
        return "rendered_swatch"
    return "photograph"


def _edge_ratio(preprocessed_rgb: np.ndarray) -> float:
    """Fraction of pixels with a non-trivial luminance step to a neighbor.

    Rendered swatches sit at ~0.0; even the smoothest fabric photograph has
    enough weave texture to push this well above 0.1.
    """
    lab = image_utils.rgb_to_lab(preprocessed_rgb)
    L = lab[:, :, 0]
    gy = np.abs(np.diff(L, axis=0))
    gx = np.abs(np.diff(L, axis=1))
    return float((np.mean(gy > 2.0) + np.mean(gx > 2.0)) / 2.0)


def _consensus(vision_result, delta_e: float):
    has_warnings = bool(vision_result.warnings)
    if delta_e < DELTA_E_AGREE and not has_warnings:
        return vision_result.hex, "vision_consensus", "high"
    if delta_e < DELTA_E_AGREE and has_warnings:
        return vision_result.hex, "vision_consensus", "medium"
    if delta_e < DELTA_E_DISAGREE:
        return vision_result.hex, "vision_claude", "medium"
    return vision_result.hex, "vision_claude", "low"
