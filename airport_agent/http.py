"""Shared HTTP session.

Uses the OS certificate store (via truststore) so requests also work behind corporate TLS
inspection proxies, without disabling certificate verification.
"""
from pathlib import Path

import requests
import truststore

truststore.inject_into_ssl()

_session = requests.Session()
_session.headers["User-Agent"] = "airport-investment-agent/0.1"


def get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 60)
    resp = _session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def download(url: str, dest: Path) -> Path:
    """Stream a file to disk (atomic: writes a .part file first)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    with _session.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(part, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    part.replace(dest)
    return dest
