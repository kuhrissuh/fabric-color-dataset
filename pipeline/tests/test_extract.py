from __future__ import annotations

from typing import List

import pytest

import extract
from models import VisionResult

VISION_HEX = "#7ED3B0"


def _vision(warnings: List[str] = None) -> VisionResult:
    return VisionResult(
        hex=VISION_HEX,
        confidence="high",
        observations="",
        warnings=list(warnings or []),
    )


@pytest.mark.parametrize(
    "delta_e, warnings, expected_method, expected_confidence",
    [
        (0.0, [], "vision_consensus", "high"),
        (2.9, [], "vision_consensus", "high"),
        (2.9, ["uneven lighting"], "vision_consensus", "medium"),
        (3.0, [], "vision_claude", "medium"),
        (6.9, [], "vision_claude", "medium"),
        (7.0, [], "vision_claude", "low"),
        (20.0, ["wrinkled"], "vision_claude", "low"),
    ],
)
def test_consensus_buckets(delta_e, warnings, expected_method, expected_confidence):
    hex_, method, confidence = extract._consensus(_vision(warnings), delta_e)
    assert hex_ == VISION_HEX
    assert method == expected_method
    assert confidence == expected_confidence
