import { Token, TradingSignal } from "../types/trading";

// API configuration with extensive debugging
console.log("🔧 Environment Variables Debug:");
console.log("- import.meta.env:", import.meta.env);
console.log("- VITE_API_URL from env:", import.meta.env.VITE_API_URL);
console.log("- VITE_DEV_MODE from env:", import.meta.env.VITE_DEV_MODE);
console.log(
  "- All VITE_ variables:",
  Object.keys(import.meta.env).filter((key) => key.startsWith("VITE_"))
);

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const LIVE_API_URL = `${API_BASE_URL}/live`;

// Debug logging
console.log("🔧 API Service Configuration:");
console.log("- VITE_API_URL:", import.meta.env.VITE_API_URL);
console.log("- API_BASE_URL:", API_BASE_URL);
console.log("- LIVE_API_URL:", LIVE_API_URL);
console.log("- Environment mode:", import.meta.env.MODE);
console.log("- Is development:", import.meta.env.DEV);

// API service class
export class ApiService {
  private static instance: ApiService;

  public static getInstance(): ApiService {
    if (!ApiService.instance) {
      ApiService.instance = new ApiService();
      console.log("🔧 ApiService instance created");
    }
    return ApiService.instance;
  }

  private async fetchWithErrorHandling<T>(url: string): Promise<T> {
    try {
      console.log(`🌐 Attempting to fetch: ${url}`);
      console.log(`🌐 Full URL breakdown:`, {
        protocol: new URL(url).protocol,
        hostname: new URL(url).hostname,
        port: new URL(url).port,
        pathname: new URL(url).pathname,
      });

      const response = await fetch(url);

      console.log(
        `📡 Response status: ${response.status} ${response.statusText}`
      );
      console.log(
        `📡 Response headers:`,
        Object.fromEntries(response.headers.entries())
      );

      if (!response.ok) {
        throw new Error(
          `HTTP error! status: ${response.status} ${response.statusText}`
        );
      }

      const data = await response.json();
      console.log(`✅ Success for ${url}:`, data);
      return data;
    } catch (error: unknown) {
      console.error(`❌ API Error for ${url}:`, error);

      // Type-safe error handling
      if (error instanceof Error) {
        console.error(`❌ Error type:`, error.constructor.name);
        console.error(`❌ Error message:`, error.message);
        console.error(`❌ Error stack:`, error.stack);
        if ("cause" in error) {
          console.error(`❌ Error cause:`, error.cause);
        }
      } else {
        console.error(`❌ Unknown error type:`, typeof error);
        console.error(`❌ Error value:`, error);
      }

      throw error;
    }
  }

  // Get live token data
  async getLiveTokens(symbols?: string[]): Promise<Token[]> {
    console.log("🎯 getLiveTokens called with symbols:", symbols);
    try {
      let url = `${LIVE_API_URL}/tokens`;

      if (symbols && symbols.length > 0) {
        const symbolsParam = symbols.join(",");
        url += `?symbols=${symbolsParam}`;
      }

      console.log("🎯 Final tokens URL:", url);
      const tokens = await this.fetchWithErrorHandling<Token[]>(url);

      // Ensure the data structure matches our Token interface
      const processedTokens = tokens.map((token) => ({
        ...token,
        // Add any missing fields with defaults
        high24h: token.high24h || token.price,
        low24h: token.low24h || token.price,
        volatility: token.volatility || 0,
      }));

      console.log("🎯 Processed tokens count:", processedTokens.length);
      return processedTokens;
    } catch (error) {
      console.error("❌ Error in getLiveTokens:", error);
      return [];
    }
  }

  // Get live trading signals
  async getLiveSignals(
    symbols?: string[],
    limit?: number
  ): Promise<TradingSignal[]> {
    try {
      let url = `${LIVE_API_URL}/signals`;
      const params = new URLSearchParams();

      if (symbols && symbols.length > 0) {
        params.append("symbols", symbols.join(","));
      }

      if (limit) {
        params.append("limit", limit.toString());
      }

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const signals = await this.fetchWithErrorHandling<TradingSignal[]>(url);

      // Ensure the data structure matches our TradingSignal interface
      return signals.map((signal) => ({
        ...signal,
        timestamp: new Date(signal.timestamp),
        pnl: signal.pnl || 0,
      }));
    } catch (error) {
      console.error("Error fetching live signals:", error);
      return [];
    }
  }

  // Get detailed token information
  async getTokenDetails(symbol: string): Promise<Token | null> {
    try {
      const tokenDetails = await this.fetchWithErrorHandling<Token>(
        `${LIVE_API_URL}/token/${symbol}`
      );

      return {
        ...tokenDetails,
        high24h: tokenDetails.high24h || tokenDetails.price,
        low24h: tokenDetails.low24h || tokenDetails.price,
        volatility: tokenDetails.volatility || 0,
      };
    } catch (error) {
      console.error(`Error fetching token details for ${symbol}:`, error);
      return null;
    }
  }

  // Get market overview
  async getMarketOverview(): Promise<{
    tokens: Token[];
    signals: TradingSignal[];
    marketSummary: any;
  } | null> {
    try {
      const overview = await this.fetchWithErrorHandling<any>(
        `${LIVE_API_URL}/market-overview`
      );

      return {
        tokens: overview.tokens.map((token: any) => ({
          ...token,
          high24h: token.high24h || token.price,
          low24h: token.low24h || token.price,
          volatility: token.volatility || 0,
        })),
        signals: overview.signals.map((signal: any) => ({
          ...signal,
          timestamp: new Date(signal.timestamp),
          pnl: signal.pnl || 0,
        })),
        marketSummary: overview.marketSummary,
      };
    } catch (error) {
      console.error("Error fetching market overview:", error);
      return null;
    }
  }

  // Get popular tokens
  async getPopularTokens(limit: number = 10): Promise<Token[]> {
    try {
      const tokens = await this.fetchWithErrorHandling<Token[]>(
        `${LIVE_API_URL}/popular-tokens?limit=${limit}`
      );

      return tokens.map((token) => ({
        ...token,
        high24h: token.high24h || token.price,
        low24h: token.low24h || token.price,
        volatility: token.volatility || 0,
      }));
    } catch (error) {
      console.error("Error fetching popular tokens:", error);
      return [];
    }
  }

  // Get trending tokens
  async getTrendingTokens(limit: number = 5): Promise<Token[]> {
    try {
      const tokens = await this.fetchWithErrorHandling<Token[]>(
        `${LIVE_API_URL}/trending?limit=${limit}`
      );

      return tokens.map((token) => ({
        ...token,
        high24h: token.high24h || token.price,
        low24h: token.low24h || token.price,
        volatility: token.volatility || 0,
      }));
    } catch (error) {
      console.error("Error fetching trending tokens:", error);
      return [];
    }
  }

  // Health check with extensive logging
  async healthCheck(): Promise<{
    status: string;
    binance_connection: boolean;
  } | null> {
    console.log("🏥 Health check starting...");
    try {
      const healthUrl = `${LIVE_API_URL}/health`;
      console.log("🏥 Health check URL:", healthUrl);

      const result = await this.fetchWithErrorHandling<any>(healthUrl);
      console.log("🏥 Health check result:", result);

      return result;
    } catch (error) {
      console.error("❌ Health check failed:", error);
      return null;
    }
  }
}

// Export singleton instance
export const apiService = ApiService.getInstance();
