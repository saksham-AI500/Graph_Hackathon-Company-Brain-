"""Synthetic Slack-style Team Chat Generator for Acme Platform Inc.

Generates ~300 chat threads across the 4 engineering teams:
- @acme/platform (#team-platform)
- @acme/payments (#team-payments)
- @acme/identity (#team-identity)
- @acme/growth (#team-growth)

Features:
- At least 25 threads containing explicit engineering decisions linked to PRs, Issues, or ADRs.
- At least 10 threads containing reversals (e.g., initial approach abandoned for new design).
- Facts aligned with ground_truth.json and synthetic repo fixtures.
- All authors drawn from fixtures/people.json.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paths
OUTPUT_DIR = Path("d:/synthetic data_hackathon/data/synthetic/chats")
LOCAL_DIR = Path("d:/grraph Hackathon/grraph Hackathon/RepoBrain/data/synthetic/chats")
PEOPLE_PATH = Path("d:/synthetic data_hackathon/data/synthetic/fixtures/people.json")


def load_people():
    with open(PEOPLE_PATH, "r", encoding="utf-8") as f:
        people = json.load(f)
    by_team = {
        "@acme/platform": [],
        "@acme/payments": [],
        "@acme/identity": [],
        "@acme/growth": [],
    }
    for p in people:
        team = p.get("team")
        if team in by_team and not p.get("is_bot"):
            by_team[team].append(p)
    return by_team


# Pre-defined 25 Decision threads (10 with reversals)
DECISION_TEMPLATES = [
    # 1. Checkout timeout decision (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "Checkout DB Connection Timeout Tuning",
        "linked_entity": "PR #236",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/236",
        "messages": [
            ("elena-rostova", "Peak load concurrency is hitting timeout limits on payments/checkout.py. Issue #44 is tracking this."),
            ("marcus-vance", "PR #326 claimed to address it, but that was just docs. We need real connection pool tuning."),
            ("marcus-vance", "Decision: We are optimizing the PostgreSQL connection pool timeout from 30s to 5s with backoff in PR #236."),
            ("elena-rostova", "LGTM. Tested under synthetic load and verified latency dropped 45%."),
        ],
        "decision_quote": "We are optimizing the PostgreSQL connection pool timeout from 30s to 5s with backoff in PR #236.",
        "reversal": False,
    },
    # 2. Reversal: Batch settlement function deprecation (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "Batch Settlement Pipeline Refactor",
        "linked_entity": "PR #238",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/238",
        "messages": [
            ("lucas-vogel", "Earlier we agreed to maintain reconcile_unsettled_batches() for backwards compatibility in runbooks."),
            ("marcus-vance", "Reversal: We are deprecating and removing reconcile_unsettled_batches() in favor of event-driven settlement in PR #238."),
            ("elena-rostova", "Noted, runbook docs/runbooks/payment-pipeline-recovery.md will need updating since it still cites the old batch function."),
        ],
        "decision_quote": "We are deprecating and removing reconcile_unsettled_batches() in favor of event-driven settlement in PR #238.",
        "reversal": True,
    },
    # 3. Token Auth Architecture (identity)
    {
        "team": "@acme/identity",
        "channel": "team-identity",
        "title": "Stateless JWT vs Redis Session Store",
        "linked_entity": "ADR-0002",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0002-token-auth.md",
        "messages": [
            ("priya-sharma", "Evaluating token structure for auth/ endpoints."),
            ("gabriel-santos", "Decision: We are adopting signed Ed25519 asymmetric JWT tokens for all microservice authentication."),
            ("priya-sharma", "Documenting in docs/adr/0002-token-auth.md."),
        ],
        "decision_quote": "We are adopting signed Ed25519 asymmetric JWT tokens for all microservice authentication.",
        "reversal": False,
    },
    # 4. Reversal: Rate Limiting Scope (identity)
    {
        "team": "@acme/identity",
        "channel": "team-identity",
        "title": "Rate Limiting Architecture",
        "linked_entity": "PR #237",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/237",
        "messages": [
            ("gabriel-santos", "Initial RFC proposed global IP-based rate limiting across all auth gateway endpoints."),
            ("priya-sharma", "Global IP limits broke enterprise NAT gateways in staging testing yesterday."),
            ("priya-sharma", "Reversal: We are abandoning IP-based limits; we are going with per-tenant rate limits in PR #237."),
            ("gabriel-santos", "Agreed. Per-tenant bucket algorithm isolates noisy neighbors without blocking enterprise egress IPs."),
        ],
        "decision_quote": "We are going with per-tenant rate limits.",
        "reversal": True,
    },
    # 5. MFA Mandate (identity)
    {
        "team": "@acme/identity",
        "channel": "team-identity",
        "title": "MFA Enforcement Policy",
        "linked_entity": "ADR-0008",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0008-mfa-mandate.md",
        "messages": [
            ("priya-sharma", "Security audit requires hard enforcement on administrative and payment-touching routes."),
            ("gabriel-santos", "Decision: Mandatory WebAuthn or TOTP MFA is required for all engineering console and API credential operations."),
            ("priya-sharma", "Formalized under ADR-0008."),
        ],
        "decision_quote": "Mandatory WebAuthn or TOTP MFA is required for all engineering console and API credential operations.",
        "reversal": False,
    },
    # 6. Reversal: Logging Architecture (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Logging Pipeline Architecture",
        "linked_entity": "ADR-0007",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0007-opentelemetry-grpc-logging.md",
        "messages": [
            ("liam-chen", "ADR-0003 mandated standard stdout JSON logging for container runtimes."),
            ("sophia-rossi", "Stdout logging docker daemon buffer saturated during Kafka replay spikes."),
            ("sophia-rossi", "Reversal: All production services must stream logs via OpenTelemetry OTLP over gRPC directly to the collector, bypassing stdout."),
            ("liam-chen", "Confirmed, documented in ADR-0007 superseding ADR-0003."),
        ],
        "decision_quote": "All production services must stream logs via OpenTelemetry OTLP over gRPC directly to the collector, bypassing stdout.",
        "reversal": True,
    },
    # 7. Database Sharding Strategy (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "PostgreSQL Sharding Strategy",
        "linked_entity": "ADR-0005",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0005-database-sharding.md",
        "messages": [
            ("caleb-rivers", "Reviewing cluster scale projections for the next 18 months."),
            ("clara-oswald", "Decision: We are partitioning payment transactional ledger tables by tenant ID hash across 16 database shards."),
            ("caleb-rivers", "Documented in docs/adr/0005-database-sharding.md."),
        ],
        "decision_quote": "We are partitioning payment transactional ledger tables by tenant ID hash across 16 database shards.",
        "reversal": False,
    },
    # 8. Reversal: Search Indexing Engine (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Search Engine Backend Selection",
        "linked_entity": "Issue #88",
        "linked_type": "Issue",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/issues/88",
        "messages": [
            ("caleb-rivers", "We originally prototyped search/ using PostgreSQL tsvector full-text indices."),
            ("liam-chen", "Reversal: We are migrating search/ from PostgreSQL tsvector to distributed OpenSearch to support sub-50ms fuzzy queries."),
            ("caleb-rivers", "Assigned Issue #88 to track the cluster rollout."),
        ],
        "decision_quote": "We are migrating search/ from PostgreSQL tsvector to distributed OpenSearch to support sub-50ms fuzzy queries.",
        "reversal": True,
    },
    # 9. Payment Gateway Redundancy (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "Secondary Payment Gateway Failover",
        "linked_entity": "PR #189",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/189",
        "messages": [
            ("marcus-vance", "Single gateway dependency caused 12 minutes downtime during upstream provider outage."),
            ("elena-rostova", "Decision: We are enabling active-active multi-acquirer failover routing for Stripe and Adyen in PR #189."),
            ("marcus-vance", "Merged and verified in staging."),
        ],
        "decision_quote": "We are enabling active-active multi-acquirer failover routing for Stripe and Adyen in PR #189.",
        "reversal": False,
    },
    # 10. Reversal: Webhook Delivery Protocol (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "Merchant Webhook Dispatch Architecture",
        "linked_entity": "PR #212",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/212",
        "messages": [
            ("marcus-vance", "We were using synchronous HTTP calls from workers to dispatch merchant webhooks."),
            ("elena-rostova", "Reversal: Abandoning direct HTTP worker calls; routing all outbound merchant webhooks through SQS dead-letter queues in PR #212."),
            ("marcus-vance", "Huge reliability win, no more blocked worker threads on slow merchant endpoints."),
        ],
        "decision_quote": "Abandoning direct HTTP worker calls; routing all outbound merchant webhooks through SQS dead-letter queues in PR #212.",
        "reversal": True,
    },
    # 11. Growth Feature Flag Evaluation Engine (growth)
    {
        "team": "@acme/growth",
        "channel": "team-growth",
        "title": "Experimentation Engine Architecture",
        "linked_entity": "PR #155",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/155",
        "messages": [
            ("aiden-cross", "Need low-latency feature flagging for A/B rollout experiments."),
            ("maya-lin", "Decision: We are implementing client-side MurmurHash3 bucketing with deterministic seed evaluation in growth/experiments/."),
            ("aiden-cross", "Deployed in PR #155."),
        ],
        "decision_quote": "We are implementing client-side MurmurHash3 bucketing with deterministic seed evaluation in growth/experiments/.",
        "reversal": False,
    },
    # 12. Reversal: Referral Credit Ledger (growth)
    {
        "team": "@acme/growth",
        "channel": "team-growth",
        "title": "Referral Bonus Allocation Logic",
        "linked_entity": "PR #204",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/204",
        "messages": [
            ("maya-lin", "Instant referral credit granting was exploited by disposable email bot rings."),
            ("aiden-cross", "Reversal: We are removing instant referral payout and enforcing a 14-day anti-fraud maturation lock in PR #204."),
            ("maya-lin", "Fraudulent credit claims dropped to zero immediately."),
        ],
        "decision_quote": "We are removing instant referral payout and enforcing a 14-day anti-fraud maturation lock in PR #204.",
        "reversal": True,
    },
    # 13. Kafka Event Schema Governance (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Event Serialization Standards",
        "linked_entity": "ADR-0004",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0004-event-schema-registry.md",
        "messages": [
            ("clara-oswald", "Uncoordinated schema changes in billing payloads broke downstream ingestion twice this month."),
            ("caleb-rivers", "Decision: All Kafka event producers must register Protobuf v3 schemas with strict backwards compatibility checks in CI."),
            ("clara-oswald", "Published ADR-0004."),
        ],
        "decision_quote": "All Kafka event producers must register Protobuf v3 schemas with strict backwards compatibility checks in CI.",
        "reversal": False,
    },
    # 14. Reversal: Secret Management Backend (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Kubernetes Secret Provider Migration",
        "linked_entity": "Issue #120",
        "linked_type": "Issue",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/issues/120",
        "messages": [
            ("liam-chen", "Previously we stored encrypted secrets directly in git using git-crypt."),
            ("sophia-rossi", "Reversal: Decommissioning git-crypt in favor of HashiCorp Vault with automated 30-day token rotation in Issue #120."),
            ("liam-chen", "All clusters migrated successfully."),
        ],
        "decision_quote": "Decommissioning git-crypt in favor of HashiCorp Vault with automated 30-day token rotation in Issue #120.",
        "reversal": True,
    },
    # 15. Service Mesh Protocol (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Internal Service-to-Service Protocol",
        "linked_entity": "ADR-0006",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0006-service-mesh-grpc.md",
        "messages": [
            ("sophia-rossi", "Internal JSON over HTTP/1.1 is consuming excessive CPU on serialization."),
            ("caleb-rivers", "Decision: All internal East-West RPC communication between microservices must use gRPC over HTTP/2 with mTLS."),
            ("sophia-rossi", "Documented in ADR-0006."),
        ],
        "decision_quote": "All internal East-West RPC communication between microservices must use gRPC over HTTP/2 with mTLS.",
        "reversal": False,
    },
    # 16. Reversal: Currency Formatting Utility (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "Floating Point vs Integer Currency Representation",
        "linked_entity": "PR #112",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/112",
        "messages": [
            ("marcus-vance", "Legacy billing modules represented amounts in floating point decimal strings."),
            ("elena-rostova", "Reversal: Prohibiting all float math for monetary values; all amounts must be stored as 64-bit integer minor currency units in PR #112."),
            ("marcus-vance", "Precision discrepancies resolved completely."),
        ],
        "decision_quote": "Prohibiting all float math for monetary values; all amounts must be stored as 64-bit integer minor currency units in PR #112.",
        "reversal": True,
    },
    # 17. OAuth2 Token Revocation Protocol (identity)
    {
        "team": "@acme/identity",
        "channel": "team-identity",
        "title": "Backchannel Logout & Token Revocation",
        "linked_entity": "PR #176",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/176",
        "messages": [
            ("priya-sharma", "Need instant token revocation when a user changes their password."),
            ("gabriel-santos", "Decision: Implementing OpenID Connect Backchannel Logout and Redis revocation bloom filters in PR #176."),
            ("priya-sharma", "Verified revocation propagates in under 20ms across all gateways."),
        ],
        "decision_quote": "Implementing OpenID Connect Backchannel Logout and Redis revocation bloom filters in PR #176.",
        "reversal": False,
    },
    # 18. Reversal: Notification Delivery Queue (growth)
    {
        "team": "@acme/growth",
        "channel": "team-growth",
        "title": "Email Dispatch Worker Architecture",
        "linked_entity": "PR #221",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/221",
        "messages": [
            ("maya-lin", "Notifications worker was executing synchronously in request thread during user onboarding."),
            ("aiden-cross", "Reversal: Decoupling user registration from notification delivery by routing via RabbitMQ dead-letter queues in PR #221."),
            ("maya-lin", "Onboarding latency reduced from 850ms to 42ms."),
        ],
        "decision_quote": "Decoupling user registration from notification delivery by routing via RabbitMQ dead-letter queues in PR #221.",
        "reversal": True,
    },
    # 19. Distributed Tracing Sampling (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "OpenTelemetry Trace Sampling Rate",
        "linked_entity": "PR #198",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/198",
        "messages": [
            ("liam-chen", "100% trace capture is overwhelming our Grafana Tempo storage."),
            ("sophia-rossi", "Decision: Setting adaptive tail-based sampling to 5% for HTTP 200 responses and 100% for error status codes in PR #198."),
            ("liam-chen", "Storage overhead dropped 80% while retaining full visibility on 5xx incidents."),
        ],
        "decision_quote": "Setting adaptive tail-based sampling to 5% for HTTP 200 responses and 100% for error status codes in PR #198.",
        "reversal": False,
    },
    # 20. Reversal: Database Connection Pooling (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "PgBouncer vs In-App Pooling",
        "linked_entity": "PR #231",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/231",
        "messages": [
            ("clara-oswald", "We previously configured in-process connection pools inside each ECS container task."),
            ("caleb-rivers", "Reversal: Eliminating in-process connection pools in favor of a centralized PgBouncer pooler in transaction mode in PR #231."),
            ("clara-oswald", "Max DB connections dropped from 1,200 to 120."),
        ],
        "decision_quote": "Eliminating in-process connection pools in favor of a centralized PgBouncer pooler in transaction mode in PR #231.",
        "reversal": True,
    },
    # 21. Idempotency Key Specification (payments)
    {
        "team": "@acme/payments",
        "channel": "team-payments",
        "title": "API Idempotency Standard",
        "linked_entity": "ADR-0001",
        "linked_type": "Document",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0001-idempotency-keys.md",
        "messages": [
            ("elena-rostova", "Network retries from client apps occasionally caused duplicate charge authorizations."),
            ("marcus-vance", "Decision: All POST requests modifying financial balance must supply a unique Idempotency-Key header cached in Redis for 24 hours."),
            ("elena-rostova", "Documented in ADR-0001."),
        ],
        "decision_quote": "All POST requests modifying financial balance must supply a unique Idempotency-Key header cached in Redis for 24 hours.",
        "reversal": False,
    },
    # 22. Reversal: Session Expiration Policy (identity)
    {
        "team": "@acme/identity",
        "channel": "team-identity",
        "title": "Web Session TTL Adjustment",
        "linked_entity": "PR #165",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/165",
        "messages": [
            ("gabriel-santos", "Initial web session TTL was 30 days without idle timeout."),
            ("priya-sharma", "Reversal: Shortening maximum web session lifespan to 12 hours with a mandatory 15-minute idle inactivity lock in PR #165."),
            ("gabriel-santos", "Aligns with SOC2 compliance requirements."),
        ],
        "decision_quote": "Shortening maximum web session lifespan to 12 hours with a mandatory 15-minute idle inactivity lock in PR #165.",
        "reversal": True,
    },
    # 23. Dark Mode Theme Engine (growth)
    {
        "team": "@acme/growth",
        "channel": "team-growth",
        "title": "Design System Token Integration",
        "linked_entity": "PR #178",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/178",
        "messages": [
            ("maya-lin", "Frontend design system tokens need standardization across React apps."),
            ("aiden-cross", "Decision: Adopting CSS custom property design tokens strictly compiled from Figma design tokens in PR #178."),
            ("maya-lin", "Looks great, full theme switching supported."),
        ],
        "decision_quote": "Adopting CSS custom property design tokens strictly compiled from Figma design tokens in PR #178.",
        "reversal": False,
    },
    # 24. Reversal: CI Build Cache Mechanism (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Docker Layer Cache in CI",
        "linked_entity": "Issue #140",
        "linked_type": "Issue",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/issues/140",
        "messages": [
            ("sophia-rossi", "Using local runner directory caching was causing cache invalidation bugs in GitHub Actions."),
            ("liam-chen", "Reversal: Replacing local runner directory caching with remote buildx registry inline cache in Issue #140."),
            ("sophia-rossi", "CI pipeline build times dropped from 14 minutes to 3.5 minutes."),
        ],
        "decision_quote": "Replacing local runner directory caching with remote buildx registry inline cache in Issue #140.",
        "reversal": True,
    },
    # 25. Synthetic Load Testing Schedule (platform)
    {
        "team": "@acme/platform",
        "channel": "team-platform",
        "title": "Continuous Performance Testing",
        "linked_entity": "PR #240",
        "linked_type": "PullRequest",
        "linked_url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/240",
        "messages": [
            ("caleb-rivers", "Need automated load verification before weekly production deployments."),
            ("clara-oswald", "Decision: We are scheduling automated nightly Locust load runs against the staging environment in PR #240."),
            ("caleb-rivers", "Approved and scheduled."),
        ],
        "decision_quote": "We are scheduling automated nightly Locust load runs against the staging environment in PR #240.",
        "reversal": False,
    },
]

# Everyday engineering chat topics for remaining 275 threads
CHAT_TOPICS = [
    ("deployment-sync", "Deploying release candidate to staging. Smoke tests passing."),
    ("ci-flakiness", "Investigating sporadic timeout in test_payments_integration.py; rerunning fixed it."),
    ("pr-review-ping", "Can someone with CODEOWNERS authority review my PR touching shared/utils/?"),
    ("standup-notes", "Standup summary: completed unit tests for retry policy, working on metrics exporter."),
    ("incident-postmortem", "Reviewing postmortem action items from last week's replica lag spike."),
    ("dependency-update", "Dependabot opened 3 minor security bump PRs; running integration suite."),
    ("codeowners-drift", "Noticing lots of PRs in payments/ are reviewed by people outside legacy-settlements."),
    ("api-spec-review", "OpenAPI spec updated for the new v2 endpoints in auth/mfa/."),
    ("performance-tuning", "P99 latency down 15ms after indexing file_path column."),
    ("on-call-handover", "Handoff complete. 0 critical pages overnight. System steady."),
]


def generate_threads():
    people_by_team = load_people()
    threads = []
    thread_counter = 1000

    # 1. Add 25 core decision threads
    base_time = datetime(2025, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
    for idx, d in enumerate(DECISION_TEMPLATES):
        t_id = f"th_{thread_counter}"
        thread_counter += 1
        t_time = base_time + timedelta(days=idx * 14, hours=random.randint(1, 8))

        msgs = []
        for offset, (author, text) in enumerate(d["messages"]):
            m_time = t_time + timedelta(minutes=offset * 4 + random.randint(1, 3))
            msgs.append({
                "message_id": f"msg_{t_id}_{offset}",
                "author": author,
                "text": text,
                "timestamp": m_time.isoformat(),
            })

        threads.append({
            "thread_id": t_id,
            "channel": d["channel"],
            "team": d["team"],
            "title": d["title"],
            "created_at": t_time.isoformat(),
            "has_decision": True,
            "decision_quote": d["decision_quote"],
            "is_reversal": d["reversal"],
            "linked_entity": d["linked_entity"],
            "linked_type": d["linked_type"],
            "linked_url": d["linked_url"],
            "thread_url": f"https://acme-corp.slack.com/archives/{d['channel']}/p{int(t_time.timestamp())}",
            "messages": msgs,
        })

    # 2. Add 275 realistic engineering discussion threads across 4 teams
    team_list = list(people_by_team.keys())
    team_channel_map = {
        "@acme/platform": "team-platform",
        "@acme/payments": "team-payments",
        "@acme/identity": "team-identity",
        "@acme/growth": "team-growth",
    }

    random.seed(20260930)  # Reproducible seed
    cur_time = datetime(2025, 6, 1, 8, 30, 0, tzinfo=timezone.utc)
    target_total = 300
    needed = target_total - len(threads)

    for i in range(needed):
        t_id = f"th_{thread_counter}"
        thread_counter += 1
        cur_time += timedelta(hours=random.randint(4, 36), minutes=random.randint(5, 55))
        team = team_list[i % len(team_list)]
        channel = team_channel_map[team]
        members = people_by_team[team]
        if not members:
            continue

        topic_tag, topic_text = CHAT_TOPICS[i % len(CHAT_TOPICS)]
        author_a = random.choice(members)["login"]
        author_b = random.choice([m["login"] for m in members if m["login"] != author_a] or [author_a])

        msgs = [
            {
                "message_id": f"msg_{t_id}_0",
                "author": author_a,
                "text": f"[{topic_tag}] {topic_text}",
                "timestamp": cur_time.isoformat(),
            },
            {
                "message_id": f"msg_{t_id}_1",
                "author": author_b,
                "text": "Acknowledged. Thanks for the heads up, tracking this.",
                "timestamp": (cur_time + timedelta(minutes=random.randint(3, 15))).isoformat(),
            },
        ]

        threads.append({
            "thread_id": t_id,
            "channel": channel,
            "team": team,
            "title": f"[{topic_tag}] Discussion",
            "created_at": cur_time.isoformat(),
            "has_decision": False,
            "decision_quote": None,
            "is_reversal": False,
            "linked_entity": None,
            "linked_type": None,
            "linked_url": None,
            "thread_url": f"https://acme-corp.slack.com/archives/{channel}/p{int(cur_time.timestamp())}",
            "messages": msgs,
        })

    return threads


def main():
    threads = generate_threads()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Write channels.json
    channels = [
        {"id": "C01", "name": "team-platform", "team": "@acme/platform", "purpose": "Platform and infrastructure discussions"},
        {"id": "C02", "name": "team-payments", "team": "@acme/payments", "purpose": "Payments and transactions core discussions"},
        {"id": "C03", "name": "team-identity", "team": "@acme/identity", "purpose": "Authentication and authorization architecture"},
        {"id": "C04", "name": "team-growth", "team": "@acme/growth", "purpose": "User acquisition, onboarding, and experimentation"},
    ]

    for path in (OUTPUT_DIR / "channels.json", LOCAL_DIR / "channels.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=2)

    # 2. Write full threads export
    for path in (OUTPUT_DIR / "threads.json", LOCAL_DIR / "threads.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(threads, f, indent=2)

    # 3. Write per-channel exports
    by_channel: dict[str, list] = {}
    for t in threads:
        ch = t["channel"]
        by_channel.setdefault(ch, []).append(t)

    for ch, ch_threads in by_channel.items():
        for d in (OUTPUT_DIR, LOCAL_DIR):
            with open(d / f"{ch}.json", "w", encoding="utf-8") as f:
                json.dump(ch_threads, f, indent=2)

    decisions = [t for t in threads if t.get("has_decision")]
    reversals = [t for t in threads if t.get("is_reversal")]

    print(f"Generated {len(threads)} total chat threads:")
    print(f"- Channels: {len(channels)}")
    print(f"- Decision threads: {len(decisions)} (target: >= 25)")
    print(f"- Reversal threads: {len(reversals)} (target: >= 10)")
    for ch, ch_threads in by_channel.items():
        print(f"  #{ch}: {len(ch_threads)} threads")


if __name__ == "__main__":
    main()
