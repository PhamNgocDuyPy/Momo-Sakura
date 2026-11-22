import { useEffect, useState } from "react";
import { DEFAULT_BACKEND_URL, DEFAULT_WEB_URL, getSettings, normalizeUrl, saveUrls } from "../shared/settings";
import { getAutoProtectMap, normalizeHost, onAutoProtectChange, setAutoProtect } from "../shared/autoProtect";
import { checkHealth } from "./health";

type Notice = { kind: "ok" | "error"; text: string } | null;

/** Asks Chrome for access to a non-default backend origin (needs a user gesture). */
async function ensureHostPermission(backendUrl: string): Promise<void> {
  const origin = `${new URL(backendUrl).origin}/*`;
  if (origin === "http://localhost:8000/*") return;
  try {
    await chrome.permissions.request({ origins: [origin] });
  } catch {
    // Not granted: the connection test below reports the failure.
  }
}

export default function Options() {
  const [backend, setBackend] = useState(DEFAULT_BACKEND_URL);
  const [web, setWeb] = useState(DEFAULT_WEB_URL);
  const [sessionId, setSessionId] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);

  const [hosts, setHosts] = useState<string[]>([]);
  const [newHost, setNewHost] = useState("");
  useEffect(() => {
    void getAutoProtectMap().then((m) => setHosts(Object.keys(m).sort()));
    return onAutoProtectChange((m) => setHosts(Object.keys(m).sort()));
  }, []);
  const addHost = async (): Promise<void> => {
    const h = normalizeHost(newHost);
    if (!h) {
      setNotice({ kind: "error", text: "Tên miền không hợp lệ. Ví dụ: chat.zalo.me" });
      return;
    }
    await setAutoProtect(h, true);
    setHosts((prev) => Array.from(new Set([...prev, h])).sort());
    setNewHost("");
  };
  const removeHost = async (h: string): Promise<void> => {
    await setAutoProtect(h, false);
    setHosts((prev) => prev.filter((x) => x !== h));
  };
  useEffect(() => {
    void getSettings().then((s) => {
      setBackend(s.backendUrl);
      setWeb(s.webUrl);
      setSessionId(s.sessionId);
    });
  }, []);

  const save = async (): Promise<void> => {
    const b = normalizeUrl(backend);
    if (b) await ensureHostPermission(b);
    try {
      await saveUrls(backend, web);
      setBackend(b ?? backend);
      setWeb(normalizeUrl(web) ?? web);
      setNotice({ kind: "ok", text: "Đã lưu cài đặt." });
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : "Không lưu được cài đặt." });
    }
  };

  const test = async (): Promise<void> => {
    const b = normalizeUrl(backend);
    if (!b) {
      setNotice({ kind: "error", text: "Địa chỉ backend không hợp lệ." });
      return;
    }
    setBusy(true);
    setNotice(null);
    await ensureHostPermission(b);
    const result = await checkHealth(b);
    setNotice({ kind: result.ok ? "ok" : "error", text: result.message });
    setBusy(false);
  };

  const field = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";
  return (
    <main className="mx-auto max-w-lg p-6 text-slate-900">
      <h1 className="text-xl font-bold text-pink-600">MoMo Guardian - Cài đặt</h1>
      <p className="mt-1 text-sm text-slate-600">Địa chỉ backend và ứng dụng web dùng cho tiện ích.</p>

      <label className="mt-5 block text-sm font-medium">
        Địa chỉ backend
        <input
          className={field}
          value={backend}
          onChange={(e) => setBackend(e.target.value)}
          placeholder={DEFAULT_BACKEND_URL}
          inputMode="url"
        />
      </label>
      <label className="mt-4 block text-sm font-medium">
        Địa chỉ ứng dụng web
        <input
          className={field}
          value={web}
          onChange={(e) => setWeb(e.target.value)}
          placeholder={DEFAULT_WEB_URL}
          inputMode="url"
        />
      </label>

      <div className="mt-5 flex gap-2">
        <button
          type="button"
          onClick={() => void save()}
          className="rounded-lg bg-pink-600 px-4 py-2 text-sm font-semibold text-white hover:bg-pink-700"
        >
          Lưu
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void test()}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          Kiểm tra kết nối
        </button>
      </div>

      {notice && (
        <p
          role="status"
          data-testid="options-notice"
          className={`mt-4 rounded-lg px-3 py-2 text-sm ${
            notice.kind === "ok" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
          }`}
        >
          {notice.text}
        </p>
      )}

      <section className="mt-8" data-testid="auto-protect-section">
        <h2 className="text-base font-semibold">Tự động bảo vệ</h2>
        <p className="mt-1 text-sm text-slate-600">
          Mặc định tắt. Khi bật cho một trang, tiện ích chấm điểm tin nhắn mới ngay trong trình duyệt (không gửi gì ra
          mạng) và gắn nhãn &quot;Guardian: nên kiểm tra&quot; cạnh tin đáng ngờ. Chỉ khi bạn bấm nhãn, tin đó mới được
          gửi đi kiểm tra. Nhãn không phải là kết luận.
        </p>
        <ul className="mt-3 space-y-2" data-testid="auto-protect-list">
          {hosts.length === 0 && <li className="text-sm text-slate-500">Chưa bật cho trang nào.</li>}
          {hosts.map((h) => (
            <li key={h} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
              <span>
                {h}: <strong>Bật</strong>
              </span>
              <button
                type="button"
                onClick={() => void removeHost(h)}
                className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
              >
                Tắt
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex gap-2">
          <input
            className={field}
            aria-label="Tên miền cần bật Tự động bảo vệ"
            value={newHost}
            onChange={(e) => setNewHost(e.target.value)}
            placeholder="chat.zalo.me"
          />
          <button
            type="button"
            onClick={() => void addHost()}
            className="mt-1 shrink-0 rounded-lg bg-pink-600 px-4 py-2 text-sm font-semibold text-white hover:bg-pink-700"
          >
            Bật
          </button>
        </div>
      </section>
      <p className="mt-6 break-all text-xs text-slate-400">Mã phiên: {sessionId || "..."}</p>
    </main>
  );
}