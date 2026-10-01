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
├── index.html              # 主站首页（关于 / 项目 / 联系）
├── offline.html            # 离线回退页（断网且页面未缓存时显示）
├── manifest.webmanifest    # PWA 应用清单（名字、图标、启动方式）
├── sw.js                   # Service Worker（必须在根目录，见下文）
├── assets/
│   ├── style.css           # 液态玻璃 × 海洋风格样式（含深/浅两套主题变量）
│   ├── theme-boot.js       # <head> 内同步应用主题，防刷新时闪色
│   ├── pwa.js              # 注册 Service Worker、更新提示、安装引导
│   ├── prefs.js            # 主题切换 + 阅读进度 + 导入导出
│   ├── offline.js          # 离线页的重试按钮
│   ├── main.js             # 滚动淡入（尊重 prefers-reduced-motion）
│   ├── icons/
│   │   ├── icon.svg        # 应用图标源文件（矢量）
│   │   ├── icon-192.png    # Android 主屏
│   │   ├── icon-512.png    # 高清 / 启动画面
│   │   ├── icon-maskable-512.png  # Android 自适应图标
│   │   └── apple-touch-icon-180.png  # iOS 主屏
│   ├── og-cover.png        # 社交分享封面图（1200×630）
│   ├── og-cover.svg        # 封面图源文件，改后重新导出 png
│   └── favicon.svg         # 站点图标
├── blog/
│   ├── index.html          # 博客列表
│   └── post-*.html         # 文章
├── scripts/
│   ├── check_integrity.py  # 完整性检查（死链 / CSP / PWA 资产）
│   └── build-icons.mjs     # 从 icon.svg 导出各尺寸 PNG
├── tests/                  # 契约测试、逻辑测试、真浏览器测试
├── playwright.config.mjs
├── _headers                # 安全响应头配置，仅 Cloudflare Pages 等平台生效
└── .github/workflows/
    ├── security.yml        # CI：每次 push 自动跑完整性检查
    └── test.yml            # CI：每次 push 自动跑三层测试
```

> `_headers` 在 GitHub Pages 上**不生效**（Pages 不支持自定义响应头），它是为将来迁移到 Cloudflare Pages 等支持该文件的平台准备的。
>
> 🔴 **但 `sw.js` 不受此限制**：Service Worker 由页面里的 JS 注册（`assets/pwa.js`），不依赖响应头，在 GitHub Pages 上可以正常工作。

---

## 设置

导航栏右侧的齿轮图标打开设置面板，提供三项内容：

| 项 | 说明 |
|------|------|
| **外观** | 三档切换：跟随系统 / 深色 / 浅色。显式选择优先于系统设置，刷新后保持 |
| **阅读记录** | 打开过的文章会自动记录，面板里可跳回 |
| **数据** | 导出 / 导入 JSON（换设备时迁移），一键清空（需二次确认） |

**数据只存在你自己浏览器的 localStorage 里**，不上传任何服务器。站点的 CSP 把 `connect-src` 限定为 `'self'`，即只允许向本站自己的域名发请求——没有后端接口可以接收数据，它做不到上传。

几个实现上的取舍，写在代码注释里了，这里重复一遍：

- **主题切换用 class 切换，不用内联样式**。CSP 的 `style-src 'self'` 没有 `unsafe-inline`，任何 `el.style.xxx` 都会触发违规。这是站点一直以来的做法，不是新加的克制。
- **导出是真的下载一个 JSON 文件**，不是复制到剪贴板 —— 剪贴板在无 HTTPS 的环境可能不可用，下载更可靠。
- **清空需要点两次**。第一次是"你确定吗"，4 秒内不确认会自动取消。丢数据的操作值得多一道门。
- **localStorage 被禁用时不报错**（隐私模式、部分企业策略）。功能降级，但站点照常能用。

---

## 离线与安装（PWA）

本站是一个 **PWA**（Progressive Web App，渐进式网页应用）：可以装到桌面/手机主屏，装完之后断网也能读已缓存的页面，二次打开几乎瞬时。

### 装成 App

| 平台 | 怎么装 |
|------|--------|
| 桌面 Chrome / Edge | 地址栏右侧出现安装图标，点一下即可；或菜单 →「安装 xiaoyu-hue」 |
| Android Chrome | 菜单 →「添加到主屏幕」，会提示装成应用 |
| iOS Safari | **不会自动提示**。点「分享」→「添加到主屏幕」。站内会有一条引导条提示这个操作 |

装完后打开没有浏览器地址栏，和原生 App 一样。

### 离线能做什么

以下内容在**首次访问时**就被预缓存下来，断网后可直接打开：

- 首页、博客列表、全部 5 篇文章
- 全部样式与脚本、图标

访问**没缓存过的**页面时（例如分享链接里的新文章），会显示一个离线提示页，上面列出可离线阅读的文章。

> 注意「首次访问就被缓存」的含义：如果你是第一次访问本站，而当时正好断网，那么什么都打不开。离线能力来自上一次成功访问时留下的缓存。

### 缓存版本与更新

`sw.js` 顶部有一个版本号：

```js
const CACHE_VERSION = 'v1';
```

**发布新内容后，把这个数字加一**（`v1` → `v2`），用户下次访问时 Service Worker 会丢掉旧缓存、重新抓取，并弹出「有新版本可用」的提示条。

不改这个数字的话，页面本体（HTML）仍会因为「网络优先」策略而更新，但样式和脚本可能停留在旧版本——所以发版时请一并改掉它。

### 为什么 Service Worker 必须在根目录

Service Worker 的**作用域受它所在路径限制**。放在 `assets/sw.js` 时，作用域会被限制在 `/assets/` 下，**拦不到页面导航**——站点看起来"注册成功了"，但离线打不开任何页面，而且控制台不报错。

所以 `sw.js` 只能放在仓库根目录。完整性检查脚本会在它被放错位置时直接报错。

### 想彻底清掉本站的缓存

- 浏览器开发者工具 → Application → Service Workers → Unregister
- 同页面 Storage → 清除本地存储
- 或者直接卸载装好的 App

### 实现上的三个取舍

- **HTML 走网络优先，绝不用缓存优先**。缓存优先会让用户永远看不到新文章，而且极难自查。
- **不无条件调用 `skipWaiting()`**。无条件调用会在用户正读文章时把页面换成新版本。必须由用户点「立即更新」后才切换。
- **`og-cover.png` 不放进预缓存**。它有 500KB，是给社交平台爬虫看的，用户浏览时不加载它——放进预缓存等于让每个访客白下载半兆。

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

> **测 PWA 功能必须用 `http://localhost:8000`，不能用 `http://127.0.0.1:8000` 之外的 IP。**
> Service Worker 只在「安全上下文」下工作：HTTPS，或 localhost。用局域网 IP（如 `192.168.x.x`）访问时，SW 会静默注册失败，离线功能不可用——这是浏览器的安全限制，不是站点的问题。

