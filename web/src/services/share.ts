/** Reads the Web Share Target inbox that `public/sw.js` fills in Cache Storage. */

export const SHARE_CACHE = "share-inbox";
export const SHARE_META_URL = "/share-inbox/meta";
export const SHARE_IMAGE_URL = "/share-inbox/image";

export interface SharedItem {
  title: string;
  text: string;
  url: string;
  image: Blob | null;
}

interface ShareMeta {
  title?: unknown;
  text?: unknown;
  url?: unknown;
}

const str = (v: unknown): string => (typeof v === "string" ? v : "");

/** True when the page was opened by the share target redirect (`/?share=1`). */
export function isShareLaunch(search: string): boolean {
  return new URLSearchParams(search).get("share") === "1";
}

/** Combine shared title/text/url into one untrusted text block for Flow B. */
export function composeSharedText(item: Pick<SharedItem, "title" | "text" | "url">): string {
  const parts = [item.title, item.text, item.url].map((s) => s.trim()).filter((s) => s !== "");
  return parts.filter((p, i) => parts.indexOf(p) === i).join("\n");
}

/** Read and clear the inbox. Returns null when nothing was shared or Cache Storage is unavailable. */
export async function readShareInbox(): Promise<SharedItem | null> {
  if (typeof caches === "undefined") return null;
  try {
    const cache = await caches.open(SHARE_CACHE);
    const metaRes = await cache.match(SHARE_META_URL);
    const imageRes = await cache.match(SHARE_IMAGE_URL);
    if (!metaRes && !imageRes) return null;
    let meta: ShareMeta = {};
    if (metaRes) {
      try {
        meta = (await metaRes.json()) as ShareMeta;
      } catch {
        meta = {};
      }
    }
    const image = imageRes ? await imageRes.blob() : null;
    await cache.delete(SHARE_META_URL);
    await cache.delete(SHARE_IMAGE_URL);
    return { title: str(meta.title), text: str(meta.text), url: str(meta.url), image };
  } catch {
    return null;
  }
}
