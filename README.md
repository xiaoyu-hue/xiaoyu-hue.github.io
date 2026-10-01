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
│   ├── style.css       # 液态玻璃 × 海洋风格样式（含深/浅两套主题变量）
│   ├── theme-boot.js   # <head> 内同步应用主题，防刷新时闪色
│   ├── prefs.js        # 主题切换 + 阅读进度 + 导入导出
│   ├── main.js         # 滚动淡入（尊重 prefers-reduced-motion）
│   ├── og-cover.png    # 社交分享封面图（1200×630）
│   ├── og-cover.svg    # 封面图源文件，改后重新导出 png
│   └── favicon.svg     # 站点图标
├── blog/
│   ├── index.html      # 博客列表
│   └── post-*.html     # 文章
├── scripts/
│   └── check_integrity.py   # 完整性检查（死链 / CSP / 第三方资源）
├── tests/              # 契约测试、逻辑测试、真浏览器测试
├── playwright.config.mjs
├── _headers            # 安全响应头配置，仅 Cloudflare Pages 等平台生效
└── .github/workflows/
    ├── security.yml    # CI：每次 push 自动跑完整性检查
    └── test.yml        # CI：每次 push 自动跑三层测试
```

> `_headers` 在 GitHub Pages 上**不生效**（Pages 不支持自定义响应头），它是为将来迁移到 Cloudflare Pages 等支持该文件的平台准备的。

---

## 设置

导航栏右侧的齿轮图标打开设置面板，提供三项内容：

| 项 | 说明 |
|------|------|
| **外观** | 三档切换：跟随系统 / 深色 / 浅色。显式选择优先于系统设置，刷新后保持 |
| **阅读记录** | 打开过的文章会自动记录，面板里可跳回 |
| **数据** | 导出 / 导入 JSON（换设备时迁移），一键清空（需二次确认） |

**数据只存在你自己浏览器的 localStorage 里**，不上传任何服务器 —— 这不是承诺，是物理约束：站点的 CSP 含 `connect-src 'none'`，浏览器会拦截任何网络请求，它做不到上传。

几个实现上的取舍，写在代码注释里了，这里重复一遍：

- **主题切换用 class 切换，不用内联样式**。CSP 的 `style-src 'self'` 没有 `unsafe-inline`，任何 `el.style.xxx` 都会触发违规。这是站点一直以来的做法，不是新加的克制。
- **导出是真的下载一个 JSON 文件**，不是复制到剪贴板 —— 剪贴板在无 HTTPS 的环境可能不可用，下载更可靠。
- **清空需要点两次**。第一次是"你确定吗"，4 秒内不确认会自动取消。丢数据的操作值得多一道门。
- **localStorage 被禁用时不报错**（隐私模式、部分企业策略）。功能降级，但站点照常能用。

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

## 测试

站点本身依然**零依赖** —— 下面的工具只在你要改代码时用来验证，访问和部署站点都不需要。

```bash
python3 -m unittest discover -s tests -t .   # 契约层：只要 python3
node --test 'tests/js/**/*.test.mjs'         # 逻辑层：需要 Node 18+
npx playwright test                          # 真浏览器层：需要 Node，先跑 npm ci
```

| 层 | 管什么 |
|------|--------|
| 契约层 | 7 个页面的 head、页脚签名、导航、CSP 是否与 `_headers` 一致；文章卡片与文章是否同步；完整性检查脚本自己是否还抓得到问题 |
| 逻辑层 | 滚动淡入的四条分支：正常观察 / 用户开了「减少动画」/ 浏览器不支持 IntersectionObserver / 浏览器没有 matchMedia |
| 真浏览器层 | 页面真的渲染了吗、CSS 和 JS 有没有被 CSP 拦掉、动效真的触发了吗、375px 下有没有元素溢出 |

每次 push 到 `main`，CI 会自动跑完三层。

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
