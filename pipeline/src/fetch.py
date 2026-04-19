"""Download HTML + swatch image for each discovered color into /raw.

Re-running this stage re-downloads but keeps paths stable. The image's
sha256 is computed from the bytes on disk and is the keystone that detects
swapped manufacturer swatch photos.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path
from typing import List, Optional

import requests

from models import DiscoveredColor, FetchedColor, LineConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "raw"

USER_AGENT = (
    "fabric-color-dataset/0.1 "
    "(+https://github.com/karissawhobson/fabric-color-dataset)"
)
REQUEST_TIMEOUT = 30
RETRIES = 2
RETRY_BACKOFF_SECONDS = 2


def fetch(
    config: LineConfig, discovered: List[DiscoveredColor]
) -> List[FetchedColor]:
    line_raw = RAW_DIR / config.manufacturer.slug / config.line.slug
    html_dir = line_raw / "html"
    image_dir = line_raw / "images"
    html_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    today = date.today()
    out: List[FetchedColor] = []
    # Dedupe identical URLs within one run (e.g. manufacturers that expose
    # every color on a single catalog page — same HTML shared by every SKU).
    url_cache: dict[str, bytes] = {}

    def _cached_get(url: str) -> bytes:
        if url not in url_cache:
            url_cache[url] = _get(session, url)
        return url_cache[url]

    for item in discovered:
        html_path = html_dir / f"{item.sku}.html"
        image_path = image_dir / f"{item.sku}.jpg"

        html_bytes = _cached_get(item.product_url)
        html_path.write_bytes(html_bytes)

        image_bytes = _cached_get(item.image_url)
        image_path.write_bytes(image_bytes)
        image_sha = hashlib.sha256(image_bytes).hexdigest()

        out.append(
            FetchedColor(
                sku=item.sku,
                product_url=item.product_url,
                image_url=item.image_url,
                html_path=html_path,
                image_path=image_path,
                image_sha256=image_sha,
                fetched_on=today,
            )
        )
    return out


def _get(session: requests.Session, url: str) -> bytes:
    last: Optional[Exception] = None
    for attempt in range(RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")
