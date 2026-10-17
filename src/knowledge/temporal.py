"""Temporal reasoning and validity helpers for RepoBrain knowledge graph.

Provides consistent, unified temporal semantics across all knowledge queries:
- Normalization to strict UTC ISO 8601 formatting.
- Point-in-time `as_of` interval checks for entities and relationships.
- Support for historical `as_of` time travel:
    valid_from <= as_of < valid_to
- Support for tombstoned nodes remaining historically queryable before their tombstone date.
- Strict exclusion of future events (event_time <= as_of).
- Explicit rejection of null/empty/invalid timestamps leaking into comparisons.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def normalize_utc_timestamp(ts: Optional[str]) -> Optional[str]:
    """Normalize any ISO 8601 string to canonical timezone-aware UTC ISO format (YYYY-MM-DDTHH:MM:SSZ).

    Guarantees consistent comparison across UTC and offset timestamps.
    Returns None if timestamp is None, empty, or unparseable.
    """
    if not ts or not isinstance(ts, str):
        return None
    clean_ts = ts.strip()
    if not clean_ts:
        return None
    try:
        dt = datetime.fromisoformat(clean_ts.replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def parse_utc_datetime(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
    norm = normalize_utc_timestamp(ts)
    if not norm:
        return None
    try:
        return datetime.fromisoformat(norm.replace("Z", "+00:00"))
    except Exception:
        return None


def is_timestamp_prior_or_equal(event_ts: Optional[str], as_of: Optional[str]) -> bool:
    """Return True if event_ts is valid, non-empty, and <= as_of.

    If as_of is None, all non-empty timestamps are considered valid (current view).
    If event_ts is None or empty, returns False (does not leak missing timestamps).
    """
    if not event_ts:
        return False
    norm_event = normalize_utc_timestamp(event_ts)
    if not norm_event:
        return False
    if not as_of:
        return True
    norm_as_of = normalize_utc_timestamp(as_of)
    if not norm_as_of:
        return True
    return norm_event <= norm_as_of


def is_edge_active_at(
    valid_from: Optional[str],
    valid_to: Optional[str],
    as_of: Optional[str],
) -> bool:
    """Evaluate whether a relationship is historically active at `as_of`.

    Standard interval semantics:
    valid_from <= as_of < valid_to
    - If valid_from is null: assumed valid from beginning of time.
    - If valid_to is null: currently open (not superseded or closed).
    """
    if not as_of:
        # Current view: only open relationships are active
        return valid_to is None or normalize_utc_timestamp(valid_to) is None

    norm_as_of = normalize_utc_timestamp(as_of)
    if not norm_as_of:
        return valid_to is None or normalize_utc_timestamp(valid_to) is None

    norm_from = normalize_utc_timestamp(valid_from)
    norm_to = normalize_utc_timestamp(valid_to)

    if norm_from and norm_from > norm_as_of:
        return False
    if norm_to and norm_to <= norm_as_of:
        return False
    return True


def is_node_active_at(
    observed_at: Optional[str],
    tombstoned_at: Optional[str],
    as_of: Optional[str],
) -> bool:
    """Evaluate whether a node is historically active and non-tombstoned at `as_of`.

    - Nodes created/observed after as_of are strictly excluded.
    - Nodes tombstoned at or before as_of are excluded from active state.
    - Nodes tombstoned after as_of were still active at as_of.
    """
    if not as_of:
        return tombstoned_at is None or normalize_utc_timestamp(tombstoned_at) is None

    norm_as_of = normalize_utc_timestamp(as_of)
    if not norm_as_of:
        return tombstoned_at is None or normalize_utc_timestamp(tombstoned_at) is None

    norm_observed = normalize_utc_timestamp(observed_at)
    if norm_observed and norm_observed > norm_as_of:
        return False

    norm_tomb = normalize_utc_timestamp(tombstoned_at)
    if norm_tomb and norm_tomb <= norm_as_of:
        return False

    return True


def build_temporal_cypher_filter(
    alias: str,
    timestamp_prop: str = "created_at",
    as_of_param: str = "as_of",
) -> str:
    """Generate Cypher WHERE clauses enforcing non-empty and <= as_of condition."""
    return f"""
    {alias}.{timestamp_prop} IS NOT NULL
    AND {alias}.{timestamp_prop} <> ''
    AND {alias}.{timestamp_prop} <= ${as_of_param}
    """.strip()
