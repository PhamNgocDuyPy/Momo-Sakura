import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from "react";
import type {
  CheckResponse,
  ContentMode,
  DecisionTier,
  FlowBContent,
  LinkedTransaction,
  ShieldStats,
} from "../types/api";

export type PopupStatus = "idle" | "ocr" | "stage1" | "stage2" | "done" | "error";

export interface PopupState {
  open: boolean;
  mode: ContentMode;
  status: PopupStatus;
  linkedTransaction: LinkedTransaction | null;
  /** Content queued by the share target; ScanPopup submits it once, then clears it. */
  autoSubmit?: FlowBContent | null;
}

export interface GuardianState {
  popup: PopupState;
  lastVerdict: CheckResponse | null;
  shieldStats: ShieldStats;
}

export type GuardianAction =
  | { type: "OPEN_POPUP"; mode?: ContentMode; linkedTransaction?: LinkedTransaction | null }
  | { type: "CLOSE_POPUP" }
  | { type: "SET_MODE"; mode: ContentMode }
  | { type: "QUEUE_SUBMIT"; content: FlowBContent }
  | { type: "CLEAR_QUEUED_SUBMIT" }
  | { type: "SET_STATUS"; status: PopupStatus }
  | { type: "VERDICT_RECEIVED"; response: CheckResponse }
  | { type: "SYNC_SHIELD_STATS"; stats: ShieldStats };

export const emptyShieldStats: ShieldStats = { checks: 0, ALLOW: 0, SOFT_FRICTION: 0, HARD_HOLD: 0 };

export const initialGuardianState: GuardianState = {
  popup: { open: false, mode: "GENERAL", status: "idle", linkedTransaction: null },
  lastVerdict: null,
  shieldStats: emptyShieldStats,
};

function bump(stats: ShieldStats, tier: DecisionTier): ShieldStats {
  return { ...stats, checks: stats.checks + 1, [tier]: stats[tier] + 1 };
}

export function guardianReducer(state: GuardianState, action: GuardianAction): GuardianState {
  switch (action.type) {
    case "OPEN_POPUP":
      return {
        ...state,
        popup: {
          open: true,
          mode: action.mode ?? "GENERAL",
          status: "idle",
          linkedTransaction: action.linkedTransaction ?? null,
        },
      };
    case "CLOSE_POPUP":
      return { ...state, popup: { ...state.popup, open: false, status: "idle" } };
    case "SET_MODE":
      return { ...state, popup: { ...state.popup, mode: action.mode } };
    case "QUEUE_SUBMIT":
      return { ...state, popup: { ...state.popup, autoSubmit: action.content } };
    case "CLEAR_QUEUED_SUBMIT":
      return { ...state, popup: { ...state.popup, autoSubmit: null } };
    case "SET_STATUS":
      return { ...state, popup: { ...state.popup, status: action.status } };
    case "VERDICT_RECEIVED": {
      const countable = action.response.from_demo !== true;
      return {
        ...state,
        lastVerdict: action.response,
        shieldStats: countable
          ? bump(state.shieldStats, action.response.verdict.decision_tier)
          : state.shieldStats,
      };
    }
    case "SYNC_SHIELD_STATS":
      return { ...state, shieldStats: action.stats };
  }
}

interface GuardianContextValue {
  state: GuardianState;
  dispatch: Dispatch<GuardianAction>;
}

const GuardianContext = createContext<GuardianContextValue | null>(null);

export function GuardianProvider({
  children,
  initialState = initialGuardianState,
}: {
  children: ReactNode;
  initialState?: GuardianState;
}) {
  const [state, dispatch] = useReducer(guardianReducer, initialState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <GuardianContext.Provider value={value}>{children}</GuardianContext.Provider>;
}

/** Like useGuardian but returns null outside a provider (e.g. isolated page tests). */
export function useGuardianOptional(): GuardianContextValue | null {
  return useContext(GuardianContext);
}

export function useGuardian(): GuardianContextValue {
  const ctx = useContext(GuardianContext);
  if (!ctx) throw new Error("useGuardian must be used inside GuardianProvider");
  return ctx;
}
