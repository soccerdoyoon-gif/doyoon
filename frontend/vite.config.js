import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 모드: http://localhost:5173 → API 요청은 backend(8000)로 전달
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1000 },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_TARGET || "http://localhost:8000",
      "/media": process.env.VITE_API_TARGET || "http://localhost:8000",
    },
  },
});
