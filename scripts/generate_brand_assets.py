"""Generate the HSPTL five-letter grid monogram SVG assets."""
from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "brand"

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 620" role="img" aria-label="{title}">
<title>{title}</title>
<desc>Five-letter HSPTL monogram arranged as a compact architectural grid: H and S on the first row, P and T on the second, and L on the third.</desc>
<g fill="none" stroke="{ink}" stroke-width="28" stroke-linecap="square" stroke-linejoin="miter">
<path d="M42 42V166 M207 42V166 M42 104H207"/>
<path d="M456 42H294V103H428V166H276"/>
<path d="M42 365V228H160C198 228 217 248 217 286C217 324 198 345 160 345H42"/>
<path d="M366 228V365"/>
<path d="M42 428V568H217"/>
</g>
<path d="M276 228H456" fill="none" stroke="{blue}" stroke-width="28" stroke-linecap="square"/>
</svg>
"""

def svg(ink: str = "#142F40", blue: str = "#205D85", title: str = "HSPTL monogram") -> str:
    return TEMPLATE.format(ink=ink, blue=blue, title=title)

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = {
        "hsptl-mark.svg": svg(),
        "hsptl-mark-compact.svg": svg(title="HSPTL compact monogram"),
        "hsptl-mark-mono-dark.svg": svg("#111827", "#111827", "HSPTL monochrome dark monogram"),
        "hsptl-mark-mono-light.svg": svg("#FFFFFF", "#FFFFFF", "HSPTL monochrome light monogram"),
        "hsptl-favicon.svg": svg(title="HSPTL favicon monogram"),
    }
    for name, content in variants.items():
        (OUT / name).write_text(content, encoding="utf-8")
        if name == "hsptl-mark.svg":
            (ROOT / "frontend" / "public" / name).write_text(content, encoding="utf-8")
        print(f"wrote {name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
