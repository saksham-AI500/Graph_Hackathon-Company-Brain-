import urllib.request
import json

data = json.load(open('C:/Users/saksham/.gemini/antigravity-ide/brain/6aa5d69b-5850-4790-8eb1-6f7a4e4165d8/.system_generated/steps/1329/output.txt'))
project = data['projects'][0]
instances = project.get('screenInstances', [])

screens_to_check = set()
for inst in instances:
  src = inst.get('sourceScreen')
  if src:
    screens_to_check.add(src)

import subprocess
import os

print(f"Checking {len(screens_to_check)} screens...")
target_keywords = ['Strict (2 Hops)', '142k commits', 'Jordan Hayes', 'Knowledge Concentration Index', 'RFC-42', 'Context cluster: @acme/platform', 'Target release: Q2 2025']

for src in sorted(screens_to_check):
    # Call stitch get_screen or view downloadUrl
    # Let's inspect using StitchMCP get_screen json schema or downloadUrl if known
    pass
