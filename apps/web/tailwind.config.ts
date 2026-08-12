import type { Config } from 'tailwindcss';

/**
 * HieuTrienEducation design system.
 *
 * The visual language is warm, rounded and confident — colourful enough to feel welcoming to a
 * twelve-year-old, restrained enough that a parent takes it seriously. Every value here is
 * original to this project.
 *
 * Two subject colours run through the whole product: violet for Mathematics, teal for Physics.
 * They appear on course cards, progress bars, skill nodes and section accents, so a student
 * learns to recognise the subject by colour before reading the label.
 */
const config: Config = {
  content: [
    './src/**/*.{ts,tsx}',
    '../../packages/*/src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Brand violet — the primary identity colour.
        brand: {
          50: '#F3F0FF',
          100: '#E7E1FF',
          200: '#CFC2FF',
          300: '#B29CFF',
          400: '#9070FF',
          500: '#6D4AFF',
          600: '#5A32F0',
          700: '#4A25CC',
          800: '#3B1FA3',
          900: '#2E1980',
        },
        // Coral — calls to action, energy, "start here".
        coral: {
          50: '#FFF3EE',
          100: '#FFE3D6',
          200: '#FFC5AC',
          300: '#FFA07B',
          400: '#FF8A5B',
          500: '#FF7A45',
          600: '#F05A20',
          700: '#C74516',
          800: '#9C3612',
          900: '#7A2B10',
        },
        // Teal — Physics, and "correct".
        teal: {
          50: '#EAFBF9',
          100: '#CDF5F0',
          200: '#9BEAE1',
          300: '#5CD9CC',
          400: '#22C7B6',
          500: '#00B8A9',
          600: '#009488',
          700: '#00756C',
          800: '#005A53',
          900: '#004640',
        },
        // Sunshine — achievements, streaks, XP.
        sun: {
          50: '#FFF9E6',
          100: '#FFF0BF',
          200: '#FFE180',
          300: '#FFD24D',
          400: '#FFC53D',
          500: '#F5B01A',
          600: '#D18F0C',
          700: '#A46E08',
          800: '#7D5406',
          900: '#5E3F05',
        },
        // Deep indigo-black for text — softer and warmer than pure black.
        ink: {
          50: '#F6F5FA',
          100: '#EDEBF3',
          200: '#D8D4E4',
          300: '#B5AECB',
          400: '#8B82A8',
          500: '#6B6188',
          600: '#524A6B',
          700: '#3E3853',
          800: '#2A2540',
          900: '#1A1633',
        },
        cream: '#FFFBF5',
        lavender: '#F7F5FF',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'var(--font-sans)', 'ui-sans-serif', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        // Generous rounding throughout — nothing in this product has a sharp corner.
        xl: '1rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        '4xl': '2.25rem',
        blob: '48% 52% 41% 59% / 55% 45% 55% 45%',
      },
      boxShadow: {
        soft: '0 2px 8px -2px rgb(26 22 51 / 0.06), 0 8px 24px -8px rgb(26 22 51 / 0.10)',
        lift: '0 8px 20px -6px rgb(26 22 51 / 0.12), 0 20px 44px -16px rgb(26 22 51 / 0.16)',
        glow: '0 0 0 4px rgb(109 74 255 / 0.12)',
        'glow-coral': '0 0 0 4px rgb(255 122 69 / 0.16)',
        // Chunky offset shadow used on playful cards and buttons.
        pop: '4px 4px 0 0 rgb(26 22 51 / 0.90)',
        'pop-sm': '3px 3px 0 0 rgb(26 22 51 / 0.85)',
      },
      backgroundImage: {
        'grid-soft':
          'linear-gradient(to right, rgb(109 74 255 / 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgb(109 74 255 / 0.05) 1px, transparent 1px)',
      },
      backgroundSize: {
        grid: '32px 32px',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'pop-in': {
          '0%': { opacity: '0', transform: 'scale(0.94)' },
          '60%': { opacity: '1', transform: 'scale(1.02)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'float-slow': {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '50%': { transform: 'translateY(-16px) rotate(3deg)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'draw-in': {
          from: { strokeDashoffset: '1000' },
          to: { strokeDashoffset: '0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'pop-in': 'pop-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both',
        float: 'float 5s ease-in-out infinite',
        'float-slow': 'float-slow 9s ease-in-out infinite',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
};

export default config;
