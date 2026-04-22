"""Claude vision extraction with content-addressable caching.

Cache key = sha256(image_bytes) + sha256(prompt_file). Editing the prompt
means creating `hex_extraction_v2.md` alongside v1; the cache key changes
automatically and everything re-extracts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

import anthropic

from models import VisionResult

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "pipeline" / "prompts"
PROMPT_FILE = PROMPTS_DIR / "hex_extraction_v1.md"
PROMPT_VERSION = "v1"

CACHE_DIR = Path.home() / ".cache" / "fabric-color-dataset" / "vision"

# The most capable currently-available Claude vision model. Bump as newer
# models ship; the prompt file's version is the stable identifier.
MODEL = "claude-opus-4-7"

HEX_RE = re.compile(r"^#[0-9A-F]{6}$")


class VisionError(Exception):
    pass


def extract(image_jpeg: bytes) -> VisionResult:
    """Call Claude vision for a single preprocessed JPEG. Cached by content."""
    key = _cache_key(image_jpeg)
    cached = _cache_load(key)
    if cached is not None:
        return _from_json(cached)

    client = _client()
    prompt = _load_prompt()
    encoded = base64.standard_b64encode(image_jpeg).decode("ascii")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except (anthropic.NotFoundError, anthropic.BadRequestError) as exc:
        if _is_model_error(exc):
            raise VisionError(
                f"Claude API rejected model {MODEL!r} "
                f"({type(exc).__name__}: {exc}). The model may have been "
                f"deprecated or retired. Update MODEL in "
                f"pipeline/src/vision.py to a current Claude vision model "
                f"and re-run."
            ) from exc
        raise

    text = _text_from_response(response)
    parsed = _parse_model_output(text)
    _cache_store(key, parsed)
    return _from_json(parsed)


def _is_model_error(exc: Exception) -> bool:
    # Anthropic returns 400 for a retired/unknown model and 404 for some
    # variants; both surface the word "model" in the message. Keep the
    # translation narrow so unrelated 400s (e.g. malformed image) bubble up.
    return "model" in str(exc).lower()


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise VisionError(
            "ANTHROPIC_API_KEY is not set; vision extraction needs it. "
            "Export the key or run only the non-vision stages."
        )
    return anthropic.Anthropic()


@lru_cache(maxsize=1)
def _load_prompt() -> str:
    return PROMPT_FILE.read_text()


@lru_cache(maxsize=1)
def _prompt_hash() -> str:
    return hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest()


def _cache_key(image_jpeg: bytes) -> str:
    image_hash = hashlib.sha256(image_jpeg).hexdigest()
    return f"{image_hash}_{PROMPT_VERSION}_{_prompt_hash()[:16]}"


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _cache_load(key: str) -> Optional[dict]:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _cache_store(key: str, parsed: dict) -> None:
    _cache_path(key).write_text(json.dumps(parsed, indent=2))


def _text_from_response(response) -> str:
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise VisionError("vision response had no text block")


def _parse_model_output(text: str) -> dict:
    # The model usually returns a single JSON object, but sometimes prefixes
    # it with a false start ("#21A css" etc.) and then emits the real answer
    # in a fenced ```json block. Try the raw text first, then each fenced
    # block (last first — that's the settled answer).
    obj = _first_parseable_json(text)
    if obj is None:
        raise VisionError(f"vision output was not valid JSON: {text!r}")

    hex_value = obj.get("hex")
    if isinstance(hex_value, str):
        hex_value = _normalize_hex(hex_value)
    if not isinstance(hex_value, str) or not HEX_RE.match(hex_value):
        raise VisionError(f"vision hex {hex_value!r} is not #RRGGBB uppercase")

    confidence = obj.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        raise VisionError(f"vision confidence {confidence!r} is not a known bucket")

    warnings = obj.get("warnings", [])
    if not isinstance(warnings, list) or not all(
        isinstance(w, str) for w in warnings
    ):
        raise VisionError(f"vision warnings must be a list of strings, got {warnings!r}")

    observations = obj.get("observations", "")
    if not isinstance(observations, str):
        raise VisionError(f"vision observations must be a string, got {observations!r}")

    return {
        "hex": hex_value,
        "confidence": confidence,
        "observations": observations,
        "warnings": warnings,
    }


_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _normalize_hex(value: str) -> str:
    # The model occasionally emits non-ASCII decimal digits inside the hex
    # (e.g. Devanagari २०४ for 204). Fold them back to ASCII so the regex
    # check doesn't reject an otherwise-correct color.
    out = []
    for ch in value.strip():
        if not ch.isascii() and ch.isdigit():
            try:
                out.append(str(unicodedata.decimal(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out).upper()


def _first_parseable_json(text: str) -> Optional[dict]:
    candidates: list[str] = []
    raw = text.strip()
    if raw:
        candidates.append(raw)
    fenced = [m.group(1).strip() for m in _FENCE_RE.finditer(text)]
    # Prefer later fenced blocks — if the model retried inline, the last
    # block is the answer it settled on.
    candidates.extend(reversed(fenced))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "hex" in obj and "confidence" in obj:
            return obj
    return None


def _from_json(obj: dict) -> VisionResult:
    return VisionResult(
        hex=obj["hex"],
        confidence=obj["confidence"],
        observations=obj["observations"],
        warnings=list(obj["warnings"]),
    )
