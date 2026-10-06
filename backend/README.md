# Contact form backend

The contact form of https://abrunacci.dev: it serves the form page and mails each message to
the inbox through [Resend](https://resend.com). The rest of the site stays static; Caddy sends
`/contact` and `/api/*` here.

The page is a plain HTML form that posts to `/api/contact`, with no cookies of its own. It runs
[Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) to tell people from bots,
so sending needs JavaScript. Without it, the form is hidden and the page offers
hello@abrunacci.dev instead.

## Routes

| Route | What it does |
| --- | --- |
| `GET /contact` | The form, with a fresh time token. |
| `GET /contact?status=sent` | The confirmation. |
| `POST /api/contact` | Receives the form (`application/x-www-form-urlencoded`). See below. |
| `GET /api/contact` | Redirects to the form (someone opened the post address by hand). |
| `GET /api/health` | `200 {"status": "ok"}` while the process is up. Nothing else to check. |
| `GET /api/static/…` | The Inter font file, the same one the landing uses, and `form.js`. |

## What happens to a message

In this order:

1. **Honeypot.** A field hidden off screen (`website`). A person never fills it; a bot that
   fills every field does. The message is discarded.
2. **Time trap.** The form carries the time it was opened, signed with `FORM_SECRET`
   (`form_token.py`). A message sent less than 3 seconds after opening, or with a token older
   than 24 hours, or with a signature that does not match, is discarded.
3. **Fields.** Name, a plausible email address and a message, within their lengths. If one is
   wrong, the form comes back with the person's text and a sentence under that field.
4. **Per-sender limit.** 5 messages an hour per IPv4 address, or per IPv6 /64 block
   (`client_ip.py`, `limits.py`). Past that, discarded.
5. **Turnstile.** The token Cloudflare's widget put in the form is checked with siteverify
   (`turnstile.py`), after the checks above so a bot they catch costs no call. Cloudflare says
   no, or there is no token: discarded. No usable answer within 5 seconds (a timeout, a network
   error, a 5xx, an `internal-error`), or Cloudflare says the secret is wrong: the message goes
   on and is mailed with `[sin verificar]` in the subject. A bot cannot make Cloudflare fail,
   and the other traps and the daily limit still apply.
6. **Spam mark.** More than 2 links, a link in the name, or link markup (HTML or BBCode) puts
   `[posible spam]` in the subject (`spam.py`). It is still mailed.
7. **Daily limit.** 20 mails a day (Argentina time). Past that, the person sees the form again
   with their text and is asked to try again tomorrow, and one notice a day says so.
8. **Mail.** Subject `[abrunacci.dev] <name>`, `Reply-To` the sender, so a reply in the inbox
   goes straight to them. If Resend fails, the person sees the form again with their text and
   an error, and can retry.

A discarded message gets the same confirmation page as a good one, so a bot cannot tell what
stopped it.

Every outcome is one JSON line in the log: `event` (`sent`, `discarded`, `daily_limit` or
`send_failed`), `reason` when there is one (why it was discarded, or Resend's error with the
sender's name and email blanked out), a random `id`, the `time` (UTC) and the message's
`length`. Turnstile adds `reason` values `turnstile: <Cloudflare's error codes>` (discarded)
and `turnstile_unavailable: <what went wrong>` (a `sent` that Turnstile could not check).
Nothing from the form is logged, nor the visitor's address: a discarded message is
gone, and in every other case the person either got through or still has their text on the
form.

### Turnstile on the page

The widget runs in Managed mode with `interaction-only` appearance: nothing shows unless
Cloudflare wants a click. `form.js` loads Cloudflare's script and keeps "Send message" disabled
until the widget hands over a token (again after a token expires). If the script cannot load
or the widget fails, it shows "You can also write to me directly at hello@abrunacci.dev." under
the form. Without JavaScript, a `<noscript>` style hides the form and shows that line instead.

The page's `Content-Security-Policy` (in `app.py`) allows scripts from itself and from
`https://challenges.cloudflare.com`, and frames from the latter, where the check runs. Nothing
else. It replaces Caddy's default CSP.

The visitor's address is not sent to siteverify.

### The visitor's address

Caddy passes it in `X-Forwarded-For`. The header is read only when the connection comes from
the container named in `TRUSTED_PROXY` (Caddy's container name); from any other peer it is
ignored and the connection's own address counts. Caddy must not have `trusted_proxies`, so it
replaces whatever header the visitor sent.

The name is resolved by Docker's DNS, which answers with Caddy's address on the network it
shares with this container, whatever that network is called. It is looked up again every
minute, and sooner (at most every 5 seconds) when a connection comes from an address it does
not know, so a recreated Caddy is recognized within seconds.

### State in memory

The per-sender counts and the day's count live in memory and start over when the container
restarts (a deploy, a rollback, a reboot). At worst that lets one more day's quota through on a
day with a deploy. `FORM_SECRET` is not in memory: it comes from the server, so a form opened
before a deploy still works after it.

## Configuration

| Variable | Required | Meaning |
| --- | --- | --- |
| `RESEND_API_KEY` | yes | A Resend key with sending access only. Secret. |
| `FORM_SECRET` | yes | At least 32 characters; signs the time token. Secret, generated on the server. |
| `MAIL_FROM` | yes | The sender, on the domain verified in Resend, e.g. `Formulario abrunacci.dev <no-reply@mail.abrunacci.dev>`. |
| `MAIL_TO` | yes | Where messages go. Secret, set on the server. |
| `TURNSTILE_SITE_KEY` | yes | The Turnstile widget's site key. Public: it is in the page. |
| `TURNSTILE_SECRET_KEY` | yes | The widget's secret key, for siteverify. Secret, set on the server. |
| `MAIL_SUBJECT_PREFIX` | no | Default `[abrunacci.dev]`. |
| `SITE_URL` | no | Default `https://abrunacci.dev`; the pages link back to it. |
| `TRUSTED_PROXY` | no | Caddy's container name, as Docker's DNS knows it. Empty: `X-Forwarded-For` is never read. |

The app refuses to start when a required one is missing, naming the variable and never its value.

On the server they come from infra's `projects.yml`; where each one is set is in
[`docs/deploy.md`](../docs/deploy.md#the-backends-configuration).

## Development

Needs [uv](https://docs.astral.sh/uv/) and Python 3.13.

```sh
cd backend
uv sync
uv run pytest            # -m "not live" skips the tests that call Cloudflare
uv run mypy
uv run ruff check .
uv run ruff format --check .
```

To try the pages locally, with a fake Resend key (sending then fails, and the form shows its
error) and [Cloudflare's test keys](https://developers.cloudflare.com/turnstile/troubleshooting/testing/):

```sh
RESEND_API_KEY=fake FORM_SECRET=$(openssl rand -hex 32) MAIL_FROM=test@example.com \
  MAIL_TO=test@example.com TURNSTILE_SITE_KEY=1x00000000000000000000AA \
  TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA \
  uv run uvicorn contact.app:create_app --factory --port 8000
```

Then open http://localhost:8000/contact. The test site keys hand out the token
`XXXX.DUMMY.TOKEN.XXXX`, which only the test secret keys accept:

| Site key | Widget |
| --- | --- |
| `1x00000000000000000000AA` | Always passes (visible). |
| `2x00000000000000000000AB` | Always blocks: the email line appears. |
| `1x00000000000000000000BB` | Always passes (invisible). |
| `3x00000000000000000000FF` | Forces a click. |

| Secret key | siteverify |
| --- | --- |
| `1x0000000000000000000000000000000AA` | Always passes: mailed. |
| `2x0000000000000000000000000000000AA` | Always fails: discarded (`turnstile: invalid-input-response`). |
| `3x0000000000000000000000000000000AA` | Token already spent: discarded (`turnstile: timeout-or-duplicate`). |

`tests/test_siteverify_live.py` calls the real siteverify with these secret keys; the other tests
use a fake Cloudflare that answers the same way.

The font in `src/contact/static/` is copied from the `@fontsource-variable/inter` version in the
root `package.json` (its version is in the file name); copy it again when that package changes.
