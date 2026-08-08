import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    fs: {
      // 必须保留项目根目录，否则连 index.html 都不在白名单会 403
      // 额外允许 dist-lib 下的构建产物（ethereal-core.js UMD）
      allow: [
        path.resolve(__dirname),
        path.resolve(__dirname, 'dist-lib'),
      ],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
