"""Export Stitch Assets for RepoBrain Project 14287344436665403466.

Exports the 5 specified screens:
1. fa8de15624f049499c5604b113a3378f -> docs/stitch/ask-dark/
2. bc93cef950e54cac8d2993808029bb3b -> docs/stitch/ask-light/
3. 5228d3d25a4f4f0a81eebe0dedecefda -> docs/stitch/compare/
4. 14828a05d43a428bb6a35f3d60e0e64c -> docs/stitch/graph-canvas/
5. 81ee8d24301f4f60a65c26388975a46f -> docs/stitch/graph-empty/

Extracts and exports design tokens to docs/stitch/design-tokens.json.
"""

import hashlib
import json
import re
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
STITCH_DIR = WORKSPACE / "docs" / "stitch"
STITCH_DIR.mkdir(parents=True, exist_ok=True)

SCREENS = [
    {
        "id": "fa8de15624f049499c5604b113a3378f",
        "folder": "ask-dark",
        "title": "RepoBrain - Ask (Dark Theme)",
        "variant": "dark",
        "deviceType": "DESKTOP",
        "width": 2560,
        "height": 2048,
        "screenshot_url": "https://lh3.googleusercontent.com/aida/AEtjO1UtFVXtWVWc8AtjYBEYMq5toNQvFXI94ZjtF8eaNWUIPzX8ZD9_F2FDXfRCXZpZvgSVA-U4WD1kbGAgkO68MTDY33YUdtIMy3TltXaBxp_CIY1LLs9OqI_BvtmPCkekfqj5PokjjK5_RO9BStMu3NGyXTnuGx44M3GbwUpGrirZZ9jNOxwTCoMYBQ2O5qh3CJ8ygaYKi_pa4JBJ0vIlIint-81RaCzpbRmHrkxmGufNMVsPdjYxZcA0GGLq",
        "html_url": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFkNDA1NTNlY2YwNTIyYTk4ODllMDRmZjkwEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086",
    },
    {
        "id": "bc93cef950e54cac8d2993808029bb3b",
        "folder": "ask-light",
        "title": "RepoBrain - Ask (Light Theme)",
        "variant": "light",
        "deviceType": "DESKTOP",
        "width": 2560,
        "height": 2346,
        "screenshot_url": "https://lh3.googleusercontent.com/aida/AEtjO1XjcRxtiVxWtt1y7yfywNR3s4j95BnWRgtL8TO5KQF8TigxA0hLd_aeCdUukUm-2c3N3qlWE89OzuLFMrN91oAMEHkUzA2AaAfo4ChJIScZjPEVzM9dpG-1dmMXuaCTwurX7BP3EkJNHrRlRu1czORRk3NO1EdRFvucHdpmlKVer7Dp2vuU-elkVwBVXXKDiQdVeTX7ElJ97-iSUmF34M4jgyWdw3JnhZlIAbo9IuURBpD-zQ2iUHDv1nY",
        "html_url": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFkNDA3YWUxZWIwOTEwN2U1M2NkMTRiYzc4EgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086",
    },
    {
        "id": "5228d3d25a4f4f0a81eebe0dedecefda",
        "folder": "compare",
        "title": "RepoBrain - Compare",
        "variant": "dark",
        "deviceType": "DESKTOP",
        "width": 2560,
        "height": 2048,
        "screenshot_url": "https://lh3.googleusercontent.com/aida/AEtjO1X9FgdM4RGTHd6vgBRQQhgSj_qXoxX_lFAn0iWbz71NIBpbNDwrVipYrcUPhe4pOS8xlFk47XB8tAr3rzMmw7HUqle7FhakhuMWgcKz-kH2wUa2IEPDkpwIrJTWLRpN_8d9lkgohOXhFYa8whQMjeNZ5gWlvb3PxQ64TvCDAfajuzwj4m5_P3cRPya-AuxX5GU9GzRdAzaR9bavAoYeXOukP8jX7f3QscZU9tj97KBqgti3NjZG5AfVOKQ",
        "html_url": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFkNDA0ZTQxNzUwMzM4NWMyYzUxMzI4MTIyEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086",
    },
    {
        "id": "14828a05d43a428bb6a35f3d60e0e64c",
        "folder": "graph-canvas",
        "title": "RepoBrain - Knowledge Graph Canvas & Evidence Path",
        "variant": "dark",
        "deviceType": "DESKTOP",
        "width": 2560,
        "height": 2048,
        "screenshot_url": "https://lh3.googleusercontent.com/aida/AEtjO1UYLQI2iu2FLmJMVfjrrmf-bn4-Ci-XPkDhaT1wo6Nk-5d3Ss0E59-X24NQvXvK1QVpcsdTYtugdQIEVwjCwonsSxsEOo-83HakIYT3Hk1FU1czI7Ika85krBKf3hPXAWfyP6jtIlQldxjnPqbhBTE8hh6G-e2xs7FhWE4ZGko_NnfkthcLXhyWKuQDbtUUNq-IHqoi1qQ7SH_pDTEiTr3ah9rJychdRx6frAw9gXup6g-e3GUfSXLfbOd3",
        "html_url": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTEzMzIyMjE1ODEwMWVlNTM0YTk2MDhlMzgyEgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086",
    },
    {
        "id": "81ee8d24301f4f60a65c26388975a46f",
        "folder": "graph-empty",
        "title": "RepoBrain - Knowledge Graph (Empty State with Dithered Orb)",
        "variant": "dark",
        "deviceType": "DESKTOP",
        "width": 2560,
        "height": 2048,
        "screenshot_url": "https://lh3.googleusercontent.com/aida/AEtjO1UO_iRZ77Y7muP3x84-W8XNL2Cbl1VAe64MIETjZPSt6xAIRNDrXWAiQUPgitPd4pKUZG8iiTemfDxw5SpEE9TzLKxUb1AwG7r1QYjh2ubrCEwAsPL30P5VbFUgE0vlzx_1E3OcxjCVwXa0baM3O000f8xkm1PUPTbpPQz3EPLCVOP2guTyrXJecv-6_Exb9_gcj9hzWIj73vzwueRRlu9dp2zNKEOSOkPSLt9LwEVw_fLVSbKTMUvnQ5Y",
        "html_url": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1ZTFiMWVkZGJiNWUwN2M0YzJlNTFiMWUyNzI0EgsSBxDP1umR9REYAZIBJAoKcHJvamVjdF9pZBIWQhQxNDI4NzM0NDQzNjY2NTQwMzQ2Ng&filename=&opi=89354086",
    },
]

