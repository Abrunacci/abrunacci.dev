# abrunacci.dev

Personal landing page of Alejandro Brunacci, served at https://abrunacci.dev.

One static page, hand-written HTML and CSS: no framework, no build step, no
JavaScript, no third-party requests.

## Layout

```
public/            everything that gets published, index.html at the root
  index.html
  styles.css
  favicon.svg
  apple-touch-icon.png
  og-image.png     share preview (1200×630)
tools/
  check_site.py    internal links and publishable-files check (used by CI)
  test_check_site.py tests for check_site.py
  render-images.sh renders og-image.png and apple-touch-icon.png
  *.html           templates for those images
```

Only `public/` is deployed. It must not contain hidden files, except
`.well-known/`.

## Common changes

- **Add a project:** copy one `<li class="project">` block in
  `public/index.html` and edit it.
- **Add the photo:** save a square image (at least 320×320 px) as
  `public/assets/photo.jpg` and replace the placeholder `<div class="avatar …">`
  with the `<img>` shown in the comment right above it.
- **Change the share image or the touch icon:** edit the templates in
  `tools/` and run `CHROME=/path/to/chrome tools/render-images.sh`.

## Checks

The same checks CI runs on every pull request:

```sh
npx --yes html-validate@11.16.0 public tools
python3 -m unittest discover -s tools
python3 tools/check_site.py public
```

To preview locally: `python3 -m http.server -d public 8000`.
