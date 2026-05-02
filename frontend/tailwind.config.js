/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#ffffff',
        surface: '#f8fafc',
        border: '#e2e8f0',
        primary: '#FF003C', // Signature War Room Red
        secondary: '#0f172a',
        accent: '#FF003C',
        danger: '#FF003C',
        success: '#059669',
      },
      fontFamily: {
        header: ['Inter Tight', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        inter: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'red-glow': '0 0 15px rgba(255, 0, 60, 0.1)',
        'red-ring': '0 0 0 1px rgba(255, 0, 60, 0.2)',
      }
    },
  },
  plugins: [],
}
