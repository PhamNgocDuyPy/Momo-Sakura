export interface HealthResult {
  ok: boolean;
  message: string;
}

/** GET {backend}/api/health. Returns a Vietnamese message; never throws. */
export async function checkHealth(backendUrl: string, timeoutMs = 5000): Promise<HealthResult> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${backendUrl}/api/health`, { signal: ctrl.signal });
    if (!res.ok) return { ok: false, message: `Backend trả về lỗi (mã ${res.status}).` };
    const body = (await res.json()) as { status?: unknown; llm_provider?: unknown; version?: unknown };
    if (body.status !== "ok") return { ok: false, message: "Backend phản hồi nhưng chưa sẵn sàng." };
    const provider = typeof body.llm_provider === "string" ? `, LLM: ${body.llm_provider}` : "";
    const version = typeof body.version === "string" ? `, phiên bản ${body.version}` : "";
    return { ok: true, message: `Kết nối thành công${provider}${version}.` };
  } catch {
    return {
      ok: false,
      message: `Không kết nối được tới ${backendUrl}. Hãy kiểm tra backend đang chạy.`,
    };
  } finally {
    clearTimeout(timer);
  }
}