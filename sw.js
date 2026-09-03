// 车管家 PWA 离线缓存：让手机独立使用时可离线打开、可"添加到主屏幕"当 APP 用
const CACHE = 'carcare-v7';
const ASSETS = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
function isNav(req){
  if(req.mode==='navigate')return true;
  try{const u=new URL(req.url);const p=u.pathname;return p==='/'||p.endsWith('/')||p.endsWith('index.html');}catch(e){return false;}
}
self.addEventListener('fetch', e => {
  // 数据请求始终走网络，保证 NAS 数据实时
  if (e.request.url.includes('/api/')) return;
  const req=e.request;
  if(isNav(req)){
    // 应用外壳「网络优先」：部署新 index.html 后，手机刷新即生效，无需手动升级缓存版本
    e.respondWith(
      fetch(req).then(resp=>{const copy=resp.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return resp;})
        .catch(()=>caches.match(req).then(r=>r||caches.match('./index.html')))
    );
    return;
  }
  // 其余静态资源（图标/清单）缓存优先，保证离线可用
  e.respondWith(
    caches.match(req).then(r => r || fetch(req).then(resp => {
      const copy = resp.clone();
      caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match('./index.html')))
  );
});
