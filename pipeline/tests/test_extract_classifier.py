from __future__ import annotations

import numpy as np

from extract import _classify, _edge_ratio
from extract_algorithmic import extract as algo_extract


def test_uniform_image_is_rendered_swatch():
    rgb = np.full((512, 512, 3), 128, dtype=np.uint8)
    algo = algo_extract(rgb)
    assert _classify(algo, rgb) == "rendered_swatch"


def test_near_uniform_image_is_rendered_swatch():
    rng = np.random.default_rng(seed=0)
    rgb = (
        128 + rng.normal(0, 0.2, (512, 512, 3))
    ).clip(0, 255).astype(np.uint8)
    algo = algo_extract(rgb)
    assert _classify(algo, rgb) == "rendered_swatch"


def test_high_variance_noise_is_photograph():
    rng = np.random.default_rng(seed=0)
    rgb = rng.integers(0, 255, (512, 512, 3), dtype=np.uint8)
    algo = algo_extract(rgb)
    assert _classify(algo, rgb) == "photograph"


def test_woven_texture_synthetic_is_photograph():
    """A low-variance image with edge structure (mimics a smooth fabric photo
    under even lighting — the exact case the edge_ratio signal is here for).
    """
    rng = np.random.default_rng(seed=1)
    base = np.full((512, 512, 3), 128, dtype=np.int32)
    # Striped weave-like luminance wobble at single-pixel scale.
    wobble = (rng.integers(-10, 10, (512, 512, 1)) * np.array([1, 1, 1]))
    rgb = (base + wobble).clip(0, 255).astype(np.uint8)
    algo = algo_extract(rgb)
    assert _classify(algo, rgb) == "photograph"


def test_edge_ratio_zero_for_uniform():
    rgb = np.full((256, 256, 3), 64, dtype=np.uint8)
    assert _edge_ratio(rgb) == 0.0


def test_edge_ratio_high_for_random_noise():
    rng = np.random.default_rng(seed=2)
    rgb = rng.integers(0, 255, (256, 256, 3), dtype=np.uint8)
    assert _edge_ratio(rgb) > 0.5
