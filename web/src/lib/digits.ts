/** Keep only ASCII digits. */
export function digitsOnly(value: string): string {
  return value.replace(/\D+/g, "");
}

/** Split a string into its individual digit characters (for per-digit display). */
export function splitDigits(value: string): string[] {
  return digitsOnly(value).split("");
}
