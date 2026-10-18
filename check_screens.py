import urllib.request

urls = {
  'a423': 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFiMTZmNjU2OTYwOTI1YzdhOGQ4MDY4NTdiEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086',
  '7ae9': 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFhZWUxMjhhNDMwMWVlNDJhYmZiMTQ1NTgzEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086',
  '0e2e': 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFiMTEyMWJmNDUwN2M0ZTRiZTBlM2JhNzNmEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086',
  '9dd2': 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFhY2EwMzQ5ODUwMzM4NTgzYjM1MjA0N2FhEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086'
}

for k, u in urls.items():
    content = urllib.request.urlopen(u).read().decode('utf-8', errors='ignore')
    print(f"=== {k} ===")
    matches = [t for t in ['Telemetry', 'Augmented', 'Runtime Modes', 'Starter Prompts', 'Domain Starter', '142k', '82', '219', 'Strict (2 Hops)', 'Tokens:', 'Caleb Rivers', 'Jordan Hayes', 'Postmortem #409', 'Security Rule #8', 'Knowledge Concentration', 'Graph Augmented'] if t.lower() in content.lower()]
    print("  Matches:", matches)
