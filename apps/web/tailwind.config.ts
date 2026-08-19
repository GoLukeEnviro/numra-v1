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
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
