# xiaoyu-hue.github.io

**[English](./README.en.md) · 中文**

> 个人主站 · 一个非程序员用 AI Agent 做出的四个项目,以及一份诚实的实验记录

[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare%20Pages-主站-F38020?style=flat-square)](https://xiaoyu-hue-github-io.pages.dev/)
[![备用站](https://img.shields.io/badge/GitHub%20Pages-备用站-48cae4?style=flat-square)](https://xiaoyu-hue.github.io/)
[![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)](LICENSE)
[![零依赖](https://img.shields.io/badge/运行时依赖-无-2F855A?style=flat-square)](https://github.com/xiaoyu-hue/xiaoyu-hue.github.io)
[![构建可选](https://img.shields.io/badge/构建-可选%20Python-3776AB?style=flat-square)](https://github.com/xiaoyu-hue/xiaoyu-hue.github.io)

**主站：<https://xiaoyu-hue-github-io.pages.dev/>**

**备用站：<https://xiaoyu-hue.github.io/>** —— 内容与主站一致，见「[部署：主站与备用站](#部署主站与备用站)」

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
├── build.py                # 构建脚本：把 src/ 拼成成品页面。零依赖，只用 Python 标准库
├── src/                    # 构建源码（改站点内容改这里）
│   ├── layouts/base.html   #   页面模板：head / 导航 / 设置面板 / 页脚 / 脚本，全站共用一份
│   ├── pages/*.body.html   #   每个页面的正文片段
│   └── data/               #   site.json（CSP / 主站域名 / 页脚）+ pages.json（每页标题摘要）
├── index.html              # ↓ 以下都是 build.py 的构建产物，直接手改会被下次构建覆盖
├── sitemap.xml             # 给搜索引擎的页面清单（含每篇文章的更新时间）
├── robots.txt              # 爬虫规则 + sitemap 位置（指向主站，与 canonical 一致）
├── feed.xml                # RSS 2.0 全文订阅源，8 篇文章都带正文
├── 404.html                # 404 页面（刻意不写结构化数据，此页不该被索引）
├── offline.html            # 离线回退页（断网且页面未缓存时显示）
├── manifest.webmanifest    # PWA 应用清单（名字、图标、启动方式）
├── sw.js                   # Service Worker（必须在根目录，见下文）
├── docs/                   # 实测记录：结论怎么来的、边界在哪
│   └── csp-jsonld.md       #   CSP 会不会拦掉 JSON-LD 结构化数据（附可复现脚本）
├── assets/
│   ├── style.css           # 液态玻璃 × 海洋风格样式（深/浅双主题 + 微动效系统四层令牌）
│   ├── theme-boot.js       # <head> 内同步应用主题与动效偏好，防刷新时闪色
│   ├── pwa.js              # 注册 Service Worker、更新提示、安装引导
│   ├── prefs.js            # 主题切换 + 动效开关 + 阅读进度 + 导入导出
│   ├── offline.js          # 离线页的重试按钮
│   ├── main.js             # 滚动淡入 + 同组错落编排（尊重所有降级路径）
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
│   ├── verify_csp_jsonld.py  # 实测：严格 CSP 下 JSON-LD 是否可读（需 playwright，可选）
│   └── build-icons.mjs     # 从 icon.svg 导出各尺寸 PNG
├── tests/                  # 契约测试、逻辑测试、真浏览器测试
├── playwright.config.mjs
├── _headers                # 安全响应头配置，仅 Cloudflare Pages 等平台生效
└── .github/workflows/
    ├── security.yml        # CI：每次 push 自动跑完整性检查 + CSP/JSON-LD 实测
    └── test.yml            # CI：每次 push 自动跑三层测试
```

> **这一层决定别人能不能找到你的站点。** 上述 `sitemap.xml` / `robots.txt` / `feed.xml` / `404.html` 与每个页面
> `<head>` 里的 JSON-LD 结构化数据，都由 `build.py` 一并生成，手改会在下次构建时被覆盖。
>
> - **搜索引擎**靠 sitemap 找到页面、靠 JSON-LD 认出「这是谁写的、什么时候发的」
> - **RSS 阅读器**靠 feed.xml 订阅；注意其中的链接已全部转成绝对地址，否则在阅读器里点开是死链
> - **AI 摘要工具**主要读 JSON-LD 这一层，而不是猜正文
>
> JSON-LD 必须内联写在 HTML 里，但本站 CSP 禁止内联脚本——这看起来直接冲突。结论是**不冲突**（详见 [`docs/csp-jsonld.md`](docs/csp-jsonld.md)），那份文档给出了实测过程与结论边界，不是推测。

> `_headers` 只在**主站（Cloudflare Pages）**上生效：CSP、X-Frame-Options、COOP、Permissions-Policy 等全部响应头都由它下发。
>
> 🟡 **备用站（GitHub Pages）不支持自定义响应头**，这是平台限制、改不了——实测备站只返回一个 HSTS，其余响应头一个都没有。
>
> 但**这不等同于备站在裸奔**：CSP 写在每个页面的 `<meta http-equiv>` 里，两站都有，脚本与样式的加载限制是一致的。真正缺失的是**只能通过响应头下发、`<meta>` 又表达不了的那几条**（详见「[两者的实际差异](#两者的实际差异)」），其中唯一有实际影响的是 iframe 嵌套防护 —— `frame-ancestors` 用 `<meta>` 下发会被浏览器直接忽略，所以备站防不住被别人嵌进 iframe。安全头以主站为准。
>
> 🔴 **但 `sw.js` 不受此限制**：Service Worker 由页面里的 JS 注册（`assets/pwa.js`），不依赖响应头，两个站点都能正常工作。

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

## 微动效系统

设置面板的「**外观**」下面还有一组「**动效**」开关（开启 / 关闭）。它不控制"有没有动画"那么简单——背后的设计目标是"动效是状态变化的说明书，不是装饰"：每一次位移、渐显、延迟，都要让用户看清"什么东西变了、从哪里来、到哪里去"。

### 四层结构

| 层 | 职责 | 文件 |
|----|------|------|
| 第 0 层 令牌 | 时长 / 缓动 / 位移的唯一取值来源 | `style.css` 末尾 |
| 第 1 层 编排 | 同组元素按序号错落启动，封顶 320ms | `main.js` + `style.css` |
| 第 2 层 降级 | 七条兜底路径，只允许关动效、不允许关内容 | `main.js` + `style.css` |
| 第 3 层 空间 | 按"有没有指针悬停能力"分流，不按屏幕宽度 | `style.css` |
| 第 4 层 开关 | `html[data-motion="off"]` 一行归零全部令牌 | `style.css` + `prefs.js` |

**为什么时长、缓动、位移都收进令牌**：散落在各处的 `0.2s` / `0.25s` / `0.35s` 无法统一调优，改一处忘一处。收敛到变量后，调慢或调快整个站点只改一个地方。

**为什么错落要封顶 320ms**：一组 30 个元素按每项 40ms 排下去，最后一个要等 1.2 秒才出现，用户会以为页面卡了。封顶后错落感保留在前几个元素上（人眼只能分辨前几下），任何长度的列表都在 1/3 秒内全部启动。

### 七条降级路径（任何一条命中都必须保证内容可见）

1. 系统级「减少动画」（最高优先级，前庭功能障碍用户）
2. 系统级「增强对比度」（关掉 opacity 过渡，只保留位移）
3. 浏览器不支持 `IntersectionObserver`
4. 动效脚本抛异常（`try/catch` 兜底，第一原则：动效可以没有，内容不能没有）
5. 后台标签页切回时，把已进入视口但仍等待的元素一次性显示
6. 脚本完全不可用（`@media(scripting:none)` 兜底）
7. 浏览器不支持 `min()` 与自定义属性组合（延迟被丢弃，但内容照常显现）

**关键的 1.5 秒硬超时兜底**：`IntersectionObserver` 有极小概率不回调（元素被移出文档、标签页被冻结）。超时后强制显示所有 `.reveal`，否则用户会看到一块永久空白。

### 与系统偏好的关系

本站开关**管不到**系统的 `prefers-reduced-motion`——系统说不要动效时，用户在本站也开不回来。这是刻意的：系统级设置表达的是无障碍需求，不该被站点覆盖。

### 容错细节

- **第 0 层必须放在 `style.css` 最末尾**：同权重靠源顺序取胜，上移会被前面的基础规则反覆盖（浅色主题块踩过同一个坑）。
- **组件规则不许用 `transition` 简写**：简写会把 `transition-delay` 一并重置为 `0s`，卡片同时带 `.card` 与 `.reveal` 时就会把错落延迟冲掉，表现为"动效齐刷刷一起出现"。这里全部改用 `transition-property` / `-duration` / `-timing-function` 长写。
- **`data-motion` 必须无条件写入 `on`/`off`**：只写 `off` 会导致用户从关切回开时，残留的 `off` 属性永远清不掉。

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
const CACHE_VERSION = 'v3';
```

**发布新内容后，把这个数字加一**（`v3` → `v4`），用户下次访问时 Service Worker 会丢掉旧缓存、重新抓取，并弹出「有新版本可用」的提示条。

不改这个数字的话，页面本体（HTML）仍会因为「网络优先」策略而更新，但样式和脚本可能停留在旧版本——所以发版时请一并改掉它。本站引入微动效系统时把版本号从 `v2` 升到了 `v3`，正是为了让老用户尽快拿到带动效的新样式与脚本。

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

**只是看站点的话，零构建、零依赖**，不需要 Node.js、不需要安装任何东西：

```bash
git clone https://github.com/xiaoyu-hue/xiaoyu-hue.github.io.git
cd xiaoyu-hue.github.io
# 双击 index.html，或用任意静态服务器：
python3 -m http.server 8000
```

推荐 Chrome / Edge。

### 要改内容时

成品 HTML 不再手写修改 —— 改 `src/` 里的源码，然后跑一次构建：

```bash
python3 build.py           # 先只比对：逐个文件告诉你会不会改动线上内容
python3 build.py --write   # 确认无误后再写入成品 HTML 与 _headers
```

`build.py` 零依赖，只用 Python 标准库，不需要 pip install、不需要 Node.js。
它会把构建结果和你仓库里的现有成品**逐字节比对**，任何非预期的差异都会被报出来并拒绝通过 ——
所以「改了模板忘了同步」这类事会被挡住，不会悄悄上线。

这次为什么要多出这一步：以前 head、导航、页脚这些样板在每个 HTML 里各抄一份，改一次要动
**10 个文件**；现在它们只在 `src/layouts/base.html` 里存在一份，CSP 与 `base_url` 也各自收敛到
一行。代价是修改多了一步构建，换来的是「不会漏改某一页」这件事由工具保证，而不是靠记性。

> **测 PWA 功能必须用 `http://localhost:8000`，不能用 `http://127.0.0.1:8000` 之外的 IP。**
> Service Worker 只在「安全上下文」下工作：HTTPS，或 localhost。用局域网 IP（如 `192.168.x.x`）访问时，SW 会静默注册失败，离线功能不可用——这是浏览器的安全限制，不是站点的问题。

---

## 部署：主站与备用站

同一个仓库有两份自动部署，内容始终同步：

| 角色 | 地址 | 平台 |
|------|------|------|
| **主站** | <https://xiaoyu-hue-github-io.pages.dev/> | Cloudflare Pages |
| **备用站** | <https://xiaoyu-hue.github.io/> | GitHub Pages |

**两边都直连同一个 GitHub 仓库**，推一次 `main`，两处各自自动构建。不需要手动同步，也不存在版本漂移——实测两边首页的内容哈希完全一致。

### 为什么留着备用站

不是为了"备份"这个概念，是因为两者的**故障域不同**：Cloudflare 出问题时 GitHub Pages 仍然在线；反过来 GitHub 挂了，Cloudflare 边缘上已经部署好的静态副本也照样能服务，只是暂时无法触发新构建。互为兜底是有实际意义的，而维护成本是零。

### 两者的实际差异

| 项目 | 主站 | 备用站 |
|------|------|--------|
| CSP | 有（响应头 + 页面 `<meta>` 双份） | **有**（页面 `<meta>`） |
| 防 iframe 嵌套（`frame-ancestors` / `X-Frame-Options`） | 有 | **无** —— `<meta>` 下发会被浏览器忽略，只能靠响应头，备站加不了 |
| `X-Content-Type-Options: nosniff` | 有 | 无 |
| `Cross-Origin-Opener-Policy` | 有 | 无 |
| `Referrer-Policy` | 有 | 无 |
| `Permissions-Policy` | 有 | 无 |
| `Strict-Transport-Security` | 有 | 有 |
| `_headers` 文件本身 | 生效，不对外暴露 | **会被当成静态文件公开提供**（内容只是安全头配置，不含敏感信息） |
| HTTP/3 | 支持 | 不支持 |
| 边缘节点 | 全球 Anycast | 单区域 |
| 自定义域名 | 支持 | 支持，但仍加不了响应头 |
| PWA / 离线 | 正常 | 正常 |

上面这些是实测两个站的响应头得出的，不是照抄平台文档。差异里**唯一有实际影响的是 iframe 嵌套防护**：备站可能被别人嵌进 iframe（点击劫持的载体），其余几条在纯静态、无登录、无表单的站点上影响很小 —— 本站 `form-action 'none'`，也没有任何需要 `nosniff` 兜底的动态内容。

### 两个容易踩的点

- **规范链接统一指向主站**：所有页面的 `<link rel="canonical">` 和 `og:url` 都写主站地址，避免搜索引擎把两个站点判成重复内容、分散权重。文章里指向子项目（`/sonder520/`、`/Nymir/`、`/xy-club/`、`/xy-intro-card/`）的链接**保留在 `github.io`**——那些是独立的 GitHub Pages 项目，`pages.dev` 上没有这些路径。
- **想自查两边是否同步**，对比首页内容哈希即可：

  ```bash
  curl -s https://xiaoyu-hue-github-io.pages.dev/ | md5sum
  curl -s https://xiaoyu-hue.github.io/ | md5sum
  ```

  两个值一致就说明备站没落后。

---

## 测试

站点本身依然**零依赖** —— 下面的工具只在你要改代码时用来验证，访问和部署站点都不需要。

```bash
python3 -m unittest discover -s tests -t .   # 契约层：只要 python3
node --test 'tests/js/**/*.test.mjs'         # 逻辑层：需要 Node 18+
npx playwright test                          # 真浏览器层：需要 Node，先跑 npm ci
python3 scripts/verify_csp_jsonld.py         # CSP/JSON-LD 实测：需要 playwright（可选）
```

真浏览器层里包含一份**可访问性基线**（`tests/e2e/a11y.spec.mjs`，用的是 axe-core）。它补的是静态审查查不到的那一类问题：CSS 里两个十六进制常量配在一起，对比度够不够，不跑浏览器、不做色彩空间计算，读代码永远看不出来 —— 本站就实测抓到过一个已经上线的问题（`--text-faint` 配 `--abyss` 只有 4.347:1，WCAG AA 要求 4.5:1）。扫描覆盖全站页面 × 浅/深两种主题，外加设置面板展开后的面板内部。

axe 只装在 devDependencies，**站点本身依旧零运行时依赖**。它对 Node 版本没有额外要求（axe-core 只要求 Node 4+），所以 CI 上现有的 Node 20 就能跑。

| 层 | 管什么 |
|------|--------|
| 契约层 | 10 个页面的 head、页脚签名、导航、CSP 是否与 `_headers` 一致；文章卡片与文章是否同步；PWA 清单合法性与图标真实尺寸；Service Worker 是否在根目录、预缓存清单有没有死链；**微动效系统的令牌齐备性、总开关、降级路径、每页动效开关成对**；**结构化数据：每页必须有 JSON-LD、必须是合法 JSON、`@type` 正确、URL 必须是绝对地址**；完整性检查脚本自己是否还抓得到问题 |
| 逻辑层 | 滚动淡入的四类分支（正常观察 / 用户开了「减少动画」/ 不支持 IntersectionObserver / 没有 matchMedia）；同组错落编号与封顶、1.5s 硬超时兜底、总开关三种取值；首屏偏好同步（含动效）与老数据兼容；Service Worker 的请求分流（导航 / 静态资源 / 其他）与跨域、非 GET 放行 |
| 真浏览器层 | 页面真的渲染了吗、CSS 和 JS 有没有被 CSP 拦掉、动效令牌真的被消费了吗、同组错落是否严格递增且封顶 320ms、开关即时生效且刷新保持、关后内容仍可见（**令牌归零是按计算值断言的，不只是看 `transition`**）、375px 下有没有元素溢出；Service Worker 注册、**断网后能否打开首页与文章**、未缓存页面是否回退到离线页；以及**可访问性基线**：全站页面 × 浅/深两种主题的对比度、语义与 ARIA，外加设置面板展开后的面板内部 |

> JSON-LD 契约单独拎出来说一句：它是那种**写错了页面照样好看、只有搜索引擎静默失效**的东西。
> 相对 URL 尤其阴 —— 本地渲染毫无问题，被抓走后就指向别人的域名了。所以让它进 CI 盯着。

每次 push 到 `main`，CI 会自动跑完三层，外加一遍 CSP/JSON-LD 实测（CI 里只装 Chromium 一个引擎，本地可以跑全三个）。

---

## 依赖

**站点本身零依赖**：不加载任何第三方 JS、CSS、字体或图片资源，`index.html` 里引用的全是本站自己的文件。字体走系统字体栈（`system-ui` / `PingFang SC` / `Microsoft YaHei` / `Noto Sans CJK SC` …），不下载任何 web font —— 省一次请求，也不会有 FOIT（字体加载完成前的空白或闪动）。访问和部署都不需要 Node.js。

下面的东西只在你要改代码、跑验证时才需要：

| 包 | 版本 | 许可证 | 用在哪 |
|------|------|--------|--------|
| [`@playwright/test`](https://github.com/microsoft/playwright) | 1.63.0 | Apache-2.0 | 真浏览器层：起本地服务、开真 Chromium 跑 83 个用例 |
| `playwright` / `playwright-core` | 1.63.0 | Apache-2.0 | 上面那个的底层，不需要单独装 |
| [`@axe-core/playwright`](https://github.com/dequelabs/axe-core-npm) | 4.13.0 | MPL-2.0 | 可访问性基线：把 axe 注入页面跑 WCAG 规则 |
| `axe-core` | 4.13.0 | MPL-2.0 | 上面那个的规则引擎，不需要单独装 |

MPL-2.0 是文件级 copyleft，但它只约束"你把这份代码的源文件改了再分发"；这里全部只作开发期工具，不进站点、不随页面分发，所以对本站的 MIT 许可没有影响。

**系统要求**

| 用途 | 需要什么 |
|------|----------|
| 契约层（84 例） | `python3` —— 只用标准库，一个 pip 包都不装 |
| 逻辑层（63 例） | Node 18+ |
| 真浏览器层（83 例） | Node 18+，Chromium 由 Playwright 自己下载（不进仓库） |
| CSP/JSON-LD 实测 | Python 3 + `playwright` —— **可选**，不装也能构建和部署站点，只是没法亲自复现 [`docs/csp-jsonld.md`](docs/csp-jsonld.md) 里的结论 |

CI 上跑的是 Node 20。

**CI 用到的 GitHub Actions**

`actions/checkout@v4`、`actions/setup-node@v4`、`actions/cache@v4`、`actions/upload-artifact@v4`。

它们目前按**版本标签**引用，没有钉到具体的 commit SHA。理论上标签是可以被移动的，但本仓库**没有任何 secrets**，两个 workflow 也都把 `permissions` 收敛到了 `contents: read`，权衡后认为风险可以接受 —— 记在这里，是因为这是个主动选择，不是没注意到。

---

## 更新站点

成品 HTML 一律不再手改（改了也会被下次构建覆盖），正确顺序是：

1. 在 `src/pages/` 加正文片段，例如 `blog-post-9.body.html`
2. 在 `src/data/pages.json` 加一条元数据，`body` 指向刚才的片段，并填好 `title` / `description` / `og_type` / `date`：

   ```json
   "blog/post-9.html": {
     "body": "blog-post-9.body.html",
     "url_path": "blog/post-9.html",
     "title": "文章标题 · xiaoyu-hue",
     "description": "一句话摘要",
     "og_type": "article",
     "footer": "page",
     "date": "2026-10-02"
   }
   ```

3. `python3 build.py --write`
4. 改项目卡片、关于与联系方式同理，改的是 `src/pages/index.body.html`

`date` 这一项不是装饰：它决定这篇文章会不会进 `feed.xml`、在 `sitemap.xml` 里有没有 `lastmod`、JSON-LD 里有没有 `datePublished`。**没填 date 的页面会被生成逻辑当作「不是文章」跳过**——所以写完发现新文章没进 RSS，先查这里。

新增文章后，**记得把新文件加进 `sw.js` 的 `PRECACHE` 清单**，否则该文章离线时打不开（完整性检查会抓到清单里的死链，但不会告诉你"少了一篇"）
- **发版时把 `sw.js` 的 `CACHE_VERSION` 加一**
- 推到 `main` 分支后，**主站与备用站会各自自动部署**（见「[部署：主站与备用站](#部署主站与备用站)」）

改了图标源文件 `assets/icons/icon.svg` 后，重新导出各尺寸：

```bash
node scripts/build-icons.mjs
```

---

## 关于作者

没有编程背景，所有代码由 AI Agent 辅助完成。协作规则（需求先确认、任务拆小步、如实标注做不到什么）写在博客第一篇文章里。

> 一半烟火以谋生，一半诗意以谋爱。

---

## 开源致敬

这个站点能长期保持"看起来简单、改起来放心"，靠的是下面这些项目。

**[Playwright](https://github.com/microsoft/playwright)** · Apache-2.0 · Microsoft

真浏览器层全部跑在它上面。最值得说的不是"能自动化点页面"，而是它让**离线**这种场景变得可测 —— 一句 `context.setOffline(true)` 就能验证"断网后首页还能不能打开"，而这恰恰是本站最核心、也最容易悄悄坏掉的能力。没有它，这类问题只能靠人手动断网去试，试两次就不试了。

**[axe-core](https://github.com/dequelabs/axe-core)** · MPL-2.0 · Deque Systems

可访问性基线的规则引擎。它抓出过两个我自己永远发现不了的问题：一是 `--text-faint` 配 `--abyss` 的对比度只有 4.347:1（要求 4.5:1），而这在 CSS 里就是两个十六进制常量，读代码看不出来；二是扫描时机 —— 元素淡入动画进行中读到的对比度是假的，逼着我把"扫之前先关动效"变成测试的一部分。Deque 把它设计成**宁可漏报也不误报**，这点很关键：误报一多，人就会开始忽略它。

**托管平台**

[Cloudflare Pages](https://pages.cloudflare.com/)（主站）与 [GitHub Pages](https://pages.github.com/)（备用站）都提供免费的静态托管与自动构建，两者故障域不同，互为兜底。它们不是本项目的依赖，但没有它们就没有这个站点。

**刻意的"不引入"**

也记一下调研后**没有**采用的东西，免得以后重复一遍调研：

- **Workbox**（SW 框架）：它需要一条 Node/npm 构建链来生成 precache 清单，而本站的构建只用 Python 标准库；换来的却只是把一段已经写好、逻辑清晰可测的手写 SW 换成黑盒。
- **StrykerJS**（变异测试）：官方 runner 里没有 `node:test`，只能用 command runner（无法做覆盖率优化，每个变异体都要跑全量测试）；而且 10.x 要求 Node ≥ 22，与 CI 的 Node 20 冲突。
- **Valibot / Zod**（运行时校验库）：本站导入校验只有三十来行手写代码，引入它们解决不了"没有测试"这个真问题，还会打破「零运行时依赖」这条底线——它们会被打进页面 JS，成为访客实际下载的一部分。
- **Web font**：见「[依赖](#依赖)」，用系统字体栈是有意的。

---

## 许可证

[MIT](LICENSE) © 2026 xiaoyu-hue
