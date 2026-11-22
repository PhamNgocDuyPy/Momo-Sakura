import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const pub = (f: string): string => readFileSync(resolve(__dirname, "..", "public", f), "utf-8");

interface Manifest {
  icons: { src: string; sizes: string }[];
  share_target: {
    action: string;
    method: string;
    enctype: string;
    params: { title: string; text: string; url: string; files: { name: string; accept: string[] }[] };
  };
}

describe("PWA manifest", () => {
  const manifest = JSON.parse(pub("manifest.webmanifest")) as Manifest;

  it("share_target accepts text, url and images over multipart POST", () => {
    const st = manifest.share_target;
    expect(st.method).toBe("POST");
    expect(st.enctype).toBe("multipart/form-data");
    expect(st.action).toBe("/share-target");
    expect(st.params.text).toBe("text");
    expect(st.params.url).toBe("url");
    expect(st.params.files[0].accept).toContain("image/*");
  });

  it("has 192 and 512 icons that exist", () => {
    const sizes = manifest.icons.map((i) => i.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");
    for (const icon of manifest.icons) expect(() => readFileSync(resolve(__dirname, "..", "public", icon.src.slice(1)))).not.toThrow();
  });

  it("service worker intercepts the share POST and redirects with 303", () => {
    const sw = pub("sw.js");
    expect(sw).toContain("share-inbox");
    expect(sw).toContain("/share-target");
    expect(sw).toMatch(/redirect\("\/\?share=1", 303\)/);
  });
});
