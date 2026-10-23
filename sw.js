const CACHE='verbos-d21b49e70cb9';
const URLS=[".","apple-touch-icon.png","assets/index--MsolQ4m.css","assets/index-Dq8sLmRy.js","data/LICENSE-CODE.txt","data/LICENSE-FSRS.txt","data/LICENSE-JEHLE.txt","data/THIRD-PARTY-NOTICES.txt","data/catalog.json","icon-192.png","icon-512.png","icon.svg","index.html","manifest.webmanifest"];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(URLS)));});
// An update waits until existing practice tabs close, so an active session stays consistent.
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('verbos-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET'||new URL(event.request.url).origin!==self.location.origin)return;
 event.respondWith(caches.open(CACHE).then(async cache=>{
  // Only immutable public app assets are precached. Ignore development-server Origin variance.
  const hit=await cache.match(event.request,{ignoreSearch:true,ignoreVary:true});
  if(hit)return hit;
  try{return await fetch(event.request);}catch(err){if(event.request.mode==='navigate')return cache.match(new URL('./index.html',self.registration.scope));throw err;}
 }));
});
