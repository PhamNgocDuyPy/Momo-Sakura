import { useEffect, useState } from "react";
import System2Questions from "./System2Questions";

interface Props {
  coolingOffSeconds: number;
  questions: string[];
  /** Called when the user presses continue after cooldown and all questions are answered. */
  onContinue: (answeredCount: number) => void;
  busy?: boolean;
}

export default function CooldownGate({ coolingOffSeconds, questions, onContinue, busy = false }: Props) {
  const [remaining, setRemaining] = useState(coolingOffSeconds);
  const [answered, setAnswered] = useState<boolean[]>(() => questions.map(() => false));

  useEffect(() => {
    setRemaining(coolingOffSeconds);
    if (coolingOffSeconds <= 0) return;
    const timer = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(timer);
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [coolingOffSeconds]);

  const answeredCount = answered.filter(Boolean).length;
  const allAnswered = answeredCount >= questions.length;
  const ready = remaining === 0 && allAnswered && !busy;

  return (
    <div className="space-y-3">
      <System2Questions
        questions={questions}
        answered={answered}
        onAnswer={(i) => setAnswered((prev) => prev.map((v, idx) => (idx === i ? true : v)))}
      />
      {remaining > 0 && (
        <p role="timer" className="text-sm text-gray-700">
          Vui lòng chờ {remaining} giây để suy nghĩ lại.
        </p>
      )}
      <button
        type="button"
        disabled={!ready}
        onClick={() => onContinue(answeredCount)}
        className="w-full rounded-lg bg-pink-600 px-4 py-2 text-white disabled:bg-gray-300"
      >
        Tiếp tục chuyển tiền
      </button>
    </div>
  );
}
