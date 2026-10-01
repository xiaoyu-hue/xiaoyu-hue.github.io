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
  { path: '/blog/post-6.html', name: 'post-6' },
  { path: '/blog/post-7.html', name: 'post-7' },
  { path: '/blog/post-8.html', name: 'post-8' },
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

test.describe('微动效系统', () => {
  // 这一组测的是「编排放到真浏览器里还成不成立」——
  // Node 层只能验证分支逻辑，验证不了 CSS 变量是否真的被消费、
  // 过渡是否真的挂在元素上。CSS 写错一个字（比如变量名拼错），
  // JS 测试全绿，页面却毫无动效。

  test('令牌真的被 CSS 消费：.reveal 的 transition 有实际时长', async ({ page }) => {
    await page.goto('/');
    const info = await page.evaluate(() => {
      const el = document.querySelector('.reveal');
      const cs = getComputedStyle(el);
      return {
        duration: cs.transitionDuration,
        property: cs.transitionProperty,
        delay: cs.transitionDelay,
      };
    });
    // 变量名拼错时，transition-duration 会退化成 0s —— 动效静默消失
    expect(info.duration).not.toBe('0s');
    expect(info.duration).toMatch(/\d/);
    expect(info.property).toContain('opacity');
    expect(info.property).toContain('transform');
  });

  test('同组错落：同父容器下第 2 个起的延迟依次递增', async ({ page }) => {
    await page.goto('/');
    const delays = await page.evaluate(() => {
      // 首页 .grid 里的四张项目卡是典型的同组元素
      const cards = Array.from(document.querySelectorAll('.grid .reveal'));
      return cards.map((el) => getComputedStyle(el).transitionDelay);
    });
    expect(delays.length).toBeGreaterThanOrEqual(3);
    // 第一个不该有延迟，后面的应当依次变大
    const toMs = (s) => {
      const first = String(s).split(',')[0].trim();
      return first.endsWith('ms') ? parseFloat(first) : parseFloat(first) * 1000;
    };
    const ms = delays.map(toMs);
    expect(ms[0]).toBe(0);
    for (let i = 1; i < ms.length; i++) {
      expect(ms[i]).toBeGreaterThan(ms[i - 1]);
    }
  });

  test('封顶 320ms：长列表不会让最后一个元素等太久', async ({ page }) => {
    await page.goto('/blog/index.html');
    // 造一个超长的同组列表，验证封顶真的生效
    const maxDelay = await page.evaluate(() => {
      const wrap = document.querySelector('.wrap');
      const probe = document.createElement('div');
      // 复用 .grid 的 --i 机制，但直接给 40 个元素手工注入 --i
      for (let i = 0; i < 40; i++) {
        const d = document.createElement('div');
        d.className = 'reveal';
        d.style.setProperty('--i', String(i));
        probe.appendChild(d);
      }
      wrap.appendChild(probe);
      const last = probe.lastElementChild;
      const v = getComputedStyle(last).transitionDelay;
      probe.remove();
      const first = String(v).split(',')[0].trim();
      return first.endsWith('ms') ? parseFloat(first) : parseFloat(first) * 1000;
    });
    expect(maxDelay).toBeLessThanOrEqual(320);
  });

  test('开启动效时按钮标为选中，且 html 上有 data-motion=on', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'on');
    await expect(page.locator('[data-motion-option="on"]')).toHaveClass(/is-active/);
    await expect(page.locator('[data-motion-option="off"]')).not.toHaveClass(/is-active/);
  });

  test('在面板里关掉动效：立即生效且刷新后保持', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();

    await expect(page.locator('html')).toHaveAttribute('data-motion', 'off');
    await expect(page.locator('[data-motion-option="off"]')).toHaveClass(/is-active/);

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'off');
  });

  test('关掉动效后过渡时长归零，内容仍然全部可见', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();
    await page.keyboard.press('Escape');

    const result = await page.evaluate(() => {
      const el = document.querySelector('.reveal');
      const cs = getComputedStyle(el);
      return { duration: cs.transitionDuration, opacity: cs.opacity };
    });
    // 归零的是"变化过程"，不是"最终状态"——
    // 内容必须仍然可见，否则开关就成了"关掉内容"
    expect(result.duration).toMatch(/^0(\.\d+)?m?s/);
    expect(result.opacity).toBe('1');
  });

  test('总开关真的把动效令牌归零（不只是把 transition 关掉）', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();

    // 上面那条测的是 .reveal 的 transitionDuration，而总开关里对应的
    // 规则是 transition:none —— 无论 --dur-base 被改成多少，它都是 0s。
    // 也就是说把 --dur-base:1ms 改成 500ms，上面那条照样绿。
    // 这条直接读令牌的计算值，才是真正在守总开关。
    const html = page.locator('html');
    await expect(html).toHaveCSS('--dur-fast', '1ms');
    await expect(html).toHaveCSS('--dur-base', '1ms');
    await expect(html).toHaveCSS('--dur-slow', '1ms');
    await expect(html).toHaveCSS('--shift-sm', '0px');
    await expect(html).toHaveCSS('--shift-md', '0px');
    await expect(html).toHaveCSS('--shift-lg', '0px');
  });

  test('开启动效时令牌没有被归零（防止总开关写反、永远生效）', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="on"]').click();

    // 反向断言：只要求"不是归零值"。不写死 240ms/6px 这些具体数字，
    // 因为它们在 @media 里另有覆盖，写死会让测试和排版改动互相打架。
    const tokens = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      return {
        base: cs.getPropertyValue('--dur-base').trim(),
        shift: cs.getPropertyValue('--shift-md').trim(),
      };
    });
    expect(tokens.base).not.toBe('1ms');
    expect(tokens.shift).not.toBe('0px');
  });

  test('关掉动效后不做滚动淡入，元素直接就在', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();
    await page.reload();

    // 无需滚动，所有 .reveal 都应当已经有 .in
    await page.waitForTimeout(200);
    const pending = await page.locator('.reveal:not(.in)').count();
    expect(pending, '关闭动效后不该还有元素在等待淡入').toBe(0);
  });

  test('关掉再打开：动效能回来（防止属性残留）', async ({ page }) => {
    // 回归测试：theme-boot.js 若只在 off 时写属性，
    // 用户切回开启后 html 上会残留 data-motion="off"，动效再也回不来。
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'off');

    await page.locator('[data-motion-option="on"]').click();
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'on');

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-motion', 'on');
    // 恢复后应当重新出现等待淡入的元素
    const n = await page.locator('.reveal').count();
    expect(n).toBeGreaterThan(0);
  });

  test('动效开关不产生 CSP 违规', async ({ page }) => {
    // 切换开关会写行内自定义属性（--i / data-motion），
    // 必须确认这条路没有踩到 style-src 'self'
    const violations = [];
    page.on('console', (msg) => {
      const t = msg.text();
      if (/Content Security Policy|CSP/i.test(t)) violations.push(t);
    });

    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-motion-option="off"]').click();
    await page.locator('[data-motion-option="on"]').click();
    await page.locator('[data-theme-option="light"]').click();
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    expect(violations, 'CSP 违规：\n' + violations.join('\n')).toEqual([]);
  });

  test('设置面板有可过渡的进出场（不再是 display 硬切）', async ({ page }) => {
    await page.goto('/');
    await page.locator('.prefs-toggle').click();

    // 必须先等过渡播完再断言。
    // visibility 是离散属性：过渡期间它会保持起始值（hidden），
    // 过渡结束才跳到 visible；而 opacity 是连续属性，会一路爬升。
    // 所以「可见」的那一刻 opacity 往往只有 0.8，
    // 直接断言 1 会失败 —— 这是过渡的正常中间态，不是 bug。
    await expect
      .poll(async () => page.evaluate(() => {
        const cs = getComputedStyle(document.querySelector('.prefs-panel'));
        return { visibility: cs.visibility, opacity: cs.opacity };
      }), { timeout: 2000 })
      .toEqual({ visibility: 'visible', opacity: '1' });

    const info = await page.evaluate(() => {
      const cs = getComputedStyle(document.querySelector('.prefs-panel'));
      return {
        duration: cs.transitionDuration,
        property: cs.transitionProperty,
      };
    });
    // display:none 是没法做过渡的，有非零时长才说明改成了可过渡方案
    expect(info.duration).not.toBe('0s');
    expect(info.property).toContain('opacity');
  });

  test('面板展开期间不会闪现（过渡中途就是可见的）', async ({ page }) => {
    // 补一条正向断言：确认「先 hidden 后 visible」的变化
    // 发生在 240ms 内，而不是一直不可见
    await page.goto('/');
    await page.locator('.prefs-toggle').click();
    await page.waitForFunction(() => {
      const cs = getComputedStyle(document.querySelector('.prefs-panel'));
      return cs.visibility === 'visible' && parseFloat(cs.opacity) > 0.5;
    }, null, { timeout: 2000 });
  });

  test('增强对比度偏好下只做位移、不做透明度过渡', async ({ page }) => {
    // 这类用户对低透明度元素的辨识力更差，
    // 若仍然淡入，内容会有一段"看不见"的时间
    await page.emulateMedia({ contrast: 'more' });
    await page.goto('/');
    const opacity = await page.evaluate(
      () => getComputedStyle(document.querySelector('.reveal')).opacity,
    );
    expect(opacity).toBe('1');
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
    // 从卡片自身的 href 推出目标，不写死文章编号 ——
    // 否则每次调整列表排序都会误报（列表本来就该能重新排序）。
    const href = await first.getAttribute('href');
    expect(href).toMatch(/^post-\d+\.html$/);

    await first.click();
    await expect(page).toHaveURL(new RegExp(href.replace('.', '\\.')));
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

test.describe('PWA：可安装与离线', () => {
  // Service Worker 在测试间不共享状态：每个 test 都是全新的 context，
  // 必须重新等它就绪，不能依赖上一个用例的注册结果。
  async function waitForSW(page) {
    await page.evaluate(async () => {
      await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, rej) => setTimeout(() => rej(new Error('SW 就绪超时')), 15000)),
      ]);
    });
  }

  test('Service Worker 注册成功且作用域覆盖全站', async ({ page }) => {
    await page.goto('/index.html');
    await waitForSW(page);

    const info = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.ready;
      return { scope: reg.scope, scriptURL: reg.active?.scriptURL ?? null };
    });

    expect(info.scriptURL).toContain('/sw.js');
    // 作用域必须是站点根，否则 blog/ 下的页面不会走缓存
    expect(new URL(info.scope).pathname).toBe('/');
  });

  test('manifest 能被浏览器取到且是合法 JSON', async ({ page, request }) => {
    const res = await request.get('/manifest.webmanifest');
    expect(res.status()).toBe(200);
    const m = await res.json();
    expect(m.name).toBeTruthy();
    expect(m.scope).toBe('/');
    expect(m.display).toBe('standalone');

    // 页面里真的声明了它（否则浏览器不知道有这个清单）
    await page.goto('/index.html');
    const href = await page.getAttribute('link[rel="manifest"]', 'href');
    expect(href).toBeTruthy();
  });

  test('所有 PWA 图标可访问', async ({ request }) => {
    const icons = [
      '/assets/icons/icon-192.png',
      '/assets/icons/icon-512.png',
      '/assets/icons/icon-maskable-512.png',
      '/assets/icons/apple-touch-icon-180.png',
    ];
    for (const src of icons) {
      const res = await request.get(src);
      expect(res.status(), `${src} 应当可访问`).toBe(200);
      expect(res.headers()['content-type']).toContain('image/png');
    }
  });

  test('断网后仍能打开首页（核心能力）', async ({ page, context }) => {
    await page.goto('/index.html');
    await waitForSW(page);
    // 等预缓存装完再断网，否则测的是「还没缓存好」而不是「离线可用」
    await page.waitForFunction(async () => {
      const names = await caches.keys();
      if (!names.length) return false;
      const c = await caches.open(names[0]);
      return (await c.keys()).length > 5;
    }, null, { timeout: 15000 });

    await context.setOffline(true);
    const res = await page.goto('/index.html');

    expect(res.status()).toBe(200);
    await expect(page).toHaveTitle(/xiaoyu-hue/);
  });

  test('断网后仍能打开已缓存的文章', async ({ page, context }) => {
    await page.goto('/index.html');
    await waitForSW(page);
    await page.waitForFunction(async () => {
      const names = await caches.keys();
      if (!names.length) return false;
      const c = await caches.open(names[0]);
      return (await c.keys()).length > 5;
    }, null, { timeout: 15000 });

    await context.setOffline(true);
    const res = await page.goto('/blog/post-3.html');

    expect(res.status()).toBe(200);
    await expect(page).toHaveTitle(/Nymir/);
  });

  test('断网后访问未缓存页面会回退到离线页', async ({ page, context }) => {
    await page.goto('/index.html');
    await waitForSW(page);
    await page.waitForFunction(async () => {
      const names = await caches.keys();
      if (!names.length) return false;
      const c = await caches.open(names[0]);
      return (await c.keys()).length > 5;
    }, null, { timeout: 15000 });

    await context.setOffline(true);
    await page.goto('/this-page-was-never-cached.html');

    // 不校验状态码：不同浏览器回退时给的状态码不一致，
    // 真正的契约是「用户看到的是离线页」。
    await expect(page.locator('body')).toContainText('你现在离线了');
  });

  test('离线页自身不注册 Service Worker', async ({ page }) => {
    await page.goto('/offline.html');
    const hasPwa = await page.evaluate(
      () => document.querySelector('script[src*="pwa.js"]') !== null,
    );
    expect(hasPwa).toBe(false);
  });

  test('PWA 相关代码不产生 CSP 违规', async ({ page }) => {
    const violations = [];
    page.on('console', (msg) => {
      const t = msg.text();
      if (/Content Security Policy|CSP/i.test(t)) violations.push(t);
    });

    await page.goto('/index.html');
    await waitForSW(page);
    await page.waitForTimeout(1500);

    expect(violations, 'CSP 违规：\n' + violations.join('\n')).toEqual([]);
  });

  test('提示条默认隐藏，不占据首屏', async ({ page }) => {
    await page.goto('/index.html');
    // 更新提示与 iOS 引导都必须默认不可见，
    // 否则会莫名其妙地盖在内容上。
    await expect(page.locator('.pwa-update')).toBeHidden();
    await expect(page.locator('.pwa-ios-hint')).toBeHidden();
  });

  test('theme-color 跟随站内主题切换', async ({ page }) => {
    await page.goto('/index.html');
    await page.locator('.prefs-toggle').click();
    await page.locator('[data-theme-option="light"]').click();

    const colors = await page.evaluate(() =>
      Array.from(document.querySelectorAll('meta[name="theme-color"]'))
        .map((m) => m.getAttribute('content')),
    );
    // 手动选定后两个 meta 应当统一成浅色，避免状态栏和页面对不上
    expect(colors.length).toBe(2);
    for (const c of colors) expect(c).toBe('#eaf4fb');
  });
});
