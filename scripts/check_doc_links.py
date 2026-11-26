"""
Checks every relative link in the project's Markdown files: the target file or folder must exist,
and a #anchor must match a heading in the target file (GitHub-style anchors).

    python scripts/check_doc_links.py

Exits with code 1 and lists the broken links if any are found. Web links (http/https/mailto) are skipped.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "node_modules", ".git", "staticfiles"}
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)")
CODE_BLOCK = re.compile(r"```.*?```", re.S)


def slug(heading):
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path):
    text = CODE_BLOCK.sub("", path.read_text(encoding="utf-8"))
    return {slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.*)$", text, re.M)}


def main():
    md_files = [p for p in ROOT.rglob("*.md") if not SKIP_DIRS & set(p.relative_to(ROOT).parts)]
    broken = []
    checked = 0
    for md in md_files:
        text = CODE_BLOCK.sub("", md.read_text(encoding="utf-8"))
        for match in LINK.finditer(text):
            target = match.group(1) or match.group(2)
            if re.match(r"^(https?:|mailto:)", target):
                continue
            checked += 1
            file_part, _, anchor = target.partition("#")
            dest = (md.parent / file_part).resolve() if file_part else md
            if not dest.exists():
                broken.append(f"{md.relative_to(ROOT)}: {target} (file not found)")
            elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                broken.append(f"{md.relative_to(ROOT)}: {target} (heading not found)")
    if broken:
        print("Broken links:")
        print("\n".join(f"  {b}" for b in broken))
        sys.exit(1)
    print(f"All {checked} relative links in {len(md_files)} Markdown files are OK.")


if __name__ == "__main__":
    main()
