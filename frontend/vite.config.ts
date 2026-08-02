import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// dev サーバは 5173。/api と /media は FastAPI(:8000) へプロキシするため、
// フロントからは同一オリジンに見える（CORS 設定はプロキシを使わない場合の保険）。
//
// ⚠️ `ws: true` は必須。リアルタイム画面のブラウザカメラ経路は
// `/api/realtime/ws`（WebSocket）を使うが、これが無いとアップグレード要求が
// 中継されず接続できない。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, ws: true },
      '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
