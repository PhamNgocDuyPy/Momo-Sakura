/* MoMo Guardian service worker: receives Web Share Target POSTs and stores them for the app. */
const SHARE_CACHE = "share-inbox";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

async function handleShare(request) {
  try {
    const form = await request.formData();
    const cache = await caches.open(SHARE_CACHE);
    const field = (name) => {
      const v = form.get(name);
      return typeof v === "string" ? v : "";
    };
    const meta = { title: field("title"), text: field("text"), url: field("url"), ts: Date.now() };
    await cache.put(
      "/share-inbox/meta",
      new Response(JSON.stringify(meta), { headers: { "Content-Type": "application/json" } }),
    );
    const image = form.get("image");
    if (image && typeof image !== "string" && image.size > 0) {
      await cache.put(
        "/share-inbox/image",
        new Response(image, { headers: { "Content-Type": image.type || "application/octet-stream" } }),
      );
    } else {
      await cache.delete("/share-inbox/image");
    }
  } catch (err) {
    // Fall through to the redirect: the app opens with an empty inbox rather than an error page.
  }
  return Response.redirect("/?share=1", 303);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method === "POST" && url.pathname === "/share-target") {
    event.respondWith(handleShare(request));
  }
});
