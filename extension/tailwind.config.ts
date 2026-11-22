import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./options.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};

export default config;