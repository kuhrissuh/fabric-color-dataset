from __future__ import annotations

import json

import pytest

import vision

VALID = {
    "hex": "#7ED3B0",
    "confidence": "high",
    "observations": "Even teal-green swatch.",
    "warnings": [],
}


def _fenced(payload: dict, lang: str = "json") -> str:
    body = json.dumps(payload)
    fence = f"```{lang}" if lang else "```"
    return f"{fence}\n{body}\n```"


def test_raw_json_parses():
    parsed = vision._parse_model_output(json.dumps(VALID))
    assert parsed["hex"] == "#7ED3B0"
    assert parsed["confidence"] == "high"


def test_fenced_json_parses():
    parsed = vision._parse_model_output(_fenced(VALID))
    assert parsed["hex"] == "#7ED3B0"


def test_garbage_prefix_then_fenced_block():
    text = '{"hex": "#21A css".\n\n' + _fenced(VALID)
    parsed = vision._parse_model_output(text)
    assert parsed["hex"] == "#7ED3B0"


def test_multiple_fenced_blocks_takes_last():
    first = {**VALID, "hex": "#111111"}
    last = {**VALID, "hex": "#222222"}
    text = _fenced(first) + "\n\nactually:\n\n" + _fenced(last)
    parsed = vision._parse_model_output(text)
    assert parsed["hex"] == "#222222"


def test_devanagari_digits_normalized():
    # २०४ is Devanagari for 204; #B8२०४A → #B8204A
    assert vision._normalize_hex("#B8२०४A") == "#B8204A"


def test_arabic_indic_digits_normalized():
    # ٢٠٤ is Arabic-Indic for 204
    assert vision._normalize_hex("#B8٢٠٤A") == "#B8204A"


def test_devanagari_digits_round_trip_through_parse():
    payload = {**VALID, "hex": "#B8२०४A"}
    parsed = vision._parse_model_output(json.dumps(payload, ensure_ascii=False))
    assert parsed["hex"] == "#B8204A"


def test_completely_malformed_raises():
    with pytest.raises(vision.VisionError, match="not valid JSON"):
        vision._parse_model_output("the swatch looks teal-ish, sorry")


def test_missing_hex_key_raises():
    payload = {"confidence": "high", "observations": "", "warnings": []}
    with pytest.raises(vision.VisionError):
        vision._parse_model_output(json.dumps(payload))


def test_missing_confidence_key_raises():
    payload = {"hex": "#7ED3B0", "observations": "", "warnings": []}
    with pytest.raises(vision.VisionError):
        vision._parse_model_output(json.dumps(payload))


def test_invalid_confidence_bucket_raises():
    payload = {**VALID, "confidence": "very-high"}
    with pytest.raises(vision.VisionError, match="confidence"):
        vision._parse_model_output(json.dumps(payload))
