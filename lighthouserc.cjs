// Lighthouse CI 配置 —— 守住「性能 / 可访问性 / SEO 不退化」的红线
//
// 设计约束（延续全站「零运行时依赖、CSP 严格、五层降级」的基调）：
//   - 复用系统 Chrome（CI / 本地同源），不下载 puppeteer 自带 Chromium
//     （CHROME_PATH 在沙箱指向 /usr/bin/google-chrome；CI 留空走自动探测）
//   - 阈值先宽松（performance ≥0.85 / a11y ≥0.90 / bp ≥0.90 / seo ≥0.90），
//     后续可逐次收紧；移动端节流会让分数抖动，宽松基线避免误报
//   - PWA 类目关闭：本站 SW / 离线能力已由 e2e + 手动验证覆盖，不在分数红线内
//   - 桌面预设 + 关闭节流：分数稳定，贴近真实桌面体验，也避开移动端模拟噪声
//
// 用 .cjs 后缀：仓库 package.json 含 "type":"module"，lhci 用 require() 加载
// 配置，CommonJS 写法最稳。
module.exports = {
  ci: {
    collect: {
      // 由 lhci 拉起静态服务器伺服站点根目录（与 e2e 用 python http.server 等价）
      staticDistDir: '.',
      url: ['http://localhost/index.html', 'http://localhost/blog/index.html'],
      numberOfRuns: 1,
      chromePath: process.env.CHROME_PATH || undefined,
      settings: {
        preset: 'desktop',
        throttlingMethod: 'provided',
        // chromeFlags 必须放在 settings 下、且为空格分隔的字符串（lhci node-runner 会再追加 --headless=new）
        chromeFlags: '--no-sandbox --disable-gpu',
      },
    },
    assert: {
      // 全部先设宽松基线；'error' 会阻断 CI，'warn' 只告警不阻断
      assertions: {
        'categories:performance': ['warn', { minScore: 0.85 }],
        'categories:accessibility': ['error', { minScore: 0.90 }],
        'categories:best-practices': ['warn', { minScore: 0.90 }],
        'categories:seo': ['error', { minScore: 0.90 }],
        'categories:pwa': 'off',
      },
    },
    // 仅本地存报告（可作 CI 产物供 review），不依赖外部 Lighthouse 服务器
    upload: {
      target: 'filesystem',
      outputDir: '.lighthouseci',
    },
  },
};
