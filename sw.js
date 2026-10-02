// Service Worker：离线可用 + 秒开。
//
// 三条铁律(改动前必读):
//
// 1. HTML 绝不走「缓存优先」。
//    一旦 HTML 被缓存优先,你更新了文章用户也永远看到旧版,
//    而且很难自查(清了浏览器缓存才发现)。导航请求必须网络优先。
//
// 2. 不要无条件调用 skipWaiting()。
//    无条件调用会在用户正读文章时把页面换成新版本,输入的内容可能丢失。
//    必须等用户在界面上点「更新」,由 message 事件触发。
//
// 3. 非 GET 请求和跨域请求必须在最前面直接放行。
//    拦截它们没有任何好处,只会制造难以定位的故障。
//
// 另外:本文件必须在站点根目录。SW 的作用域受脚本路径限制,
// 放进 assets/ 就只能拦截 /assets/ 下的请求,拦不到页面导航。

const CACHE_PREFIX = 'xiaoyu-hue';
// 发布新内容后改这个版本号,activate 时会清掉旧缓存,用户即可看到更新。
// v6:视觉/微动效体系大升级 —— View Transitions 跨页过渡、滚动驱动入场
// (Scroll-driven Animations)、容器查询 + :has 精准响应式、color-mix 派生色、
// text-wrap:balance、allow-discrete 入场过渡。全部纯原生 CSS、零依赖、不改 CSP,
// 且都接入现有的 prefers-reduced-motion / data-motion=off 降级网络。
// v5:每个页面都新增了 JSON-LD 结构化数据与 RSS 自动发现链接,
// 另外新增 sitemap.xml / robots.txt / feed.xml / 404.html 四个文件。
// 不改版本号的话,已安装 PWA 的用户会继续从旧缓存里拿到没有结构化数据的页面。
// v4:修掉「导航请求把 404 也缓存进去」的问题。仅改代码不够 ——
// 已经被写进缓存的错误响应,只有靠换缓存名才能在 activate 时被清掉。
// v8:双主题个性化升级（极光背景/胶片噪点/4光球系统/流光增强）
//    纯原生 CSS 零依赖；换缓存名让已装 PWA 清缓存拿新样式。
const CACHE_VERSION = 'v8';
const CACHE_NAME = `${CACHE_PREFIX}-${CACHE_VERSION}`;

const OFFLINE_URL = '/offline.html';

// 预缓存清单:安装时一次性抓取,让站点在这些页面内离线可用。
//
// 注意清单里没有 og-cover.png —— 它有 500KB,是给社交平台爬虫看的,
// 用户浏览时从不加载它,放进预缓存等于让每个访客白下载半兆。
//
// '/' 和 '/index.html' 都列出:它们在 URL 上是两个不同的键,
// GitHub Pages 会把 '/' 重定向到 '/index.html',两个都缓存最稳。
const PRECACHE = [
  '/',
  '/index.html',
  '/blog/index.html',
  '/blog/post-1.html',
  '/blog/post-2.html',
  '/blog/post-3.html',
  '/blog/post-4.html',
  '/blog/post-5.html',
  '/blog/post-6.html',
  '/blog/post-7.html',
  '/blog/post-8.html',
  '/offline.html',
  '/manifest.webmanifest',
  '/assets/style.css',
  '/assets/theme-boot.js',
  '/assets/prefs.js',
  '/assets/pwa.js',
  '/assets/main.js',
  '/assets/offline.js',
  '/assets/favicon.svg',
  '/assets/icons/icon-192.png',
  '/assets/icons/icon-512.png',
  '/assets/icons/icon-maskable-512.png',
];

// ---------- 策略判定(纯函数,便于在 Node 里单测分支) ----------

/** 请求类型。三类走不同策略,见下面注释。 */
const KIND = { NAVIGATION: 'navigation', ASSET: 'asset', OTHER: 'other' };

/** 这些后缀的响应内容很少变,适合「缓存优先」。 */
const ASSET_RE = /\.(?:css|js|mjs|svg|png|jpg|jpeg|webp|avif|ico|woff2?|ttf|json|webmanifest)$/i;

