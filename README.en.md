# xiaoyu-hue.github.io

> Personal site — four open-source projects built by a non-programmer with AI agents, plus an honest record of the experiment

**English · [中文](./README.md)**

[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare%20Pages-Primary-F38020?style=flat-square)](https://xiaoyu-hue-github-io.pages.dev/)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Mirror-48cae4?style=flat-square)](https://xiaoyu-hue.github.io/)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
[![Build](https://img.shields.io/badge/build-none-6B728C?style=flat-square)](https://github.com/xiaoyu-hue/xiaoyu-hue.github.io)

**Primary site: <https://xiaoyu-hue-github-io.pages.dev/>**

**Mirror: <https://xiaoyu-hue.github.io/>** — same content, see [Deployment: primary site and mirror](#deployment-primary-site-and-mirror)

---

## What this is

Someone with no programming background decided to treat AI agents as a production tool — and shipped four open-source projects.

This site exists to answer one question: **how far can AI push someone who has never written code?**

It is not a portfolio. It is a **verifiable record of an experiment** — every project states plainly what it cannot do, which scenarios it should not be used in, and which judgment calls have not been professionally validated.

> The code was written by AI. The decisions were mine.

---

## The four projects

| Project | One-liner | Stack | License |
|---------|-----------|-------|---------|
| 🌊 [sonder520](https://github.com/xiaoyu-hue/sonder520) | Personal work and life manager; data never leaves your browser | Vanilla JS · PWA · zero-dependency | MIT |
| ✦ [Nymir](https://github.com/xiaoyu-hue/Nymir) | Anonymous tree hole · P2P encrypted chat · burn after reading | React 19 · TypeScript · WebRTC | AGPL-3.0 |
| 💎 [xy-club](https://github.com/xiaoyu-hue/xy-club) | Reusable club website template with a visual admin panel | Node.js · Express | MIT |
| 🪪 [xy-intro-card](https://github.com/xiaoyu-hue/xy-intro-card) | Personal intro card generator — just double-click | Single-file HTML/CSS/JS | MIT |

All four are live; links are in each repository.

---

## Structure

```
xiaoyu-hue.github.io/
├── index.html              # Home (about / projects / contact)
├── offline.html            # Offline fallback page
├── manifest.webmanifest    # PWA app manifest (name, icons, launch mode)
├── sw.js                   # Service Worker (must live at the root, see below)
├── assets/
│   ├── style.css           # Liquid glass × ocean theme (dark + light variables)
│   ├── theme-boot.js       # Applies theme inside <head> to avoid a flash
│   ├── pwa.js              # Service Worker registration, update prompt, install hint
│   ├── prefs.js            # Theme, reading log, import/export
│   ├── offline.js          # Retry button on the offline page
│   ├── main.js             # Scroll reveal (respects prefers-reduced-motion)
│   ├── icons/              # App icons (svg source + generated PNGs)
│   ├── og-cover.png        # Social share cover (1200×630)
│   └── favicon.svg         # Site icon
├── blog/
│   ├── index.html          # Blog index
│   └── post-*.html         # Articles
├── scripts/
│   ├── check_integrity.py  # Integrity check (links / CSP / PWA assets)
│   └── build-icons.mjs     # Exports PNG icons from icon.svg
├── tests/                  # Contract, logic, and real-browser tests
├── playwright.config.mjs
├── _headers                # Security headers; applies on Cloudflare Pages-style hosts
└── .github/workflows/
    ├── security.yml    # CI: runs the integrity check on every push
    └── test.yml        # CI: runs the three test layers on every push
```

> `_headers` only takes effect on the **primary site (Cloudflare Pages)**: CSP, X-Frame-Options, COOP, Permissions-Policy and the rest are all delivered from it.
>
> 🟡 **The mirror (GitHub Pages) cannot serve custom response headers** — a platform limit, not a config mistake. Measured directly, the mirror returns HSTS and nothing else.
>
> **That does not mean the mirror is unprotected.** The CSP lives in a `<meta http-equiv>` tag on every page, so both sites enforce the same script and style restrictions. What is actually missing is only the set of headers that *cannot* be expressed via `<meta>` (see [What actually differs](#what-actually-differs)) — and of those, the one with real consequences is clickjacking protection: `frame-ancestors` delivered through `<meta>` is ignored by browsers, so the mirror cannot stop someone embedding it in an iframe. Treat the primary site's headers as authoritative.
>
> 🔴 **`sw.js` is not affected by that limitation.** A Service Worker is registered from JavaScript (`assets/pwa.js`), not from response headers, so it works on both sites.

---

## Settings

The gear icon at the right of the nav bar opens a settings panel with three things:

| Item | What it does |
|------|--------------|
| **Appearance** | Three-way switch: follow system / dark / light. An explicit choice overrides the system setting and survives reload |
| **Reading log** | Articles you open are recorded automatically; the panel links back to them |
| **Data** | Export / import JSON (to move between devices), and a reset button (requires a second click) |

**Your data stays in your own browser's localStorage** and is never uploaded anywhere. The site's CSP restricts `connect-src` to `'self'`, meaning requests may only go to the site's own origin — there is no backend that could receive your data.

A few trade-offs, also documented in the code comments:

- **Theme switching uses class toggling, never inline styles.** The `style-src 'self'` CSP has no `unsafe-inline`, so any `el.style.xxx` triggers a violation. This is how the site has always worked, not new restraint.
- **Export downloads a real JSON file** rather than copying to the clipboard — the clipboard may be unavailable without HTTPS; a download is more reliable.
- **Resetting takes two clicks.** The first asks "are you sure"; if you don't confirm within 4 seconds it cancels itself. Destructive actions deserve a second door.
- **A disabled localStorage does not throw** (private mode, some corporate policies). The feature degrades; the site keeps working.

---

## Offline & install (PWA)

This site is a **PWA** (Progressive Web App): it can be installed to your desktop or phone home screen, then works offline for cached pages and opens almost instantly on repeat visits.

### Install it as an app

| Platform | How |
|----------|-----|
| Desktop Chrome / Edge | An install icon appears in the address bar; or menu → "Install xiaoyu-hue" |
| Android Chrome | Menu → "Add to Home screen" |
| iOS Safari | **No automatic prompt.** Tap Share → "Add to Home Screen". The site shows a hint bar for this |

Once installed, it opens without a browser address bar, like a native app.

### What works offline

The following is pre-cached on your **first visit** and opens without a network:

- Home, blog index, all 5 articles
- All styles, scripts, and icons

Visiting a page that was **never cached** shows an offline notice listing the articles you can read offline.

> Note what "pre-cached on first visit" implies: if your very first visit happens while offline, nothing will load. Offline support comes from the cache left by a previous successful visit.

### Cache version and updates

`sw.js` starts with a version constant:

```js
const CACHE_VERSION = 'v1';
```

**After publishing new content, bump this number** (`v1` → `v2`). On the user's next visit the Service Worker drops the old cache, re-fetches, and shows a "new version available" bar.

If you don't bump it, the HTML itself still updates (it is network-first), but styles and scripts may stay on the old version — so change it whenever you publish.

### Why the Service Worker must be at the root

A Service Worker's **scope is limited by its path**. At `assets/sw.js` its scope would be confined to `/assets/`, so it would **never see page navigations** — registration appears to succeed, yet nothing works offline, and the console stays silent.

So `sw.js` must live at the repository root. The integrity checker fails loudly if it is moved.

### Clearing the cache completely

- DevTools → Application → Service Workers → Unregister
- Same panel → Storage → clear local storage
- Or just uninstall the installed app

### Three implementation trade-offs

- **HTML is network-first, never cache-first.** Cache-first would hide new articles forever, and it is very hard to self-diagnose.
- **`skipWaiting()` is never called unconditionally.** Doing so would swap the page out from under someone mid-read. It only switches after the user clicks "Update now".
- **`og-cover.png` is excluded from the precache.** It is 500KB, aimed at social crawlers, and never loaded during normal browsing — precaching it would make every visitor download half a megabyte for nothing.

---

## Local preview

**No build step, no dependencies.** You do not need Node.js or anything installed:

```bash
git clone https://github.com/xiaoyu-hue/xiaoyu-hue.github.io.git
cd xiaoyu-hue.github.io
# Just double-click index.html, or serve it:
python3 -m http.server 8000
```

> **Testing PWA features requires `http://localhost:8000`, not a LAN IP.**
> Service Workers only run in a secure context: HTTPS, or localhost. Over a LAN IP (e.g. `192.168.x.x`) registration fails silently and offline mode is unavailable — that is a browser security rule, not a site bug.

Chrome or Edge recommended.

---

## Deployment: primary site and mirror

One repository, two automatic deployments, always in sync:

| Role | URL | Platform |
|------|-----|----------|
| **Primary** | <https://xiaoyu-hue-github-io.pages.dev/> | Cloudflare Pages |
| **Mirror** | <https://xiaoyu-hue.github.io/> | GitHub Pages |

**Both are wired to the same GitHub repository.** One push to `main` builds each of them. Nothing to sync by hand, no version drift — the two home pages hash identically.

### Why keep the mirror

Not for the comfort of the word "backup", but because the two have **different failure domains**: if Cloudflare has a bad day, GitHub Pages is still up; if GitHub goes down, the already-deployed static copies keep serving from Cloudflare's edge — only new builds are blocked. The redundancy is real, and it costs nothing to maintain.

### What actually differs

| | Primary | Mirror |
|---|---------|--------|
| CSP | Yes (response header + page `<meta>`) | **Yes** (page `<meta>`) |
| Anti-framing (`frame-ancestors` / `X-Frame-Options`) | Yes | **No** — `<meta>` delivery is ignored by browsers, and the mirror cannot send headers |
| `X-Content-Type-Options: nosniff` | Yes | No |
| `Cross-Origin-Opener-Policy` | Yes | No |
| `Referrer-Policy` | Yes | No |
| `Permissions-Policy` | Yes | No |
| `Strict-Transport-Security` | Yes | Yes |
| The `_headers` file | Applied, not exposed | **Publicly downloadable** as a static file (it only contains header config, nothing sensitive) |
| HTTP/3 | Yes | No |
| Edge | Global Anycast | Single region |
| Custom domain | Supported | Supported, still no custom headers |
| PWA / offline | Works | Works |

These rows come from measuring both sites, not from copying platform docs. **Only the anti-framing gap has real consequences**: the mirror could be embedded in someone else's iframe (a clickjacking vector). The rest matter little on a static site with no login and no forms — this one sets `form-action 'none'` and serves no dynamic content that would need `nosniff` as a backstop.

### Two things that bite

- **Canonical URLs point at the primary site.** Every page's `<link rel="canonical">` and `og:url` uses the primary domain, so search engines do not treat the two sites as duplicate content. Links to the sub-projects (`/sonder520/`, `/Nymir/`, `/xy-club/`, `/xy-intro-card/`) **stay on `github.io`** — those are separate GitHub Pages projects and do not exist under `pages.dev`.
- **To check whether both are in sync**, compare home page hashes:

  ```bash
  curl -s https://xiaoyu-hue-github-io.pages.dev/ | md5sum
  curl -s https://xiaoyu-hue.github.io/ | md5sum
  ```

  Identical output means the mirror has not fallen behind.

---

## Tests

The site itself stays **dependency-free** — the tools below are only for verifying changes. You do not need any of them to visit or deploy the site.

```bash
python3 -m unittest discover -s tests -t .   # contract layer: needs python3 only
node --test 'tests/js/**/*.test.mjs'         # logic layer: needs Node 18+
npx playwright test                          # real browser: needs Node, run `npm ci` first
```

The real-browser layer includes an **accessibility baseline** (`tests/e2e/a11y.spec.mjs`, built on axe-core). It covers what static review cannot: whether two hex colours in a CSS file actually clear the contrast threshold is invisible to code reading — you need a browser and colour-space maths. This site had exactly that problem live (`--text-faint` on `--abyss` measured 4.347:1 against a 4.5:1 requirement). The scan covers every page × light/dark themes, plus the settings panel while it is open.

axe lives in devDependencies only — **the site itself still ships zero runtime dependencies**. It has no extra Node requirement (axe-core asks for Node 4+), so CI's existing Node 20 runs it fine.

| Layer | What it covers |
|-------|----------------|
| Contract | `<head>` of all 8 pages, footer signature, nav, whether the CSP still matches `_headers`; whether post cards and articles stay in sync; PWA manifest validity and real icon dimensions; whether `sw.js` sits at the root and whether the precache list has dead links; whether the integrity checker itself still catches problems |
| Logic | The four branches of the scroll reveal (normal / reduced motion / no IntersectionObserver / no matchMedia); Service Worker request routing (navigation vs asset vs other) and its bypass rules for cross-origin and non-GET |
| Real browser | Does the page actually render? Did CSP block CSS or JS? Does the reveal really fire? Does anything overflow at 375px? Also: Service Worker registration, **whether the home page and articles open while offline**, and whether uncached pages fall back to the offline page; plus an **accessibility baseline** — contrast, semantics and ARIA across every page × light/dark themes, and inside the settings panel while it is open |

Every push to `main` runs all three layers in CI.

---

## Updating the site

- Edit `index.html` to update project cards, the about section, and contact info
- To add an article: copy `blog/post-1.html`, change the content, then add a `.post-card` to `blog/index.html`
- After adding an article, **add the new file to `sw.js`'s `PRECACHE` list**, otherwise it will not open offline (the integrity check catches dead links in the list, but it cannot tell you something is *missing*)
- **Bump `CACHE_VERSION` in `sw.js` whenever you publish**
- Pushing to `main` triggers an automatic deploy on **both the primary site and the mirror** (see [Deployment](#deployment-primary-site-and-mirror))

After editing the icon source `assets/icons/icon.svg`, regenerate the PNGs:

```bash
node scripts/build-icons.mjs
```

---

## About the author

No programming background; all code was produced with AI agent assistance. The collaboration rules used (confirm requirements before starting, break large tasks into verifiable steps, state honestly what cannot be done) are described in the first blog post.

> 一半烟火以谋生，一半诗意以谋爱 *(Half for a living, half for love)*

---

## License

[MIT](LICENSE) © 2026 xiaoyu-hue
