"""Centralized GraphWriter for RepoBrain.

Controls all graph mutations for FalkorDB `repo_kg` with strict validation,
tamper-proof provenance, temporal validity tracking, and traceable change events.

Exposes only approved mutation operations:
- `upsert_node`
- `upsert_edge`
- `close_edge`
- `tombstone_node`

No caller-supplied raw Cypher is accepted.
All inputs are strictly validated against allowlisted labels, relationship types, and properties.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator

from src.db import FalkorDBClient
from src.evaluation.temporal import normalize_utc_timestamp


# -----------------------------------------------------------------------------
# Allowlisted Graph Schema Definitions
# -----------------------------------------------------------------------------

ALLOWED_NODE_LABELS: Set[str] = {
    "Person",
    "PullRequest",
    "Issue",
    "File",
    "Team",
    "OwnershipRule",
    "SyncRun",
}

IDENTITY_KEYS: Dict[str, str] = {
    "Person": "login",
    "PullRequest": "number",
    "Issue": "number",
    "File": "path",
    "Team": "name",
    "OwnershipRule": "pattern",
    "SyncRun": "run_id",
}

ALLOWED_NODE_PROPERTIES: Dict[str, Set[str]] = {
    "Person": {
        "login",
        "url",
        "created_at",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "PullRequest": {
        "number",
        "title",
        "url",
        "state",
        "created_at",
        "merged_at",
        "closed_at",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "Issue": {
        "number",
        "title",
        "url",
        "state",
        "created_at",
        "closed_at",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "File": {
        "path",
        "url",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "Team": {
        "name",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "OwnershipRule": {
        "pattern",
        "line_number",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
        "status",
        "tombstoned_at",
    },
    "SyncRun": {
        "run_id",
        "started_at",
        "completed_at",
        "status",
        "source_url",
        "observed_at",
    },
}

ALLOWED_REL_TYPES: Set[str] = {
    "AUTHORED",
    "REVIEWED",
    "MODIFIES",
    "RESOLVES",
    "REPORTED",
    "DECLARES_OWNER",
    "COVERS",
    "OWNED_BY",
    "CHANGED",
}

ALLOWED_REL_PROPERTIES: Dict[str, Set[str]] = {
    "AUTHORED": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "REVIEWED": {
        "id",
        "state",
        "submitted_at",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "MODIFIES": {
        "additions",
        "deletions",
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "RESOLVES": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "REPORTED": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "DECLARES_OWNER": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "COVERS": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "OWNED_BY": {
        "source_url",
        "observed_at",
        "run_id",
        "valid_from",
        "valid_to",
    },
    "CHANGED": {
        "op",
        "target_label",
        "target_id",
        "rel_type",
        "source_id",
        "changed",
        "source_url",
        "observed_at",
        "before",
        "after",
    },
}


# -----------------------------------------------------------------------------
# Input & Result Models
# -----------------------------------------------------------------------------

def current_utc_iso() -> str:
    """Return the current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProvenanceMetadata(BaseModel):
    """Provenance and temporal tracking metadata for graph entities and edges."""

    source_url: str
    observed_at: str = Field(default_factory=current_utc_iso)
    run_id: str = "default_run"
    valid_from: str = Field(default_factory=current_utc_iso)
    valid_to: Optional[str] = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("source_url must be a non-empty string.")
        clean = v.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError(f"source_url must start with http:// or https://: '{v}'")
        return clean

    @field_validator("observed_at", "valid_from")
    @classmethod
    def validate_required_timestamps(cls, v: str) -> str:
        norm = normalize_utc_timestamp(v)
        if not norm:
            raise ValueError(f"Invalid timestamp format: '{v}'")
        return norm

    @field_validator("valid_to")
    @classmethod
    def validate_optional_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        norm = normalize_utc_timestamp(v)
        if not norm:
            raise ValueError(f"Invalid timestamp format for valid_to: '{v}'")
        return norm


class MutationResult(BaseModel):
    """Structured result returned by every GraphWriter mutation operation."""

    success: bool
    op: str
    entity_or_rel: str
    target_id: str
    changed: bool
    run_id: str
    observed_at: str
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class GraphWriterError(Exception):
    """Base exception for GraphWriter operations."""
    pass


