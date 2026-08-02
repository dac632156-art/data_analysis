/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cosmic: {
          deep: '#eef2ff',
          space: '#faf5ff',
          starlight: '#60a5fa',
          galaxy: '#8b5cf6',
          moon: '#0f172a',
          aurora: '#f472b6',
        },
        glass: {
          DEFAULT: 'rgba(255, 255, 255, 0.55)',
          border: 'rgba(255, 255, 255, 0.75)',
        },
        accent: {
          DEFAULT: '#8b5cf6',
          soft: '#a78bfa',
          blue: '#60a5fa',
          pink: '#f472b6',
        },
        text: {
          primary: '#0f172a',
          secondary: '#475569',
          muted: '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      backdropBlur: {
        glass: '20px',
      },
      boxShadow: {
        'cosmic-card': '0 0 15px rgba(100, 180, 255, 0.15)',
        'cosmic-card-hover': '0 0 25px rgba(100, 180, 255, 0.35)',
        'cosmic-portal': '0 0 30px rgba(139, 92, 246, 0.2), 0 0 60px rgba(56, 189, 248, 0.1)',
        'cosmic-portal-hover': '0 0 50px rgba(34, 211, 238, 0.4), 0 0 100px rgba(56, 189, 248, 0.3)',
        'cosmic-glow': '0 0 20px rgba(139, 92, 246, 0.3), 0 0 40px rgba(56, 189, 248, 0.15)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'slide-up': 'slide-up 0.5s ease-out',
        'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
        'spin-slow': 'spin 12s linear infinite',
        'spin-slower': 'spin 20s linear infinite',
        'spin-reverse': 'spin-reverse 8s linear infinite',
        'breathe': 'breathe 4s ease-in-out infinite',
        'stars-twinkle': 'stars-twinkle 12s ease-in-out infinite',
        'nebula-float': 'nebula-float 18s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(139, 92, 246, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(139, 92, 246, 0.6)' },
        },
        'spin-reverse': {
          from: { transform: 'rotate(360deg)' },
          to: { transform: 'rotate(0deg)' },
        },
        breathe: {
          '0%, 100%': {
            boxShadow: '0 0 20px rgba(139, 92, 246, 0.3), 0 0 40px rgba(56, 189, 248, 0.15)',
          },
          '50%': {
            boxShadow: '0 0 30px rgba(139, 92, 246, 0.5), 0 0 60px rgba(56, 189, 248, 0.3), 0 0 80px rgba(34, 211, 238, 0.15)',
          },
        },
        'stars-twinkle': {
          '0%, 100%': { opacity: '0.6' },
          '25%': { opacity: '0.85' },
          '50%': { opacity: '0.5' },
          '75%': { opacity: '0.9' },
        },
        'nebula-float': {
          '0%': { transform: 'translate(0, 0) scale(1)', opacity: '0.7' },
          '33%': { transform: 'translate(15px, -10px) scale(1.03)', opacity: '0.85' },
          '66%': { transform: 'translate(-10px, 8px) scale(0.97)', opacity: '0.65' },
          '100%': { transform: 'translate(0, 0) scale(1)', opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