/**
 * 是否应当完全放行、不介入。
 *
 * 非 GET 和跨域请求一律放行 —— 交给浏览器默认行为。
 */
function shouldBypass(request) {
  if (request.method !== 'GET') return true;
  try {
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return true;
    // 只处理 http/https;data:、blob: 等交给浏览器
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return true;
  } catch (e) {
    return true;
  }
  return false;
}

/** 判定请求属于哪一类,决定用哪种缓存策略。 */
function kindOf(request) {
  if (request.mode === 'navigate') return KIND.NAVIGATION;
  let pathname;
  try {
    pathname = new URL(request.url).pathname;
  } catch (e) {
    return KIND.OTHER;
  }
  return ASSET_RE.test(pathname) ? KIND.ASSET : KIND.OTHER;
}

// 导出给 Node 单测用(浏览器里 self.__sw 不影响任何行为)
self.__sw = {
  shouldBypass, kindOf, shouldCache, KIND, PRECACHE, CACHE_NAME, ASSET_RE,
};

// ---------- 生命周期 ----------

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      // allSettled 而不是 all:任何单个资源失败(网络抖动、某张图暂时 404)
      // 都不该让整个安装失败 —— 那会导致站点完全离线不可用,因小失大。
      const results = await Promise.allSettled(
        PRECACHE.map((url) => cache.add(new Request(url, { cache: 'reload' }))),
      );
      const failed = results
        .map((r, i) => (r.status === 'rejected' ? PRECACHE[i] : null))
        .filter(Boolean);
      if (failed.length) {
        console.warn('[sw] 以下资源预缓存失败(不影响安装):', failed);
      }
      // 这里刻意不调用 skipWaiting(),等用户确认更新
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => n.startsWith(CACHE_PREFIX) && n !== CACHE_NAME)
          .map((n) => caches.delete(n)),
      );
      // 让新 SW 立即接管已打开的页面
      await self.clients.claim();
    })(),
  );
});

// ---------- 请求处理 ----------

/**
 * 只缓存成功响应。
 *
 * 把 404 之类的错误响应存进去，用户之后离线打开就是一张错误页，
 * 而且它会一直留到下次 CACHE_VERSION 变更 —— 缓存一旦被错误响应
 * 污染，用户自己没办法清，只能等站点发版。
 *
 * 三个分支（导航 / 静态资源 / 其他）必须都走这里。以前是三处各写
 * 一遍 `fresh.ok`，导航那个漏了，就是这么出的问题。
 */
function shouldCache(response) {
  return !!(response && response.ok);
}

/** 导航:网络优先 → 缓存 → 离线页。 */
async function handleNavigation(request) {
  try {
    const fresh = await fetch(request);
    if (shouldCache(fresh)) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, fresh.clone());
    }
    return fresh;
  } catch (e) {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    if (offline) return offline;
    // 连离线页都没缓存上(极端情况),至少给个可读的响应
    return new Response('离线，且本地没有可用的缓存。', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
}

/** 静态资源:缓存优先 → 联网并存入。 */
async function handleAsset(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const fresh = await fetch(request);
  if (shouldCache(fresh)) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, fresh.clone());
  }
  return fresh;
}

/** 其他:先用缓存,同时后台静默更新。 */
async function handleOther(request) {
  const cached = await caches.match(request);
  const network = fetch(request)
    .then((fresh) => {
      if (shouldCache(fresh)) {
        caches.open(CACHE_NAME).then((c) => c.put(request, fresh.clone()));
      }
      return fresh;
    })
    .catch(() => null);
  return cached || (await network) || Response.error();
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (shouldBypass(request)) return;

  const kind = kindOf(request);
  if (kind === KIND.NAVIGATION) {
    event.respondWith(handleNavigation(request));
  } else if (kind === KIND.ASSET) {
    event.respondWith(handleAsset(request));
  } else {
    event.respondWith(handleOther(request));
  }
});

// ---------- 与页面的通信 ----------

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    // 由用户在「有新版本」提示条上点击后触发
    self.skipWaiting();
  }
});
