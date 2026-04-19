"""Tests for image_utils.py color-space math and image preprocessing."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import image_utils


# ---------------------------------------------------------------------------
# hex_to_rgb / rgb_to_hex
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hex_str,expected", [
    ("#000000", [0, 0, 0]),
    ("#FFFFFF", [255, 255, 255]),
    ("#FF8040", [255, 128, 64]),
    ("#7ED3B0", [126, 211, 176]),
])
def test_hex_to_rgb_known_values(hex_str, expected):
    result = image_utils.hex_to_rgb(hex_str)
    np.testing.assert_array_equal(result, expected)


@pytest.mark.parametrize("rgb,expected", [
    ([0, 0, 0], "#000000"),
    ([255, 255, 255], "#FFFFFF"),
    ([255, 128, 64], "#FF8040"),
])
def test_rgb_to_hex_known_values(rgb, expected):
    arr = np.array(rgb, dtype=np.uint8)
    assert image_utils.rgb_to_hex(arr) == expected


@pytest.mark.parametrize("hex_str", [
    "#000000", "#FFFFFF", "#7ED3B0", "#FF0000", "#0000FF", "#ABCDEF",
])
def test_hex_round_trip(hex_str):
    assert image_utils.rgb_to_hex(image_utils.hex_to_rgb(hex_str)) == hex_str


# ---------------------------------------------------------------------------
# rgb_to_lab / lab_to_rgb
# ---------------------------------------------------------------------------

def test_black_lab():
    black = np.zeros((1, 1, 3), dtype=np.uint8)
    lab = image_utils.rgb_to_lab(black)[0, 0]
    assert abs(lab[0]) < 0.5   # L ≈ 0
    assert abs(lab[1]) < 0.5   # a ≈ 0
    assert abs(lab[2]) < 0.5   # b ≈ 0


def test_white_lab():
    white = np.full((1, 1, 3), 255, dtype=np.uint8)
    lab = image_utils.rgb_to_lab(white)[0, 0]
    assert abs(lab[0] - 100) < 0.5  # L ≈ 100
    assert abs(lab[1]) < 0.5        # a ≈ 0
    assert abs(lab[2]) < 0.5        # b ≈ 0


def test_rgb_lab_round_trip():
    # A solid patch of an arbitrary color should survive the round-trip
    # within ±1 due to integer rounding.
    original = np.array([[[126, 211, 176]]], dtype=np.uint8)
    lab = image_utils.rgb_to_lab(original)
    recovered = image_utils.lab_to_rgb(lab)
    np.testing.assert_allclose(recovered.astype(int), original.astype(int), atol=1)


def test_rgb_lab_round_trip_all_black():
    original = np.zeros((4, 4, 3), dtype=np.uint8)
    lab = image_utils.rgb_to_lab(original)
    recovered = image_utils.lab_to_rgb(lab)
    np.testing.assert_allclose(recovered.astype(int), original.astype(int), atol=1)


def test_rgb_lab_round_trip_all_white():
    original = np.full((4, 4, 3), 255, dtype=np.uint8)
    lab = image_utils.rgb_to_lab(original)
    recovered = image_utils.lab_to_rgb(lab)
    np.testing.assert_allclose(recovered.astype(int), original.astype(int), atol=1)


# ---------------------------------------------------------------------------
# delta_e_76
# ---------------------------------------------------------------------------

def test_delta_e_identical_colors():
    assert image_utils.delta_e_76("#7ED3B0", "#7ED3B0") == pytest.approx(0.0, abs=1e-6)


def test_delta_e_black_white():
    # L* goes 0→100, so ΔE76 ≈ 100
    de = image_utils.delta_e_76("#000000", "#FFFFFF")
    assert de == pytest.approx(100.0, abs=1.0)


def test_delta_e_symmetry():
    a, b = "#7ED3B0", "#7BD1AE"
    assert image_utils.delta_e_76(a, b) == pytest.approx(
        image_utils.delta_e_76(b, a), abs=1e-9
    )


def test_delta_e_high_confidence_threshold():
    # The two hex values from the kona-cotton test fixture are very close.
    # ΔE < 3 → would bucket as "high" confidence.
    de = image_utils.delta_e_76("#7ED3B0", "#7BD1AE")
    assert de < 3.0


def test_delta_e_low_confidence_threshold():
    # Black vs bright red are clearly different — should exceed the low-
    # confidence threshold of ΔE ≥ 7.
    de = image_utils.delta_e_76("#000000", "#FF0000")
    assert de >= 7.0


def test_delta_e_nonnegative():
    de = image_utils.delta_e_76("#123456", "#654321")
    assert de >= 0.0


# ---------------------------------------------------------------------------
# load_and_preprocess
# ---------------------------------------------------------------------------

def test_load_and_preprocess_solid_color(tmp_path):
    color = (126, 211, 176)
    img = Image.new("RGB", (800, 600), color=color)
    path = tmp_path / "swatch.jpg"
    img.save(path, format="JPEG", quality=95)

    result = image_utils.load_and_preprocess(path)

    assert result.ndim == 3
    assert result.shape[2] == 3
    assert result.dtype == np.uint8
    # Long edge should be ≤ 512 after downscaling
    assert max(result.shape[:2]) <= 512
    # Center crop of a solid-color image: mean should be close to the original
    # (JPEG encoding introduces slight loss, so allow ±10)
    np.testing.assert_allclose(result.mean(axis=(0, 1)), color, atol=10)


def test_load_and_preprocess_already_small(tmp_path):
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    path = tmp_path / "small.jpg"
    img.save(path, format="JPEG", quality=95)

    result = image_utils.load_and_preprocess(path)
    # Image is smaller than 512px — downscale should not upscale
    assert max(result.shape[:2]) <= 100


def test_load_and_preprocess_returns_uint8(tmp_path):
    img = Image.new("RGB", (300, 400), color=(10, 20, 30))
    path = tmp_path / "swatch.png"
    img.save(path, format="PNG")

    result = image_utils.load_and_preprocess(path)
    assert result.dtype == np.uint8


# ---------------------------------------------------------------------------
# encode_jpeg
# ---------------------------------------------------------------------------

def test_encode_jpeg_produces_valid_jpeg():
    arr = np.full((64, 64, 3), 128, dtype=np.uint8)
    data = image_utils.encode_jpeg(arr)
    # JPEG magic bytes: FF D8 FF
    assert data[:3] == b"\xff\xd8\xff"


def test_encode_jpeg_is_decodable():
    arr = np.full((64, 64, 3), 200, dtype=np.uint8)
    data = image_utils.encode_jpeg(arr)
    img = Image.open(io.BytesIO(data))
    assert img.mode == "RGB"
    assert img.size == (64, 64)
