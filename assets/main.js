// 滚动淡入 + 同组错落编排。
//
// 本文件是「微动效系统」的第 1 层（编排）与第 2 层（降级）的运行时部分。
// CSS 那边的第 0/3/4 层见 assets/style.css 末尾的「微动效系统」块。
//
// 改动前必读的三条约束：
// 1. CSP 为 style-src 'self'，没有 unsafe-inline。所以这里给元素写
//    --i 只能用 el.style.setProperty（行内自定义属性），不能用
//    setAttribute('style', ...)。前者不触发 CSP，后者会。（见下方说明）
// 2. CSP 为 script-src 'self'，一切逻辑都在本文件里，不许内联。
// 3. 无论发生什么，.reveal 元素最终都必须可见。
//    动效可以不要，内容不能没有 —— 这是整个系统的第一原则。

(function () {
  'use strict';

  var REVEAL = '.reveal';
  // 兜底硬超时：超过这个时间还没被观察到的元素，一律强制显示。
  // 存在的意义：IntersectionObserver 有个极小概率不回调的场景 ——
  // 元素在 observer 注册前就被脚本移出文档、或页面在后台标签页里
  // 被浏览器完全冻结。没有这条兜底，用户会看到一块永久空白。
  var REVEAL_TIMEOUT = 1500;

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  // ---------- 偏好读取 ----------
  // 为什么在这里再读一次 localStorage，而 theme-boot.js 已经读过：
  // theme-boot.js 只负责「第一帧之前」把属性写上去，它跑在 <head> 里，
  // 那时 DOM 还不存在，没法做任何元素级处理。本文件跑在 </body> 前，
  // 需要知道用户关没关动效，才能决定要不要装观察器。
  // 两处读的是同一个键，取值逻辑刻意保持简单，不做二次抽象 ——
  // 抽成共享模块要多一个 <script>，而多一个脚本就多一次串行请求，
  // 对首屏是净损失。
  function readPrefs() {
    try {
      var raw = window.localStorage.getItem('xiaoyu-hue:prefs:v1');
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (!obj || obj.schema !== 1) return null;
      return obj;
    } catch (e) {
      return null;   // 隐私模式 / 数据损坏：当作没有偏好
    }
  }

  function motionEnabled() {
    // 优先级最高：用户在设置面板里关掉了动效
    var root = document.documentElement;
    if (root && root.getAttribute('data-motion') === 'off') return false;
    var saved = readPrefs();
    if (saved && saved.motion === 'off') return false;
    // 其次：用户在操作系统里声明了「减少动画」
    try {
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return false;
      }
    } catch (e) {
      // matchMedia 不可用时按「允许动效」处理，
      // 因为 CSS 那边还有 @media(scripting:none) 与
      // @media(prefers-reduced-motion) 两道独立兜底
    }
    return true;
  }

  // ---------- 第 1 层：编排 ----------
  // 给每个 .reveal 元素标注它在「同组」里的序号，CSS 用
  // transition-delay: min(calc(--stagger-step * --i), 320ms) 消费它。
  //
  // 什么叫同组：同一个直接父元素下的 .reveal 算一组。
  // 为什么不是整页统一编号：整页编号会让首屏之外的元素也排到很后面，
  // 用户滚动到那里时延迟早就过完了，等于白排；
  // 按父元素分组，每一屏内的元素各自从头错落，节奏才对。
  function assignStaggerIndex() {
    var groups = new Map();
    all(REVEAL).forEach(function (el) {
      var parent = el.parentElement || document.body;
      var list = groups.get(parent);
      if (!list) {
        list = [];
        groups.set(parent, list);
      }
      list.push(el);
    });
    groups.forEach(function (list) {
      list.forEach(function (el, i) {
        // 只写真正需要错落的（第 2 个及以后）。
        // 第 1 个不写，让 CSS 的 var(--i, 0) 走缺省值，
        // 少一次行内属性写入 —— 首屏元素越少改动越好。
        if (i === 0) return;
        el.style.setProperty('--i', String(i));
      });
    });
  }

  // ---------- 第 2 层：降级 ----------
  // 路径 3：浏览器不支持 IntersectionObserver
  // 路径 4：动效逻辑本身抛异常
  // 两条都走同一个出口 —— 全部立刻显示。
  function showAll(reason) {
    all(REVEAL).forEach(function (el) { el.classList.add('in'); });
    if (reason && window.console && console.info) {
      console.info('[motion] 已降级为「立即显示」：' + reason);
    }
  }

  function initReveal() {
    if (!motionEnabled()) {
      showAll('用户关闭了动效');
      return;
    }
    if (!('IntersectionObserver' in window)) {
      showAll('浏览器不支持 IntersectionObserver');
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });

    all(REVEAL).forEach(function (el) { io.observe(el); });

    // 硬超时兜底。清定时器不是必须的（元素已可见，再 add 一次 .in
    // 无副作用），但保留是为了让「降级日志」只在真的出问题时打出来，
    // 免得正常情况也刷一行 info，掩盖真正的异常。
    var timer = window.setTimeout(function () {
      var pending = all(REVEAL).filter(function (el) {
        return !el.classList.contains('in');
      });
      if (!pending.length) return;
      pending.forEach(function (el) { el.classList.add('in'); });
      if (window.console && console.info) {
        console.info('[motion] ' + pending.length + ' 个元素超时未进入视口，已强制显示');
      }
    }, REVEAL_TIMEOUT);

    // 路径 5：后台标签页暂停。
    // 页面切到后台时浏览器会节流定时器与观察器回调，用户切回来时
    // 可能看到一批元素「集体闪现」。主动在切回时把等待中的元素
    // 一次性显示，把「迟到的集体闪现」换成「一次干净的直达」。
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'visible') return;
      window.clearTimeout(timer);
      var pending = all(REVEAL).filter(function (el) {
        return !el.classList.contains('in');
      });
      // 只处理已经进入视口的，剩下的继续等观察器 ——
      // 否则用户一路滚到底再切回来，会看到整页瞬间全部亮起
      pending.forEach(function (el) {
        var rect = el.getBoundingClientRect();
        if (rect.top < (window.innerHeight || 0) && rect.bottom > 0) {
          el.classList.add('in');
        }
      });
    });
  }

  // ---------- 导航滚动加深 ----------
  // 滚过 8px 就给 .nav 加 .scrolled（纯 class 切换，守 CSP）。
  // 为什么用 rAF 节流而不是直接改：scroll 事件在某些触控板上
  // 一秒能触发上百次，每次都算一次 class 切换会白白占主线程。
  function initNav() {
    var nav = document.querySelector('.nav');
    if (!nav) return;
    var ticking = false;
    function update() {
      nav.classList.toggle('scrolled', window.scrollY > 8);
      ticking = false;
    }
    window.addEventListener('scroll', function () {
      if (!ticking && window.requestAnimationFrame) {
        ticking = true;
        window.requestAnimationFrame(update);
      } else if (!ticking) {
        update();
      }
    }, { passive: true });
  }

  // ---------- 跟手水波纹（⑩ 微动效新增） ----------
  // 在指针落点注入一个 .ripple__dot，由 CSS 负责「炸开 + 消散」动画。
  // 全程守 CSP：用 el.style.setProperty 写坐标，不写 style 属性（后者会触发 CSP）。
  // 门禁：motionEnabled() 已含 reduced-motion 与 data-motion=off 的双重否决，
  //       关动效时监听器根本不装，CSS 里 .ripple__dot 也另有 display:none 兜底。
  function initRipple() {
    if (!motionEnabled()) return;
    if (!document.addEventListener || !document.createElement) return;
    document.addEventListener('pointerdown', function (e) {
      var t = (e.target && e.target.closest)
        ? e.target.closest('.btn, .card, .post-card')
        : null;
      if (!t) return;
      var r = t.getBoundingClientRect();
      var d = Math.max(r.width, r.height) * 2;
      var span = document.createElement('span');
      span.className = 'ripple__dot';
      span.style.setProperty('width', d + 'px');
      span.style.setProperty('height', d + 'px');
      span.style.setProperty('left', (e.clientX - r.left - d / 2) + 'px');
      span.style.setProperty('top', (e.clientY - r.top - d / 2) + 'px');
      span.addEventListener('animationend', function () {
        if (span.parentNode) span.parentNode.removeChild(span);
      });
      t.appendChild(span);
    }, { passive: true });
  }

  // ---------- 启动 ----------
  // 整段包在 try/catch 里：这是第 2 层「降级路径 4」的落点。
  // 任何一处抛异常（老浏览器缺 API、扩展脚本污染了原型链…），
  // 都必须保证 .reveal 全部可见 —— 顶多动效没了，页面绝不能白屏。
  try {
    assignStaggerIndex();
    initReveal();
    initNav();
    initRipple();
  } catch (e) {
    showAll('动效脚本异常：' + (e && e.message ? e.message : e));
  }
})();
