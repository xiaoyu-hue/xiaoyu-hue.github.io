# xiaoyu-hue.github.io

**[English](./README.en.md) · 中文**

> 个人主站 · 一个非程序员用 AI Agent 做出的四个项目,以及一份诚实的实验记录

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-在线访问-48cae4?style=flat-square)](https://xiaoyu-hue.github.io/)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
[![零构建](https://img.shields.io/badge/构建-无-6B728C?style=flat-square)](https://github.com/xiaoyu-hue/xiaoyu-hue.github.io)

**在线访问：<https://xiaoyu-hue.github.io/>**

---

## 这是什么

一个不会写代码的人，把 AI Agent 当成生产工具，做出了四个开源项目。

这个站点用来回答一个问题：**一个没有编程背景的人，能被 AI 推到哪一步？**

它不是作品集展示页，而是一份**可验证的实验记录**——每个项目都如实标注了自己做不到什么、哪些场景不该用、哪些判断还没经过专业验证。

> 代码是 AI 写的，判断是我做的。

---

## 四个项目

| 项目 | 一句话 | 技术栈 | 协议 |
|------|--------|--------|------|
| 🌊 [sonder520](https://github.com/xiaoyu-hue/sonder520) | 本地个人工作与生活管理工具，数据只存浏览器 | 原生 JS · PWA · 零依赖 | MIT |
| ✦ [Nymir](https://github.com/xiaoyu-hue/Nymir) | 匿名树洞 · P2P 加密聊天 · 阅读即焚 | React 19 · TypeScript · WebRTC | AGPL-3.0 |
| 💎 [xy-club](https://github.com/xiaoyu-hue/xy-club) | 可复用的俱乐部官网模板 + 可视化后台 | Node.js · Express | MIT |
| 🪪 [xy-intro-card](https://github.com/xiaoyu-hue/xy-intro-card) | 个人介绍名片生成器，双击即用 | 原生 HTML/CSS/JS 单文件 | MIT |

四个项目都可以直接在线体验，链接在各项目的仓库里。

---

## 目录结构

```
xiaoyu-hue.github.io/
├── index.html          # 主站首页（关于 / 项目 / 联系）
├── assets/
│   ├── style.css       # 液态玻璃 × 海洋风格样式
│   └── main.js         # 滚动淡入（尊重 prefers-reduced-motion）
├── blog/
│   ├── index.html      # 博客列表
│   └── post-*.html     # 文章
├── scripts/
│   └── check_integrity.py   # 完整性检查（死链 / CSP / 第三方资源）
├── docs/
│   └── EDGE_SETUP.md   # 边缘层配置说明（可选增强）
├── _headers            # 安全响应头配置，仅 Cloudflare Pages 等平台生效
└── .github/workflows/
    └── security.yml    # CI：每次 push 自动跑完整性检查
```

> `_headers` 在 GitHub Pages 上**不生效**（Pages 不支持自定义响应头），它是为将来迁移到 Cloudflare Pages 等支持该文件的平台准备的。详见 `docs/EDGE_SETUP.md`。

---

## 本地预览

**零构建、零依赖**，不需要 Node.js、不需要安装任何东西：

```bash
git clone https://github.com/xiaoyu-hue/xiaoyu-hue.github.io.git
cd xiaoyu-hue.github.io
# 双击 index.html，或用任意静态服务器：
python3 -m http.server 8000
```

推荐 Chrome / Edge。

---

## 安全

本站是纯静态站点：无后端、无数据库、无登录态、不收集访客数据。已实施的防护：

- **零第三方资源** —— 不加载任何外部 CDN（已移除 Google Fonts）
- **严格 CSP** —— 以 `<meta http-equiv>` 下发，不含 `unsafe-inline` / `unsafe-eval`
- **CI 自检** —— 每次 push 自动校验死链、CSP 一致性、第三方资源与内联脚本回归

**已知局限**：GitHub Pages 不支持自定义响应头，因此 HSTS、`X-Frame-Options`、`nosniff` 等**均无法设置**；`frame-ancestors` 在 meta 形式下会被浏览器忽略，防点击劫持能力实际缺失。完整清单见 [SECURITY.md](SECURITY.md)，补齐方案见 [docs/EDGE_SETUP.md](docs/EDGE_SETUP.md)。

漏洞报告请走 GitHub 私有漏洞报告（仓库 → Security → Advisories）。

---

## 更新站点

- 改 `index.html` 可更新项目卡片、关于与联系方式
- 新增文章：复制 `blog/post-1.html` 改内容，再往 `blog/index.html` 加一张 `.post-card`
- 推到 `main` 分支后，GitHub Pages 会自动部署

---

## 关于作者

没有编程背景，所有代码由 AI Agent 辅助完成。协作规则（需求先确认、任务拆小步、如实标注做不到什么）写在博客第一篇文章里。

> 一半烟火以谋生，一半诗意以谋爱。

---

## 许可证

[MIT](LICENSE) © 2026 xiaoyu-hue
