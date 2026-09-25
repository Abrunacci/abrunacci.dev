# abrunacci.dev

Personal landing page of Alejandro Brunacci, served at https://abrunacci.dev.

One static page built with [Astro](https://astro.build): the output is plain
HTML with its CSS inline, no JavaScript and no third-party requests.

## Layout

```
src/
  pages/index.astro   the page
  styles/global.css   its styles, inlined into the page by the build
  data/projects.yaml  the projects it lists
  content.config.ts   schema of projects.yaml, checked by the build
  components/
    Avatar.astro      the photo, or a monogram while there is none
  assets/photo.*      the photo, optional (see below)
public/               copied as is to the root of the site
  favicon.svg
  apple-touch-icon.png
  og-image.png        share preview (1200×630)
dist/                 the built site (not committed)
tools/
  check_site.py       internal links and publishable-files check (used by CI)
  test_check_site.py  tests for check_site.py
  render-images.sh    renders og-image.png and apple-touch-icon.png
  *.html              templates for those images
```

`npm run build` writes the site to `dist/`, and that is what gets deployed.
It must not contain hidden files, except `.well-known/`.

The server caches everything under `/assets/` for a year, so a file there must
never change under the same name. Only the build writes there, with a content
hash in every name (`photo.4f8cjK8z_Ny5af.avif`). `tools/check_site.py` fails
on a file under `assets/` without one, and if `public/assets/` exists.

## Common changes

- **Add a project:** add an entry to `src/data/projects.yaml`. The build
  fails if a field is missing, unknown or not an `https://` URL.
- **Add the photo:** save a square image (at least 256×256 px) as
  `src/assets/photo.jpg` (or `.jpeg`, `.png`, `.webp`, `.avif`). Nothing else
  changes: the page shows it instead of the monogram, and the build writes
  resized AVIF and WebP copies to `/assets/`.
- **Change the share image or the touch icon:** edit the templates in
  `tools/` and run `CHROME=/path/to/chrome tools/render-images.sh`.

## Contact address

The page publishes `hello@abrunacci.dev`. That mailbox does not exist on its
own: Cloudflare Email Routing forwards it to a personal inbox, and that rule is
managed in the [infra](https://github.com/Abrunacci/infra) repo together with
the root domain. The routing has to be live before this page is published, or
mail sent from it bounces.

## Deploy

`.github/workflows/deploy.yml` publishes the site to https://abrunacci.dev on
every push to `main`, or by hand from the Actions tab (**Run workflow**, on
`main`):

1. **Check** builds the site, runs the same checks as CI and keeps `dist/` as
   the run's artifact.
2. **Deploy to production** waits for approval in the `production`
   environment. Then it sends that artifact as a tar over SSH to the server,
   where a key that can only deploy this site publishes it as a new release.
3. It then checks that the site serves the root and every file of `dist/`
   byte for byte, and fails the run if not.

If the checks or the upload fail, what was published before stays
published. If only the last check fails, the new release is already live:
fix it and push again, or roll it back on the server (`site-rollback`, run by
the admin; CI cannot).

Runs go one at a time: a run waiting for approval holds back the ones pushed
after it, and a newer waiting run replaces an older one, so the latest push
wins.

**Before the first deploy**, the server side must be ready: this project
(`abrunacci-dev`) in the infra repo's `projects.yml` with its `deploy_key`,
applied, and the `production` environment set up with required reviewers,
`main` as its only branch, and two secrets, `DEPLOY_SSH_KEY` and
`DEPLOY_KNOWN_HOSTS`. Otherwise GitHub creates the environment on the first
run, without protection, and the deploy fails. How to create the key and the
secrets and how to set up the environment, and the server's rules for what a
release may contain, are documented in the
[infra](https://github.com/Abrunacci/infra) repo, "Deploying a project" in
`ansible/README.md`.

To redeploy an earlier commit, open its Deploy run and choose **Re-run all
jobs**: the checks run again on that commit, with that commit's workflow, and
it is sent as a new release. GitHub allows it for 30 days; after that, push a
revert instead. The same applies when an approval comes more than 7 days
late: the run's artifact is gone, so re-run all jobs.

## Development

Needs Node.js 22.22+ or 24.8+ (CI uses 24) and Python 3.12 or later.

```sh
npm ci            # install the exact versions in package-lock.json
npm run dev       # live preview at http://localhost:4321
npm run build     # build the site into dist/
npm run preview   # serve dist/ as it will be published
```

## Checks

The same checks CI runs on every pull request, after `npm run build`:

```sh
npx --no html-validate dist tools
python3 -m unittest discover -s tools
python3 tools/check_site.py dist
```
