/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F6F5F1",
        ink: "#1B1D1F",
        muted: "#5F6368",
        line: "#E3E1DA",
        safe: "#1E8E3E",
        caution: "#D97706",
        danger: "#D93025",
        info: "#1A73E8",
        offline: "#80868B",
        brand: "#0F766E",
        night: { bg: "#111315", surface: "#1A1D20", line: "#2A2E33", text: "#ECEDEE" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
      },
      borderRadius: { card: "16px", sheet: "24px" },
      boxShadow: { float: "0 6px 24px rgba(0,0,0,.12)" },
      keyframes: {
        pulsering: { "0%": { transform: "scale(.6)", opacity: ".9" }, "100%": { transform: "scale(2.4)", opacity: "0" } },
        slideup: { "0%": { transform: "translateY(24px)", opacity: "0" }, "100%": { transform: "none", opacity: "1" } },
        flash: { "0%,100%": { opacity: "1" }, "50%": { opacity: ".35" } },
      },
      animation: {
        pulsering: "pulsering 1.6s ease-out infinite",
        slideup: "slideup .22s ease-out",
        flash: "flash 1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
