import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ember: {
          50: "#fff8ed",
          100: "#ffebc7",
          200: "#ffd48f",
          300: "#ffba57",
          400: "#f79c2d",
          500: "#df7f12",
          600: "#b6620d",
          700: "#8c490f",
          800: "#5f3210",
          900: "#351c0d"
        }
      },
      fontFamily: {
        sans: ["'Sora'", "ui-sans-serif", "system-ui"]
      },
      backgroundImage: {
        grid: "linear-gradient(to right, rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.08) 1px, transparent 1px)"
      }
    }
  },
  plugins: []
};

export default config;
