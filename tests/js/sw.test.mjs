// sw.js 策略判定逻辑的单元测试。
//
// 定位说明：sw.js 是 Service Worker 脚本，依赖 self、caches、fetch 等
// 全局对象，无法直接 import。它主动把纯函数挂在 self.__sw 上，
// 这里用 vm 沙箱造一个最小 self，只取那几个函数来测分支。
//
// 这一层测的是「判定逻辑对不对」，不测缓存行为本身 ——
// 真实行为（真的断网能不能打开）由 tests/e2e 用真 Chromium 覆盖。
//
// 运行：node --test "tests/js/**/*.test.mjs"

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(path.join(here, '..', '..', 'sw.js'), 'utf8');

const ORIGIN = 'https://xiaoyu-hue.github.io';

/**
 * 在沙箱里执行 sw.js，取回它导出的纯函数。
 *
 * 沙箱需要提供 self.location.origin（shouldBypass 用它判断跨域），
 * 以及各事件注册函数（注册时不执行回调，所以给空函数即可）。
 */
function loadSW() {
  const noop = () => {};
  const sandbox = {
    self: {
      location: { origin: ORIGIN },
      addEventListener: noop,
      skipWaiting: noop,
      clients: { claim: noop },
    },
    caches: { open: noop, keys: noop, match: noop, delete: noop },
    fetch: noop,
    Response: { error: noop },
    Request: function Request() {},
    URL,
    console: { warn: noop, info: noop, log: noop },
    Promise,
  };
  sandbox.self.self = sandbox.self;
  runInNewContext(SOURCE, sandbox);
  return sandbox.self.__sw;
}

/** 造一个最小 Request 形状的桩。 */
function req(url, { method = 'GET', mode = 'cors' } = {}) {
  return { url, method, mode };
}

const sw = loadSW();

// ---------- shouldBypass ----------

test('非 GET 请求一律放行', () => {
  for (const method of ['POST', 'PUT', 'DELETE', 'HEAD', 'PATCH']) {
    assert.equal(
      sw.shouldBypass(req(`${ORIGIN}/index.html`, { method })),
      true,
      `${method} 应当被放行`,
    );
  }
});

test('跨域请求一律放行', () => {
  assert.equal(
    sw.shouldBypass(req('https://example.com/x.js')),
    true,
    '跨域请求应当被放行',
  );
});

test('同源 GET 请求才介入', () => {
  assert.equal(sw.shouldBypass(req(`${ORIGIN}/index.html`)), false);
  assert.equal(sw.shouldBypass(req(`${ORIGIN}/assets/style.css`)), false);
});

test('非 http(s) 协议放行', () => {
  assert.equal(sw.shouldBypass(req('data:text/plain,hi')), true);
  assert.equal(sw.shouldBypass(req('blob:https://x/y')), true);
});

test('无法解析的 URL 放行，不抛错', () => {
  assert.doesNotThrow(() => sw.shouldBypass(req('这不是一个 URL')));
  assert.equal(sw.shouldBypass(req('这不是一个 URL')), true);
});

// ---------- kindOf ----------

test('导航请求识别为 navigation', () => {
  assert.equal(
    sw.kindOf(req(`${ORIGIN}/`, { mode: 'navigate' })),
    sw.KIND.NAVIGATION,
  );
  assert.equal(
    sw.kindOf(req(`${ORIGIN}/blog/post-1.html`, { mode: 'navigate' })),
    sw.KIND.NAVIGATION,
  );
});

test('常见静态资源后缀识别为 asset', () => {
  const paths = [
    '/assets/style.css',
    '/assets/main.js',
    '/assets/pwa.js',
    '/assets/favicon.svg',
    '/assets/icons/icon-192.png',
    '/manifest.webmanifest',
    '/fonts/x.woff2',
  ];
  for (const p of paths) {
    assert.equal(sw.kindOf(req(ORIGIN + p)), sw.KIND.ASSET, `${p} 应当是 asset`);
  }
});

