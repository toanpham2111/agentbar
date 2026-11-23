import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const localChrome = "/usr/bin/google-chrome";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "test-results",
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:1420",
    launchOptions: existsSync(localChrome) ? { executablePath: localChrome } : {},
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev",
    env: { VITE_DEMO_MODE: "true" },
    url: "http://127.0.0.1:1420",
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "tablet-768", use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } } },
    { name: "mobile-375", use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 } } },
  ],
});