print("=== EXPORTING STITCH ASSETS ===\n")
all_files = []
html_texts = []
extracted_configs = {}

def parse_tailwind_config(html_str: str) -> dict:
    idx1 = html_str.find("tailwind.config =")
    if idx1 == -1:
        return {}
    idx2 = html_str.find("</script>", idx1)
    raw = html_str[idx1 + len("tailwind.config ="):idx2].strip()
    fixed = re.sub(r'([{,\s])([a-zA-Z0-9_\-]+)\s*:', r'\1"\2":', raw)
    fixed = re.sub(r',\s*([\}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except Exception:
        colors = dict(re.findall(r'"([a-zA-Z0-9_\-]+)"\s*:\s*"([#a-zA-Z0-9]+)"', raw))
        return {"theme": {"extend": {"colors": colors}}}

for sc in SCREENS:
    out_dir = STITCH_DIR / sc["folder"]
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Exporting: {sc['title']} -> docs/stitch/{sc['folder']}/")

    # 1. Download HTML
    req = urllib.request.Request(sc["html_url"], headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        html_bytes = resp.read()
    html_file = out_dir / "screen.html"
    html_file.write_bytes(html_bytes)
    all_files.append(html_file)
    html_str = html_bytes.decode("utf-8", errors="replace")
    html_texts.append(html_str)

    cfg = parse_tailwind_config(html_str)
    if cfg:
        extracted_configs[sc["folder"]] = cfg

    # 2. Download Screenshot
    req = urllib.request.Request(sc["screenshot_url"], headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        img_bytes = resp.read()
    img_file = out_dir / "screenshot.png"
    img_file.write_bytes(img_bytes)
    all_files.append(img_file)

    # 3. Metadata
    meta = {
        "screenId": sc["id"],
        "title": sc["title"],
        "variant": sc["variant"],
        "deviceType": sc["deviceType"],
        "width": sc["width"],
        "height": sc["height"],
        "exportedFrom": f"projects/14287344436665403466/screens/{sc['id']}",
    }
    meta_file = out_dir / "metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    all_files.append(meta_file)

# Build synthesized CSS variables from the tailwind colors, spacing, borderRadius
dark_cfg = extracted_configs.get("ask-dark", {}).get("theme", {}).get("extend", {})
light_cfg = extracted_configs.get("ask-light", {}).get("theme", {}).get("extend", {})

css_variables = {
    ":root (light theme)": {},
    ":root.dark (dark theme)": {},
}

if light_cfg:
    for k, v in light_cfg.get("colors", {}).items():
        css_variables[":root (light theme)"][f"--color-{k}"] = v
    for k, v in light_cfg.get("borderRadius", {}).items():
        css_variables[":root (light theme)"][f"--radius-{k.lower()}"] = v
    for k, v in light_cfg.get("spacing", {}).items():
        css_variables[":root (light theme)"][f"--spacing-{k}"] = v

if dark_cfg:
    for k, v in dark_cfg.get("colors", {}).items():
        css_variables[":root.dark (dark theme)"][f"--color-{k}"] = v
    for k, v in dark_cfg.get("borderRadius", {}).items():
        css_variables[":root.dark (dark theme)"][f"--radius-{k.lower()}"] = v
    for k, v in dark_cfg.get("spacing", {}).items():
        css_variables[":root.dark (dark theme)"][f"--spacing-{k}"] = v

tokens = {
    "project_id": "14287344436665403466",
    "theme_name": "RepoBrain Developer Intelligence",
    "export_note": "Design tokens extracted from Stitch Project designTheme and HTML <script id='tailwind-config'> objects.",
    "color_palette_summary": {
        "primary": "#4f46e5",
        "primary_hover": "#4338ca",
        "secondary": "#0d9488",
        "tertiary": "#7c3aed",
        "neutral_dark": "#131315",
        "neutral_light": "#fafaf9",
        "surface_dark": "#1b1b1d",
        "surface_light": "#ffffff",
        "border_dark": "#3f484e",
        "border_light": "#e7e5e4",
    },
    "entity_taxonomy": {
        "Person": "#2563eb",
        "Team": "#7c3aed",
        "Module": "#0d9488",
        "File": "#64748b",
        "PullRequest": "#4f46e5",
        "Issue": "#ea580c",
        "Comment": "#94a3b8",
        "Document": "#b45309",
        "Decision": "#db2777",
    },
    "semantic_tones": {
        "verified": "#16a34a",
        "stale": "#d97706",
        "error": "#dc2626",
        "neutral": "#71717a",
    },
    "typography": {
        "interface_font": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "mono_font": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        "tokens": {
            "headline-xl": {"fontSize": "24px", "fontWeight": "600", "lineHeight": "32px"},
            "headline-lg": {"fontSize": "20px", "fontWeight": "600", "lineHeight": "28px"},
            "headline-md": {"fontSize": "18px", "fontWeight": "600", "lineHeight": "26px"},
            "title-sm": {"fontSize": "15px", "fontWeight": "600", "lineHeight": "22px"},
            "body-default": {"fontSize": "14px", "fontWeight": "400", "lineHeight": "20px"},
            "body-medium": {"fontSize": "14px", "fontWeight": "500", "lineHeight": "20px"},
            "body-compact": {"fontSize": "13px", "fontWeight": "400", "lineHeight": "18px"},
            "mono-default": {"fontSize": "13px", "fontWeight": "400", "lineHeight": "18px"},
            "mono-compact": {"fontSize": "12px", "fontWeight": "400", "lineHeight": "16px"},
            "caption": {"fontSize": "12px", "fontWeight": "400", "lineHeight": "16px"},
            "caption-mono": {"fontSize": "11px", "fontWeight": "500", "lineHeight": "14px"},
        },
    },
    "spacing": {
        "space-xs": "0.25rem",
        "space-sm": "0.5rem",
        "space-md": "0.75rem",
        "space-lg": "1rem",
        "space-xl": "1.5rem",
        "space-2xl": "2rem",
        "gutter": "1rem",
        "gutter-desktop": "1.5rem",
        "margin": "1rem",
        "margin-desktop": "2rem",
    },
    "radii": {
        "sm": "0.25rem",
        "default": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px",
    },
    "css_variables_extracted": css_variables,
    "tailwind_theme_configs_extracted": extracted_configs,
}

tokens_file = STITCH_DIR / "design-tokens.json"
tokens_file.write_text(json.dumps(tokens, indent=2) + "\n", encoding="utf-8")
all_files.append(tokens_file)

print("\n--- EXPORTED FILES & SHA-256 ---")
for f in sorted(all_files):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    rel = f.relative_to(WORKSPACE)
    print(f"{rel}: {h}")

print("\nSTEP 3 Complete!")
