# 边缘层配置说明

> 说明：本文是在站点前加一层边缘服务、补齐 GitHub Pages 拿不到的 HTTP 安全响应头的操作指南。
> 仓库侧的准备工作（`_headers`、`.nojekyll`、meta CSP）**已完成**，剩余步骤在 Cloudflare 后台完成。
>
> ⚠️ **开始前请先看「迁移前必读」**，有一个无法回避的域名代价。

---

## 为什么需要它

GitHub Pages **不支持自定义响应头**，也不读取 `_headers` 文件。因此在纯 Pages 部署下，以下响应头**全部拿不到**：

| 响应头 | GitHub Pages | 边缘层 |
|--------|--------------|--------|
| `Content-Security-Policy`（HTTP 头形式） | ❌ | ✅ |
| `X-Frame-Options` / `frame-ancestors` | ❌ | ✅ |
| 真实 HSTS（可自定义时长 / preload） | ⚠️ 固定值，不可配置 | ✅ |
| `X-Content-Type-Options: nosniff` | ❌ | ✅ |
| `Permissions-Policy` | ❌ | ✅ |
| `Cross-Origin-Opener-Policy` | ❌ | ✅ |

当前站点已用 `<meta http-equiv="Content-Security-Policy">` 做降级防护，但它有三个已知缺口：`frame-ancestors` 在 meta 下被浏览器忽略、`sandbox` 与 `report-to` 同样无效。**补齐这些只能靠边缘层。**

---

## 迁移前必读：域名代价

`xiaoyu-hue.github.io` **这个地址带不走** —— 它是 GitHub 的域名，Cloudflare Pages 上不存在这个地址。

迁移后你会得到 `xiaoyu-hue.pages.dev`（或绑定的自有域名）。由此有两个后果：

1. **旧链接不会自动跳转** —— GitHub Pages 不支持服务端 301，做不到真正的重定向。已分享出去的 `xiaoyu-hue.github.io` 链接不会指向新站。
2. **主站会和四个项目分离** —— `sonder520` / `Nymir` / `xy-club` / `xy-intro-card` 部署在 `xiaoyu-hue.github.io/<repo>/` 子路径上，它们不随主站迁移。

### 建议的过渡做法（不是二选一）

**先并存，别急着删。** 推荐这样走：

1. 建 Cloudflare Pages 项目，验证新站一切正常（页面、样式、安全头）
2. **GitHub Pages 保持开启**，旧地址继续可用 —— 只是没有新的安全头而已
3. 确认新站稳定后，再决定要不要让旧地址退休

这样即使新站出问题，旧站还在，不会造成服务中断。

---

## 两条路线

### 路线 A：部署到 Cloudflare Pages（推荐）

仓库侧已备好：根目录的 **`_headers`** 写好了完整配置，Cloudflare Pages 会自动读取并应用。

### 逐步操作（照着点即可）

**第 1 步 · 进入创建页**
Cloudflare Dashboard → 左侧 **Workers & Pages** → **Create** → 切到 **Pages** 标签 → **Connect to Git**

**第 2 步 · 授权并选仓库**
点 GitHub → 授权（若仓库未列出，选 "Only select repositories" 加上 `xiaoyu-hue.github.io`）→ 选中 **`xiaoyu-hue/xiaoyu-hue.github.io`** → **Begin setup**

**第 3 步 · 填配置（这一步最容易填错，照抄）**

| 字段 | 填什么 | 为什么 |
|------|--------|--------|
| Project name | `xiaoyu-hue` | 决定默认域名 `xiaoyu-hue.pages.dev` |
| Production branch | `main` | 每次推 main 自动部署 |
| Framework preset | **None** | 本站无框架；选错会自动加多余构建步骤 |
| Build command | **留空** | 纯静态，无构建 |
| Build output directory | **留空** | 站点文件就在仓库根目录 |
| Environment variables | 不用填 | — |

> ⚠️ **Build output directory 留空，不要填 `/`**。本站没有 `dist/` 之类的产物目录，填了反而可能部署失败。

**第 4 步 · 部署**
点 **Save and Deploy**，等 1–2 分钟。首次部署完成后会拿到 `https://xiaoyu-hue.pages.dev`。

### 本仓库已做的配套准备

