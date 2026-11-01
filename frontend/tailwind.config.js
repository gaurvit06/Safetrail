/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // The pitch deck's palette: warm charcoal and paper, with teal, gold, purple and alert red.
      colors: {
        bg: "#F4EFE8",
        paper: "#EFE8DE",
        ink: "#211D1A",
        muted: "#6B6157",
        line: "#E6DCCD",
        safe: "#1E8E3E",
        caution: "#A86207",
        gold: "#E8A317",
        danger: "#D93025",
        info: "#6B3E8E",
        offline: "#8A7E72",
        brand: "#0F766E",
        night: { bg: "#211D1A", surface: "#2E2824", line: "#4A423B", text: "#F4EFE8" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Barlow Condensed", "Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: { card: "16px", sheet: "24px" },
      boxShadow: { float: "0 6px 24px rgba(33,29,26,.16)" },
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
