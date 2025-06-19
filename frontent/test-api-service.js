// Test script to verify API service functionality
console.log("🧪 Testing API Service...");

// Mock the browser environment for testing
global.fetch = async (url) => {
  console.log(`🌐 Mock fetch called for: ${url}`);

  if (url.includes("/health")) {
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Map([["content-type", "application/json"]]),
      json: async () => ({
        status: "healthy",
        service: "live_data_service",
        timestamp: Date.now(),
        binance_connection: true,
        last_test: Date.now() - 1000,
      }),
    };
  }

  if (url.includes("/tokens")) {
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Map([["content-type", "application/json"]]),
      json: async () => [
        {
          id: "btc",
          symbol: "BTCUSDT",
          name: "Bitcoin",
          price: 43250.45,
          change24h: 2.34,
          volume: 28500000000,
          marketCap: 847000000000,
          icon: "₿",
          high24h: 44000,
          low24h: 42500,
          volatility: 1.2,
          timestamp: Date.now(),
        },
      ],
    };
  }

  throw new Error(`Mock fetch: Unhandled URL ${url}`);
};

// Mock browser URL constructor
global.URL = class {
  constructor(url) {
    const parts = url.split("://");
    const protocol = parts[0] + ":";
    const rest = parts[1].split("/");
    const hostPort = rest[0].split(":");

    this.protocol = protocol;
    this.hostname = hostPort[0];
    this.port = hostPort[1] || "";
    this.pathname = "/" + rest.slice(1).join("/");
  }
};

// Mock environment
const mockEnv = {
  VITE_API_URL: "http://localhost:8000/api/v1",
  MODE: "development",
  DEV: true,
};

// Mock import.meta.env
global.importMeta = {
  env: mockEnv,
};

// Test the API service logic
async function testApiService() {
  console.log("🔧 Testing API configuration...");

  const API_BASE_URL = mockEnv.VITE_API_URL || "http://localhost:8000/api/v1";
  const LIVE_API_URL = `${API_BASE_URL}/live`;

  console.log("- API_BASE_URL:", API_BASE_URL);
  console.log("- LIVE_API_URL:", LIVE_API_URL);

  // Test health check
  console.log("\n🏥 Testing health check...");
  try {
    const healthUrl = `${LIVE_API_URL}/health`;
    console.log("Health URL:", healthUrl);

    const response = await fetch(healthUrl);
    console.log("Response status:", response.status);

    const data = await response.json();
    console.log("✅ Health check result:", data);
  } catch (error) {
    console.error("❌ Health check failed:", error.message);
  }

  // Test tokens
  console.log("\n🎯 Testing tokens...");
  try {
    const tokensUrl = `${LIVE_API_URL}/tokens`;
    console.log("Tokens URL:", tokensUrl);

    const response = await fetch(tokensUrl);
    console.log("Response status:", response.status);

    const data = await response.json();
    console.log("✅ Tokens result:", data.length, "tokens");
    console.log("First token:", data[0]);
  } catch (error) {
    console.error("❌ Tokens failed:", error.message);
  }

  console.log("\n🎉 API Service test completed!");
}

testApiService();
