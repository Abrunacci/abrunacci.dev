#!/usr/bin/env python3
"""Checks the publishable directory before it is deployed.

- The site root exists and has an index.html.
- Every internal reference in an HTML file (href, src, srcset, and the share
  metadata og:image, og:url and twitter:image) points to a file that exists
  under the site root. References to https://abrunacci.dev count as internal.
- Every url(...) in a CSS file or in a <style> element points to a file that
  exists.
- Every fragment link (#id) points to an element with that id in the target
  page. Legacy <a name> anchors are not recognised.
- There are no hidden files or directories, except .well-known/ at the root.
- Every file under assets/ has a content hash in its name (name.HASH.ext):
  the server caches assets/ for a year, so a file there must never change
  under the same name.
- There are no symbolic links: the server rejects them, and the CI artifact
  would carry whatever they point to on the runner instead.

Usage: tools/check_site.py [SITE_DIR]   (default: dist)
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE_HOST = "abrunacci.dev"
URL_ATTRS = {"href", "src"}
URL_META_KEYS = {"og:image", "og:url", "twitter:image"}
CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")
# What Astro writes to assets/: photo.4f8cjK8z_Ny5af.avif, index.B7Ca1Qx2.css
HASHED_NAME = re.compile(r"\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: set[str] = set()
        # Text of the <style> element being read, None outside one.
        self.style: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "style":
            self.style = []
        values = {name: value or "" for name, value in attrs}
        if "id" in values:
            self.ids.add(values["id"])
        for name in URL_ATTRS & values.keys():
            self.refs.append(values[name])
        if "srcset" in values:
            candidates = values["srcset"].split(",")
            self.refs.extend(c.split()[0] for c in candidates if c.strip())
        meta_key = values.get("property") or values.get("name")
        if tag == "meta" and meta_key in URL_META_KEYS:
            self.refs.append(values.get("content", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self.style is not None:
            self.refs.extend(css_urls("".join(self.style)))
            self.style = None

    def handle_data(self, data: str) -> None:
        if self.style is not None:
            self.style.append(data)


def css_urls(css: str) -> list[str]:
    return [m.group(2) for m in CSS_URL.finditer(css)]


def parse(page: Path) -> PageParser:
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    return parser


def is_internal(ref: str) -> bool:
    parts = urlsplit(ref)
    if not parts.scheme and not parts.netloc:
        return True
    return parts.scheme in {"", "http", "https"} and parts.hostname == SITE_HOST


def resolve(ref: str, source: Path, root: Path) -> tuple[Path, str]:
    """Returns the file an internal ref points to and its fragment."""
    parts = urlsplit(ref)
    path = unquote(parts.path)
    if not path:
        target = source
    elif path.startswith("/"):
        target = root / path.lstrip("/")
    else:
        target = source.parent / path
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target.resolve(), parts.fragment


def check_hidden(root: Path) -> list[str]:
    errors = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        hidden = [i for i, part in enumerate(rel.parts) if part.startswith(".")]
        if hidden and not (hidden == [0] and rel.parts[0] == ".well-known"):
            errors.append(f"{rel}: hidden file or directory outside .well-known/")
    return errors


def check_asset_names(root: Path) -> list[str]:
    return [
        f"{path.relative_to(root)}: no content hash in the name under assets/"
        for path in sorted((root / "assets").rglob("*"))
        if path.is_file() and not HASHED_NAME.search(path.name)
    ]


def check_symlinks(root: Path) -> list[str]:
    return [
        f"{path.relative_to(root)}: symbolic link"
        for path in sorted(root.rglob("*"))
        if path.is_symlink()
    ]


def check_refs(
    source: Path, refs: list[str], root: Path, pages: dict[Path, PageParser]
) -> list[str]:
    errors = []
    rel_source = source.relative_to(root)
    for ref in refs:
        if not is_internal(ref):
            continue
        target, fragment = resolve(ref, source, root)
        if not target.is_relative_to(root):
            errors.append(f"{rel_source}: {ref!r} points outside the site root")
        elif not target.is_file():
            missing = target.relative_to(root)
            errors.append(f"{rel_source}: {ref!r} is broken (no {missing})")
        elif fragment and target in pages and fragment not in pages[target].ids:
            errors.append(f"{rel_source}: {ref!r} points to a missing id")
    return errors


def check_site(root: Path) -> list[str]:
    root = root.resolve()
    if not root.is_dir():
        return [f"{root} is not a directory"]

    errors = check_hidden(root) + check_symlinks(root) + check_asset_names(root)
    if not (root / "index.html").is_file():
        errors.append("index.html is missing at the site root")

    pages = {page.resolve(): parse(page) for page in sorted(root.rglob("*.html"))}
    for page, parsed in pages.items():
        errors += check_refs(page, parsed.refs, root, pages)
    for sheet in sorted(root.rglob("*.css")):
        refs = css_urls(sheet.read_text(encoding="utf-8"))
        errors += check_refs(sheet.resolve(), refs, root, pages)
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    errors = check_site(root)
    for error in errors:
        print(f"error: {error}")
    print(f"checked {root}/: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
