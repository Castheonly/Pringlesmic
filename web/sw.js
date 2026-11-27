// Service worker mínimo: permite instalar el panel como app. Siempre pide la versión más nueva.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
