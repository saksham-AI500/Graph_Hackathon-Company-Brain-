import subprocess
import json
from pathlib import Path

fixtures_root = Path("data/synthetic/fixtures")
synth_root = Path("d:/synthetic data_hackathon")

items = [
    # Q1
    ("Q1", "Issue #42", "data/synthetic/fixtures/issues/42.json", 4, 'title'),
    ("Q1", "PR #145 title", "data/synthetic/fixtures/pulls/145.json", 5, 'title'),
    ("Q1", "PR #145 body", "data/synthetic/fixtures/pulls/145.json", 6, 'body'),
    ("Q1", "Elena Rostova review", "data/synthetic/fixtures/pulls/145.json", 112, 'elena-rostova'),
    ("Q1", "Doc runbook", "docs/runbooks/payment-pipeline-recovery.md", 7, 'Related Issues'),
    
    # Q3
    ("Q3", "payment-pipeline-recovery.md", "docs/runbooks/payment-pipeline-recovery.md", 19, 'reconcile_unsettled_batches'),
    ("Q3", "0005-database-sharding.md", "docs/adr/0005-database-sharding.md", 10, 'payments/ledger.py'),
    ("Q3", "payments_refunds-README.md", "docs/modules/payments_refunds-README.md", 1, 'payments/refunds'),

    # Q5
    ("Q5", "@acme/payments", "data/synthetic/fixtures/codeowners.txt", 10, 'payments/ @acme/payments'),
    ("Q5", "@acme/legacy-settlements", "data/synthetic/fixtures/codeowners.txt", 11, 'payments/refunds/ @acme/legacy-settlements'),
    ("Q5", "Lucas Vogel departed", "data/synthetic/fixtures/people.json", 341, 'lucas-vogel'),

    # Q7
    ("Q7", "Marcus Vance expertise", "data/synthetic/fixtures/people.json", 285, 'marcus-vance'),
    ("Q7", "Gabriel Santos expertise", "data/synthetic/fixtures/people.json", 302, 'gabriel-santos'),

    # Q9
    ("Q9", "ADR-0004 Quote", "docs/adr/0004-network-retry-policy.md", 13, 'Retry policy: exponential backoff with jitter'),

    # Q11
    ("Q11", "ADR-0002 Date", "docs/adr/0002-token-auth.md", 5, '2025-10-15'),
    ("Q11", "ADR-0008 Date", "docs/adr/0008-mfa-mandate.md", 5, '2026-03-01'),

    # Q13
    ("Q13", "Before Step 1 owner", "changes/step_1.json", 10, '@acme/growth'),
    ("Q13", "After Step 1 owner", "changes/step_1.json", 13, '@acme/platform'),
    ("Q13", "Current codeowners owner", "data/synthetic/fixtures/codeowners.txt", 16, 'search/ @acme/platform'),

    # Q14
    ("Q14", "Stale runbook", "docs/runbooks/payment-pipeline-recovery.md", 16, 'STALE PROCEDURE'),
    ("Q14", "Code removed in PR 230", "docs/runbooks/payment-pipeline-recovery.md", 21, 'completely removed in PR #230'),

    # Q15
    ("Q15", "payments/refunds rule", "data/synthetic/fixtures/codeowners.txt", 11, 'payments/refunds/ @acme/legacy-settlements'),
    ("Q15", "Lucas Vogel departed", "data/synthetic/fixtures/people.json", 341, 'lucas-vogel'),
    ("Q15", "payments rule", "data/synthetic/fixtures/codeowners.txt", 10, 'payments/ @acme/payments'),

    # Q19
    ("Q19", "billing/ owner", "data/synthetic/fixtures/codeowners.txt", 14, 'billing/ @acme/payments'),
]

print("GROUNDING VERIFICATION:")
for qid, desc, rel_path, expected_line, pattern in items:
    # Resolve target file
    if rel_path.startswith("data/"):
        full_path = Path(rel_path)
    else:
        full_path = synth_root / rel_path

    if not full_path.exists():
        print(f"[{qid}] {desc} | {rel_path} | NOT FOUND ON DISK")
        continue

    lines = full_path.read_text(encoding="utf-8").splitlines()
    actual_line_idx = None
    matched_text = ""
    for idx, l in enumerate(lines, 1):
        if pattern.lower() in l.lower():
            actual_line_idx = idx
            matched_text = l.strip()
            break

    found = "YES" if actual_line_idx is not None else "NO"
    print(f"[{qid}] {desc} | {rel_path}:{actual_line_idx or expected_line} | Found: {found} | Matched: {matched_text[:60]}")
