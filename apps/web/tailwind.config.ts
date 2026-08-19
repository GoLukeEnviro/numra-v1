import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0B0B0F",
        surface: "#13131A",
        "surface-2": "#191921",
        gold: "#C8A96B",
        bronze: "#8F6B3E",
        ivory: "#F2EBDD",
        text: "#E8E3D8",
        muted: "#9E98A4",
        plum: "#604B72",
        danger: "#E28B7C",
        "danger-surface": "#3A1E1B",
        success: "#8FBF9F",
      },
      fontFamily: {
        serif: ["ui-serif", "Georgia", "Cambria", "Times New Roman", "serif"],
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      borderRadius: {
        xl: "0.875rem",
      },
      boxShadow: {
        gold: "0 0 0 1px rgba(200,169,107,0.35)",
        // Elevation for surfaces that sit above the page (hero, report sheet). Pure
        // shadow, no border change, so it composes with the existing hairline borders.
        elevated: "0 18px 40px -24px rgba(0,0,0,0.85)",
      },
      maxWidth: {
        // Long-form reading measure for report prose. Slightly wider than Tailwind's
        // built-in `prose` (65ch) because report body text is set at 1.0625rem.
        reading: "68ch",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        // The ceiling for motion in this app: a few pixels of rise with the fade.
        // Anything larger reads as decoration, on a product whose whole promise is
        // that nothing on screen is embellished. Both are disabled wholesale by the
        // prefers-reduced-motion block in globals.css.
        "rise-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        "rise-in": "rise-in 240ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
