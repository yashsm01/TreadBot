import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ["lucide-react"],
  },
  define: {
    // Define environment variables directly in Vite config
    "import.meta.env.VITE_API_URL": JSON.stringify(
      process.env.VITE_API_URL || "http://localhost:8000/api/v1"
    ),
    "import.meta.env.VITE_DEV_MODE": JSON.stringify(
      process.env.VITE_DEV_MODE || "true"
    ),
    "import.meta.env.VITE_AUTO_REFRESH_INTERVAL": JSON.stringify(
      process.env.VITE_AUTO_REFRESH_INTERVAL || "30000"
    ),
    "import.meta.env.VITE_ENABLE_MOCK_FALLBACK": JSON.stringify(
      process.env.VITE_ENABLE_MOCK_FALLBACK || "true"
    ),
  },
  server: {
    host: true,
    port: 5173,
  },
});