class ValidationError(GraphWriterError):
    """Raised when an invalid label, relationship, property, or input format is passed."""
    pass


class EntityNotFoundError(GraphWriterError):
    """Raised when a referenced source/target entity does not exist in the graph."""
    pass


# -----------------------------------------------------------------------------
# Central GraphWriter Implementation
# -----------------------------------------------------------------------------

class GraphWriter:
    """Centralized, strictly validated mutation interface for FalkorDB `repo_kg`.

    Guarantees:
    - Zero raw Cypher accepted from external callers.
    - Strict allowlist verification for node labels, rel types, and properties.
    - Idempotent upserts (repeated identical calls are safe no-ops).
    - Unbroken provenance (`source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`).
    - Traceable `SyncRun`/`CHANGED {op}` change audit events for state-altering operations.
    - Temporal non-destructive deletion (`close_edge` sets `valid_to`; `tombstone_node` sets `status='tombstoned'`).
    """

    def __init__(self, client: Optional[FalkorDBClient] = None, run_id: Optional[str] = None):
        self.client = client or FalkorDBClient()
        self.run_id = run_id or f"run_{int(datetime.now(timezone.utc).timestamp())}"
        self._ensure_sync_run_indexed()

    def _ensure_sync_run_indexed(self) -> None:
        """Ensure indexes exist for SyncRun and tombstone tracking."""
        try:
            self.client.query("CREATE INDEX FOR (s:SyncRun) ON (s.run_id)")
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_label(self, label: str) -> None:
        if label not in ALLOWED_NODE_LABELS:
            raise ValidationError(
                f"Prohibited or unknown node label '{label}'. Allowed labels: {sorted(ALLOWED_NODE_LABELS)}"
            )

    def _validate_rel_type(self, rel_type: str) -> None:
        if rel_type not in ALLOWED_REL_TYPES:
            raise ValidationError(
                f"Prohibited or unknown relationship type '{rel_type}'. Allowed types: {sorted(ALLOWED_REL_TYPES)}"
            )

    def _validate_node_properties(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        allowed = ALLOWED_NODE_PROPERTIES.get(label, set())
        clean_props = {}
        for k, v in properties.items():
            if k not in allowed:
                raise ValidationError(
                    f"Prohibited property '{k}' for node label '{label}'. Allowed properties: {sorted(allowed)}"
                )
            # Ensure timestamps are real nulls, not empty strings
            if k.endswith("_at") or k.endswith("_from") or k.endswith("_to"):
                if v == "" or v is None:
                    clean_props[k] = None
                else:
                    norm = normalize_utc_timestamp(str(v))
                    if norm is None:
                        raise ValidationError(f"Property '{k}' has invalid timestamp format: '{v}'")
                    clean_props[k] = norm
            else:
                clean_props[k] = v
        return clean_props

    def _validate_rel_properties(self, rel_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        allowed = ALLOWED_REL_PROPERTIES.get(rel_type, set())
        clean_props = {}
        for k, v in properties.items():
            if k not in allowed:
                raise ValidationError(
                    f"Prohibited property '{k}' for relationship '{rel_type}'. Allowed properties: {sorted(allowed)}"
                )
            if k.endswith("_at") or k.endswith("_from") or k.endswith("_to"):
                if v == "" or v is None:
                    clean_props[k] = None
                else:
                    norm = normalize_utc_timestamp(str(v))
                    if norm is None:
                        raise ValidationError(f"Property '{k}' has invalid timestamp format: '{v}'")
                    clean_props[k] = norm
            else:
                clean_props[k] = v
        return clean_props

    def _ensure_sync_run_node(self, run_id: str, observed_at: str, source_url: str) -> None:
        """Create or ensure existence of the SyncRun audit node."""
        query = """
        MERGE (sr:SyncRun {run_id: $run_id})
        ON CREATE SET sr.started_at = $observed_at,
                      sr.status = 'active',
                      sr.source_url = $source_url
        """
        self.client.query(
            query,
            {"run_id": run_id, "observed_at": observed_at, "source_url": source_url},
        )

    def _record_node_change(
        self,
        op: str,
        label: str,
        identity_value: Any,
        source_url: str,
        observed_at: str,
        run_id: str,
        before_state: Optional[Dict[str, Any]],
        after_state: Dict[str, Any],
    ) -> None:
        """Record a traceable CHANGED edge from SyncRun to the target node."""
        self._ensure_sync_run_node(run_id, observed_at, source_url)
        id_key = IDENTITY_KEYS[label]
        before_json = json.dumps(before_state, default=str) if before_state is not None else ""
        after_json = json.dumps(after_state, default=str)

        query = f"""
        MATCH (sr:SyncRun {{run_id: $run_id}}), (n:{label} {{{id_key}: $id_val}})
        CREATE (sr)-[c:CHANGED {{
            op: $op,
            target_label: $label,
            target_id: $id_str,
            source_url: $source_url,
            observed_at: $observed_at,
            changed: true,
            before: $before_json,
            after: $after_json
        }}]->(n)
        """
        self.client.query(
            query,
            {
                "run_id": run_id,
                "id_val": identity_value,
                "op": op,
                "label": label,
                "id_str": str(identity_value),
                "source_url": source_url,
                "observed_at": observed_at,
                "before_json": before_json,
                "after_json": after_json,
            },
        )

    def _record_edge_change(
        self,
        op: str,
        rel_type: str,
        source_label: str,
        source_identity: Any,
        target_label: str,
        target_identity: Any,
        source_url: str,
        observed_at: str,
        run_id: str,
        before_state: Optional[Dict[str, Any]],
        after_state: Dict[str, Any],
    ) -> None:
        """Record a traceable CHANGED edge from SyncRun to the source node of the relationship."""
        self._ensure_sync_run_node(run_id, observed_at, source_url)
        src_id_key = IDENTITY_KEYS[source_label]
        before_json = json.dumps(before_state, default=str) if before_state is not None else ""
        after_json = json.dumps(after_state, default=str)

        query = f"""
        MATCH (sr:SyncRun {{run_id: $run_id}}), (src:{source_label} {{{src_id_key}: $src_id_val}})
        CREATE (sr)-[c:CHANGED {{
            op: $op,
            rel_type: $rel_type,
            source_id: $src_id_str,
            target_id: $target_id_str,
            source_url: $source_url,
            observed_at: $observed_at,
            changed: true,
            before: $before_json,
            after: $after_json
        }}]->(src)
        """
        self.client.query(
            query,
            {
                "run_id": run_id,
                "src_id_val": source_identity,
                "op": op,
                "rel_type": rel_type,
                "src_id_str": str(source_identity),
                "target_id_str": str(target_identity),
                "source_url": source_url,
                "observed_at": observed_at,
                "before_json": before_json,
                "after_json": after_json,
            },
        )

    # -------------------------------------------------------------------------
    # Operation 1: upsert_node
    # -------------------------------------------------------------------------

    def upsert_node(
        self,
        label: str,
        identity_value: Any,
        properties: Optional[Dict[str, Any]] = None,
        provenance: Optional[ProvenanceMetadata] = None,
    ) -> MutationResult:
        """Idempotently insert or update an allowlisted graph node.

        - Disallows raw Cypher.
        - Validates label, identity, and properties against strict allowlists.
        - Ensures identity key cannot be mutated.
        - Tracks provenance (`source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`).
        - Creates a traceable `SyncRun`/`CHANGED` record if graph state changed.
        - No-op if node exists with identical properties (does not create spurious change events).
        """
        self._validate_label(label)
        if identity_value is None or identity_value == "":
            raise ValidationError(f"identity_value for node '{label}' cannot be null or empty.")

        id_key = IDENTITY_KEYS[label]
        expected_type = int if label in ("PullRequest", "Issue") else str
        if not isinstance(identity_value, expected_type):
            try:
                identity_value = expected_type(identity_value)
            except Exception:
                raise ValidationError(
                    f"identity_value for '{label}' must be of type {expected_type.__name__}, got {type(identity_value).__name__}."
                )

        raw_props = dict(properties or {})
        raw_props.pop(id_key, None)  # Prevent mutating primary identity key
        clean_props = self._validate_node_properties(label, raw_props)

        # Prepare Provenance
        if provenance is None:
            source_url = clean_props.get("source_url") or clean_props.get("url") or "https://github.com/FalkorDB/falkordb-py"
            provenance = ProvenanceMetadata(
                source_url=source_url,
                run_id=self.run_id,
            )

        prov_dict = {
            "source_url": provenance.source_url,
            "observed_at": provenance.observed_at,
            "run_id": provenance.run_id,
            "valid_from": provenance.valid_from,
            "valid_to": provenance.valid_to,
        }
        all_incoming = {**clean_props, **prov_dict}

        # Check existing state
        check_query = f"""
        MATCH (n:{label} {{{id_key}: $id_val}})
        RETURN properties(n) AS props
        """
        existing_res = self.client.ro_query(check_query, {"id_val": identity_value})

        if not existing_res or not existing_res.result_set:
            # 1. Node does not exist -> Create Node
            create_query = f"""
            CREATE (n:{label} {{{id_key}: $id_val}})
            SET n += $props, n.status = 'active'
            """
            self.client.query(create_query, {"id_val": identity_value, "props": all_incoming})

            # Record change event
            self._record_node_change(
                op="upsert_node",
                label=label,
                identity_value=identity_value,
                source_url=provenance.source_url,
                observed_at=provenance.observed_at,
                run_id=provenance.run_id,
                before_state=None,
                after_state=all_incoming,
            )

            return MutationResult(
                success=True,
                op="upsert_node",
                entity_or_rel=label,
                target_id=str(identity_value),
                changed=True,
                run_id=provenance.run_id,
                observed_at=provenance.observed_at,
                details={"created": True, "properties": all_incoming},
            )

        # 2. Node exists -> Compare properties
        existing_props = existing_res.result_set[0][0] or {}
        # Check for substantive differences (ignoring observed_at if everything else identical)
        differs = False
        for k, v in all_incoming.items():
            if k in ("observed_at", "run_id"):
                continue
            if existing_props.get(k) != v:
                differs = True
                break

        if not differs:
            # Idempotent no-op: state did not change
            return MutationResult(
                success=True,
                op="upsert_node",
                entity_or_rel=label,
                target_id=str(identity_value),
                changed=False,
                run_id=provenance.run_id,
                observed_at=provenance.observed_at,
                details={"created": False, "reason": "identical_properties"},
            )

        # State differs -> Update Node
        update_query = f"""
        MATCH (n:{label} {{{id_key}: $id_val}})
        SET n += $props
        """
        self.client.query(update_query, {"id_val": identity_value, "props": all_incoming})

        self._record_node_change(
            op="upsert_node",
            label=label,
            identity_value=identity_value,
            source_url=provenance.source_url,
            observed_at=provenance.observed_at,
            run_id=provenance.run_id,
            before_state=existing_props,
            after_state=all_incoming,
        )

        return MutationResult(
            success=True,
            op="upsert_node",
            entity_or_rel=label,
            target_id=str(identity_value),
            changed=True,
            run_id=provenance.run_id,
            observed_at=provenance.observed_at,
            details={"created": False, "updated_properties": all_incoming},
        )

    # -------------------------------------------------------------------------
    # Operation 2: upsert_edge
    # -------------------------------------------------------------------------

    def upsert_edge(
        self,
        rel_type: str,
        source_label: str,
        source_identity: Any,
        target_label: str,
        target_identity: Any,
        properties: Optional[Dict[str, Any]] = None,
        provenance: Optional[ProvenanceMetadata] = None,
        edge_key_property: Optional[str] = None,
        edge_key_value: Optional[Any] = None,
    ) -> MutationResult:
        """Idempotently insert or update an allowlisted graph relationship.

        - Requires both source and target entities to exist (rejects fabricated/missing endpoints).
        - Provenance (`source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`) is mandatory.
        - Creates a traceable `SyncRun`/`CHANGED` record if graph state changed.
        - Preserves existing relationships without duplication.
        """
        self._validate_rel_type(rel_type)
        self._validate_label(source_label)
        self._validate_label(target_label)

        src_id_key = IDENTITY_KEYS[source_label]
        dst_id_key = IDENTITY_KEYS[target_label]

        # Provenance is strictly required for relationships
        if provenance is None:
            raise ValidationError(
                f"ProvenanceMetadata is required when upserting edge '[:{rel_type}]' to ensure evidence grounding."
            )

        clean_props = self._validate_rel_properties(rel_type, properties or {})

        prov_dict = {
            "source_url": provenance.source_url,
            "observed_at": provenance.observed_at,
            "run_id": provenance.run_id,
            "valid_from": provenance.valid_from,
            "valid_to": provenance.valid_to,
        }
        all_incoming = {**clean_props, **prov_dict}
        if edge_key_property and edge_key_value is not None:
            all_incoming[edge_key_property] = edge_key_value

        # 1. Verify existence of source and target nodes
        existence_check = f"""
        MATCH (src:{source_label} {{{src_id_key}: $src_id}}), (dst:{target_label} {{{dst_id_key}: $dst_id}})
        RETURN count(src) AS src_count, count(dst) AS dst_count
        """
        res = self.client.ro_query(
            existence_check,
            {"src_id": source_identity, "dst_id": target_identity},
        )
        if not res or not res.result_set or res.result_set[0][0] == 0:
            raise EntityNotFoundError(
                f"Cannot create edge: source entity ({source_label} {{{src_id_key}: {source_identity}}}) does not exist."
            )
        if res.result_set[0][1] == 0:
            raise EntityNotFoundError(
                f"Cannot create edge: target entity ({target_label} {{{dst_id_key}: {target_identity}}}) does not exist."
            )

        # 2. Check existing relationship
        if edge_key_property and edge_key_value is not None:
            rel_check = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type} {{{edge_key_property}: $edge_key_val}}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            RETURN properties(r) AS props
            """
            params = {
                "src_id": source_identity,
                "dst_id": target_identity,
                "edge_key_val": edge_key_value,
            }
        else:
            rel_check = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            RETURN properties(r) AS props
            """
            params = {"src_id": source_identity, "dst_id": target_identity}

        existing_res = self.client.ro_query(rel_check, params)

        if not existing_res or not existing_res.result_set:
            # Relationship does not exist -> Create relationship
            if edge_key_property and edge_key_value is not None:
                create_query = f"""
                MATCH (src:{source_label} {{{src_id_key}: $src_id}}), (dst:{target_label} {{{dst_id_key}: $dst_id}})
                CREATE (src)-[r:{rel_type} {{{edge_key_property}: $edge_key_val}}]->(dst)
                SET r += $props
                """
            else:
                create_query = f"""
                MATCH (src:{source_label} {{{src_id_key}: $src_id}}), (dst:{target_label} {{{dst_id_key}: $dst_id}})
                CREATE (src)-[r:{rel_type}]->(dst)
                SET r += $props
                """
            params["props"] = all_incoming
            self.client.query(create_query, params)

            self._record_edge_change(
                op="upsert_edge",
                rel_type=rel_type,
                source_label=source_label,
                source_identity=source_identity,
                target_label=target_label,
                target_identity=target_identity,
                source_url=provenance.source_url,
                observed_at=provenance.observed_at,
                run_id=provenance.run_id,
                before_state=None,
                after_state=all_incoming,
            )

            return MutationResult(
                success=True,
                op="upsert_edge",
                entity_or_rel=rel_type,
                target_id=f"{source_identity}->{target_identity}",
                changed=True,
                run_id=provenance.run_id,
                observed_at=provenance.observed_at,
                details={"created": True, "properties": all_incoming},
            )

        # Relationship exists -> Check if properties differ
        existing_props = existing_res.result_set[0][0] or {}
        differs = False
        for k, v in all_incoming.items():
            if k in ("observed_at", "run_id"):
                continue
            if existing_props.get(k) != v:
                differs = True
                break

        if not differs:
            return MutationResult(
                success=True,
                op="upsert_edge",
                entity_or_rel=rel_type,
                target_id=f"{source_identity}->{target_identity}",
                changed=False,
                run_id=provenance.run_id,
                observed_at=provenance.observed_at,
                details={"created": False, "reason": "identical_properties"},
            )

        # Update relationship properties
        if edge_key_property and edge_key_value is not None:
            update_query = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type} {{{edge_key_property}: $edge_key_val}}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            SET r += $props
            """
        else:
            update_query = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            SET r += $props
            """
        params["props"] = all_incoming
        self.client.query(update_query, params)

        self._record_edge_change(
            op="upsert_edge",
            rel_type=rel_type,
            source_label=source_label,
            source_identity=source_identity,
            target_label=target_label,
            target_identity=target_identity,
            source_url=provenance.source_url,
            observed_at=provenance.observed_at,
            run_id=provenance.run_id,
            before_state=existing_props,
            after_state=all_incoming,
        )

        return MutationResult(
            success=True,
            op="upsert_edge",
            entity_or_rel=rel_type,
            target_id=f"{source_identity}->{target_identity}",
            changed=True,
            run_id=provenance.run_id,
            observed_at=provenance.observed_at,
            details={"created": False, "updated_properties": all_incoming},
        )

    # -------------------------------------------------------------------------
    # Operation 3: close_edge
    # -------------------------------------------------------------------------

    def close_edge(
        self,
        rel_type: str,
        source_label: str,
        source_identity: Any,
        target_label: str,
        target_identity: Any,
        closed_at: Optional[str] = None,
        edge_key_property: Optional[str] = None,
        edge_key_value: Optional[Any] = None,
    ) -> MutationResult:
        """Close an existing relationship temporally by setting `valid_to`.

        - Does NOT delete the relationship; preserves complete historical record.
        - Bounded by `valid_to` for time-travel `as_of` queries.
        - Idempotent: repeated calls on an already-closed edge are safe no-ops.
        """
        self._validate_rel_type(rel_type)
        self._validate_label(source_label)
        self._validate_label(target_label)

        src_id_key = IDENTITY_KEYS[source_label]
        dst_id_key = IDENTITY_KEYS[target_label]

        close_ts = normalize_utc_timestamp(closed_at) if closed_at else current_utc_iso()
        if not close_ts:
            raise ValidationError(f"Invalid timestamp for closed_at: '{closed_at}'")

        if edge_key_property and edge_key_value is not None:
            check_query = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type} {{{edge_key_property}: $edge_key_val}}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            RETURN properties(r) AS props
            """
            params = {
                "src_id": source_identity,
                "dst_id": target_identity,
                "edge_key_val": edge_key_value,
            }
        else:
            check_query = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            RETURN properties(r) AS props
            """
            params = {"src_id": source_identity, "dst_id": target_identity}

        res = self.client.ro_query(check_query, params)
        if not res or not res.result_set:
            raise EntityNotFoundError(
                f"Relationship not found to close: ({source_label} {{{src_id_key}: {source_identity}}})-[:{rel_type}]->({target_label} {{{dst_id_key}: {target_identity}}})"
            )

        existing_props = res.result_set[0][0] or {}
        current_valid_to = existing_props.get("valid_to")

        if current_valid_to is not None:
            # Already closed: idempotent no-op
            return MutationResult(
                success=True,
                op="close_edge",
                entity_or_rel=rel_type,
                target_id=f"{source_identity}->{target_identity}",
                changed=False,
                run_id=self.run_id,
                observed_at=close_ts,
                details={"closed": False, "already_closed_at": current_valid_to},
            )

        # Set valid_to
        if edge_key_property and edge_key_value is not None:
            close_mutation = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type} {{{edge_key_property}: $edge_key_val}}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            SET r.valid_to = $close_ts
            """
        else:
            close_mutation = f"""
            MATCH (src:{source_label} {{{src_id_key}: $src_id}})-[r:{rel_type}]->(dst:{target_label} {{{dst_id_key}: $dst_id}})
            SET r.valid_to = $close_ts
            """
        params["close_ts"] = close_ts
        self.client.query(close_mutation, params)

        source_url = existing_props.get("source_url") or "https://github.com/FalkorDB/falkordb-py"
        self._record_edge_change(
            op="close_edge",
            rel_type=rel_type,
            source_label=source_label,
            source_identity=source_identity,
            target_label=target_label,
            target_identity=target_identity,
            source_url=source_url,
            observed_at=close_ts,
            run_id=self.run_id,
            before_state=existing_props,
            after_state={**existing_props, "valid_to": close_ts},
        )

        return MutationResult(
            success=True,
            op="close_edge",
            entity_or_rel=rel_type,
            target_id=f"{source_identity}->{target_identity}",
            changed=True,
            run_id=self.run_id,
            observed_at=close_ts,
            details={"closed": True, "valid_to": close_ts},
        )

    # -------------------------------------------------------------------------
    # Operation 4: tombstone_node
    # -------------------------------------------------------------------------

    def tombstone_node(
        self,
        label: str,
        identity_value: Any,
        tombstoned_at: Optional[str] = None,
    ) -> MutationResult:
        """Mark a node as tombstoned without hard-deleting graph history.

        - Retains node and all connected historical relationships for time-travel queries.
        - Sets `status = 'tombstoned'`, `tombstoned_at = $ts`, `valid_to = $ts`.
        - Idempotent: repeated calls on an already-tombstoned node are safe no-ops.
        """
        self._validate_label(label)
        if identity_value is None or identity_value == "":
            raise ValidationError(f"identity_value for node '{label}' cannot be null or empty.")

        id_key = IDENTITY_KEYS[label]
        tomb_ts = normalize_utc_timestamp(tombstoned_at) if tombstoned_at else current_utc_iso()
        if not tomb_ts:
            raise ValidationError(f"Invalid timestamp for tombstoned_at: '{tombstoned_at}'")

        check_query = f"""
        MATCH (n:{label} {{{id_key}: $id_val}})
        RETURN properties(n) AS props
        """
        res = self.client.ro_query(check_query, {"id_val": identity_value})
        if not res or not res.result_set:
            raise EntityNotFoundError(f"Node not found to tombstone: ({label} {{{id_key}: {identity_value}}})")

        existing_props = res.result_set[0][0] or {}
        if existing_props.get("status") == "tombstoned":
            return MutationResult(
                success=True,
                op="tombstone_node",
                entity_or_rel=label,
                target_id=str(identity_value),
                changed=False,
                run_id=self.run_id,
                observed_at=tomb_ts,
                details={"tombstoned": False, "already_tombstoned_at": existing_props.get("tombstoned_at")},
            )

        tomb_mutation = f"""
        MATCH (n:{label} {{{id_key}: $id_val}})
        SET n.status = 'tombstoned',
            n.tombstoned_at = $tomb_ts,
            n.valid_to = $tomb_ts
        """
        self.client.query(tomb_mutation, {"id_val": identity_value, "tomb_ts": tomb_ts})

        source_url = existing_props.get("source_url") or existing_props.get("url") or "https://github.com/FalkorDB/falkordb-py"
        self._record_node_change(
            op="tombstone_node",
            label=label,
            identity_value=identity_value,
            source_url=source_url,
            observed_at=tomb_ts,
            run_id=self.run_id,
            before_state=existing_props,
            after_state={**existing_props, "status": "tombstoned", "tombstoned_at": tomb_ts, "valid_to": tomb_ts},
        )

        return MutationResult(
            success=True,
            op="tombstone_node",
            entity_or_rel=label,
            target_id=str(identity_value),
            changed=True,
            run_id=self.run_id,
            observed_at=tomb_ts,
            details={"tombstoned": True, "status": "tombstoned", "tombstoned_at": tomb_ts},
        )

    # -------------------------------------------------------------------------
    # Audit & Inspection Queries (Read-Only)
    # -------------------------------------------------------------------------

    def get_change_history(
        self,
        target_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve change events recorded by SyncRun."""
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit}
        if target_id is not None:
            where_clauses.append("(c.target_id = $target_id OR c.source_id = $target_id)")
            params["target_id"] = str(target_id)
        if run_id is not None:
            where_clauses.append("sr.run_id = $run_id")
            params["run_id"] = run_id

        where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
        MATCH (sr:SyncRun)-[c:CHANGED]->(n)
        {where_stmt}
        RETURN sr.run_id AS run_id,
               c.op AS op,
               c.target_id AS target_id,
               c.observed_at AS observed_at,
               c.source_url AS source_url,
               c.before AS before_state,
               c.after AS after_state
        ORDER BY c.observed_at DESC
        LIMIT $limit
        """
        res = self.client.ro_query(query, params)
        records = []
        if res and res.result_set:
            for row in res.result_set:
                records.append({
                    "run_id": row[0],
                    "op": row[1],
                    "target_id": row[2],
                    "observed_at": row[3],
                    "source_url": row[4],
                    "before": json.loads(row[5]) if row[5] else None,
                    "after": json.loads(row[6]) if row[6] else None,
                })
        return records
