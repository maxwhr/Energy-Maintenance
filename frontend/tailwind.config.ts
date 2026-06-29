import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['system-ui', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif']
      },
      colors: {
        scada: {
          void: '#05080d',
          panel: '#0b111a',
          rail: '#101821',
          line: '#263545',
          grid: '#1d2a36',
          cyan: '#00b8f1',
          blue: '#2f7db6',
          green: '#3acb35',
          amber: '#ff9a00',
          red: '#de3a15',
          steel: '#6e9abb'
        }
      }
    }
  }
} satisfies Config
