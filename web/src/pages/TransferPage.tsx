import { useState } from "react";
import { useLocation } from "react-router-dom";
import CalmShield from "../components/guardian/CalmShield";
import ContextElicitation from "../components/guardian/ContextElicitation";
import CooldownGate from "../components/guardian/CooldownGate";
import DecisionTrace from "../components/guardian/DecisionTrace";
import ResultCard from "../components/guardian/ResultCard";
import BankHandoff from "../components/transfer/BankHandoff";
import FastUnblockDialog from "../components/transfer/FastUnblockDialog";
import TransferForm, {
  parsedAmount,
  type TransferFormValues,
} from "../components/transfer/TransferForm";
import TwoStepConfirm from "../components/transfer/TwoStepConfirm";
import { formatVnd } from "../lib/amount";
import { ApiError, api } from "../services/api";
import { useGuardianOptional } from "../state/guardianStore";
import type { CheckResponse, ContextChoice, Prefill, SourceIntegrity } from "../types/api";

interface TransferLocationState {
  prefill?: Prefill;
  origin_verdict_id?: string;
  confirmation_token?: string;
}

type Phase = "form" | "confirm" | "result" | "sent";

function initialValues(prefill: Prefill | undefined): TransferFormValues {
  return {
    bankBin: prefill?.bank_bin ?? "",
    accountNumber: prefill?.account_number ?? "",
    amountText: prefill?.amount_vnd != null ? String(prefill.amount_vnd) : "",
    memo: prefill?.memo ?? "",
  };
}

interface Integrity {
  sourceIntegrity: SourceIntegrity;
  confirmationToken: string | null;
}

/**
 * Flow A source integrity for a transfer opened from Guardian (F1).
 * - OCR account confirmed in NameConfirm and left unchanged: OCR_CONFIRMED_BY_USER + token.
 * - VietQR-verified prefill left unchanged: keep VALID_VIETQR_CRC.
 * - Anything else (typed, edited, or OCR the user re-checked in TwoStepConfirm): USER_TYPED.
 */
export function resolveIntegrity(
  routeState: TransferLocationState | null,
  values: TransferFormValues,
): Integrity {
  const prefill = routeState?.prefill;
  const unchanged =
    prefill != null &&
    prefill.bank_bin === values.bankBin &&
    prefill.account_number === values.accountNumber;
  if (prefill && unchanged) {
    if (routeState?.confirmation_token) {
      return { sourceIntegrity: "OCR_CONFIRMED_BY_USER", confirmationToken: routeState.confirmation_token };
    }
    if (prefill.source_integrity_for_flow_a === "VALID_VIETQR_CRC") {
      return { sourceIntegrity: "VALID_VIETQR_CRC", confirmationToken: null };
    }
  }
  return { sourceIntegrity: "USER_TYPED", confirmationToken: null };
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.messageVi ?? "Guardian không thực hiện được yêu cầu này.";
  return "Không thể kết nối tới Guardian. Vui lòng thử lại.";
}

