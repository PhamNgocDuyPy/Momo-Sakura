import { useId, useState } from "react";
import type { CaptureSource } from "./conversation";

export interface ReadInfo {
  source: CaptureSource;
  messages: string[];
}

export function readSummaryText(info: ReadInfo): string {
  const n = info.messages.length;
  if (info.source === "panel") return `Guardian đã đọc ${n} tin nhắn trong khung chat`;
  if (info.source === "selection") return "Guardian đã đọc đoạn bạn đã chọn";
  return `Guardian đã đọc ${n} đoạn văn bản đang hiển thị trên trang`;
}

/**
 * Tells the user what was read and lets them review it. The list is rendered from the strings
 * captured locally; opening it makes no request.
 */
export default function ReadSummary({ info }: { info: ReadInfo }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  return (
    <div data-testid="read-summary" className="mb-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
      <div className="flex items-center justify-between gap-2">
        <span data-testid="read-summary-text" className="font-medium">
          {readSummaryText(info)}
        </span>
        <button
          type="button"
          data-testid="read-toggle"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded-md px-2 py-1 font-semibold text-pink-600 hover:bg-pink-50"
        >
          {open ? "Ẩn nội dung đã đọc" : "Xem nội dung đã đọc"}
        </button>
      </div>
      {open && (
        <ol
          id={listId}
          data-testid="read-list"
          className="mt-2 max-h-40 space-y-1 overflow-y-auto border-t border-slate-200 pt-2"
        >
          {info.messages.map((m, i) => (
            <li key={i} className="whitespace-pre-wrap break-words rounded bg-white px-2 py-1 text-slate-800">
              {m}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
