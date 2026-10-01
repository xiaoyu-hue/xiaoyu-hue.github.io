// 真浏览器实测：这些是 Python / Node 逻辑层测不到的东西
// —— 页面真的渲染出来了吗？CSS 和 JS 真的没被 CSP 拦掉吗？动效真的触发了吗？
//
// 运行：npx playwright test（会自己起一个本地静态服务器）

import { test, expect } from '@playwright/test';

const PAGES = [
  { path: '/', name: '首页' },
  { path: '/blog/index.html', name: '博客列表' },
  { path: '/blog/post-1.html', name: 'post-1' },
  { path: '/blog/post-2.html', name: 'post-2' },
  { path: '/blog/post-3.html', name: 'post-3' },
  { path: '/blog/post-4.html', name: 'post-4' },
  { path: '/blog/post-5.html', name: 'post-5' },
];

const SIGNATURE = '一半烟火以谋生，一半诗意以谋爱';

test.describe('每个页面都能干净加载', () => {
  for (const { path, name } of PAGES) {
    test(`${name}：无控制台错误、无资源加载失败`, async ({ page }) => {
      const problems = [];
      page.on('console', (msg) => {
        if (msg.type() === 'error') problems.push(`console error: ${msg.text()}`);
      });
      page.on('pageerror', (err) => problems.push(`page error: ${err.message}`));
      page.on('requestfailed', (req) => {
        problems.push(`请求失败: ${req.url()} (${req.failure()?.errorText ?? '未知原因'})`);
      });

      await page.goto(path);
      await page.waitForLoadState('networkidle');

      // CSP 违规会以控制台错误的形式出现，所以这里同时覆盖了「CSP 是否拦错了东西」
      expect(problems, `${name} 加载时出现了问题`).toEqual([]);
    });
  }

  test('样式表真的生效（没被 CSP 拦掉）', async ({ page }) => {
    await page.goto('/');
    const bg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(bg).not.toBe('rgb(255, 255, 255)');
  });

  test('每页的页脚签名都可见且逐字一致', async ({ page }) => {
    const seen = [];
    for (const { path, name } of PAGES) {
      await page.goto(path);
      const sign = page.locator('.sign').first();
      await expect(sign, `${name} 的签名没有渲染出来`).toBeVisible();
      seen.push((await sign.textContent()).trim());
    }
    expect(new Set(seen).size, '7 个页面的签名不一致').toBe(1);
    expect(seen[0]).toBe(SIGNATURE);
  });

  test('每页都有非空标题', async ({ page }) => {
    for (const { path, name } of PAGES) {
      await page.goto(path);
      const title = await page.title();
      expect(title.trim(), `${name} 的标题是空的`).not.toBe('');
    }
  });
});

test.describe('滚动淡入动效', () => {
  test('首页滚动到底后所有淡入元素都已显示', async ({ page }) => {
    await page.goto('/');
    // 关掉平滑滚动，否则滚动位置断言必然 flaky
    await page.evaluate(() => {
      document.documentElement.style.scrollBehavior = 'auto';
    });
    // 逐个把每个 .reveal 滚到视口中央，确保 IntersectionObserver 一定观察到交叉
    // （单纯「滚到底等 400ms」是竞态：IO 回调可能在断言之后才触发，导致偶发失败）
    const n = await page.locator('.reveal').count();
    for (let i = 0; i < n; i++) {
      await page.evaluate((idx) => {
        document.querySelectorAll('.reveal')[idx].scrollIntoView({ block: 'center' });
      }, i);
      await page.waitForTimeout(50);
    }
    // 断言 class 而不是 opacity：0.7s 的过渡动画会让 opacity 断言 flaky
    await expect
      .poll(async () => page.locator('.reveal:not(.in)').count(), { timeout: 10000 })
      .toBe(0);
  });

  test('用户开了「减少动画」时元素立即可见，不需要滚动', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.waitForTimeout(300);
    const pending = await page.locator('.reveal:not(.in)').count();
    expect(pending, '减少动画时应当立即显示，而不是等滚动').toBe(0);
  });
});

test.describe('移动端布局', () => {
  test('375px 宽度下没有元素横向溢出', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    for (const { path, name } of PAGES) {
      await page.goto(path);
      const offenders = await page.evaluate(() => {
        // CSS 里 body{overflow-x:hidden} 会让 scrollWidth 检查恒真（假绿），
        // 所以先用 CSSOM 放开，再逐个量元素。
        document.body.style.overflowX = 'visible';
        const bad = [];
        for (const el of document.querySelectorAll('body *')) {
          // .orb / .ocean-bg 是 position:fixed 的装饰层，故意出血到视口外
          if (el.classList.contains('orb') || el.classList.contains('ocean-bg')) continue;
          const rect = el.getBoundingClientRect();
          if (rect.width === 0 && rect.height === 0) continue;
          if (rect.right > window.innerWidth + 1 || rect.left < -1) {
            bad.push(
              `${el.tagName.toLowerCase()}.${el.className} ` +
              `left=${Math.round(rect.left)} right=${Math.round(rect.right)}`,
            );
          }
        }
        return bad;
      });
      expect(offenders, `${name} 在 375px 下有元素超出视口`).toEqual([]);
    }
  });
});

