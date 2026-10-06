# abrunacci.dev

Personal landing page of Alejandro Brunacci, served at https://abrunacci.dev.

One static page, in English at `/` and in Spanish at `/es/`, built with
[Astro](https://astro.build): the output is plain
HTML with its CSS inline, one font file (Inter, self-hosted from the
`@fontsource-variable/inter` package), one small inline script (the dots of the
projects carousel on phones, about 0.6 KB) and no third-party requests.

## Layout

```
src/
  pages/index.astro   the page in English, at /
  pages/es/index.astro  the page in Spanish, at /es/
  i18n/               every text of the page, one file per language (see
                      CONTRIBUTING.md, "Language")
  styles/global.css   its styles, inlined into the page by the build
  data/projects.yaml  the projects it lists, with a summary per language
  content.config.ts   schema of projects.yaml, checked by the build and by
                      npm run check
  components/
    Page.astro        the page itself, in the language its route passes
    Avatar.astro      the photo, or a monogram while there is none
    Icon.astro        inline SVG icons (mail, GitHub, LinkedIn, arrow)
  assets/photo.*      the photo, optional (see below)
public/               copied as is to the root of the site
  favicon.svg
  apple-touch-icon.png
  og-image.png        share preview (1200×630), og-image-es.png in Spanish
  robots.txt          lets crawlers in and points them to the sitemap
  sitemap.xml         the pages search engines should index
dist/                 the built site (not committed)
backend/              the contact form's service (FastAPI): serves /contact
                      and /api/*, mails each message; see backend/README.md
docs/deploy.md        how the site and the backend are deployed
tools/
  check_site.py       internal links and publishable-files check (used by CI)
  test_check_site.py  tests for check_site.py
  render-images.sh    renders the share images and apple-touch-icon.png
  *.html              templates for those images
```

The availability line under the photo is in `src/i18n/` (an empty one hides
it); the list of technologies in the header is a constant at the top of
`src/components/Page.astro`.

`npm run build` writes the site to `dist/`, and that is what gets deployed.
It must not contain hidden files, except `.well-known/`.

The server caches everything under `/assets/` for a year, so a file there must
never change under the same name. Only the build writes there, with a content
hash in every name (`photo.4f8cjK8z_Ny5af.avif`,
`fonts/cb13050e68e771d7.woff2`). `tools/check_site.py` fails on a file under
`assets/` without one, and if `public/assets/` exists.

## Common changes

- **Add a project:** add an entry to `src/data/projects.yaml`, with its
  summary in English and Spanish. The build fails if a field is missing,
  unknown or not an `https://` URL. Its `stack`
  lists only what the project really uses.
- **Add the photo:** save a square image (at least 800×800 px) as
  `src/assets/photo.jpg` (or `.jpeg`, `.png`, `.webp`, `.avif`). Nothing else
  changes: the page shows it instead of the monogram, and the build writes
  resized AVIF and WebP copies to `/assets/`, up to 624 px wide for
  high-density screens.
- **Add a page:** list its URL in `public/sitemap.xml` if search engines
  should index it. `/contact` is left out on purpose: it is a form with
  nothing to find by searching.
- **Change a text:** edit it in `src/i18n/en.ts` and `src/i18n/es.ts`; the
  contact form's are in `backend/src/contact/texts.py`.
- **Change the share image or the touch icon:** edit the templates in
  `tools/` (the Spanish texts of the share image are in the script at the
  end of `og-image.html`) and run `CHROME=/path/to/chrome tools/render-images.sh` (after
  `npm ci`: the templates load Inter from `node_modules/`). The favicon is
  `public/favicon.svg`, edited by hand.

## Contact form

The contact buttons link to `/contact` (`/contact?lang=es` on `/es/`), the
form served by `backend/` (see `backend/README.md`); Caddy sends `/contact` and `/api/*` there, and
everything else is this static site. The page shows no email address.

The form mails each message to `hello@abrunacci.dev`. That mailbox does not
exist on its own: Cloudflare Email Routing forwards it to a personal inbox, and
that rule is managed in the [infra](https://github.com/Abrunacci/infra) repo
together with the root domain.

## Deploy

`.github/workflows/deploy.yml` deploys on every push to `main`, after approval
in the `production` environment: first the backend's image, by digest, then
`dist/` as the site. [`docs/deploy.md`](docs/deploy.md) covers the workflow,
the image, the backend's configuration, what the server expects and what to
do when a deploy fails.

## Development

Needs Node.js 22.22+ or 24.8+ (CI uses 24) and Python 3.12 or later.

```sh
npm ci            # install the exact versions in package-lock.json
npm run dev       # live preview at http://localhost:4321
npm run build     # build the site into dist/
npm run preview   # serve dist/ as it will be published
```

## Checks

The same checks CI runs on every pull request. The type check runs on the
sources; the others, after `npm run build`:

```sh
npm run check     # astro check: types in src/, including the content schema
npx --no html-validate dist tools
python3 -m unittest discover -s tools
python3 tools/check_site.py dist
```
