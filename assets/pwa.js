// PWA 客户端逻辑：注册 Service Worker、新版本提示、安装引导。
//
// 与 prefs.js 的分工：prefs.js 管「用户偏好」（主题、阅读进度），
// 本文件管「应用生命周期」（离线、更新、安装）。两者互不依赖。
//
// 三条约束（改动前必读）：
// 1. CSP 为 style-src 'self'，所有视觉效果必须用 class 切换，
//    不能用 el.style.xxx。样式写在 assets/style.css 里。
// 2. Service Worker 只在 HTTPS 或 localhost 下可用；
//    其他环境下 navigator.serviceWorker 存在但注册会失败，需静默降级。
// 3. SW 必须用绝对路径 /sw.js 注册。用相对路径 'sw.js' 时，
//    blog/post-1.html 会去找 /blog/sw.js，直接 404。
(function () {
  'use strict';

  // ---------- 工具 ----------

  function store(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* 隐私模式下静默降级 */ }
    return null;
  }

  function session(key, value) {
    try {
      if (value === undefined) return window.sessionStorage.getItem(key);
      window.sessionStorage.setItem(key, value);
    } catch (e) { /* 同上 */ }
    return null;
  }

  // ---------- 1. 注册 Service Worker ----------

  function registerSW() {
    if (!('serviceWorker' in navigator)) return;

    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function (reg) {
          watchUpdate(reg);
        })
        .catch(function (err) {
          // 本地用 http:// 非 localhost 访问、或浏览器禁用 SW 时会走到这里。
          // 离线功能不可用，但站点本身照常工作，不需要打扰用户。
          if (window.console && console.info) {
            console.info('[pwa] Service Worker 未注册（不影响站点功能）：', err.message);
          }
        });
    });
  }

  // ---------- 2. 新版本提示 ----------

  function watchUpdate(reg) {
    // 已有 SW 在控制这个页面，才谈得上「更新」。
    // 首次安装时 controller 为空，不该弹提示。
    if (!navigator.serviceWorker.controller) return;

    reg.addEventListener('updatefound', function () {
      var incoming = reg.installing;
      if (!incoming) return;

      incoming.addEventListener('statechange', function () {
        if (incoming.state !== 'installed') return;
        if (!navigator.serviceWorker.controller) return;
        // 本次会话已经点过「稍后」就不再打扰
        if (session('xiaoyu-hue:update-dismissed') === '1') return;
        showUpdateBar(reg);
      });
    });
  }

  function showUpdateBar(reg) {
    var bar = document.querySelector('.pwa-update');
    if (!bar) return;

    var reloading = false;
    // 新 SW 接管后刷新页面，用户才会看到新内容
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    });

    bar.classList.add('is-visible');

    var btnGo = bar.querySelector('.pwa-update-go');
    var btnLater = bar.querySelector('.pwa-update-later');

    if (btnGo) {
      btnGo.addEventListener('click', function () {
        bar.classList.remove('is-visible');
        if (reg.waiting) {
          // 等用户确认后才让它跳过等待，见 sw.js 的 message 处理
          reg.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
      });
    }
    if (btnLater) {
      btnLater.addEventListener('click', function () {
        bar.classList.remove('is-visible');
        session('xiaoyu-hue:update-dismissed', '1');
      });
    }
  }

  // ---------- 3. 安装引导 ----------

  function isIOS() {
    var ua = navigator.userAgent || '';
    // iPadOS 13+ 的 UA 伪装成 macOS，靠触摸点数区分
    var iPadOS = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
    return /iPhone|iPad|iPod/.test(ua) || iPadOS;
  }

  function isStandalone() {
    // iOS 用 navigator.standalone；其他平台用 display-mode 媒体查询
    if (navigator.standalone) return true;
    try {
      return window.matchMedia('(display-mode: standalone)').matches;
    } catch (e) {
      return false;
    }
  }

  function setupIOSHint() {
    if (!isIOS()) return;
    if (isStandalone()) return;
    if (store('xiaoyu-hue:ios-hint-dismissed') === '1') return;

    var bar = document.querySelector('.pwa-ios-hint');
    if (!bar) return;

    bar.classList.add('is-visible');

    var btn = bar.querySelector('.pwa-ios-close');
    if (btn) {
      btn.addEventListener('click', function () {
        bar.classList.remove('is-visible');
        store('xiaoyu-hue:ios-hint-dismissed', '1');
      });
    }
  }

  // 注：曾有一个 setupInstallButton()，监听 beforeinstallprompt 并驱动
  // 页面里的 .pwa-install 按钮。但 .pwa-install / .pwa-install-note 这两个
  // 元素在任何页面都不存在，函数第一行 `if (!btn) return` 之后就再无执行，
  // 属纯死代码，已删除。清单（manifest）本身完整可安装，浏览器原生安装提示
  // 不受影响；若日后要提供站内安装入口，再连同按钮一起加回来。

  // ---------- 4. theme-color 跟随站内主题 ----------
  //
  // manifest 的 theme_color 是单值，<head> 里用两个带 media 的
  // <meta name="theme-color"> 按系统偏好自动选。
  // 但用户在站内手动切主题时不走 prefers-color-scheme，
  // 已安装的 PWA 状态栏颜色会和页面打架，所以这里主动同步。
  //
  // 只改 <meta> 的 content 属性，不碰内联样式，CSP 允许。

  var THEME_COLORS = { dark: '#04111d', light: '#eaf4fb' };

  function syncThemeColor() {
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    if (!metas.length) return;

    var effective = document.documentElement.getAttribute('data-theme') || 'dark';
    var color = THEME_COLORS[effective] || THEME_COLORS.dark;
    var isSystem = document.documentElement.getAttribute('data-theme-pref') === 'system';

    Array.prototype.forEach.call(metas, function (m) {
      if (isSystem) {
        // 跟随系统时把控制权还给 media 查询，恢复各自原本的颜色
        var media = m.getAttribute('media') || '';
        m.setAttribute('content', /light/.test(media) ? THEME_COLORS.light : THEME_COLORS.dark);
      } else {
        // 用户手动选定后，两个 meta 统一成同一个颜色，谁都不会覆盖错
        m.setAttribute('content', color);
      }
    });
  }

  function observeTheme() {
    syncThemeColor();
    // data-theme 由 prefs.js 写在 <html> 上，用 MutationObserver 跟着它变，
    // 这样主题切换逻辑仍然只存在于 prefs.js 一处。
    if (typeof MutationObserver === 'function') {
      new MutationObserver(syncThemeColor).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme', 'data-theme-pref'],
      });
    }
  }

  // ---------- 启动 ----------

  function boot() {
    registerSW();
    setupIOSHint();
    observeTheme();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
