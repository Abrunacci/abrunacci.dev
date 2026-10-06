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
- Every commit is authored by Alejandro Brunacci, with no `Co-Authored-By`
  trailer or attribution line. The required job checks it in its step
  **Check commit metadata**, a composite action from the
  [infra](https://github.com/Abrunacci/infra) repo pinned to a commit SHA;
  its README there lists the rules.
- Commit messages, pull request titles and descriptions and review comments
  are in English. Commit subjects are imperative and describe the change
  ("Add the photo to the header"), without a type prefix.

## Before opening a pull request

- Run the checks listed in the README: the type check on the sources, the
  others after `npm run build`.
- If `tools/` changed: `ruff check tools`, `ruff format --check tools` and
  `mypy --strict tools`.
- If `backend/` changed: the checks in `backend/README.md` (pytest, mypy and
  ruff, with uv). CI runs them in the job **Backend tests and lint**, and
  builds the image in **Backend image**.
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
- The published page ships one small inline script: the dots of the projects
  carousel on phones (about 0.6 KB, no dependencies). Everything else works
  without it. Adding more is a decision for its own pull request, stating its
  size and why it is worth it.
- The contact page, served by the backend, loads its own script
  (`backend/src/contact/static/form.js`, under 1 KB) and Cloudflare Turnstile.
  Without JavaScript it hides the form and offers the email address instead.

## Dependabot

`.github/dependabot.yml` opens version updates once a month, for npm and for
the GitHub Actions in the workflows, skipping releases younger than 7 days:

- npm minor and patch updates come together in one pull request; each major
  comes alone.
- All action updates come together. Actions are pinned to commit SHAs with
  the version in a comment, and Dependabot updates both.
- Majors of `typescript` are ignored until `@astrojs/check` supports them.

Security updates are enabled in the repository settings and arrive at any
time.

Their pull requests are reviewed like any other: the required check has to
pass, and merging deploys after approval. Before merging, also:

- Read the release notes of what changed, majors especially.
- For `astro` or `@fontsource-variable/inter`: build `main` and the branch,
  compare `dist/` (`diff -r`), and if it differs, compare screenshots at 320,
  390 and 1440 px in light and dark mode. A new Inter file gets a new hashed
  name, so the year-long cache under `/assets/` stays safe.
- For a major of `@astrojs/check` or `html-validate`: expect new findings, and
  fix them in the same pull request or a separate one before merging.
- When an update needs another package updated too (a major of `astro` that
  needs a newer `@astrojs/check` or `typescript`), they arrive in separate
  pull requests and the first one can fail the required check. Update the
  other package by hand on the same Dependabot branch
  (`npm i -E <pkg>@<version>`), commit, and let the check run again. Do not
  merge them separately.
- For actions: check that the version comment matches the pinned SHA's
  release.

## Caching

The server caches `/assets/` for a year. Only the build writes there, with a
content hash in every file name; `tools/check_site.py` fails otherwise, and if
`public/assets/` exists. Files in `public/` keep their names and are published
outside `/assets/`.
