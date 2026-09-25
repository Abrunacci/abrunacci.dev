# Contributing

How changes are made in this repository. The README covers the layout, the
common changes and the deploy.

## Branches and pull requests

- Every change goes through a pull request to `main`; nothing is pushed to
  `main` directly. Merging deploys (after approval in the `production`
  environment).
- One topic per pull request, small enough to review in one sitting. A
  refactor that should not change the page goes in its own pull request,
  separate from visual changes.
- `main` requires the check **Validate HTML and internal links**, the name of
  the job in `.github/workflows/ci.yml`. Do not rename that job without
  updating the ruleset first, or pull requests wait for a check that never
  comes.
- Commit messages, pull request titles and descriptions and review comments
  are in English. Commit subjects are imperative and describe the change
  ("Add the photo to the header"), without a type prefix.

## Before opening a pull request

- Run the checks listed in the README, after `npm run build`.
- If `tools/` changed: `ruff check tools`, `ruff format --check tools` and
  `mypy --strict tools`.
- If the page can look different: capture it at desktop (1440 px) and phone
  (390 px) widths, in light and dark mode, and compare with `main`. A change
  that should not alter the page must produce the same pixels.
- Keep it accessible: text contrast of at least 4.5:1 (3:1 for large text and
  for borders of controls), a visible focus on everything that can be
  focused, and a text alternative for every image that carries information.

## Dependencies

- Versions are exact in `package.json` and locked in `package-lock.json`;
  install with `npm ci`.
- Install scripts are disabled (`.npmrc`). A dependency that needs one has to
  be approved explicitly.
- The published page ships no JavaScript. Adding any is a decision for its own
  pull request, stating its size and why it is worth it.

## Caching

The server caches `/assets/` for a year. Only the build writes there, with a
content hash in every file name; `tools/check_site.py` fails otherwise. Files
in `public/` keep their names and are published outside `/assets/`.
