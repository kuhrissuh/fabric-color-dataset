"""Orchestrate vision + algorithmic extraction, pick final hex + confidence.

Consensus logic (from docs/project-plan.md):

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

import extract_algorithmic
import image_utils
import vision
from models import ExtractionResult, ParsedColor

DELTA_E_AGREE = 3.0
DELTA_E_DISAGREE = 7.0


def extract(parsed: List[ParsedColor]) -> List[ExtractionResult]:
    out: List[ExtractionResult] = []
    for item in parsed:
        preprocessed = image_utils.load_and_preprocess(item.image_path)
        algo = extract_algorithmic.extract(preprocessed)

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
                vision=vision_result,
                delta_e=delta_e,
                final_hex=final_hex,
                final_method=final_method,
                final_confidence=final_confidence,
            )
        )
    return out


def _consensus(vision_result, delta_e: float):
    has_warnings = bool(vision_result.warnings)
    if delta_e < DELTA_E_AGREE and not has_warnings:
        return vision_result.hex, "vision_consensus", "high"
    if delta_e < DELTA_E_AGREE and has_warnings:
        return vision_result.hex, "vision_consensus", "medium"
    if delta_e < DELTA_E_DISAGREE:
        return vision_result.hex, "vision_claude", "medium"
    return vision_result.hex, "vision_claude", "low"
