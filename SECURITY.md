# 安全政策

> 最后更新：2026-10-01

本站是一个**纯静态站点**：没有后端、没有数据库、没有登录态、没有 Cookie、不收集任何访客数据。这份文档说明它的安全模型、已实施的防护，以及**哪些防护是拿不到的**。

---

## 一、报告安全问题

**请优先使用 GitHub 私有漏洞报告**（仓库 → Security → Advisories → Report a vulnerability），避免在公开 issue 里披露细节。

如果仓库未开启私有报告，可开 issue，但**请不要在其中写明可利用的具体细节**，只描述现象与影响范围即可。

| 项目 | 说明 |
|------|------|
| 响应时间 | 目标 7 个工作日内首次回复；无法修复也会说明原因 |
| 处理流程 | 确认 → 评估影响 → 修复并发布 → 公开披露（如适用） |
| 语言 | 中文 / 英文均可 |

**不接**：要求代为安全审计、付费渗透测试、以及把本站当作靶场的未授权测试。

> 本项目由 AI 辅助开发，作者为零编程基础的个人开发者，**未经过专业安全审计**。这与四个项目仓库（`sonder520` / `Nymir` / `xy-club` / `xy-intro-card`）的标注口径一致。

---

## 二、安全模型

### 天生不存在的风险

因为是纯静态站点，以下常见风险**结构上不成立**：

- 注入类：SQL 注入、命令注入、服务端模板注入 —— 无后端、无数据库
- 身份类：越权、会话劫持、CSRF —— 无登录态、无 Cookie、无表单
- 上传类：任意文件上传、路径穿越 —— 无上传功能
- 依赖类：第三方库漏洞 —— **零构建依赖、零运行时依赖**

### 已实施的防护

| 措施 | 状态 | 说明 |
|------|------|------|
| 零第三方资源 | ✅ | 已移除全部 Google Fonts 外链，不加载任何外部 CDN 资源 |
| 内容安全策略（CSP） | ✅ | 以 `<meta http-equiv>` 下发，**不含** `unsafe-inline` / `unsafe-eval` |
| Referrer 策略 | ✅ | `strict-origin-when-cross-origin` |
| 全站 HTTPS | ✅ | GitHub Pages 提供 |
| HSTS | ✅ | GitHub 对 `*.github.io` 域统一发送 `max-age=31556952`（约 1 年），无需配置 |
| 无内联脚本 | ✅ | 全站 0 处内联 `<script>`、0 处 `on*=` 事件属性 |
| 应用层逻辑最小化 | ✅ | `assets/main.js` 仅 18 行，只做滚动淡入，不接触用户输入 |

### 当前 CSP 策略

```
default-src 'self';
script-src 'self';
style-src 'self';
font-src 'self';
img-src 'self' data:;
connect-src 'none';
object-src 'none';
base-uri 'self';
form-action 'none'
```

`connect-src 'none'` 表示页面不发起任何 fetch / XHR 请求。

---

## 三、已知局限（这部分请认真读）

诚实说明：以下防护**本站拿不到**，不是没做，是平台不支持。

### 1. 无法设置 HTTP 安全响应头

GitHub Pages **不支持自定义响应头**，也不读取 `_headers` 文件（那是 Netlify / Cloudflare Pages 的特性）。实测本站响应头中**确实缺失**的：

- `X-Frame-Options`
- `X-Content-Type-Options: nosniff`
- `Permissions-Policy`
- `Cross-Origin-Opener-Policy`
- `Content-Security-Policy`（HTTP 头形式 —— 当前以 `<meta>` 降级实现）

**例外：HSTS 是有的。** 实测响应头含 `strict-transport-security: max-age=31556952`（约 1 年），由 GitHub 对 `*.github.io` 域统一发送，本站无需任何配置。

> 该结论对 `github.io` 域实测成立。**若将来改用自定义域名，HSTS 是否仍自动提供尚未实测**，届时需自行验证。

### 2. 防点击劫持能力实际缺失

`frame-ancestors` 只在 HTTP 响应头下生效，通过 `<meta>` 下发时**浏览器会直接忽略**。因此本站**无法阻止被嵌套进 iframe**。

> 我们曾经在 meta CSP 里写过 `frame-ancestors 'none'`，但它只会产生一条「该指令被忽略」的 console 提示，不提供任何实际防护。为免制造虚假安全感，已移除。真正的防嵌套需要边缘层，见下一节。

### 3. 未使用的 meta 伪造头

MDN 明确警告不要用 `<meta http-equiv>` 设置安全头（*"may lead to a false sense of security"*）。`http-equiv` 的标准合法值只有 7 个，其中**不含** `X-Frame-Options` / `X-Content-Type-Options` / `Strict-Transport-Security`。

网上流传的这类写法**无效**，本站不会采用：

```html
<!-- ❌ 无效，本站不使用 -->
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta http-equiv="X-Frame-Options" content="DENY">
```

### 4. 其他

- 站点内容为公开静态文件，**无法防止整站镜像或抄袭**
- **无法防御 GitHub 账号本身被攻破** —— 开启两步验证是唯一的实质性缓解
- 未经专业安全审计

---

## 四、边缘层部署（可选增强）

若需要完整的 HTTP 安全响应头，可在站点前加一层边缘服务（如 Cloudflare），或部署到支持 `_headers` 的平台。仓库根目录下的 **`_headers`** 文件已备好配置，直接生效。

边缘层能补齐的能力：真正的 HSTS、`X-Frame-Options`、`nosniff`、`Permissions-Policy`、完整 CSP 响应头（含 `frame-ancestors`），以及 WAF 与 DDoS 防护。

---

## 五、维护者自查清单

| 项 | 位置 |
|----|------|
| Secret Scanning + Push Protection | 仓库 Settings → Security |
| 分支保护（禁止 force push / 删除 main） | 仓库 Settings → Branches |
| 两步验证（2FA） | 账号 Settings → Password and authentication |
| 凭据使用 fine-grained token，定期轮换 | 账号 Settings → Developer settings |

> 注：以上均需在 GitHub 网页端操作，无法通过仓库文件配置。

---

## 六、许可证

[MIT](LICENSE) © 2026 xiaoyu-hue
