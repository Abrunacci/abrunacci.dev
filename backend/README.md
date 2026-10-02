# Contact form backend

The contact form of https://abrunacci.dev: it serves the form page and mails each message to
the inbox through [Resend](https://resend.com). The rest of the site stays static; Caddy sends
`/contact` and `/api/*` here.

The page works without JavaScript or cookies: a plain HTML form that posts to `/api/contact`.

## Routes

| Route | What it does |
| --- | --- |
| `GET /contact` | The form, with a fresh time token. |
| `GET /contact?status=sent` | The confirmation. |
| `POST /api/contact` | Receives the form (`application/x-www-form-urlencoded`). See below. |
| `GET /api/contact` | Redirects to the form (someone opened the post address by hand). |
| `GET /api/health` | `200 {"status": "ok"}` while the process is up. Nothing else to check. |
| `GET /api/static/…` | The Inter font file, the same one the landing uses. |

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
5. **Spam mark.** More than 2 links, a link in the name, or link markup (HTML or BBCode) puts
   `[posible spam]` in the subject (`spam.py`). It is still mailed.
6. **Daily limit.** 20 mails a day (Argentina time). Past that, the message is accepted and
   written to the log instead of mailed, and one notice a day says so.
7. **Mail.** Subject `[abrunacci.dev] <name>`, `Reply-To` the sender, so a reply in the inbox
   goes straight to them. If Resend fails, the person sees the form again with their text and
   an error, and can retry.

A discarded message gets the same confirmation page as a good one, so a bot cannot tell what
stopped it. Every outcome is one JSON line in the log (`event`: `sent`, `held`, `discarded`
with its `reason`, or `send_failed`); all but `sent` carry the whole message, so none is lost.

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
| `MAIL_TO` | yes | Where messages go. |
| `MAIL_SUBJECT_PREFIX` | no | Default `[abrunacci.dev]`. |
| `SITE_URL` | no | Default `https://abrunacci.dev`; the pages link back to it. |
| `TRUSTED_PROXY` | no | Caddy's container name, as Docker's DNS knows it. Empty: `X-Forwarded-For` is never read. |

The app refuses to start when a required one is missing, naming the variable and never its value.

## Development

Needs [uv](https://docs.astral.sh/uv/) and Python 3.13.

```sh
cd backend
uv sync
uv run pytest
uv run mypy
uv run ruff check .
uv run ruff format --check .
```

To try the pages locally, with a fake key (sending then fails, and the form shows its error):

```sh
RESEND_API_KEY=fake FORM_SECRET=$(openssl rand -hex 32) MAIL_FROM=test@example.com \
  MAIL_TO=test@example.com uv run uvicorn contact.app:create_app --factory --port 8000
```

Then open http://localhost:8000/contact.

The font in `src/contact/static/` is copied from the `@fontsource-variable/inter` version in the
root `package.json` (its version is in the file name); copy it again when that package changes.
