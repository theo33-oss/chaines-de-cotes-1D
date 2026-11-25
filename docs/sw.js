"use strict";
// Service worker : le site reste utilisable sans Internet après une première visite.
// Fichiers du site : réseau d'abord (toujours la dernière version), copie gardée pour le hors ligne.
// Bibliothèques des CDN (Pyodide, Plotly, html-to-image, roue plotly) : copie gardée d'abord, d'une version du site à l'autre.
// Le numéro change avec construire_web.py (empreinte du zip, de app.js et de style.css) : les anciennes copies sont effacées.

const VERSION = "chainecotes-1.1.0-80dc1951";
const CDN_CACHE = "chainecotes-cdn"; // adresses à version figée : gardées d'une version du site à l'autre
const CDN = ["https://cdn.jsdelivr.net/", "https://cdnjs.cloudflare.com/", "https://files.pythonhosted.org/", "https://pypi.org/"];

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    // l'adresse github.io est partagée avec d'autres projets (MecaStruct…) : seules les copies de ce site sont effacées
    for (const nom of await caches.keys()) if (nom.startsWith("chainecotes-") && nom !== VERSION && nom !== CDN_CACHE) await caches.delete(nom);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = req.url;
  if (CDN.some((c) => url.startsWith(c))) {
    e.respondWith((async () => {
      const cache = await caches.open(CDN_CACHE);
      const garde = await cache.match(req);
      if (garde) return garde;
      const rep = await fetch(req);
      if (rep.ok) cache.put(req, rep.clone());
      return rep;
    })());
  } else if (url.startsWith(self.registration.scope)) {
    e.respondWith((async () => {
      const cache = await caches.open(VERSION);
      try {
        const rep = await fetch(req);
        // ?verif= et ?maj= sont à usage unique (horodatage) : les garder ferait grossir le cache à chaque visite
        if (rep.ok && !/[?&](verif|maj)=/.test(url)) cache.put(req, rep.clone());
        return rep;
      } catch (err) {
        // hors ligne : la copie gardée, sans tenir compte de ?maj= ou ?verif= ; le zip garde son ?v= (son empreinte)
        const garde = await cache.match(req, { ignoreSearch: !url.includes("chainecotes.zip") });
        if (garde) return garde;
        throw err;
      }
    })());
  }
});
