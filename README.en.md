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
│   └── main.js         # Scroll reveal (respects prefers-reduced-motion)
├── blog/
│   ├── index.html      # Blog index
│   └── post-*.html     # Articles
├── scripts/
│   └── check_integrity.py   # Integrity check (links / CSP / third-party)
├── docs/
│   └── EDGE_SETUP.md   # Edge layer setup (optional hardening)
├── _headers            # Security headers; applies on Cloudflare Pages-style hosts
└── .github/workflows/
    └── security.yml    # CI: runs the integrity check on every push
```

> `_headers` has **no effect on GitHub Pages** (Pages does not support custom response headers). It is included for a future move to a host that supports it, such as Cloudflare Pages. See `docs/EDGE_SETUP.md`.

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

## Security

This is a purely static site: no backend, no database, no login state, no visitor data collected. Measures in place:

- **Zero third-party resources** — nothing is loaded from an external CDN (Google Fonts has been removed)
- **Strict CSP** — delivered via `<meta http-equiv>`, with no `unsafe-inline` / `unsafe-eval`
- **CI self-check** — every push verifies dead links, CSP consistency, third-party resources, and inline-script regressions

**Known limitations:** GitHub Pages does not support custom response headers, so `X-Frame-Options`, `nosniff`, and `Permissions-Policy` **cannot be set**; `frame-ancestors` is ignored by browsers when delivered via meta, so clickjacking protection is effectively absent. (HSTS is an exception — GitHub sends it for all `*.github.io` domains, no configuration needed.) Full list in [SECURITY.md](SECURITY.md); how to close the gap in [docs/EDGE_SETUP.md](docs/EDGE_SETUP.md).

Report vulnerabilities via GitHub private vulnerability reporting (repo → Security → Advisories).

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
