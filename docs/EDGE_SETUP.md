# 边缘层配置说明

> 说明：本文记录如何在站点前加一层边缘服务，以补齐 GitHub Pages 拿不到的 HTTP 安全响应头。
> **这是一份待执行的配置指南，尚未启用。** 当前站点仍直接跑在 GitHub Pages 上。

---

## 为什么需要它

GitHub Pages **不支持自定义响应头**，也不读取 `_headers` 文件。因此在纯 Pages 部署下，以下响应头**全部拿不到**：

| 响应头 | GitHub Pages | 边缘层 |
|--------|--------------|--------|
| `Content-Security-Policy`（HTTP 头形式） | ❌ | ✅ |
| `Strict-Transport-Security`（HSTS） | ❌ | ✅ |
| `X-Frame-Options` / `frame-ancestors` | ❌ | ✅ |
| `X-Content-Type-Options: nosniff` | ❌ | ✅ |
| `Permissions-Policy` | ❌ | ✅ |
| `Cross-Origin-Opener-Policy` | ❌ | ✅ |

当前站点已用 `<meta http-equiv="Content-Security-Policy">` 做降级防护，但它有三个已知缺口：`frame-ancestors` 在 meta 下被浏览器忽略、`sandbox` 与 `report-to` 同样无效。**补齐这些只能靠边缘层。**

---

## 两条路线

### 路线 A：部署到 Cloudflare Pages（推荐）

仓库根目录的 **`_headers`** 文件已写好配置，Cloudflare Pages 会自动读取并应用。

1. Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git
2. 选择 `xiaoyu-hue/xiaoyu-hue.github.io`
3. 构建配置：
   - Framework preset：**None**
   - Build command：**留空**
   - Build output directory：**`/`**
4. 部署完成后验证（见下方）

> 仓库已包含 `.nojekyll` 空文件。它的作用是禁用 Jekyll 处理 —— 否则以 `_` 开头的 `_headers` 会在构建时被跳过，导致配置静默失效。**不要删除它。**

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

1. **`Strict-Transport-Security` 未加 `preload`** —— preload 一旦提交很难撤回，且要求 `includeSubDomains`，对 `*.github.io` 这类共享子域不合适。**等你确定长期使用自有域名后，再考虑加 `includeSubDomains; preload`。**
2. **边缘层 CSP 与 meta CSP 会同时生效** —— 浏览器取两者的**交集**（更严格者胜）。当前两者策略一致，无冲突。将来若放宽其中一处，记得另一处同步修改。

---

## 如何验证（不要只看配置文件存在）

配置完务必实测，而不是假设生效：

```bash
curl -sI https://你的域名/ | grep -iE 'content-security|x-frame|strict-transport|nosniff|permissions'
```

**预期**：返回上述响应头行。

**若仍跑在纯 GitHub Pages 上，预期是「什么都没有」** —— 这是正常的，正是本文要解决的问题：

```bash
curl -sI https://xiaoyu-hue.github.io/ | grep -i 'content-security'
# 无输出 = 符合预期（Pages 不支持）
```

另外，站点里的 meta CSP 是在 HTML 内的，不会被 `curl -I` 显示。确认它存在用：

```bash
curl -s https://xiaoyu-hue.github.io/ | grep -o 'Content-Security-Policy[^>]*'
```

---

## 迁移后需要同步的事

- [ ] `SECURITY.md` 第三节「已知局限」需更新（届时部分防护已补齐）
- [ ] 若启用 CSP 报告（`report-to`），需要一个接收端点，当前未配置
- [ ] 自定义域名场景下，补充 DNS 加固：CAA 记录 + DNSSEC
