#!/usr/bin/env node

const { spawn } = require("child_process");
const path = require("path");

// Set environment variables
process.env.VITE_API_URL =
  process.env.VITE_API_URL || "http://localhost:8000/api/v1";
process.env.VITE_DEV_MODE = "true";
process.env.VITE_AUTO_REFRESH_INTERVAL = "30000";
process.env.VITE_ENABLE_MOCK_FALLBACK = "true";

console.log("🚀 Starting Development Server...");
console.log("📡 API URL:", process.env.VITE_API_URL);
console.log(
  "🔄 Auto-refresh interval:",
  process.env.VITE_AUTO_REFRESH_INTERVAL + "ms"
);
console.log("");

// Start the Vite dev server
const viteProcess = spawn("npm", ["run", "dev"], {
  stdio: "inherit",
  shell: true,
  cwd: __dirname,
});

viteProcess.on("close", (code) => {
  console.log(`\n🛑 Development server exited with code ${code}`);
  process.exit(code);
});

// Handle process termination
process.on("SIGINT", () => {
  console.log("\n🛑 Shutting down development server...");
  viteProcess.kill("SIGINT");
});

process.on("SIGTERM", () => {
  console.log("\n🛑 Shutting down development server...");
  viteProcess.kill("SIGTERM");
});
