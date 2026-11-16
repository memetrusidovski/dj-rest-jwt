import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  // dj-rest-jwt-client is linked from ../../js; use one copy of React.
  resolve: { dedupe: ["react", "react-dom"] },
  server: {
    port: 5173,
    host: true,
    // Same origin for the SPA and the API, so the httpOnly cookies and the
    // CSRF cookie just work. In production put both behind one domain the
    // same way (or use a subdomain + CORS with credentials).
    proxy: {
      "/api": { target: backend },
      "/admin": { target: backend },
      "/static": { target: backend },
    },
  },
});
