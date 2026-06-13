"""Shared deterministic constants for ingestion + ML pipeline modules.

Pulling these into one module prevents drift between artifact versions and
keeps the seed used by every pipeline run identical.
"""

from __future__ import annotations

# Anchor date in numeric form (YYYYMMDD). Used to seed every deterministic
# random sample, train/holdout split, and synthetic-record generator across
# the pipeline so artifact checksums stay stable across re-runs.
DETERMINISTIC_SEED: int = 20260612

# Default country scope for the subset-first ingestion path. Used as the
# fallback when a CLI is invoked without `--countries`.
DEFAULT_COUNTRIES: tuple[str, ...] = ("SE", "DE", "IE")
