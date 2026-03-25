import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Backend defaults to localhost:3000 for dev, can be overridden via env
const BACKEND_HOST = process.env.VITE_BACKEND_HOST || "http://localhost:3000"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: BACKEND_HOST,
        changeOrigin: true,
        secure: false,
      },
      "/socket.io": {
        target: BACKEND_HOST,
        changeOrigin: true,
        ws: true,
        secure: false,
      },
    },
  },
})

