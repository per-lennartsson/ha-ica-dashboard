import { defineConfig } from "vitest/config";

// The card is one ES module that the integration serves to Home Assistant.
export default defineConfig({
  define: {
    __INKOP_VERSION__: JSON.stringify(process.env.npm_package_version ?? "dev"),
  },
  build: {
    lib: {
      entry: "src/inkop-card.ts",
      formats: ["es"],
      fileName: () => "inkop-card.js",
    },
    outDir: "../custom_components/inkop/www",
    emptyOutDir: true,
    target: "es2022",
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/types.ts"],
    },
  },
});
