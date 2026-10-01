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
  ],
  webServer: {
    command: `python3 -m http.server ${PORT} --bind 127.0.0.1`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
