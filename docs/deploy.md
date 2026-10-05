# Deploy

How the site and the contact form's backend reach the server, what the server
expects from them, and what to look at when a deploy fails.

The server side (the `deploy` user, `deploy-backend`, Caddy, secrets, rollbacks,
monitoring) lives in the [infra](https://github.com/Abrunacci/infra) repo and is
documented in its
[`ansible/README.md`](https://github.com/Abrunacci/infra/blob/main/ansible/README.md):
"Deploying a project", "Deploying a backend", "Backend secrets", "Backend status
and rollbacks", "Backend logs" and "Status page and alerts". This repo's code
decides what is in the workflow, the image and the app; infra decides how the
server runs them. If the two disagree, this page is the one to fix.

## What runs where

| | |
| --- | --- |
| URL | https://abrunacci.dev. `https://www.abrunacci.dev` redirects there (301, keeping path and query). |
| Site | `dist/`, static files served by Caddy. |
| Backend | `backend/`, the image `ghcr.io/abrunacci/abrunacci-dev-backend`, listening on port 8000. |
| Routes to the backend | `/api/*` and `/contact`, with the path unchanged. Everything else is the site. |
| Health | `GET /api/health`; any 2xx is healthy. |
| Database | None. |
| Memory | 128 MB for the backend container, no swap. |
| Infra entry | Project `abrunacci-dev` in infra's `projects.yml`. |

## The workflow

`.github/workflows/deploy.yml` runs on every push to `main`, and by hand from
the Actions tab (**Run workflow**, on `main`). It does not look at what
changed: every run publishes the image and deploys both the backend and the
site.

1. **Check** builds the site, runs the same checks as CI and keeps `dist/` as
   the run's artifact.
2. **Check the backend** runs the backend's tests and linters.
3. **Publish the backend image** builds `backend/` and pushes it to GHCR.
4. **Deploy to production** waits for approval in the `production`
   environment. Then:
   1. It deploys the backend by digest. The server pulls that image, replaces
      the container and asks for `/api/health` from Caddy's container for up
      to 60 seconds. If it gets no 2xx, it puts the previous release back and
      the job fails, before the site is touched.
   2. It sends the site as a tar over SSH. The server checks and extracts it
      as an unprivileged user and only then switches the published site,
      atomically. If anything fails, what was published stays published.
   3. It checks that the site serves the root and every file of `dist/` byte
      for byte, and that `/api/health` answers and `/contact` serves the
      form.

If only the last step fails, the new release is already live: fix it and push
again, or roll it back on the server (the admin runs `site-rollback` or
`backend-rollback`; CI cannot).

Runs go one at a time: a run waiting for approval holds back the ones pushed
after it, and a newer waiting run replaces an older one, so the latest push
wins.

To redeploy an earlier commit, open its Deploy run and choose **Re-run all
jobs**: the checks run again on that commit, with that commit's workflow, and
it goes out as a new release. GitHub allows it for 30 days; after that, push a
revert instead. The same applies when an approval comes more than 7 days late:
the run's artifact is gone, so re-run all jobs.

### SSH

Both deploys log in as `deploy@server.abrunacci.dev` with this project's deploy
key. On the server that key has a forced command: it can only deploy
`abrunacci-dev`, with no shell and no forwarding. CI only chooses which commit
and which image digest.

```sh
ssh deploy@server.abrunacci.dev deploy-backend "$GITHUB_SHA" "sha256:<digest>" "$GITHUB_RUN_ID" </dev/null
tar -C site -cz . | ssh deploy@server.abrunacci.dev deploy "$GITHUB_SHA" "$GITHUB_RUN_ID"
```

The workflow passes `-i <key> -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes
-o BatchMode=yes -o ConnectTimeout=15`, with the server's line from the
`DEPLOY_KNOWN_HOSTS` secret as the only known host. Never
`StrictHostKeyChecking=no`.

### The image

- The publish job has `packages: write` and logs in to `ghcr.io` with
  `GITHUB_TOKEN`.
- What the deploy sends is the `digest` output of the **Build and push** step
  (`docker/build-push-action`): `sha256:` and 64 hex characters, never a tag.
  The deploy job refuses to start without one. The server takes the image's
  name from `projects.yml`, not from CI.
- Each image is also tagged with its commit SHA and `latest`, for people; the
  server never uses tags. It is one manifest, linux/amd64 (no provenance or
  SBOM).
- **The package must stay public.** The server pulls it without logging in; a
  private package fails every deploy with `unauthorized`.
- No version is ever deleted. The server keeps the images of its last releases
  locally, but a rollback on a rebuilt server pulls them from GHCR.

### GitHub settings

- Environment `production`: required reviewer Alejandro, `main` as its only
  branch, and two secrets, `DEPLOY_SSH_KEY` (the private deploy key) and
  `DEPLOY_KNOWN_HOSTS` (the server's `known_hosts` line). Without them set up
  first, GitHub creates the environment on the first run, unprotected, and the
  deploy fails. How to create the key and the line is in infra's guide,
  "Deploying a project".
- Ruleset on `main`: requires the check **Validate HTML and internal links**
  (see `CONTRIBUTING.md`).

## The backend's configuration

Nothing is configured in this repo: every value comes from the server. The
names are declared in infra's `projects.yml`, so adding, removing or renaming
one is a pull request in infra. What each one means is in
[`backend/README.md`](../backend/README.md#configuration).

| Name | Kind | Set by |
| --- | --- | --- |
| `MAIL_FROM` | public, `Formulario abrunacci.dev <no-reply@mail.abrunacci.dev>` | `env` in `projects.yml` |
| `TRUSTED_PROXY` | public, `caddy` | `env` in `projects.yml` |
| `FORM_SECRET` | secret, generated on the server (64 hex characters) | infra's playbook |
| `RESEND_API_KEY` | secret, a Resend key with sending access only | the admin, `project-secret abrunacci-dev set RESEND_API_KEY` |
| `MAIL_TO` | secret | the admin, `project-secret abrunacci-dev set MAIL_TO` |

`MAIL_SUBJECT_PREFIX` and `SITE_URL` are optional and not set on the server:
their defaults are the production values.

- A change reaches the container on the next deploy, or right away with
  `backend-rollback abrunacci-dev --restart` (admin).
- `project-secret abrunacci-dev rotate FORM_SECRET` makes a new one and
  restarts the backend: forms open at that moment stop working.
- A deploy refuses to start if a declared secret is missing, or if one is set
  that `projects.yml` does not declare.
- `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `APP_DB_USER` and
  `APP_DB_PASSWORD` are reserved by infra.

**When the app needs a new variable**, the infra pull request goes first
(merged, applied, and with its value set if it is a secret), then the deploy of
the image that reads it.

## What the server expects from the container

- **Its own user.** It runs as uid/gid 10005, whatever the image says (the
  image's own user, 10001, is only used locally). Never root.
- **A read-only filesystem**, except `/tmp` (tmpfs, emptied on every restart).
- **No capabilities**, `no-new-privileges`, at most 256 processes.
- **Listens on `0.0.0.0:8000`**, with no published ports. Its only network is
  `edge-abrunacci-dev`, shared only with Caddy, which is also its way out to
  Resend.
- **The visitor's address.** Caddy has no `trusted_proxies`, so it always
  writes the real address (IPv4 or IPv6) in `X-Forwarded-For`. On
  `edge-abrunacci-dev`, the name `caddy` resolves to Caddy's address there,
  hence `TRUSTED_PROXY=caddy`. Limits per address group IPv6 by /64.
- **Health.** `/api/health` answers 2xx within 60 seconds of starting. There
  is no Docker healthcheck: a hung process is not restarted; the status page
  notices it (below).
- **Shutdown.** SIGTERM, with 20 seconds of grace. During a deploy Caddy holds
  requests for up to 15 seconds.
- **Headers.** Caddy adds `Strict-Transport-Security` and
  `X-Content-Type-Options` and removes `Server`. `Referrer-Policy` and
  `Content-Security-Policy: frame-ancestors 'none'` are defaults the backend
  replaces with its own.
- **Request bodies** up to 10 MB in Caddy; the backend stops reading at 32 KB.

What the backend keeps in memory (the per-sender and daily limits) starts over
on every deploy, rollback or restart; see
[`backend/README.md`](../backend/README.md#state-in-memory).

### Logs and personal data

The container's stdout and stderr go to the server's journal, tagged
`backend.abrunacci-dev`, within a 1 GB cap for the whole server. The backend
logs one line per message with the event, its reason, an ID, the time and the
message's length, and nothing from the form: no name, email, text or visitor
address (see
[`backend/README.md`](../backend/README.md#what-happens-to-a-message)).
Changing what is logged is something to tell infra, which documents it.

## What the server does with the site

The tar may only hold regular files and directories, with `index.html` at the
root and no hidden files except `.well-known/` at the root. Limits: 25 MB
compressed, 100 MB extracted, 5000 entries, 20 levels deep, 2 minutes to
upload. `tools/check_site.py` checks the hidden files before the upload.

Caddy then:

- **Answers any path that is not a file with `index.html`** (meant for single
  page apps). The site has only its front page and no 404 page of its own, so
  a page that does not exist returns the front page with a 200.
- **Caches `/assets/*` for a year as immutable.** Only the build writes there,
  with a content hash in every name, and `tools/check_site.py` fails
  otherwise (see the README).
- Revalidates everything else on every visit.

## When something fails

In the CI log, the server's message appears as is:

| Message | What happened | What to do |
| --- | --- | --- |
| `Permission denied (publickey)` | The key in `DEPLOY_SSH_KEY` is not the project's `deploy_key` in `projects.yml`. | Check the secret; a new key needs an infra pull request. |
| `Host key verification failed` | `DEPLOY_KNOWN_HOSTS` does not match the server. | Generate it again (infra's guide, "Deploying a project"). |
| `deploy-backend: the backend's secrets are not ready: …` | `RESEND_API_KEY` or `MAIL_TO` is missing, or there is one too many. | Admin: `project-secret abrunacci-dev list`. |
| `deploy-backend: cannot pull …: unauthorized` (or `not found`) | The package is no longer public, or the digest does not exist. | Check the package's visibility in GHCR. |
| `deploy-backend: release … not healthy within 60s (…); back to release …, which is healthy` | The new image did not answer `/api/health`. | Admin: `journalctl -t backend-log`. The container's log never reaches CI. |
| `… which is NOT healthy either` | The previous release is not healthy either. | Urgent. Admin: `backend-status abrunacci-dev`. |
| `another deploy, rollback or secret change of abrunacci-dev is running` | Two operations at once. | Run it again. |
| `deploy: rejected: …` | The site's tar broke a rule above. | The reason is in the message. |

Outside CI:

- Gatus checks `https://abrunacci.dev/` (200) and
  `https://abrunacci.dev/api/health` (2xx) every minute, plus the certificate.
  After 3 failures in a row it mails the admin, and again when it recovers.
  Public page: https://status.abrunacci.dev.
- A failure to send through Resend does not fail `/api/health`: it only shows
  in the log (`send_failed`) and in mails not arriving.
- On the server (admin, with `sudo`): `backend-status abrunacci-dev`,
  `journalctl -t backend.abrunacci-dev --since -1h`, `journalctl -t
  deploy-backend`, `journalctl -t deploy`, `backend-rollback abrunacci-dev`
  (`--list` shows the releases it can go back to) and `site-rollback
  abrunacci-dev`.
