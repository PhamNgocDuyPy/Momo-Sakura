import { useMemo, useState } from "react";
import { formatVnd, parseAmount } from "../../lib/amount";
import { api, ApiError } from "../../services/api";
import type {
  ReceiptItem,
  SplitAssignment,
  SplitComputeResponse,
  SplitParticipant,
} from "../../types/api";
import SplitShareCard from "./SplitShareCard";

export const MAX_PEOPLE = 20;
export const MAX_ITEMS = 30;
const PAYEE_ID = "p1";
const SPLIT_MEMO = "Chia hoa don";

interface Row {
  uid: number;
  name: string;
  quantity: string;
  price: string;
}

interface Props {
  /** Items read from the receipt by Flow B (`extensions.receipt`). */
  items: ReceiptItem[];
  /** Receipt total read by Flow B; null when the receipt had no readable total. */
  totalVnd: number | null;
}

const INPUT = "w-full rounded-lg border border-slate-300 px-2 py-2 text-sm";

function toRows(items: ReceiptItem[]): Row[] {
  return items.slice(0, MAX_ITEMS).map((it, i) => ({
    uid: i + 1,
    name: it.name,
    quantity: String(it.quantity),
    price: String(it.unit_price_vnd),
  }));
}

function parseRow(r: Row): ReceiptItem | null {
  const name = r.name.trim().slice(0, 60);
  const quantity = Number(r.quantity);
  const price = parseAmount(r.price);
  if (name === "" || !Number.isInteger(quantity) || quantity < 1 || quantity > 99) return null;
  if (price === null || price > 100_000_000) return null;
  return { name, quantity, unit_price_vnd: price };
}

