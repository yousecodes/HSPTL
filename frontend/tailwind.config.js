/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{html,js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        hsptl: {
          indigo: { DEFAULT: '#174438', light: '#1F5B49', glow: '#7FA58F' },
          teal: { DEFAULT: '#2F7764', light: '#DDEBE2', dark: '#194D40' },
          surface: { canvas: '#F4F7F2', card: '#FCFDF9', border: '#DCE5DB' },
          dark: { canvas: '#10241D', card: '#1A342B', border: '#365244' },
          status: { correct: '#3C936C', warning: '#C28D40', danger: '#B95D50' },
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
};
