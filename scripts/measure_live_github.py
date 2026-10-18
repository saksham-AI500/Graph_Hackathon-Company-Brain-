import subprocess
import json
import re

repo = "saksham-AI500/company-brain-synthetic-testbed"

def run_gh(endpoint, include=False):
    cmd = ["gh", "api"]
    if include:
        cmd.append("--include")
    cmd.append(endpoint)
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout

print("=== MEASURING LIVE GITHUB COUNTS ===")

# PRs
out_prs = run_gh(f"/search/issues?q=repo:{repo}+type:pr")
data_prs = json.loads(out_prs)
print(f"Live PRs: {data_prs.get('total_count')}")

# Issues
out_issues = run_gh(f"/search/issues?q=repo:{repo}+type:issue")
data_issues = json.loads(out_issues)
print(f"Live Issues: {data_issues.get('total_count')}")

# Review comments
try:
    out_rc = run_gh(f"/repos/{repo}/pulls/comments?per_page=1", include=True)
    m_rc = re.search(r'link:.*[?&]page=(\d+)>; rel="last"', out_rc, re.I)
    if m_rc:
        print(f"Live PR Review Comments: {m_rc.group(1)}")
    else:
        rc_list = json.loads(run_gh(f"/repos/{repo}/pulls/comments"))
        print(f"Live PR Review Comments: {len(rc_list)}")
except Exception as e:
    print(f"Live PR Review Comments Error: {e}")

# Issue comments
try:
    out_ic = run_gh(f"/repos/{repo}/issues/comments?per_page=1", include=True)
    m_ic = re.search(r'link:.*[?&]page=(\d+)>; rel="last"', out_ic, re.I)
    if m_ic:
        print(f"Live Issue Comments: {m_ic.group(1)}")
    else:
        ic_list = json.loads(run_gh(f"/repos/{repo}/issues/comments"))
        print(f"Live Issue Comments: {len(ic_list)}")
except Exception as e:
    print(f"Live Issue Comments Error: {e}")

# Commits
try:
    out_cm = run_gh(f"/repos/{repo}/commits?per_page=1", include=True)
    m_cm = re.search(r'link:.*[?&]page=(\d+)>; rel="last"', out_cm, re.I)
    if m_cm:
        print(f"Live Commits: {m_cm.group(1)}")
    else:
        cm_list = json.loads(run_gh(f"/repos/{repo}/commits"))
        print(f"Live Commits: {len(cm_list)}")
except Exception as e:
    print(f"Live Commits Error: {e}")