test('HTML 不是 asset —— 它必须走网络优先', () => {
  // 这条是整个 SW 里最关键的判断：
  // 一旦 HTML 被当成 asset（缓存优先），用户将永远看不到更新。
  assert.equal(sw.kindOf(req(`${ORIGIN}/index.html`)), sw.KIND.OTHER);
  assert.equal(sw.kindOf(req(`${ORIGIN}/blog/post-1.html`)), sw.KIND.OTHER);
});

test('后缀匹配不区分大小写', () => {
  assert.equal(sw.kindOf(req(`${ORIGIN}/assets/Style.CSS`)), sw.KIND.ASSET);
  assert.equal(sw.kindOf(req(`${ORIGIN}/assets/Icon-192.PNG`)), sw.KIND.ASSET);
});

test('相似但不匹配的后缀不会被误判', () => {
  // .jsx / .css.map 这类不该被当成可长期缓存的资源
  assert.equal(sw.kindOf(req(`${ORIGIN}/x.jsx`)), sw.KIND.OTHER);
  assert.equal(sw.kindOf(req(`${ORIGIN}/x.jsonlike`)), sw.KIND.OTHER);
});

// ---------- 预缓存清单 ----------

test('预缓存清单非空且无重复', () => {
  assert.ok(sw.PRECACHE.length > 0, 'PRECACHE 不能为空');
  assert.equal(
    new Set(sw.PRECACHE).size,
    sw.PRECACHE.length,
    'PRECACHE 有重复项',
  );
});

test('预缓存路径全部以 / 开头', () => {
  for (const p of sw.PRECACHE) {
    assert.ok(p.startsWith('/'), `${p} 应当以 / 开头`);
  }
});

test('预缓存必须包含首页、离线页与离线脚本', () => {
  for (const needed of ['/index.html', '/offline.html', '/assets/offline.js']) {
    assert.ok(sw.PRECACHE.includes(needed), `PRECACHE 缺少 ${needed}`);
  }
});

test('预缓存不包含 og-cover.png', () => {
  // 它是给社交爬虫看的，用户浏览时从不加载，500KB 白下载
  assert.ok(
    !sw.PRECACHE.some((p) => p.includes('og-cover')),
    'og-cover.png 不该进预缓存清单',
  );
});

// ---------- 缓存命名 ----------

test('缓存名带版本号，便于发布时整体替换', () => {
  assert.match(sw.CACHE_NAME, /^xiaoyu-hue-v\d+$/);
});

// ---------- 什么响应才配进缓存 ----------

test('shouldCache：只认成功响应', () => {
  assert.equal(sw.shouldCache({ ok: true }), true, '2xx 应当缓存');
  assert.equal(sw.shouldCache({ ok: false }), false, '4xx/5xx 不该缓存');
  assert.equal(sw.shouldCache(null), false, 'null 不该缓存');
  assert.equal(sw.shouldCache(undefined), false, 'undefined 不该缓存');
});

test('shouldCache：挡住 404 才是它存在的理由', () => {
  // 导航请求以前缺这个判断，404 会被写进缓存。后果不是"多存了一个
  // 坏条目"那么轻：用户之后离线打开那页就是一张 404，而且清不掉，
  // 只能等站点改 CACHE_VERSION 发版。
  const notFound = { ok: false, status: 404 };
  assert.equal(sw.shouldCache(notFound), false);
});

test('三个分支都用 shouldCache，没人手写 fresh.ok 绕过', () => {
  // 以前是三处各写一遍 fresh.ok，导航那个漏了才出的问题。
  // 收敛成一个函数之后，这里守住"别再有人绕过它"。
  const calls = SOURCE.match(/if \(shouldCache\(/g) || [];
  assert.equal(calls.length, 3, `应当有 3 处调用 shouldCache，实际 ${calls.length} 处`);

  // 先剥掉注释再查。shouldCache 自己的说明里就写了 fresh.ok 这个
  // 反例（正是它解释的来历），不剥离会被自己误判成"有人绕过了"。
  const codeOnly = SOURCE
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
  const withoutFn = codeOnly.replace(/function shouldCache[\s\S]*?\n}/, '');
  assert.ok(
    !/\.ok\b/.test(withoutFn),
    '除了 shouldCache 内部，不该再有裸的 .ok 判断',
  );
});
