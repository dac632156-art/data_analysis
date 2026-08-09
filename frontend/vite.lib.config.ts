import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// lib 构建专用插件：把组件里 `new URL('...背景.png'/bg5.png', import.meta.url)`
// 重定向到 1x1 占位，避免 14MB 真实水彩图进 UMD。
// 导出 HTML 通过 cardBgUrl prop 传入真实 base64（见 assets.ts），组件优先用 cardBgUrl。
function stubEtherealBg() {
  return {
    name: 'stub-ethereal-bg',
    enforce: 'pre',
    transform(code: string, id: string) {
      if (id.includes('EtherealCharts') && /背景\.png|bg5\.png/.test(code)) {
        return code
          .replace(/背景\.png/g, '_placeholder.png')
          .replace(/bg5\.png/g, '_placeholder.png');
      }
      return null;
    },
  };
}

// 把「仙气看板组件树」打包成 UMD，供单文件导出 HTML 复用（与屏幕共用一份代码）
export default defineConfig({
  plugins: [react(), stubEtherealBg()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  // 公共资源不拷入 lib 产物（导出 HTML 自带背景图，地图走运行时 fetch）
  publicDir: false,
  build: {
    // 大图（背景.png/bg5.png）输出为独立 asset 而非内联，UMD 体积控制在代码层
    assetsInlineLimit: 0,
    outDir: 'dist-lib',
    emptyOutDir: true,
    lib: {
      entry: path.resolve(__dirname, 'src/components/EtherealCharts/etherealCoreEntry.tsx'),
      name: 'EtherealCore',
      formats: ['umd'],
      fileName: () => 'ethereal-core.js',
    },
    rollupOptions: {
      // 仅 external React/ReactDOM（走 CDN）；echarts/echarts-gl/组件全部打包进 UMD
      // 注意：react/jsx-runtime 不 external（由 plugin-react automatic runtime 打进 UMD，
      // 内部引用 external React），避免 CDN 缺 jsx-runtime 全局导致运行失败。
      external: ['react', 'react-dom'],
      output: {
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
        },
        assetFileNames: 'ethereal-core.[ext]',
      },
    },
  },
});
