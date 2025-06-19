import { useState, useEffect, useCallback } from "react";
import {
  Token,
  TradingSignal,
  MarketData,
  MarketSummary,
} from "../types/trading";
import { apiService } from "../services/api";
import { mockTokens, mockSignals } from "../data/mockData";

export const useMarketData = () => {
  const [marketData, setMarketData] = useState<MarketData>({
    tokens: [],
    signals: [],
    selectedToken: null,
  });

  const [marketSummary, setMarketSummary] = useState<MarketSummary | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(true);

  // Function to load live data
  const loadLiveData = useCallback(async () => {
    console.log("🚀 loadLiveData called");
    try {
      setError(null);

      // Check API health first
      console.log("🏥 Starting health check...");
      const healthCheck = await apiService.healthCheck();
      console.log("🏥 Health check response:", healthCheck);

      if (!healthCheck || !healthCheck.binance_connection) {
        console.warn("⚠️ API health check failed, using fallback data");
        console.warn("⚠️ Health check result:", healthCheck);
        setIsOnline(false);
        // Use mock data as fallback
        setMarketData({
          tokens: mockTokens,
          signals: mockSignals,
          selectedToken: null,
        });
        return;
      }

      console.log("✅ Health check passed, setting online status");
      setIsOnline(true);

      // Load market overview (includes tokens and signals)
      console.log("📊 Attempting to load market overview...");
      const overview = await apiService.getMarketOverview();
      console.log("📊 Market overview response:", overview);

      if (overview) {
        console.log("✅ Using market overview data");
        setMarketData({
          tokens: overview.tokens,
          signals: overview.signals,
          selectedToken: null,
        });
        setMarketSummary(overview.marketSummary);
      } else {
        // Fallback to individual API calls
        console.log("🔄 Market overview failed, trying individual calls...");
        const [tokens, signals] = await Promise.all([
          apiService.getLiveTokens(),
          apiService.getLiveSignals(),
        ]);

        console.log("🎯 Individual API results:", {
          tokensCount: tokens.length,
          signalsCount: signals.length,
        });

        setMarketData({
          tokens: tokens.length > 0 ? tokens : mockTokens,
          signals: signals.length > 0 ? signals : mockSignals,
          selectedToken: null,
        });
      }
    } catch (error) {
      console.error("❌ Error in loadLiveData:", error);
      console.error(
        "❌ Error stack:",
        error instanceof Error ? error.stack : "No stack trace"
      );
      setError("Failed to load live data. Using cached data.");
      setIsOnline(false);

      // Use mock data as fallback
      console.log("🔄 Using mock data as fallback");
      setMarketData({
        tokens: mockTokens,
        signals: mockSignals,
        selectedToken: null,
      });
    }
  }, []);

  // Initial data load
  useEffect(() => {
    const initializeData = async () => {
      setIsLoading(true);
      await loadLiveData();
      setIsLoading(false);
    };

    initializeData();
  }, [loadLiveData]);

  // Auto-refresh data every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      if (isOnline) {
        try {
          // Get fresh token data
          const freshTokens = await apiService.getLiveTokens();
          if (freshTokens.length > 0) {
            setMarketData((prev) => ({
              ...prev,
              tokens: freshTokens,
            }));
          }

          // Get fresh signals periodically (every 2 minutes)
          const now = Date.now();
          const lastSignalUpdate = localStorage.getItem("lastSignalUpdate");
          const shouldUpdateSignals =
            !lastSignalUpdate || now - parseInt(lastSignalUpdate) > 120000; // 2 minutes

          if (shouldUpdateSignals) {
            const freshSignals = await apiService.getLiveSignals();
            if (freshSignals.length > 0) {
              setMarketData((prev) => ({
                ...prev,
                signals: freshSignals,
              }));
              localStorage.setItem("lastSignalUpdate", now.toString());
            }
          }
        } catch (error) {
          console.error("Error during auto-refresh:", error);
          // Don't update error state during auto-refresh to avoid UI flicker
        }
      }
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [isOnline]);

  const selectToken = useCallback((tokenId: string) => {
    setMarketData((prev) => ({
      ...prev,
      selectedToken: tokenId,
    }));
  }, []);

  const getTokenSignals = useCallback(
    (tokenId: string) => {
      return marketData.signals.filter(
        (signal) =>
          signal.tokenId === tokenId ||
          signal.tokenId === tokenId.replace("USDT", "") ||
          signal.tokenId === `${tokenId}USDT`
      );
    },
    [marketData.signals]
  );

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    await loadLiveData();
    setIsLoading(false);
  }, [loadLiveData]);

  // Get token by symbol
  const getTokenBySymbol = useCallback(
    (symbol: string) => {
      return marketData.tokens.find(
        (token) =>
          token.symbol === symbol ||
          token.symbol === `${symbol}USDT` ||
          token.id === symbol
      );
    },
    [marketData.tokens]
  );

  // Get trending tokens (top gainers)
  const getTrendingTokens = useCallback(() => {
    return marketData.tokens
      .filter((token) => token.change24h > 0)
      .sort((a, b) => b.change24h - a.change24h)
      .slice(0, 5);
  }, [marketData.tokens]);

  // Get top losers
  const getTopLosers = useCallback(() => {
    return marketData.tokens
      .filter((token) => token.change24h < 0)
      .sort((a, b) => a.change24h - b.change24h)
      .slice(0, 5);
  }, [marketData.tokens]);

  return {
    marketData,
    marketSummary,
    isLoading,
    error,
    isOnline,
    selectToken,
    getTokenSignals,
    refreshData,
    getTokenBySymbol,
    getTrendingTokens,
    getTopLosers,
  };
};
