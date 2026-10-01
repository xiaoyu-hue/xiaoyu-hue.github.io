# xiaoyu-hue.github.io

> Personal site — four open-source projects built by a non-programmer with AI agents, plus an honest record of the experiment

**English · [中文](./README.md)**

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-48cae4?style=flat-square)](https://xiaoyu-hue.github.io/)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
[![Build](https://img.shields.io/badge/build-none-6B728C?style=flat-square)](https://github.com/xiaoyu-hue/xiaoyu-hue.github.io)

**Live site: <https://xiaoyu-hue.github.io/>**

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
├── index.html          # Home (about / projects / contact)
├── assets/
│   ├── style.css       # Liquid glass × ocean theme
│   ├── main.js         # Scroll reveal (respects prefers-reduced-motion)
│   └── favicon.svg     # Site icon
├── blog/
│   ├── index.html      # Blog index
│   └── post-*.html     # Articles
├── scripts/
│   └── check_integrity.py   # Integrity check (links / CSP / third-party)
├── tests/              # Contract, logic, and real-browser tests
├── playwright.config.mjs
├── _headers            # Security headers; applies on Cloudflare Pages-style hosts
└── .github/workflows/
    ├── security.yml    # CI: runs the integrity check on every push
    └── test.yml        # CI: runs the three test layers on every push
```

> `_headers` has **no effect on GitHub Pages** (Pages does not support custom response headers). It is included for a future move to a host that supports it, such as Cloudflare Pages.

---

## Settings

The gear icon at the right of the nav bar opens a settings panel with three things:

| Item | What it does |
|------|--------------|
| **Appearance** | Three-way switch: follow system / dark / light. An explicit choice overrides the system setting and survives reload |
| **Reading log** | Articles you open are recorded automatically; the panel links back to them |
| **Data** | Export / import JSON (to move between devices), and a reset button (requires a second click) |

**Your data stays in your own browser's localStorage** and is never uploaded anywhere — that is not a promise, it is a physical constraint: the site's CSP includes `connect-src 'none'`, so the browser blocks every network request. Uploading is not possible.

A few trade-offs, also documented in the code comments:

- **Theme switching uses class toggling, never inline styles.** The `style-src 'self'` CSP has no `unsafe-inline`, so any `el.style.xxx` triggers a violation. This is how the site has always worked, not new restraint.
- **Export downloads a real JSON file** rather than copying to the clipboard — the clipboard may be unavailable without HTTPS; a download is more reliable.
- **Resetting takes two clicks.** The first asks "are you sure"; if you don't confirm within 4 seconds it cancels itself. Destructive actions deserve a second door.
- **A disabled localStorage does not throw** (private mode, some corporate policies). The feature degrades; the site keeps working.

---

## Local preview

**No build step, no dependencies.** You do not need Node.js or anything installed:

```bash
git clone https://github.com/xiaoyu-hue/xiaoyu-hue.github.io.git
cd xiaoyu-hue.github.io
# Just double-click index.html, or serve it:
python3 -m http.server 8000
```

Chrome or Edge recommended.

---

## Tests

The site itself stays **dependency-free** — the tools below are only for verifying changes. You do not need any of them to visit or deploy the site.

```bash
python3 -m unittest discover -s tests -t .   # contract layer: needs python3 only
node --test 'tests/js/**/*.test.mjs'         # logic layer: needs Node 18+
npx playwright test                          # real browser: needs Node, run `npm ci` first
```

| Layer | What it covers |
|-------|----------------|
| Contract | `<head>` of all 7 pages, footer signature, nav, whether the CSP still matches `_headers`; whether post cards and articles stay in sync; whether the integrity checker itself still catches problems |
| Logic | The four branches of the scroll reveal: normal observation / user prefers reduced motion / browser lacks IntersectionObserver / browser lacks matchMedia |
| Real browser | Does the page actually render? Did CSP block CSS or JS? Does the reveal really fire? Does anything overflow at 375px? |

Every push to `main` runs all three layers in CI.

---

## Updating the site

- Edit `index.html` to update project cards, the about section, and contact info
- To add an article: copy `blog/post-1.html`, change the content, then add a `.post-card` to `blog/index.html`
- Pushing to `main` triggers an automatic GitHub Pages deploy

---

## About the author

No programming background; all code was produced with AI agent assistance. The collaboration rules used (confirm requirements before starting, break large tasks into verifiable steps, state honestly what cannot be done) are described in the first blog post.

> 一半烟火以谋生，一半诗意以谋爱 *(Half for a living, half for love)*

---

## License

[MIT](LICENSE) © 2026 xiaoyu-hue
