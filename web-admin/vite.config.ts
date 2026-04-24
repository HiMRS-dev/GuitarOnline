import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function resolveVendorChunk(moduleId: string): string | undefined {
  if (!moduleId.includes("node_modules/")) {
    return undefined;
  }

  if (
    moduleId.includes("/react-admin/") ||
    moduleId.includes("/ra-core/") ||
    moduleId.includes("/ra-ui-materialui/") ||
    moduleId.includes("/ra-i18n-polyglot/") ||
    moduleId.includes("/ra-language-english/") ||
    moduleId.includes("/@mui/") ||
    moduleId.includes("/@emotion/")
  ) {
    return "vendor-admin-platform";
  }
  if (moduleId.includes("/@fullcalendar/")) {
    return "vendor-fullcalendar";
  }
  if (moduleId.includes("/react-dom/")) {
    return "vendor-react-dom";
  }
  if (moduleId.includes("/react-router/") || moduleId.includes("/react-router-dom/")) {
    return "vendor-react-router";
  }
  if (moduleId.includes("/@tanstack/")) {
    return "vendor-tanstack";
  }
  return undefined;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const rawBasePath = env.VITE_BASE_PATH?.trim() || "/";
  const basePath = rawBasePath.endsWith("/") ? rawBasePath : `${rawBasePath}/`;
  const devApiTarget = env.VITE_DEV_API_TARGET?.trim() || "http://localhost:8000";

  return {
    base: basePath,
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: devApiTarget,
          changeOrigin: true
        }
      }
    },
    build: {
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          manualChunks(id) {
            return resolveVendorChunk(id);
          }
        }
      }
    }
  };
});
