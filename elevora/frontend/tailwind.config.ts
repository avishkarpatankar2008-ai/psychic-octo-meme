import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 900: "#F7F7FB", 600: "#A4A7B8", 400: "#6F7386" },
        navy: { 950: "#070812", 900: "#0C0E19", 800: "#131626", 700: "#1A1D31" },
        accent: { DEFAULT: "#7C5CFF", 600: "#7C5CFF", 700: "#6545E8", 300: "#B8A8FF", 100: "#1C1738" },
        surface: { DEFAULT: "#0D0F1B", muted: "#090B14", border: "rgba(255,255,255,.09)" },
        success: "#45D39A", warning: "#F0B45B", danger: "#FF6B78",
      },
      fontFamily: { sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"] },
      borderRadius: { sm: "8px", md: "12px", lg: "16px", xl: "22px" },
      boxShadow: { soft: "0 20px 80px rgba(0,0,0,.35)" },
    },
  },
  plugins: [],
};
export default config;
