/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1a1a2e',
        'ink-soft': '#4a4a5e',
        accent: {
          DEFAULT: '#1a1a2e',
          hover: '#2d2d4e',
        },
      },
    },
  },
  plugins: [],
}