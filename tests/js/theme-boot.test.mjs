// theme-boot.js 的逻辑测试。
//
// 定位说明：这个文件跑在 <head> 里、样式表之前，是「首屏不闪」的唯一保障。
// 它出的问题都很难自查（表现为"刷新时黑一下"这种一闪而过的主观感受），
// 所以用逻辑测试把它的分支钉死。
//
// 覆盖重点：
// - data-motion 必须「无条件写入」而不是「只在 off 时写入」
// - 老数据缺 motion 字段时要当作 on（不能突然把老用户的动效关掉）
// - 任何异常都不能让它崩掉，否则连主题都应用不了
//
// 运行：node --test tests/js/

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(
  path.join(here, '..', '..', 'assets', 'theme-boot.js'),
  'utf8',
);

const KEY = 'xiaoyu-hue:prefs:v1';

/**
 * 在沙箱里执行 theme-boot.js，返回它写进 documentElement 的属性。
 *
 * @param {object} opts
 * @param {string|null} opts.raw        localStorage 里存的原始字符串
 * @param {boolean} opts.systemLight    系统是否浅色（仅 theme=system 时有意义）
 * @param {boolean} opts.storageThrows  localStorage 读取是否抛异常
 */
function runBoot({ raw = null, systemLight = false, storageThrows = false } = {}) {
  const attrs = {};
  const sandbox = {
    document: {
      documentElement: {
        setAttribute: (k, v) => { attrs[k] = v; },
      },
    },
    window: {
      localStorage: {
        getItem: () => {
          if (storageThrows) throw new Error('SecurityError');
          return raw;
        },
      },
      matchMedia: (q) => ({
        matches: /light/.test(q) ? systemLight : false,
      }),
    },
  };
  runInNewContext(SOURCE, sandbox);
  return attrs;
}

const prefs = (obj) => JSON.stringify(obj);

// ---------- 主题 ----------

test('全新用户：跟随系统，深色系统给 dark', () => {
  const attrs = runBoot({});
  assert.equal(attrs['data-theme'], 'dark');
  assert.equal(attrs['data-theme-pref'], 'system');
});

test('全新用户：跟随系统，浅色系统给 light', () => {
  const attrs = runBoot({ systemLight: true });
  assert.equal(attrs['data-theme'], 'light');
  assert.equal(attrs['data-theme-pref'], 'system');
});

test('显式选浅色时不受系统深色影响', () => {
  const raw = prefs({ schema: 1, theme: 'light', motion: 'on' });
  const attrs = runBoot({ raw, systemLight: false });
  assert.equal(attrs['data-theme'], 'light');
  assert.equal(attrs['data-theme-pref'], 'light');
});

test('schema 不匹配的旧数据被忽略，退回跟随系统', () => {
  const raw = prefs({ schema: 0, theme: 'light', motion: 'off' });
  const attrs = runBoot({ raw, systemLight: false });
  assert.equal(attrs['data-theme'], 'dark');
  assert.equal(attrs['data-theme-pref'], 'system');
  assert.equal(attrs['data-motion'], 'on', '旧 schema 数据整体作废，动效也要退回默认');
});

test('theme 取值非法时退回跟随系统，但 motion 仍可生效', () => {
  const raw = prefs({ schema: 1, theme: 'rainbow', motion: 'off' });
  const attrs = runBoot({ raw });
  assert.equal(attrs['data-theme-pref'], 'system', '非法主题值不该被采信');
  assert.equal(attrs['data-motion'], 'off', '同一份数据里合法的字段仍应生效');
});

// ---------- 动效（本次新增的核心） ----------

test('motion=off 时写入 off', () => {
  const raw = prefs({ schema: 1, theme: 'system', motion: 'off' });
  const attrs = runBoot({ raw });
  assert.equal(attrs['data-motion'], 'off');
});

test('motion=on 时**必须**显式写入 on', () => {
  // 这是本文件最容易写错的一处：
  // 如果只在 off 时写属性，用户把开关从 off 切回 on 后，
  // html 上残留的 data-motion="off" 永远不会被清掉，
  // 表现为「关了之后再也打不开动效」，且刷新也没用。
  const raw = prefs({ schema: 1, theme: 'system', motion: 'on' });
  const attrs = runBoot({ raw });
  assert.equal(attrs['data-motion'], 'on');
});

test('老数据缺 motion 字段：当作 on，不打扰老用户', () => {
  // 本次改动之前写入的数据都没有 motion 字段（PWA 版本升上来的用户），
  // 不能因为字段缺失就默认给他们关掉动效。
  const raw = prefs({ schema: 1, theme: 'dark', reading: { 'post-1': { at: 'x' } } });
  const attrs = runBoot({ raw });
  assert.equal(attrs['data-motion'], 'on');
});

test('motion 取值意外时不关动效', () => {
  for (const weird of ['OFF', 'true', 0, null, {}, 'yes']) {
    const raw = prefs({ schema: 1, theme: 'system', motion: weird });
    const attrs = runBoot({ raw });
    assert.equal(attrs['data-motion'], 'on', `motion=${JSON.stringify(weird)} 不该关掉动效`);
  }
});

test('全新用户默认开动效', () => {
  const attrs = runBoot({});
  assert.equal(attrs['data-motion'], 'on');
});

// ---------- 健壮性 ----------

test('localStorage 抛异常时不崩，属性仍全部写入', () => {
  let attrs;
  assert.doesNotThrow(() => {
    attrs = runBoot({ storageThrows: true });
  });
  // 关键：即使读不到偏好，也必须把三个属性写全。
  // 少了 data-motion，CSS 的 :root[data-motion="off"] 规则就没法覆盖，
  // 用户切开关时会出现「本次会话生效、刷新后失效」的诡异现象。
  assert.equal(attrs['data-theme'], 'dark');
  assert.equal(attrs['data-theme-pref'], 'system');
  assert.equal(attrs['data-motion'], 'on');
});

test('localStorage 里是非法 JSON 时不崩', () => {
  let attrs;
  assert.doesNotThrow(() => {
    attrs = runBoot({ raw: '{ 这不是 JSON' });
  });
  assert.equal(attrs['data-motion'], 'on');
});

test('三个属性在任何路径下都会被写全', () => {
  // 参数化跑一遍所有输入形态，确认没有"少写一个属性"的分支
  const cases = [
    {},
    { raw: prefs({ schema: 1, theme: 'light', motion: 'off' }) },
    { raw: prefs({ schema: 1, theme: 'dark', motion: 'on' }) },
    { raw: 'null' },
    { raw: '[]' },
    { storageThrows: true },
  ];
  for (const c of cases) {
    const attrs = runBoot(c);
    for (const key of ['data-theme', 'data-theme-pref', 'data-motion']) {
      assert.ok(
        attrs[key] !== undefined,
        `输入 ${JSON.stringify(c)} 下漏写了 ${key}`,
      );
    }
  }
});
