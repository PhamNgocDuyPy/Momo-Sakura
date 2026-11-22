import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_BACKEND_URL,
  DEFAULT_WEB_URL,
  STORAGE_KEYS,
  generateUuidV4,
  getSettings,
  getWebUrl,
  isUuidV4,
  normalizeUrl,
  saveUrls,
} from "../src/shared/settings";
import { installChromeStorage } from "./helpers";

describe("uuid v4", () => {
  it("generates valid v4 ids", () => {
    for (let i = 0; i < 20; i++) expect(isUuidV4(generateUuidV4())).toBe(true);
  });
  it("rejects other values", () => {
    expect(isUuidV4("123")).toBe(false);
    expect(isUuidV4("6ba7b810-9dad-11d1-80b4-00c04fd430c8")).toBe(false); // v1
    expect(isUuidV4(undefined)).toBe(false);
  });
});

describe("normalizeUrl", () => {
  it("trims trailing slashes and keeps http(s) only", () => {
    expect(normalizeUrl(" http://localhost:8000/ ")).toBe("http://localhost:8000");
    expect(normalizeUrl("https://api.example.com/guardian//")).toBe("https://api.example.com/guardian");
    expect(normalizeUrl("javascript:alert(1)")).toBeNull();
    expect(normalizeUrl("ftp://x")).toBeNull();
    expect(normalizeUrl("")).toBeNull();
    expect(normalizeUrl("không phải url")).toBeNull();
  });
});

describe("getSettings", () => {
  let store: Record<string, unknown>;
  beforeEach(() => {
    store = installChromeStorage();
  });

  it("returns defaults and persists a new uuid v4 session id", async () => {
    const s = await getSettings();
    expect(s.backendUrl).toBe(DEFAULT_BACKEND_URL);
    expect(s.webUrl).toBe(DEFAULT_WEB_URL);
    expect(isUuidV4(s.sessionId)).toBe(true);
    expect(store[STORAGE_KEYS.sessionId]).toBe(s.sessionId);
  });

  it("reuses the stored session id", async () => {
    const a = await getSettings();
    const b = await getSettings();
    expect(b.sessionId).toBe(a.sessionId);
  });

  it("replaces an invalid stored session id", async () => {
    store[STORAGE_KEYS.sessionId] = "abc";
    const s = await getSettings();
    expect(isUuidV4(s.sessionId)).toBe(true);
  });

  it("saves URLs normalized and falls back to defaults when stored values are invalid", async () => {
    await saveUrls("http://127.0.0.1:9000/", "http://localhost:3000/");
    expect(await getSettings()).toMatchObject({ backendUrl: "http://127.0.0.1:9000", webUrl: "http://localhost:3000" });
    store[STORAGE_KEYS.backendUrl] = "javascript:1";
    expect((await getSettings()).backendUrl).toBe(DEFAULT_BACKEND_URL);
    await expect(saveUrls("nope", "http://localhost:5173")).rejects.toThrow();
  });

  it("getWebUrl does not create a session id", async () => {
    expect(await getWebUrl()).toBe(DEFAULT_WEB_URL);
    expect(store[STORAGE_KEYS.sessionId]).toBeUndefined();
  });
});