"""Tests for check_site.py. Run with: python3 -m unittest discover tools"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from check_site import check_public_assets, check_site, main

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<title>t</title>
<link rel="stylesheet" href="/styles.css">
<meta property="og:image" content="https://abrunacci.dev/og.png">
</head>
<body><h1 id="top">t</h1>{body}</body>
</html>
"""


class CheckSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "public"
        self.root.mkdir()
        self.write("styles.css", "body { color: red; }")
        self.write("og.png", "")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, content: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def page(self, body: str = "", name: str = "index.html") -> None:
        self.write(name, PAGE.format(body=body))

    def errors(self) -> list[str]:
        return check_site(self.root)

    def assert_one_error(self, fragment: str) -> None:
        errors = self.errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(fragment, errors[0])

    def test_valid_site_passes(self) -> None:
        self.page(
            '<a href="#top">top</a> <a href="/">home</a> <a href="https://example.com">x</a>'
            ' <a href="mailto:a@b.c">mail</a> <a href="sub/">sub</a> <a href="sub/#s">s</a>'
        )
        self.page(
            '<h2 id="s">s</h2><a href="../index.html#top">up</a>', "sub/index.html"
        )
        self.write(".well-known/security.txt", "Contact: mailto:a@b.c")
        self.assertEqual(self.errors(), [])

    def test_missing_root(self) -> None:
        self.tmp.cleanup()
        self.assert_one_error("is not a directory")

    def test_empty_root(self) -> None:
        for path in self.root.iterdir():
            path.unlink()
        self.assert_one_error("index.html is missing")

    def test_broken_relative_link(self) -> None:
        self.page('<img src="assets/photo.jpg" alt="">')
        self.assert_one_error("'assets/photo.jpg' is broken")

    def test_broken_srcset(self) -> None:
        self.page('<img src="og.png" srcset="og.png 1x, og@2x.png 2x" alt="">')
        self.assert_one_error("'og@2x.png' is broken")

    def test_missing_fragment(self) -> None:
        self.page('<a href="#contact">contact</a>')
        self.assert_one_error("points to a missing id")

    def test_directory_without_index(self) -> None:
        self.write("sub/file.txt", "")
        self.page('<a href="sub/">sub</a>')
        self.assert_one_error("is broken")

    def test_link_outside_root(self) -> None:
        self.page('<a href="../secret.txt">x</a>')
        self.assert_one_error("outside the site root")

    def test_own_domain_variants_are_internal(self) -> None:
        for ref in (
            "https://abrunacci.dev/nope.png",
            "HTTPS://ABRUNACCI.DEV/nope.png",
            "http://abrunacci.dev:443/nope.png",
            "//abrunacci.dev/nope.png",
        ):
            with self.subTest(ref=ref):
                self.page(f'<a href="{ref}">x</a>')
                self.assert_one_error("is broken")

    def test_twitter_image_by_name(self) -> None:
        self.page('<meta name="twitter:image" content="/nope.png">')
        self.assert_one_error("is broken")

    def test_broken_css_url(self) -> None:
        self.page()
        self.write("styles.css", "body { background: url('missing.png'); }")
        self.assert_one_error("styles.css: 'missing.png' is broken")

    def test_broken_url_in_style_element(self) -> None:
        self.page('<style>@font-face { src: url("fonts/x.woff2"); }</style>')
        self.assert_one_error("index.html: 'fonts/x.woff2' is broken")

    def test_url_in_style_element_resolves_from_the_page(self) -> None:
        self.write("fonts/x.woff2", "")
        self.page("<style>@font-face { src: url(fonts/x.woff2); }</style>")
        self.assertEqual(self.errors(), [])

    def test_assets_need_a_hash_in_the_name(self) -> None:
        self.page()
        self.write("assets/photo.4f8cjK8z_Ny5af.avif", "")
        self.write("assets/index.B7Ca1Qx2.css", "")
        self.assertEqual(self.errors(), [])
        for name in ("assets/photo.jpg", "assets/img/photo.v2.jpg"):
            with self.subTest(name=name):
                self.write(name, "")
                self.assert_one_error(f"{name}: no content hash")
                (self.root / name).unlink()

    def test_public_assets_must_not_exist(self) -> None:
        public = Path(self.tmp.name) / "repo-public"
        public.mkdir()
        self.assertEqual(check_public_assets(public), [])
        (public / "assets").mkdir()
        self.assertEqual(len(check_public_assets(public)), 1)

    def test_main_checks_public_assets(self) -> None:
        self.page()
        public = Path(self.tmp.name) / "repo-public"
        (public / "assets").mkdir(parents=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check_site.py", str(self.root)], public), 1)
            (public / "assets").rmdir()
            self.assertEqual(main(["check_site.py", str(self.root)], public), 0)

    def test_url_in_style_element_of_a_subpage(self) -> None:
        self.write("fonts/x.woff2", "")
        self.page(
            '<style>@font-face { src: url("../fonts/x.woff2"); }</style>',
            "sub/index.html",
        )
        self.page()
        self.assertEqual(self.errors(), [])
        self.page(
            '<style>@font-face { src: url("fonts/x.woff2"); }</style>', "sub/index.html"
        )
        self.assert_one_error("sub/index.html: 'fonts/x.woff2' is broken")

    def test_hidden_files(self) -> None:
        self.page()
        for name in (".env", "sub/.well-known/x", ".well-known/.secret"):
            with self.subTest(name=name):
                self.write(name, "")
                self.assertTrue(any("hidden" in e for e in self.errors()))
                (self.root / name).unlink()

    def test_symlinks(self) -> None:
        self.page()
        os.symlink("styles.css", self.root / "link.css")
        os.symlink(self.root, self.root / "loop")
        errors = self.errors()
        self.assertEqual(
            errors, ["link.css: symbolic link", "loop: symbolic link"], errors
        )


if __name__ == "__main__":
    unittest.main()
