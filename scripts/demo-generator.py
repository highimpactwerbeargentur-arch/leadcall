#!/usr/bin/env python3
"""Demo-Generator für Vorschau-Formulare.

Usage:
    python scripts/demo-generator.py "Firmenname" pfad/zum/logo.png
"""

import re
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "kunden" / "_template"
TEMPLATE_HTML = TEMPLATE_DIR / "index.html"
KUNDEN_DIR = REPO_ROOT / "kunden"


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = (s.replace("ä", "ae")
           .replace("ö", "oe")
           .replace("ü", "ue")
           .replace("ß", "ss"))
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: demo-generator.py <Firmenname> <Logo-Pfad>", file=sys.stderr)
        return 2

    firmenname = sys.argv[1]
    logo_src = Path(sys.argv[2])

    if not logo_src.is_file():
        print(f"Logo nicht gefunden: {logo_src.as_posix()}", file=sys.stderr)
        return 1

    if not TEMPLATE_HTML.is_file():
        print(f"Template fehlt: {TEMPLATE_HTML.as_posix()}", file=sys.stderr)
        return 1

    slug = slugify(firmenname)
    if not slug:
        print(f"Slug aus '{firmenname}' ist leer", file=sys.stderr)
        return 1

    target_dir = KUNDEN_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    html = TEMPLATE_HTML.read_text(encoding="utf-8")
    html = html.replace("{{FIRMENNAME}}", firmenname)
    (target_dir / "index.html").write_text(html, encoding="utf-8")

    shutil.copyfile(logo_src, target_dir / "logo.png")

    print(f"https://leadcall24.de/kunden/{slug}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