test.describe('站内导航', () => {
  test('博客列表点击第一张卡片进入对应文章', async ({ page }) => {
    await page.goto('/blog/index.html');
    const first = page.locator('.post-card').first();
    const heading = (await first.locator('h3').textContent()).trim();
    await first.click();
    await expect(page).toHaveURL(/post-2\.html/);
    await expect(page.locator('h1')).toHaveText(heading);
  });

  test('文章里的「返回博客」能回到列表页', async ({ page }) => {
    await page.goto('/blog/post-1.html');
    await page.getByRole('link', { name: /返回博客/ }).click();
    await expect(page).toHaveURL(/blog\/index\.html/);
    await expect(page.locator('.post-card').first()).toBeVisible();
  });

  test('导航栏的博客链接可用', async ({ page }) => {
    await page.goto('/');
    await page.locator('.nav-links').getByRole('link', { name: '博客' }).click();
    await expect(page).toHaveURL(/blog\/index\.html/);
  });
});

test.describe('设置面板', () => {
  test('三档主题可切换，且显式选择能覆盖系统设置', async ({ page }) => {
    // 关键场景：系统是深色，用户在面板里选浅色 —— 必须真的变浅色。
    // 单靠 prefers-color-scheme 做不到这件事。
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/');
    await page.locator('.prefs-toggle').click();

    await page.locator('[data-theme-option="light"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(lightBg).not.toBe('rgb(4, 17, 29)');

    await page.locator('[data-theme-option="dark"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor))
      .toBe('rgb(4, 17, 29)');
  });

  test('主题选择在刷新后保持', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-theme-option="light"]').click();
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.locator('html')).toHaveAttribute('data-theme-pref', 'light');
  });

  test('面板可用 Esc 关闭，点击外部也关闭', async ({ page }) => {
    await page.goto('/');
    const panel = page.locator('.prefs-panel');

    await page.locator('.prefs-toggle').click();
    await expect(panel).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();

    await page.locator('.prefs-toggle').click();
    await expect(panel).toBeVisible();
    await page.mouse.click(5, 500);
    await expect(panel).toBeHidden();
  });

  test('导出后的面板不会因程序触发的下载点击而关闭', async ({ page }) => {
    // 回归测试：导出时插入的 <a> 的 click 会冒泡到 document，
    // 曾被「点击外部关闭」逻辑误判，导致用户看不到导出提示。
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('.prefs-export').click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^xiaoyu-hue-prefs-\d{4}-\d{2}-\d{2}\.json$/);
    await expect(page.locator('.prefs-panel')).toBeVisible();
    await expect(page.locator('.prefs-msg')).toContainText('已导出');
  });

  test('清空需要二次确认，避免误点丢数据', async ({ page }) => {
    await page.goto('/blog/post-1.html');
    await page.locator('.prefs-toggle').click();
    await expect(page.locator('.prefs-reading')).toContainText('post-1');

    await page.locator('.prefs-reset').click();
    await expect(page.locator('.prefs-reset')).toContainText('再点一次');
    // 第一次点击不应清空
    await expect(page.locator('.prefs-reading')).toContainText('post-1');

    await page.locator('.prefs-reset').click();
    await expect(page.locator('.prefs-reading')).toContainText('还没有阅读记录');
  });

  test('打开文章会记录阅读进度', async ({ page }) => {
    await page.goto('/blog/post-5.html');
    await page.locator('.prefs-toggle').click();
    const box = page.locator('.prefs-reading');
    await expect(box).toContainText('post-5');
    const href = await box.locator('a').first().getAttribute('href');
    // 文件在 /blog/ 下时链接应是同级相对路径
    expect(href).toBe('post-5.html');
  });

  test('localStorage 存的是带 schema 的结构化数据', async ({ page }) => {
    await page.goto('/blog/post-2.html');
    const raw = await page.evaluate(() => localStorage.getItem('xiaoyu-hue:prefs:v1'));
    const obj = JSON.parse(raw);
    expect(obj.schema).toBe(1);
    expect(obj.theme).toBe('system');
    expect(obj.reading['post-2']).toBeTruthy();
  });
});
