interface Props {
  message: string;
  onRetry?: () => void;
  onClose: () => void;
}

/** Shown for any failure. It never shows a verdict, so it can never read as ALLOW. */
export default function ErrorPanel({ message, onRetry, onClose }: Props) {
  return (
    <section
      role="alert"
      data-testid="error-panel"
      className="rounded-xl border-2 border-slate-300 bg-slate-50 p-4"
    >
      <h2 className="text-base font-bold text-slate-900">Chưa kiểm tra được</h2>
      <p data-testid="error-message" className="mt-2 text-sm text-slate-700">
        {message}
      </p>
      <p className="mt-2 text-xs text-slate-500">
        Chưa có kết luận nào về tin nhắn này. Đừng chuyển tiền nếu bạn còn nghi ngờ.
      </p>
      <div className="mt-3 flex gap-2">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            data-testid="error-retry"
            className="flex-1 rounded-xl bg-pink-600 px-4 py-2 text-sm font-semibold text-white hover:bg-pink-700"
          >
            Thử lại
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          data-testid="error-close"
          className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Đóng
        </button>
      </div>
    </section>
  );
}