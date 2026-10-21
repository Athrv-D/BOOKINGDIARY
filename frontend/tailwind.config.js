/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        booking: {
          50: "#eff6ff",
          600: "#2563eb",
          700: "#1d4ed8"
        }
      }
    }
  },
  plugins: []
};
