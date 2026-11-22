interface Props {
  questions: string[];
  /** answers[i] is true once question i has been answered. */
  answered: boolean[];
  onAnswer: (index: number) => void;
}

export default function System2Questions({ questions, answered, onAnswer }: Props) {
  if (questions.length === 0) return null;
  return (
    <ul className="space-y-2" aria-label="Câu hỏi kiểm tra">
      {questions.map((q, i) => (
        <li key={q} className="rounded-lg bg-white p-3 text-sm">
          <p>{q}</p>
          <div className="mt-2 flex gap-2">
            {["Rồi", "Chưa"].map((label) => (
              <button
                key={label}
                type="button"
                aria-label={`${label} - câu ${i + 1}`}
                aria-pressed={answered[i] === true}
                onClick={() => onAnswer(i)}
                className="rounded-md border border-gray-300 px-3 py-1 text-xs"
              >
                {label}
              </button>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
