import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  // Frappe serves files from booking_diary/public at /assets/booking_diary/.
  base: "/assets/booking_diary/frontend/",
  build: {
    outDir: fileURLToPath(new URL("../booking_diary/public/frontend", import.meta.url)),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
