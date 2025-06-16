import { useState, useEffect, useCallback } from 'react';
import { Token, TradingSignal, MarketData } from '../types/trading';
import { mockTokens, mockSignals } from '../data/mockData';

export const useMarketData = () => {
  const [marketData, setMarketData] = useState<MarketData>({
    tokens: mockTokens,
    signals: mockSignals,
    selectedToken: null
  });

  const [isLoading, setIsLoading] = useState(false);

  // Simulate real-time price updates
  useEffect(() => {
    const interval = setInterval(() => {
      setMarketData(prev => ({
        ...prev,
        tokens: prev.tokens.map(token => ({
          ...token,
          price: token.price * (1 + (Math.random() - 0.5) * 0.002), // ±0.1% variation
          change24h: token.change24h + (Math.random() - 0.5) * 0.1
        }))
      }));
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const selectToken = useCallback((tokenId: string) => {
    setMarketData(prev => ({
      ...prev,
      selectedToken: tokenId
    }));
  }, []);

  const getTokenSignals = useCallback((tokenId: string) => {
    return marketData.signals.filter(signal => signal.tokenId === tokenId);
  }, [marketData.signals]);

  const refreshData = useCallback(async () => {
    setIsLoading(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsLoading(false);
  }, []);

  return {
    marketData,
    isLoading,
    selectToken,
    getTokenSignals,
    refreshData
  };
};