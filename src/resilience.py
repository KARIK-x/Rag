"""
LOCUS RAG Resilience Primitives — Phase 14.

Reusable resilience helpers wired into the pipeline:

1. ``retry_with_backoff`` — bounded exponential-backoff retry for a single
   operation. Retries ONLY failures classified as transient by
   ``is_transient_error``; permanent errors (auth, permission, unsupported,
   catalog-missing) fail immediately.
2. ``safe_subpath`` — construct a path under a base directory, rejecting
   traversal (``..``/absolute). Used for downloaded and extracted file paths
   derived from Drive file IDs.
3. ``assert_not_in_locus_drive`` — enforce the /Users/ashim/locus_drive
   READ-ONLY boundary in code before any write occurs.

Small, tested primitives only — no circuit breakers, health monitors, or
other generic machinery beyond what the pipeline needs.
"""

import logging
import random
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# The authoritative Drive catalog + sync directory. NEVER written to.
LOCUS_DRIVE_DIR = Path("/Users/ashim/locus_drive")


# ─── Transient-failure classification ─────────────────────────────────────────

# Google API / network surface error fragments that indicate a retryable
# transient condition. Permanent errors (auth, permission, 404, unsupported)
# must NOT be retried.
_TRANSIENT_FRAGMENTS = (
    "connection", "connect", "reset", "timeout", "timed out",
    "temporary", "try again", "retry", "rate limit", "quota",
    "502", "503", "429", "service unavailable", "unavailable",
    "socket", "ssl", "dns", "interrupt", "econnreset", "econnrefused",
)


def is_transient_error(exc: BaseException) -> bool:
    """Classify an exception (and its ``__cause__`` chain) as transient.

    ``IngestionError`` collapses all download failures into one wrapper whose
    only signal is the message text, so we classify on the message of the
    exception AND its chained original error. Auth/permission/404 signals
    force permanent (never retried).
    """
    if not exc:
        return False
    messages = []
    cur: BaseException | None = exc
    while cur is not None:
        messages.append(str(cur).lower())
        cur = cur.__cause__

    # Permanent signals take precedence — never retry these.
    permanent_fragments = (
        "permission", "auth", "forbidden", "denied", "credentials",
        "not found", "404", "unsupported", "invalid", "does not exist",
        "not permitted", "unauthorized", "403",
    )
    for m in messages:
        if any(p in m for p in permanent_fragments):
            return False

    for m in messages:
        if any(f in m for f in _TRANSIENT_FRAGMENTS):
            return True
    return False


# ─── Bounded retry with exponential backoff ───────────────────────────────────

def retry_with_backoff(
    fn: Callable[[], Any],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.1,
    retryable: Callable[..., bool] = is_transient_error,
) -> Any:
    """Run ``fn`` with bounded exponential-backoff retry.

    - Only ``retryable(exc)`` failures are retried (default: transient only).
    - ``attempts`` is the TOTAL number of tries (1 initial + attempts-1 retries).
    - Delay: ``base_delay * 2**attempt`` capped at ``max_delay``, plus jitter.
    - On final failure, re-raises the last exception unchanged.
    - Never sleeps on a permanent error.

    Returns the value of ``fn()`` on success.
    """
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            if attempt >= attempts or not retryable(exc):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter_amount = delay * jitter * random.uniform(0, 1)
            logger.warning(
                "Transient failure on attempt %d/%d (%s); retrying in %.2fs",
                attempt, attempts, exc, delay + jitter_amount,
            )
            time.sleep(delay + jitter_amount)


# ─── Safe path construction ───────────────────────────────────────────────────

class UnsafePathError(ValueError):
    """Raised when constructing a path escapes its intended base directory."""


def safe_subpath(base_dir: Path, *components: str) -> Path:
    """Join ``components`` under ``base_dir`` and verify containment.

    Raises ``UnsafePathError`` if the result resolves outside ``base_dir``
    (e.g. a ``drive_file_id`` containing ``../`` or an absolute path).
    """
    base = base_dir.resolve()
    candidate = base.joinpath(*components)
    resolved = candidate.resolve(strict=False)
    if resolved != base and base not in resolved.parents:
        raise UnsafePathError(f"Path resolves outside base directory {base}: {candidate}")
    return resolved


# ─── Drive READ-ONLY boundary ─────────────────────────────────────────────────

class LocusDriveWriteError(ValueError):
    """Raised when a code path attempts to write inside /Users/ashim/locus_drive."""


def assert_not_in_locus_drive(path: Path) -> None:
    """Refuse any resolved path that falls under /Users/ashim/locus_drive.

    Enforces the READ-ONLY Drive boundary in code before any write.
    """
    resolved = path.resolve()
    if resolved == LOCUS_DRIVE_DIR or LOCUS_DRIVE_DIR in resolved.parents:
        raise LocusDriveWriteError(
            f"Refusing write inside read-only {LOCUS_DRIVE_DIR}: {resolved}"
        )


__all__ = [
    "is_transient_error",
    "retry_with_backoff",
    "safe_subpath",
    "UnsafePathError",
    "assert_not_in_locus_drive",
    "LocusDriveWriteError",
]