---

## 测试

站点本身依然**零依赖** —— 下面的工具只在你要改代码时用来验证，访问和部署站点都不需要。

```bash
python3 -m unittest discover -s tests -t .   # 契约层：只要 python3
node --test 'tests/js/**/*.test.mjs'         # 逻辑层：需要 Node 18+
npx playwright test                          # 真浏览器层：需要 Node，先跑 npm ci
```

| 层 | 管什么 |
|------|--------|
| 契约层 | 8 个页面的 head、页脚签名、导航、CSP 是否与 `_headers` 一致；文章卡片与文章是否同步；PWA 清单合法性与图标真实尺寸；Service Worker 是否在根目录、预缓存清单有没有死链；完整性检查脚本自己是否还抓得到问题 |
| 逻辑层 | 滚动淡入的四条分支（正常观察 / 用户开了「减少动画」/ 不支持 IntersectionObserver / 没有 matchMedia）；Service Worker 的请求分流（导航 / 静态资源 / 其他）与跨域、非 GET 放行 |
| 真浏览器层 | 页面真的渲染了吗、CSS 和 JS 有没有被 CSP 拦掉、动效真的触发了吗、375px 下有没有元素溢出；Service Worker 注册、**断网后能否打开首页与文章**、未缓存页面是否回退到离线页 |

每次 push 到 `main`，CI 会自动跑完三层。

---

## 更新站点

- 改 `index.html` 可更新项目卡片、关于与联系方式
- 新增文章：复制 `blog/post-1.html` 改内容，再往 `blog/index.html` 加一张 `.post-card`
- 新增文章后，**记得把新文件加进 `sw.js` 的 `PRECACHE` 清单**，否则该文章离线时打不开（完整性检查会抓到清单里的死链，但不会告诉你"少了一篇"）
- **发版时把 `sw.js` 的 `CACHE_VERSION` 加一**
- 推到 `main` 分支后，GitHub Pages 会自动部署

改了图标源文件 `assets/icons/icon.svg` 后，重新导出各尺寸：

```bash
node scripts/build-icons.mjs
```

---

## 关于作者

没有编程背景，所有代码由 AI Agent 辅助完成。协作规则（需求先确认、任务拆小步、如实标注做不到什么）写在博客第一篇文章里。

> 一半烟火以谋生，一半诗意以谋爱。

---

## 许可证

[MIT](LICENSE) © 2026 xiaoyu-hue
