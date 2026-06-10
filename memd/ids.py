from __future__ import annotations

import hashlib


def stable_id(*parts: object, prefix: str = "mem") -> str:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
