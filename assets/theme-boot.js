// 首屏防闪：在样式表加载前同步决定主题与动效偏好。
//
// 为什么必须单独一个文件、且放在 <head>：
// prefs.js 在 </body> 前加载，那时 HTML 已经解析完，浏览器可能已经用默认
// 深色画过一帧 —— 浅色用户会看到明显的「先黑后白」闪烁。
// 本文件放在 <head>，在 <link rel="stylesheet"> 之前执行，
// 抢在第一帧渲染前把 data-theme / data-motion 写上去。
//
// 为什么动效偏好也合进这里，而不是单开第四个 <head> 脚本：
// <head> 里的每个 <script src> 都是串行阻塞的，多一个就多一次
// 网络往返才轮到样式表；而且两个脚本各自写一次 documentElement，
// 会多出一次样式重算，反而更容易闪。合并后只读一次 localStorage。
//
// 约束：不能用内联 <script>（CSP script-src 'self' 会拦），所以独立成文件。
(function () {
  'use strict';
  var KEY = 'xiaoyu-hue:prefs:v1';
  var theme = 'system';
  var motion = 'on';
  try {
    var raw = window.localStorage.getItem(KEY);
    if (raw) {
      var obj = JSON.parse(raw);
      if (obj && obj.schema === 1) {
        if (/^(system|dark|light)$/.test(obj.theme)) {
          theme = obj.theme;
        }
        // 只有显式的 'off' 才关动效：字段缺失（老数据）或取值意外，
        // 都按 'on' 处理，保证升级上来的老用户不会突然被动效消失困扰
        if (obj.motion === 'off') {
          motion = 'off';
        }
      }
    }
  } catch (e) {
    // 读不到（隐私模式 / 数据损坏）就用默认值，不影响后续
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
  // 注意：CSS 那边的总开关同时接受 html[data-motion="off"]，
  // 所以这里必须无条件写上 'on' 或 'off'，不能只在 off 时写 ——
  // 否则用户从 off 切回 on 时，属性还留在 off 上，动效再也回不来。
  root.setAttribute('data-motion', motion);
})();
