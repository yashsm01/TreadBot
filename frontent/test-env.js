// Simple environment variable test
console.log("🔧 Environment Variables Test:");
console.log("- NODE_ENV:", process.env.NODE_ENV);
console.log("- VITE_API_URL:", process.env.VITE_API_URL);
console.log("- VITE_DEV_MODE:", process.env.VITE_DEV_MODE);

console.log("\n📋 All environment variables:");
Object.keys(process.env)
  .filter(
    (key) =>
      key.startsWith("VITE_") || key.includes("API") || key.includes("URL")
  )
  .forEach((key) => {
    console.log(`- ${key}: ${process.env[key]}`);
  });

console.log("\n🌐 Testing API URL construction:");
const apiUrl = process.env.VITE_API_URL || "http://localhost:8000/api/v1";
console.log("- Final API URL:", apiUrl);
console.log("- Live API URL:", `${apiUrl}/live`);

// Test if we can reach the API
console.log("\n🔍 Testing API connectivity...");
const testAPI = async () => {
  try {
    const response = await fetch(`${apiUrl}/live/health`);
    const data = await response.json();
    console.log("✅ API is reachable:", data);
  } catch (error) {
    console.log("❌ API is not reachable:", error.message);
  }
};

// Only test if fetch is available (Node 18+)
if (typeof fetch !== "undefined") {
  testAPI();
} else {
  console.log("⚠️ Fetch not available in this Node version");
}
