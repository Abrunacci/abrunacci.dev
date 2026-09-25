# abrunacci.dev

Personal landing page of Alejandro Brunacci, served at https://abrunacci.dev.

One static page, hand-written HTML and CSS: no framework, no build step, no
JavaScript, no third-party requests.

## Layout

```
public/               everything that gets published, index.html at the root
  index.html
  styles.css
  favicon.svg
  apple-touch-icon.png
  og-image.png        share preview (1200×630)
tools/
  check_site.py       internal links and publishable-files check (used by CI)
  test_check_site.py  tests for check_site.py
  render-images.sh    renders og-image.png and apple-touch-icon.png
  *.html              templates for those images
```

Only `public/` is deployed. It must not contain hidden files, except
`.well-known/`.

## Common changes

- **Add a project:** copy one `<li class="project">` block in
  `public/index.html` and edit it.
- **Add the photo:** save a square image (at least 320×320 px) as
  `public/img/photo.jpg` and replace the placeholder `<div class="avatar …">`
  with the `<img>` shown in the comment right above it. Keep files that may
  change under the same name out of `public/assets/`: the server caches
  everything there for a year, as files whose names change with their
  content.
- **Change the share image or the touch icon:** edit the templates in
  `tools/` and run `CHROME=/path/to/chrome tools/render-images.sh`.

## Contact address

The page publishes `hello@abrunacci.dev`. That mailbox does not exist on its
own: Cloudflare Email Routing forwards it to a personal inbox, and that rule is
managed in the [infra](https://github.com/Abrunacci/infra) repo together with
the root domain. The routing has to be live before this page is published, or
mail sent from it bounces.

## Deploy

`.github/workflows/deploy.yml` publishes `public/` to https://abrunacci.dev on
every push to `main`, or by hand from the Actions tab (**Run workflow**, on
`main`). There is no build step:

1. **Check** runs the same checks as CI and keeps `public/` as the run's
   artifact.
2. **Deploy to production** waits for approval in the `production`
   environment. Then it sends that artifact as a tar over SSH to the server,
   where a key that can only deploy this site publishes it as a new release.
3. It then checks that the site serves the root and every file of `public/`
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

## Checks

The same checks CI runs on every pull request:

```sh
npx --yes html-validate@11.16.0 public tools
python3 -m unittest discover -s tools
python3 tools/check_site.py public
```

To preview locally: `python3 -m http.server -d public 8000`.