export default function TransferPage() {
  const location = useLocation();
  const routeState = (location.state ?? null) as TransferLocationState | null;
  const guardian = useGuardianOptional();
  const dispatch = guardian?.dispatch;

  const [values, setValues] = useState<TransferFormValues>(() => initialValues(routeState?.prefill));
  const [phase, setPhase] = useState<Phase>("form");
  const [response, setResponse] = useState<CheckResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showUnblock, setShowUnblock] = useState(false);
  const [calmDismissed, setCalmDismissed] = useState(false);

  const amount = parsedAmount(values);
  const { sourceIntegrity, confirmationToken } = resolveIntegrity(routeState, values);

  const receive = (res: CheckResponse): void => {
    setResponse(res);
    setPhase("result");
    dispatch?.({ type: "VERDICT_RECEIVED", response: res });
  };

  const runCheck = async (): Promise<void> => {
    if (amount === null) return;
    setBusy(true);
    setError(null);
    try {
      receive(
        await api.flowACheck({
          bank_bin: values.bankBin,
          account_number: values.accountNumber,
          amount_vnd: amount,
          memo: values.memo === "" ? null : values.memo,
          source_integrity: sourceIntegrity,
          confirmation_token: confirmationToken,
          origin_verdict_id: routeState?.origin_verdict_id ?? null,
          client_time: new Date().toISOString(),
        }),
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const chooseContext = async (choice: ContextChoice): Promise<void> => {
    if (response === null) return;
    setBusy(true);
    setError(null);
    try {
      receive(await api.context({ verdict_id: response.verdict_id, context: choice }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const commit = async (answeredQuestions: number): Promise<void> => {
    if (response === null) return;
    setBusy(true);
    setError(null);
    try {
      await api.transferCommit({
        verdict_id: response.verdict_id,
        cooldown_completed: true,
        answered_questions: answeredQuestions,
      });
      setPhase("sent");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const askGuardian = (): void => {
    if (response === null || amount === null) return;
    dispatch?.({
      type: "OPEN_POPUP",
      linkedTransaction: {
        verdict_id: response.verdict_id,
        bank_bin: values.bankBin,
        account_number: values.accountNumber,
        amount_vnd: amount,
      },
    });
  };

  const tier = response?.verdict.decision_tier;

  return (
    <main className="mx-auto max-w-md space-y-4 p-4">
      <h1 className="text-xl font-semibold">Chuyển tiền</h1>

      {phase === "form" && (
        <TransferForm values={values} onChange={setValues} onSubmit={() => setPhase("confirm")} />
      )}

      {phase === "confirm" && amount !== null && (
        <TwoStepConfirm
          bankBin={values.bankBin}
          accountNumber={values.accountNumber}
          amountVnd={amount}
          memo={values.memo}
          busy={busy}
          onConfirm={() => void runCheck()}
          onBack={() => setPhase("form")}
        />
      )}

      {phase === "result" && response !== null && (
        <>
          <CalmShield
            hints={response.ui_hints}
            bullets={response.verdict.evidence_bullets}
            onContinue={() => setCalmDismissed(true)}
            dismissed={calmDismissed}
          >
          <ResultCard response={response}>
            {tier === "ALLOW" && response.ui_hints.show_transfer_now && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void commit(0)}
                className="rounded-lg bg-pink-600 px-4 py-2 text-white disabled:bg-gray-300"
              >
                Chuyển ngay
              </button>
            )}
            {tier === "SOFT_FRICTION" && (
              <button
                type="button"
                onClick={askGuardian}
                className="rounded-lg border border-amber-600 px-4 py-2 text-amber-800"
              >
                Kiểm tra cùng Guardian
              </button>
            )}
            {tier === "HARD_HOLD" && response.verdict.allow_fast_unblock && (
              <button
                type="button"
                onClick={() => setShowUnblock(true)}
                className="rounded-lg border border-red-600 px-4 py-2 text-red-800"
              >
                Mở chặn nhanh
              </button>
            )}
          </ResultCard>
          </CalmShield>
          <BankHandoff
            verdictId={response.verdict_id}
            tier={response.verdict.decision_tier}
            handoffAllowed={response.ui_hints.handoff_allowed}
            bankBin={values.bankBin}
            accountNumber={values.accountNumber}
            amountVnd={amount}
            memo={values.memo}
          />

          {response.ui_hints.show_context_elicitation && (
            <ContextElicitation
              disabled={busy}
              onChoose={(c) => void chooseContext(c)}
              onInviteChatImage={askGuardian}
            />
          )}

          {tier === "SOFT_FRICTION" && (
            <CooldownGate
              key={response.verdict_id}
              coolingOffSeconds={response.verdict.cooling_off_seconds}
              questions={response.verdict.system2_check_questions}
              busy={busy}
              onContinue={(n) => void commit(n)}
            />
          )}

          {showUnblock && tier === "HARD_HOLD" && (
            <FastUnblockDialog
              verdictId={response.verdict_id}
              onCancel={() => setShowUnblock(false)}
              onUnblocked={(res) => {
                setShowUnblock(false);
                receive(res);
              }}
            />
          )}

          <DecisionTrace response={response} />
        </>
      )}

      {phase === "sent" && amount !== null && (
        <p role="status" className="rounded-xl bg-green-50 p-4 text-sm text-green-800">
          Đã mô phỏng chuyển {formatVnd(amount)}. Đây là dữ liệu mô phỏng, không có tiền thật được chuyển.
        </p>
      )}

      {error !== null && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </main>
  );
}