/** F3: editable receipt items, people, equal or per-item split, per-person VietQR. */
export default function BillSplit({ items, totalVnd }: Props) {
  const [rows, setRows] = useState<Row[]>(() => toRows(items));
  const [nextUid, setNextUid] = useState(() => Math.min(items.length, MAX_ITEMS) + 1);
  const [people, setPeople] = useState<SplitParticipant[]>([
    { id: PAYEE_ID, display_name: "Bạn" },
    { id: "p2", display_name: "Người 2" },
  ]);
  const [nextPerson, setNextPerson] = useState(3);
  const [newName, setNewName] = useState("");
  const [mode, setMode] = useState<"EQUAL" | "BY_ITEM">("EQUAL");
  const [assign, setAssign] = useState<Record<number, string[]>>({});
  const initialTotal = totalVnd ?? items.reduce((s, it) => s + it.quantity * it.unit_price_vnd, 0);
  const [totalText, setTotalText] = useState(String(initialTotal));
  const [result, setResult] = useState<SplitComputeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const parsed = useMemo(() => rows.map(parseRow), [rows]);
  const validItems = parsed.every((p) => p !== null) && rows.length > 0;
  const total = parseAmount(totalText);
  const itemsSum = parsed.reduce((s, p) => s + (p ? p.quantity * p.unit_price_vnd : 0), 0);

  const invalidate = (): void => {
    setResult(null);
    setError(null);
  };
  const editRow = (uid: number, patch: Partial<Row>): void => {
    setRows((rs) => rs.map((r) => (r.uid === uid ? { ...r, ...patch } : r)));
    invalidate();
  };
  const addRow = (): void => {
    if (rows.length >= MAX_ITEMS) return;
    setRows((rs) => [...rs, { uid: nextUid, name: "", quantity: "1", price: "0" }]);
    setNextUid((n) => n + 1);
    invalidate();
  };
  const removeRow = (uid: number): void => {
    setRows((rs) => rs.filter((r) => r.uid !== uid));
    invalidate();
  };
  const addPerson = (): void => {
    const name = newName.trim().slice(0, 40);
    if (name === "" || people.length >= MAX_PEOPLE) return;
    setPeople((ps) => [...ps, { id: `p${nextPerson}`, display_name: name }]);
    setNextPerson((n) => n + 1);
    setNewName("");
    invalidate();
  };
  const removePerson = (id: string): void => {
    if (id === PAYEE_ID) return;
    setPeople((ps) => ps.filter((p) => p.id !== id));
    setAssign((a) => Object.fromEntries(Object.entries(a).map(([k, v]) => [k, v.filter((x) => x !== id)])));
    invalidate();
  };
  const toggle = (uid: number, pid: string): void => {
    setAssign((a) => {
      const cur = a[uid] ?? [];
      return { ...a, [uid]: cur.includes(pid) ? cur.filter((x) => x !== pid) : [...cur, pid] };
    });
    invalidate();
  };

  const unassigned = mode === "BY_ITEM" && rows.some((r) => (assign[r.uid] ?? []).length === 0);
  const canCompute = validItems && total !== null && people.length >= 1 && !unassigned && !busy;

  const compute = async (): Promise<void> => {
    if (!canCompute || total === null) return;
    const body = parsed.filter((p): p is ReceiptItem => p !== null);
    const assignments: SplitAssignment[] | null =
      mode === "BY_ITEM"
        ? rows.map((r, i) => ({ item_index: i, participant_ids: assign[r.uid] ?? [] }))
        : null;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.splitCompute({
          items: body,
          receipt_total_vnd: total,
          participants: people,
          mode,
          assignments,
          payee: "SELF",
          memo: SPLIT_MEMO,
        }),
      );
    } catch (e) {
      setResult(null);
      setError(
        e instanceof ApiError && e.messageVi
          ? e.messageVi
          : "Chưa chia được hóa đơn lúc này. Bạn thử lại sau nhé.",
      );
    } finally {
      setBusy(false);
    }
  };

  const nameOf = (id: string): string => people.find((p) => p.id === id)?.display_name ?? id;

  return (
    <section data-testid="bill-split" aria-label="Chia hóa đơn" className="space-y-4 rounded-xl border border-pink-200 bg-white p-3">
      <h3 className="text-base font-semibold text-slate-900">Chia hóa đơn</h3>

      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">Các món (bạn có thể sửa)</p>
        {rows.map((r, i) => (
          <div key={r.uid} data-testid={`item-row-${i}`} className="space-y-1 rounded-lg bg-slate-50 p-2">
            <div className="flex gap-2">
              <input
                aria-label={`Tên món ${i + 1}`}
                className={INPUT}
                value={r.name}
                onChange={(e) => editRow(r.uid, { name: e.target.value })}
              />
              <button
                type="button"
                aria-label={`Xóa món ${i + 1}`}
                className="rounded-lg px-2 text-slate-500 hover:bg-slate-200"
                onClick={() => removeRow(r.uid)}
              >
                ✕
              </button>
            </div>
            <div className="flex gap-2">
              <input
                aria-label={`Số lượng món ${i + 1}`}
                inputMode="numeric"
                className={`${INPUT} w-20`}
                value={r.quantity}
                onChange={(e) => editRow(r.uid, { quantity: e.target.value })}
              />
              <input
                aria-label={`Đơn giá món ${i + 1}`}
                inputMode="text"
                className={INPUT}
                value={r.price}
                onChange={(e) => editRow(r.uid, { price: e.target.value })}
              />
            </div>
            {parsed[i] === null && <p className="text-xs text-red-700">Kiểm tra lại tên, số lượng (1–99) và đơn giá.</p>}
            {mode === "BY_ITEM" && (
              <div className="flex flex-wrap gap-1 pt-1" role="group" aria-label={`Ai ăn món ${i + 1}`}>
                {people.map((p) => {
                  const on = (assign[r.uid] ?? []).includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      aria-pressed={on}
                      data-testid={`assign-${i}-${p.id}`}
                      onClick={() => toggle(r.uid, p.id)}
                      className={`rounded-full border px-3 py-1 text-xs ${on ? "border-pink-600 bg-pink-600 text-white" : "border-slate-300 bg-white text-slate-700"}`}
                    >
                      {p.display_name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
        <button
          type="button"
          disabled={rows.length >= MAX_ITEMS}
          onClick={addRow}
          className="w-full rounded-lg border border-dashed border-slate-300 py-2 text-sm text-slate-700 disabled:opacity-50"
        >
          + Thêm món
        </button>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">Tổng trên hóa đơn</span>
          <input
            aria-label="Tổng trên hóa đơn"
            inputMode="text"
            className={INPUT}
            value={totalText}
            onChange={(e) => {
              setTotalText(e.target.value);
              invalidate();
            }}
          />
        </label>
        <p className="text-xs text-slate-500">Tổng các món: {formatVnd(itemsSum)}</p>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">Người cùng chia ({people.length}/{MAX_PEOPLE})</p>
        <ul className="flex flex-wrap gap-2">
          {people.map((p) => (
            <li key={p.id} className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-sm">
              {p.display_name}
              {p.id !== PAYEE_ID && (
                <button type="button" aria-label={`Bỏ ${p.display_name}`} className="text-slate-500" onClick={() => removePerson(p.id)}>
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input
            aria-label="Tên người mới"
            className={INPUT}
            placeholder="Tên người cùng chia"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addPerson();
              }
            }}
          />
          <button
            type="button"
            disabled={newName.trim() === "" || people.length >= MAX_PEOPLE}
            onClick={addPerson}
            className="shrink-0 rounded-lg border border-pink-300 px-3 text-sm font-medium text-pink-700 disabled:opacity-50"
          >
            Thêm
          </button>
        </div>
      </div>

      <div role="radiogroup" aria-label="Cách chia" className="grid grid-cols-2 gap-2">
        {(
          [
            ["EQUAL", "Chia đều"],
            ["BY_ITEM", "Gán theo món"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={mode === value}
            onClick={() => {
              setMode(value);
              invalidate();
            }}
            className={`rounded-lg border px-3 py-2 text-sm font-medium ${mode === value ? "border-pink-600 bg-pink-50 text-pink-700" : "border-slate-300 text-slate-700"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {unassigned && <p className="text-xs text-amber-800">Mỗi món cần ít nhất một người để chia.</p>}

      <button
        type="button"
        data-testid="split-compute"
        disabled={!canCompute}
        onClick={() => void compute()}
        className="w-full rounded-xl bg-pink-600 px-4 py-3 text-base font-semibold text-white disabled:bg-slate-300"
      >
        {busy ? "Đang tính…" : "Tính phần mỗi người"}
      </button>

      {error && (
        <p role="alert" data-testid="split-error" className="rounded-lg bg-red-50 p-2 text-sm text-red-800">
          {error}
        </p>
      )}

      {result?.status === "TOTAL_MISMATCH" && (
        <div role="alert" data-testid="split-mismatch" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">Tổng các món chưa khớp với tổng hóa đơn</p>
          <p>
            Các món cộng lại {formatVnd(result.items_sum_vnd)}, hóa đơn ghi {formatVnd(result.total_vnd)}, chênh{" "}
            <strong data-testid="split-mismatch-amount">{formatVnd(Math.abs(result.mismatch_vnd))}</strong>
            . Bạn hãy sửa lại món hoặc tổng hóa đơn rồi tính lại.
          </p>
        </div>
      )}

      {result?.status === "OK" && (
        <div className="space-y-2" data-testid="split-result">
          <p className="text-sm font-medium text-slate-700">Tổng {formatVnd(result.total_vnd)}</p>
          <ul className="space-y-2">
            {result.shares.map((s) => (
              <SplitShareCard key={s.participant_id} name={nameOf(s.participant_id)} share={s} />
            ))}
          </ul>
          {result.shares.some((s) => s.qr_status === "QR_ERROR") && (
            <p data-testid="split-qr-error" className="text-xs text-amber-800">
              Một số phần chưa tạo được mã QR. Bạn hãy báo số tiền trực tiếp cho người đó.
            </p>
          )}
          <p className="text-xs text-slate-500">Mã QR chuyển về tài khoản mô phỏng của bạn.</p>
        </div>
      )}
    </section>
  );
}
