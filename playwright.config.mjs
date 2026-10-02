import { defineConfig, devices } from '@playwright/test';

const PORT = 8000;
// 关键：baseURL 和 webServer.url 必须用同一个 host 字符串。
// 一个写 localhost、一个写 127.0.0.1 会导致同源判定失败，
// CSS / JS 被 CSP 拦掉，看起来像「CSP 有问题」，其实是配置自己错了。
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: 'tests/e2e',
  outputDir: 'test-results',
  fullyParallel: true,
  // python3 -m http.server 是单线程的，扛不住和测试数一样多的并发连接。
  // 用例变多后（23 个 worker）会出现 networkidle 偶发超时，
  // 看起来像「页面有问题」，其实是本地静态服务器先扛不住了。
  // 限制并发，让本地和 CI 都稳定。
  workers: process.env.CI ? 2 : 4,
  forbidOnly: !!process.env.CI,
  // 真浏览器测试偶发抖动，CI 上给一次重试；本地不重试，免得掩盖问题
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      // 仅运行跨浏览器降级护栏。其余用例（site/a11y/visual）在各自 spec 顶部
      // 用 test.skip 排除 firefox 项目，避免重复跑、也避免视觉基线在 firefox 下误生成。
    },
  ],
  webServer: {
    // 用 ThreadingHTTPServer 而非单线程 http.server：chromium + firefox 两个项目
    // 并行时并发连接数翻倍，单线程服务器会出现偶发连接重置导致测试红。
    // daemon_threads=True 让进程退出时不再抛 BrokenPipeError。
    command: `python3 -c "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler; h=ThreadingHTTPServer(('127.0.0.1', ${PORT}), SimpleHTTPRequestHandler); h.daemon_threads=True; h.serve_forever()"`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
