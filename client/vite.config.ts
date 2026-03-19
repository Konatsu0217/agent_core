import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  publicDir: 'public',
  server: {
    port: 3000,
    open: true,
    proxy: {
      // HTTP API 代理到后端
      '/api': {
        target: 'http://127.0.0.1:38888',
        changeOrigin: true,
      },
      // WebSocket 代理到后端
      '/ws': {
        target: 'ws://127.0.0.1:38888',
        ws: true,
        changeOrigin: true,
      },
      // 保留 files 代理（如有静态资源服务）
      '/files': {
        target: 'http://127.0.0.1:38888',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});
