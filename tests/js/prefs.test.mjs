// prefs.js 的纯逻辑测试。
//
// 定位说明：prefs.js 是 IIFE，无法 import，所以这里用 vm 沙箱 + 极简桩来跑。
// 覆盖的是「存储读写、数据校验、导入导出格式」这些不依赖真实浏览器的部分；
// 真实 DOM 交互（面板开关、文件导入）由 tests/e2e 覆盖。
//
// 运行：node --test tests/js/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(path.join(here, '..', '..', 'assets', 'prefs.js'), 'utf8');

const KEY = 'xiaoyu-hue:prefs:v1';

/** 造一个够用的 localStorage 桩 */
function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
    _dump: () => Object.fromEntries(map),
  };
}

/**
 * 在沙箱里执行 prefs.js。
 * pathname 用来模拟"当前在哪一页"，影响阅读进度的键名。
 */
function runPrefs({ storage = makeStorage(), light = false, pathname = '/', hasMatchMedia = true } = {}) {
  const sandbox = {};
  const listeners = {};

  sandbox.window = {
    localStorage: storage,
    location: { pathname },
    setTimeout: (fn) => { fn(); return 0; },
    clearTimeout: () => {},
    addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
    matchMedia: hasMatchMedia
      ? (q) => ({ matches: light && /light/.test(q), addEventListener: () => {}, addListener: () => {} })
      : undefined,
  };
  sandbox.document = {
    readyState: 'complete',
    documentElement: { setAttribute: () => {}, getAttribute: () => null },
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({ style: {}, classList: { add(){}, remove(){}, toggle(){} }, appendChild(){}, setAttribute(){}, click(){} }),
    body: { appendChild(){}, removeChild(){} },
  };
  sandbox.Blob = function () {};
  sandbox.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };
  sandbox.FileReader = function () {};
  sandbox.localStorage = storage;

  // IIFE 立即执行；把内部状态通过 storage 观察
  runInNewContext(SRC, sandbox);
  return { storage };
}

test('全新用户：不写入任何数据，只是空读', () => {
  const { storage } = runPrefs({ pathname: '/' });
  // 首页没有阅读进度可记，不该产生写入
  assert.equal(storage.getItem(KEY), null, '首次访问不该写入 localStorage');
});

test('打开博客文章后记录阅读进度', () => {
  const { storage } = runPrefs({ pathname: '/blog/post-3.html' });
  const raw = storage.getItem(KEY);
  assert.ok(raw, '应当写入 localStorage');
  const obj = JSON.parse(raw);
  assert.equal(obj.schema, 1, 'schema 版本应为 1');
  assert.ok(obj.reading['post-3'], '应记录 post-3');
  assert.match(obj.reading['post-3'].at, /^\d{4}-\d{2}-\d{2}T/, 'at 应为 ISO 时间');
});

test('阅读进度不会被二次访问覆盖首次时间', () => {
  const first = runPrefs({ pathname: '/blog/post-1.html' });
  const t1 = JSON.parse(first.storage.getItem(KEY)).reading['post-1'].at;
  // 用第一次的结果作为第二次的初始存储
  const second = runPrefs({ pathname: '/blog/post-1.html', storage: first.storage });
  const t2 = JSON.parse(second.storage.getItem(KEY)).reading['post-1'].at;
  assert.equal(t2, t1, '重复打开同一篇不该刷新首次阅读时间');
});

test('损坏的 localStorage 数据被忽略，不抛异常', () => {
  assert.doesNotThrow(() => {
    runPrefs({ storage: makeStorage({ [KEY]: '{ 这不是 JSON' }) });
  });
  assert.doesNotThrow(() => {
    runPrefs({ storage: makeStorage({ [KEY]: '{"schema":999,"theme":"rainbow"}' }) });
  });
});

test('schema 不匹配时忽略旧数据', () => {
  const stale = makeStorage({ [KEY]: JSON.stringify({ schema: 0, theme: 'dark', reading: {} }) });
  const { storage } = runPrefs({ storage: stale, pathname: '/blog/post-2.html' });
  const obj = JSON.parse(storage.getItem(KEY));
  assert.equal(obj.schema, 1, '应当用新 schema 覆盖');
  assert.ok(obj.reading['post-2'], '新数据应正常记录');
});

test('localStorage 被禁用时不抛异常（隐私模式）', () => {
  const broken = {
    getItem: () => { throw new Error('SecurityError'); },
    setItem: () => { throw new Error('SecurityError'); },
    removeItem: () => { throw new Error('SecurityError'); },
  };
  assert.doesNotThrow(() => {
    runPrefs({ storage: broken, pathname: '/blog/post-1.html' });
  });
});

test('非文章页不产生阅读记录', () => {
  for (const p of ['/', '/blog/index.html']) {
    const { storage } = runPrefs({ pathname: p });
    assert.equal(storage.getItem(KEY), null, `${p} 不该写入阅读进度`);
  }
});
