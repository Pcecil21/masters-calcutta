/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        augusta: '#006747',
        'augusta-light': '#00875f',
        'augusta-dark': '#004d35',
        gold: '#FDD835',
        'gold-dark': '#F9A825',
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scroll-left': 'scroll-left 30s linear infinite',
      },
      keyframes: {
        'scroll-left': {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(-100%)' },
        },
      },
    },
  },
  plugins: [],
};
