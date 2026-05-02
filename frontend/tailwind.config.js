/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#101010', // Midnight Void
        surface: '#080808',    // Deep Space
        border: '#333333',     // Dark Carbon
        primary: '#E7C59A',    // Amber Glow
        secondary: '#F3F3F3',  // Polar White
        accent: '#E7C59A',
        danger: '#E7C59A',
        success: '#00AC5C',    // Neon Green
        slate: '#C1C1C1',
        ash: '#949494',
      },
      fontFamily: {
        aeonik: ['Inter', 'sans-serif'],
        input: ['IBM Plex Mono', 'monospace'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        'amber-glow': '0 0 15px rgba(231, 197, 154, 0.15)',
      }
    },
  },
  plugins: [],
}