| 文件 | 作用 |
|------|------|
| `_headers` | 安全响应头配置，Cloudflare Pages 自动应用 |
| `.nojekyll` | 空文件。作用是禁用 Jekyll 处理 —— 否则以 `_` 开头的 `_headers` 会在构建时被跳过，导致配置**静默失效**。**不要删除。** |
| meta CSP | 与 `_headers` 里的 CSP 策略一致。两者并存时浏览器取交集，当前一致，无冲突 |

> 部署产物会包含 `scripts/`、`docs/`、`.github/` 等目录。它们本来就是公开的，无敏感内容；若不想暴露可用 Cloudflare 的构建排除规则，但当前没必要。

### 路线 B：保留 GitHub Pages，前面套 Cloudflare 代理

适合要用自定义域名的场景。此时 `_headers` **不生效**（请求不经过 Cloudflare Pages），需要在 Cloudflare 后台手动配置：

- SSL/TLS → Edge Certificates → 开启 HSTS
- Rules → Transform Rules（或 Cloudflare 的 Response Header Rules）→ 添加与 `_headers` 相同的头

配置内容照抄仓库里的 `_headers`。

---

## `_headers` 当前配置

```
/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()
  Cross-Origin-Opener-Policy: same-origin
  Strict-Transport-Security: max-age=31536000
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'
```

两点说明，避免照抄时踩坑：

1. **`Strict-Transport-Security` 未加 `preload`** —— preload 一旦提交很难撤回，且要求 `includeSubDomains`。注意 GitHub Pages 已为 `*.github.io` 统一发送 `max-age=31556952`（约 1 年），此处配置会覆盖它。**等你确定长期使用自有域名后，再考虑加 `includeSubDomains; preload`。**
2. **边缘层 CSP 与 meta CSP 会同时生效** —— 浏览器取两者的**交集**（更严格者胜）。当前两者策略一致，无冲突。将来若放宽其中一处，记得另一处同步修改。

---

## 如何验证（不要只看配置文件存在）

配置完务必实测，而不是假设生效：

**① 安全响应头**（部署到 pages.dev 后）

```bash
curl -sI https://xiaoyu-hue.pages.dev/ | grep -iE \
  'content-security|x-frame|strict-transport|nosniff|permissions|cross-origin'
```

预期返回 6 行左右，含 `content-security-policy`、`x-frame-options`、`x-content-type-options: nosniff`、`permissions-policy`、`cross-origin-opener-policy`、`strict-transport-security`。

**② 对照：GitHub Pages 上能拿到什么**

```bash
curl -sI https://xiaoyu-hue.github.io/ | grep -iE \
  'content-security|x-frame|nosniff|permissions|strict-transport'
```

预期**只返回 `strict-transport-security` 一行**（GitHub 对 `*.github.io` 统一发送）。其余全部缺失 —— 这正是本文要解决的问题，也是判断配置是否生效的基准线。

**③ meta CSP（HTML 内，`curl -I` 看不到）**

```bash
curl -s https://xiaoyu-hue.pages.dev/ | grep -o 'Content-Security-Policy[^>]*'
```

另外，站点里的 meta CSP 是在 HTML 内的，不会被 `curl -I` 显示。确认它存在用：

```bash
curl -s https://xiaoyu-hue.github.io/ | grep -o 'Content-Security-Policy[^>]*'
```

---

## 部署后验收清单

安全头对了不代表站没坏。**CSP 加严是会让页面白屏的**，所以逐项确认：

- [ ] `curl -sI` 能看到上述 6 个安全响应头
- [ ] 首页 200 且正常渲染（不是白屏）
- [ ] 打开浏览器 DevTools → Console，**零 CSP 报错**
- [ ] Network 面板无被 block 的资源（红色条目）
- [ ] 玻璃卡片样式生效（`.glass` 有毛玻璃背景）
- [ ] 滚动淡入动画正常
- [ ] 逐个页面走一遍：首页 / 博客列表 / 5 篇文章
- [ ] 本地跑 `python3 scripts/check_integrity.py` 仍全绿

## 迁移后需要同步的事

- [ ] `SECURITY.md` 第三节「已知局限」需更新（届时部分防护已补齐）
- [ ] 若启用 CSP 报告（`report-to`），需要一个接收端点，当前未配置
- [ ] 自定义域名场景下，补充 DNS 加固：CAA 记录 + DNSSEC
- [ ] 决定 `xiaoyu-hue.github.io` 的去留 —— 建议新站稳定运行一段时间后再处理
