import json
import sys
from pathlib import Path
sys.path.insert(0, ".")

from src.agent.tools import get_default_tool_registry
from src.agent.fixture_tools import execute_fixture_tool

registry = get_default_tool_registry()

print("=" * 60)
print("TESTING TOOLS FOR Q5, Q7, Q9, Q11, Q14")
print("=" * 60)

# Q5: Who owns payments/refund.py according to CODEOWNERS?
# Tool: who_owns
print("\n--- Q5: who_owns(file_path='payments/refund.py') ---")
res5 = registry.execute("who_owns", {"file_path": "payments/refund.py"})
print("Success:", res5.success)
print("Data:", json.dumps(res5.data, indent=2))
print("Evidence URLs:", res5.evidence_urls)

# Q7: Who should review a new PR touching both auth/ and payments/?
# Tool: suggest_reviewers
print("\n--- Q7: suggest_reviewers(modules=['auth/', 'payments/']) ---")
res7 = registry.execute("suggest_reviewers", {"file_path_or_pr": "auth/,payments/"})
print("Success:", res7.success)
print("Data:", json.dumps(res7.data, indent=2))
print("Evidence URLs:", res7.evidence_urls)

# Q9: Why did we choose the retry policy? Quote the source.
# Tool: trace_decision
print("\n--- Q9: trace_decision(query_or_pr='retry policy') ---")
res9 = registry.execute("trace_decision", {"query_or_pr": "retry policy"})
print("Success:", res9.success)
print("Data:", json.dumps(res9.data, indent=2))
print("Evidence URLs:", res9.evidence_urls)

# Q11: Which decisions affect auth/, listed by date, with sources?
# Tool: trace_decision
print("\n--- Q11: trace_decision(query_or_pr='auth/') ---")
res11 = registry.execute("trace_decision", {"query_or_pr": "auth/"})
print("Success:", res11.success)
print("Data:", json.dumps(res11.data, indent=2))
print("Evidence URLs:", res11.evidence_urls)

# Q14: Is the incident runbook still accurate, or has the code changed since it was written?
# Tool: find_stale_docs
print("\n--- Q14: find_stale_docs() ---")
res14 = registry.execute("find_stale_docs", {})
print("Success:", res14.success)
print("Data:", json.dumps(res14.data, indent=2))
print("Evidence URLs:", res14.evidence_urls)
