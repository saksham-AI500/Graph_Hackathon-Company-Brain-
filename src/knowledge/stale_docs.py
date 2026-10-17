"""Stale-document detection based on grounded graph relationships and temporal causality.

Rule from AGENT_BRIEF:
    "A document is potentially stale if a file it documents changed after the document's last edit."

Guarantees:
- Strict evidence-grounded document-to-file associations only:
    1. Direct `(:Document)-[:REFERENCES]->(:File)`
    2. Indirect via PR: `(:Document)-[:REFERENCES]->(:PullRequest)-[:MODIFIES]->(:File)`
    3. Architecture Decision link: `(:Decision)-[:DECIDED_IN]->(:Document)` and `(:Decision)-[:AFFECTS]->(:File)`
- No semantic similarity or filename guessing.
- Distinguishes "POTENTIALLY_STALE" from "CONFIRMED_INCORRECT" or "UP_TO_DATE".
- Missing/invalid timestamps treated as "UNRESOLVED_TIMESTAMPS".
- Enforces strict `as_of` temporal cutoff (future PRs merged after as_of are excluded).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.knowledge.temporal import normalize_utc_timestamp, parse_utc_datetime


@dataclass
class StaleDocumentFinding:
    """Findings for a document associated with a specific repository file."""
    document_path: str
    document_title: Optional[str]
    document_url: Optional[str]
    document_last_modified: Optional[str]
    documented_file_path: str
    file_url: Optional[str]
    file_last_modified: Optional[str]
    diff_days: float  # Positive if file was modified after document
    status: str  # "POTENTIALLY_STALE", "UP_TO_DATE", "UNRESOLVED_TIMESTAMPS"
    modifying_prs: List[Dict[str, Any]] = field(default_factory=list)
    grounding_relationship: str = "EXPLICIT_REFERENCE"
    evidence_urls: List[str] = field(default_factory=list)
    as_of: Optional[str] = None
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StaleDocumentationReport:
    """Aggregated repository-level stale documentation audit."""
    as_of: str
    total_documents_checked: int
    potentially_stale_count: int
    up_to_date_count: int
    unresolved_count: int
    findings: List[StaleDocumentFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "total_documents_checked": self.total_documents_checked,
            "potentially_stale_count": self.potentially_stale_count,
            "up_to_date_count": self.up_to_date_count,
            "unresolved_count": self.unresolved_count,
            "findings": [f.to_dict() for f in self.findings],
        }


def check_document_staleness(
    client: FalkorDBClient,
    document_path: str,
    as_of: Optional[str] = None,
) -> List[StaleDocumentFinding]:
    """Check staleness of a single document against all files it grounded in graph relationships."""
    norm_as_of = normalize_utc_timestamp(as_of)
    as_of_dt = parse_utc_datetime(norm_as_of) or datetime.now(timezone.utc)
    as_of_str = norm_as_of or as_of_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Fetch document node and metadata
    doc_query = """
    MATCH (d:Document {path: $path})
    RETURN d.path AS path, d.title AS title, coalesce(d.url, d.source_url) AS url,
           coalesce(d.observed_at, d.created_at, d.valid_from) AS doc_ts, d.status AS status
    """
    doc_res = client.ro_query(doc_query, {"path": document_path})
    if not doc_res or not doc_res.result_set:
        return []

    row = doc_res.result_set[0]
    doc_title = row[1]
    doc_url = row[2]
    raw_doc_ts = row[3]
    doc_status = row[4]

    norm_doc_ts = normalize_utc_timestamp(raw_doc_ts)

    # 2. Find grounded file associations:
    # 2a. Direct REFERENCES edge to File
    # 2b. REFERENCES edge to PullRequest that MODIFIES File
    # 2c. Decision DECIDED_IN Document and Decision AFFECTS File
    grounded_query = """
    MATCH (d:Document {path: $path})
    OPTIONAL MATCH (d)-[:REFERENCES]->(f1:File)
    OPTIONAL MATCH (d)-[:REFERENCES]->(pr:PullRequest)-[:MODIFIES]->(f2:File)
    OPTIONAL MATCH (dec:Decision)-[:DECIDED_IN]->(d), (dec)-[:AFFECTS]->(f3:File)
    RETURN collect(DISTINCT {file_path: f1.path, file_url: f1.url, rel: 'DIRECT_REFERENCE'}) +
           collect(DISTINCT {file_path: f2.path, file_url: f2.url, rel: 'PR_REFERENCE'}) +
           collect(DISTINCT {file_path: f3.path, file_url: f3.url, rel: 'DECISION_AFFECTS'}) AS grounded
    """
    grounded_res = client.ro_query(grounded_query, {"path": document_path})
    grounded_files: Dict[str, Dict[str, Any]] = {}

    if grounded_res and grounded_res.result_set and grounded_res.result_set[0][0]:
        for item in grounded_res.result_set[0][0]:
            fp = item.get("file_path")
            if fp and fp not in grounded_files:
                grounded_files[fp] = item

    if not grounded_files:
        return []

    findings: List[StaleDocumentFinding] = []

    for file_path, g_info in grounded_files.items():
        rel_type = g_info.get("rel", "EXPLICIT_REFERENCE")
        f_url = g_info.get("file_url")

        # Query all merged PRs modifying this file before or at as_of
        pr_query = """
        MATCH (f:File {path: $file_path})<-[m:MODIFIES]-(pr:PullRequest)
        WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> ''
        RETURN pr.number AS pr_number, pr.title AS pr_title, pr.url AS pr_url, pr.merged_at AS merged_at
        ORDER BY pr.merged_at DESC
        """
        pr_res = client.ro_query(pr_query, {"file_path": file_path})

        eligible_prs = []
        if pr_res and pr_res.result_set:
            for p_row in pr_res.result_set:
                p_num, p_title, p_url, p_merged = int(p_row[0]), str(p_row[1]), str(p_row[2]), str(p_row[3])
                p_norm_ts = normalize_utc_timestamp(p_merged)
                if not p_norm_ts:
                    continue
                # Exclude future PRs after as_of
                if norm_as_of and p_norm_ts > norm_as_of:
                    continue
                eligible_prs.append({
                    "pr_number": p_num,
                    "title": p_title,
                    "url": p_url,
                    "merged_at": p_norm_ts,
                })

        if not norm_doc_ts:
            findings.append(StaleDocumentFinding(
                document_path=document_path,
                document_title=doc_title,
                document_url=doc_url,
                document_last_modified=None,
                documented_file_path=file_path,
                file_url=f_url,
                file_last_modified=eligible_prs[0]["merged_at"] if eligible_prs else None,
                diff_days=0.0,
                status="UNRESOLVED_TIMESTAMPS",
                modifying_prs=[],
                grounding_relationship=rel_type,
                evidence_urls=[u for u in [doc_url, f_url] if u],
                as_of=as_of_str,
                explanation="Document timestamp is missing or invalid; cannot deterministically establish staleness.",
            ))
            continue

        if not eligible_prs:
            # File has no recorded modifications prior to as_of
            findings.append(StaleDocumentFinding(
                document_path=document_path,
                document_title=doc_title,
                document_url=doc_url,
                document_last_modified=norm_doc_ts,
                documented_file_path=file_path,
                file_url=f_url,
                file_last_modified=None,
                diff_days=0.0,
                status="UP_TO_DATE",
                modifying_prs=[],
                grounding_relationship=rel_type,
                evidence_urls=[u for u in [doc_url, f_url] if u],
                as_of=as_of_str,
                explanation="No modifying PRs recorded for documented file prior to as_of cutoff.",
            ))
            continue

        latest_pr = eligible_prs[0]
        latest_file_ts = latest_pr["merged_at"]
        doc_dt = parse_utc_datetime(norm_doc_ts)
        file_dt = parse_utc_datetime(latest_file_ts)

        diff_seconds = (file_dt - doc_dt).total_seconds()
        diff_days = round(diff_seconds / 86400.0, 2)

        # PRs that modified the file strictly after the document edit
        later_prs = [p for p in eligible_prs if p["merged_at"] > norm_doc_ts]

        if diff_seconds > 0 and later_prs:
            evidence_urls = [u for u in [doc_url, f_url] if u] + [p["url"] for p in later_prs[:3] if p.get("url")]
            findings.append(StaleDocumentFinding(
                document_path=document_path,
                document_title=doc_title,
                document_url=doc_url,
                document_last_modified=norm_doc_ts,
                documented_file_path=file_path,
                file_url=f_url,
                file_last_modified=latest_file_ts,
                diff_days=diff_days,
                status="POTENTIALLY_STALE",
                modifying_prs=later_prs,
                grounding_relationship=rel_type,
                evidence_urls=list(dict.fromkeys(evidence_urls)),
                as_of=as_of_str,
                explanation=(
                    f"Document was last observed at {norm_doc_ts}, but documented file '{file_path}' "
                    f"was modified {diff_days} days later by {len(later_prs)} PR(s) (latest: PR #{latest_pr['pr_number']} at {latest_file_ts})."
                ),
            ))
        else:
            evidence_urls = [u for u in [doc_url, f_url] if u] + [latest_pr["url"]]
            findings.append(StaleDocumentFinding(
                document_path=document_path,
                document_title=doc_title,
                document_url=doc_url,
                document_last_modified=norm_doc_ts,
                documented_file_path=file_path,
                file_url=f_url,
                file_last_modified=latest_file_ts,
                diff_days=diff_days,
                status="UP_TO_DATE",
                modifying_prs=[],
                grounding_relationship=rel_type,
                evidence_urls=list(dict.fromkeys(evidence_urls)),
                as_of=as_of_str,
                explanation=f"Document observed at {norm_doc_ts} is newer than latest file modification ({latest_file_ts}).",
            ))

    return findings


def audit_repository_documentation_staleness(
    client: FalkorDBClient,
    as_of: Optional[str] = None,
) -> StaleDocumentationReport:
    """Audit all active documents in the repository for potential staleness."""
    norm_as_of = normalize_utc_timestamp(as_of)
    as_of_str = norm_as_of or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch all active documents in FalkorDB
    query = """
    MATCH (d:Document)
    WHERE d.status IS NULL OR d.status <> 'tombstoned'
    RETURN d.path AS path
    ORDER BY d.path ASC
    """
    res = client.ro_query(query)
    all_findings: List[StaleDocumentFinding] = []
    stale_count = 0
    up_to_date_count = 0
    unresolved_count = 0
    total_docs = 0

    if res and res.result_set:
        for row in res.result_set:
            doc_path = str(row[0])
            total_docs += 1
            doc_findings = check_document_staleness(client, doc_path, as_of=as_of)
            for f in doc_findings:
                all_findings.append(f)
                if f.status == "POTENTIALLY_STALE":
                    stale_count += 1
                elif f.status == "UP_TO_DATE":
                    up_to_date_count += 1
                else:
                    unresolved_count += 1

    return StaleDocumentationReport(
        as_of=as_of_str,
        total_documents_checked=total_docs,
        potentially_stale_count=stale_count,
        up_to_date_count=up_to_date_count,
        unresolved_count=unresolved_count,
        findings=all_findings,
    )
