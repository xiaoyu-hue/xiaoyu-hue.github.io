// 真浏览器实测：Phase-2 微交互（自定义光标 / 鼠标光晕 / 卡片 3D 倾斜 / 磁吸按钮）
//
// 这组用例是「作用域 bug」的防回归探针。此前这 4 个函数定义在 IIFE 之外，
// 却调用了 IIFE 内部的 motionEnabled()，导致 ReferenceError 被 try/catch 吞掉、
// 4 个交互在生产环境全部静默失效，而 CI 全绿（无测试覆盖它们）。
//
// 它们有几个共同特征，使本组成为可靠的回归守卫：
//   - 元素由 JS 在脚本末尾动态创建（.custom-cursor / .mouse-glow），没有 CSS 兜底；
//   - 倾斜/磁吸通过写「行内 transform」生效（不是样式表里的 class），
//     所以读到行内 transform 变化，就等于证明监听真的挂上了。
// 只要其中任何一个不再被注入/挂监听，下面用例立刻红 —— 不会再静默漏网。

import { test, expect } from '@playwright/test';

// 仅 chromium 项目运行（与 site.spec 一致）
test.skip(({ browserName }) => browserName === 'firefox', '仅 chromium 项目运行');

test.describe('Phase-2 微交互（作用域 bug 防回归）', () => {
  test('开启动效时自定义光标与鼠标光晕被注入（JS 创建，无 CSS 兜底）', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/');

    // 元素由 main.js 在脚本末尾创建，用 poll 等它出现，防止时序误报
    await expect
      .poll(() => page.locator('.custom-cursor').count(), { timeout: 5000 })
      .toBeGreaterThan(0);
    await expect
      .poll(() => page.locator('.mouse-glow').count(), { timeout: 5000 })
      .toBeGreaterThan(0);
  });

  test('开启动效时卡片 3D 倾斜真的挂上了监听（悬停后行内 transform 出现 perspective/rotate）', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/');

    const card = page.locator('.card').first();
    await card.scrollIntoViewIfNeeded();
    const box = await card.boundingBox();
    // 移到卡片中心：距离中心有偏移，JS 才会算出非零 rotateX/rotateY
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);

    await expect
      .poll(async () => (await card.evaluate((el) => el.style.transform)) || '', { timeout: 5000 })
      .toMatch(/perspective|rotate/i);
  });

  test('开启动效时磁吸按钮真的挂上了监听（悬停后行内 transform 出现 translate）', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/');

    const btn = page.locator('.btn').first();
    await btn.scrollIntoViewIfNeeded();
    const box = await btn.boundingBox();
    // 故意移到偏离中心的位置，确保算出的位移非零
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.25);

    await expect
      .poll(async () => (await btn.evaluate((el) => el.style.transform)) || '', { timeout: 5000 })
      .toMatch(/translate/i);
  });

  test('关闭动效（减少动画）时不注入自定义光标，门禁仍生效', async ({ page }) => {
    // 反向断言：防止「不管开关总注入」的假绿。
    // 若 main.js 不再读 motionEnabled，这条会失败。
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.waitForTimeout(500);

    expect(await page.locator('.custom-cursor').count(), '关闭动效后不应注入自定义光标').toBe(0);
  });
});
