#!/usr/bin/env python3
"""Checks the publishable directory before it is deployed.

- Every internal reference (href, src, srcset, og:image on this site) in an
  HTML file points to a file that exists under the site root.
- Every fragment link (#id) points to an id that exists in the target page.
- There are no hidden files or directories, except .well-known/.

Usage: tools/check_site.py [SITE_DIR]   (default: public)
"""

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE_ORIGIN = "https://abrunacci.dev"
URL_ATTRS = {"href", "src"}
URL_META_PROPERTIES = {"og:image", "og:url", "twitter:image"}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if "id" in values:
            self.ids.add(values["id"])
        for name in URL_ATTRS & values.keys():
            self.refs.append(values[name])
        if "srcset" in values:
            self.refs.extend(c.split()[0] for c in values["srcset"].split(",") if c.strip())
        if tag == "meta" and values.get("property") in URL_META_PROPERTIES:
            self.refs.append(values.get("content", ""))


def parse(page: Path) -> PageParser:
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    return parser


def resolve(ref: str, page: Path, root: Path) -> tuple[Path, str] | None:
    """Returns (target file, fragment) for internal refs, None for external ones."""
    parts = urlsplit(ref)
    if parts.scheme or parts.netloc:
        if f"{parts.scheme}://{parts.netloc}" != SITE_ORIGIN:
            return None
    elif ref.startswith(("mailto:", "tel:", "data:")):
        return None

    path = unquote(parts.path)
    if not path:
        target = page
    elif path.startswith("/"):
        target = root / path.lstrip("/")
    else:
        target = page.parent / path
    if target.is_dir() or path.endswith("/"):
        target = target / "index.html"
    return target, parts.fragment


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "public").resolve()
    errors: list[str] = []

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        hidden = [p for p in rel.parts if p.startswith(".")]
        if hidden and hidden[0] != ".well-known":
            errors.append(f"{rel}: hidden file or directory outside .well-known/")

    pages = {page: parse(page) for page in sorted(root.rglob("*.html"))}
    for page, parsed in pages.items():
        rel_page = page.relative_to(root)
        for ref in parsed.refs:
            resolved = resolve(ref, page, root)
            if resolved is None:
                continue
            target, fragment = resolved
            target = target.resolve()
            if not target.is_relative_to(root):
                errors.append(f"{rel_page}: {ref!r} points outside the site root")
            elif not target.is_file():
                errors.append(f"{rel_page}: {ref!r} is broken (no {target.relative_to(root)})")
            elif fragment and target.suffix == ".html":
                target_ids = pages[target].ids if target in pages else parse(target).ids
                if fragment not in target_ids:
                    errors.append(f"{rel_page}: {ref!r} points to a missing id")

    for error in errors:
        print(f"error: {error}")
    print(f"checked {len(pages)} page(s) in {root.name}/: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
