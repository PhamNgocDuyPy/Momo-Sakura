import type { CheckResponse, Stage2Event } from "../shared/types";

export type CheckState =
  | { phase: "idle" }
  | { phase: "scanning"; charCount: number }
  | { phase: "stage2"; charCount: number; stage2: Stage2Event }
  | { phase: "final"; response: CheckResponse }
  | { phase: "error"; message: string };

export type CheckAction =
  | { type: "start"; charCount: number }
  | { type: "stage2"; event: Stage2Event }
  | { type: "final"; response: CheckResponse }
  | { type: "error"; message: string }
  | { type: "close" };

export function checkReducer(state: CheckState, action: CheckAction): CheckState {
  switch (action.type) {
    case "start":
      return { phase: "scanning", charCount: action.charCount };
    case "stage2":
      // Ignore late events after a final/error/close.
      if (state.phase !== "scanning" && state.phase !== "stage2") return state;
      return { phase: "stage2", charCount: state.charCount, stage2: action.event };
    case "final":
      if (state.phase !== "scanning" && state.phase !== "stage2") return state;
      return { phase: "final", response: action.response };
    case "error":
      // A late disconnect error must not replace a delivered result.
      if (state.phase !== "scanning" && state.phase !== "stage2") return state;
      return { phase: "error", message: action.message };
    case "close":
      return { phase: "idle" };
  }
}