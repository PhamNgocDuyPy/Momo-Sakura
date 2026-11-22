/** Opens the Guardian web app (URL from settings) in a new tab. */
export default function OpenGuardianButton({ webUrl }: { webUrl: string }) {
  return (
    <a
      href={webUrl}
      target="_blank"
      rel="noopener noreferrer"
      data-testid="open-guardian"
      className="block w-full rounded-xl bg-pink-600 px-4 py-2.5 text-center text-sm font-semibold text-white shadow hover:bg-pink-700"
    >
      Mở MoMo Guardian
    </a>
  );
}