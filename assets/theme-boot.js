// 首屏防闪：在样式表加载前同步决定主题。
//
// 为什么必须单独一个文件、且放在 <head>：
// prefs.js 在 </body> 前加载，那时 HTML 已经解析完，浏览器可能已经用默认
// 深色画过一帧 —— 浅色用户会看到明显的「先黑后白」闪烁。
// 本文件放在 <head>，在 <link rel="stylesheet"> 之前执行，
// 抢在第一帧渲染前把 data-theme 写上去。
//
// 约束：不能用内联 <script>（CSP script-src 'self' 会拦），所以独立成文件。
(function () {
  'use strict';
  var KEY = 'xiaoyu-hue:prefs:v1';
  var theme = 'system';
  try {
    var raw = window.localStorage.getItem(KEY);
    if (raw) {
      var obj = JSON.parse(raw);
      if (obj && obj.schema === 1 && /^(system|dark|light)$/.test(obj.theme)) {
        theme = obj.theme;
      }
    }
  } catch (e) {
    // 读不到就用默认值，不影响后续
  }
  var eff = theme;
  if (theme === 'system') {
    try {
      eff = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    } catch (e) {
      eff = 'dark';
    }
  }
  var root = document.documentElement;
  root.setAttribute('data-theme', eff);
  root.setAttribute('data-theme-pref', theme);
})();
