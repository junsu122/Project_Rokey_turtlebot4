import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// FMS Flask API(기본 localhost:5000)로의 프록시 — CORS 우회 + /api 폴링.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // FMS는 세션 로그인을 요구하므로 /login 도 같은 출처로 프록시(쿠키 동일 출처).
      "/api": { target: process.env.VITE_FMS_URL || "http://localhost:5000", changeOrigin: true },
      "/login": { target: process.env.VITE_FMS_URL || "http://localhost:5000", changeOrigin: true },
    },
  },
});
