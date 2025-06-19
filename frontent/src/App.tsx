import React from 'react';
import { useMarketData } from './hooks/useMarketData';
import { Header } from './components/Header';
import { TokenGrid } from './components/TokenGrid';
import { SignalsSection } from './components/SignalsSection';

function App() {
  const {
    marketData,
    marketSummary,
    isLoading,
    error,
    isOnline,
    selectToken,
    getTokenSignals,
    refreshData
  } = useMarketData();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <Header onRefresh={refreshData} isLoading={isLoading} />

      {/* Connection Status & Error Display */}
      {!isOnline && (
        <div className="bg-yellow-600/20 border border-yellow-500/30 mx-4 mt-4 p-3 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
            <span className="text-yellow-200 text-sm">
              Using offline data - API connection unavailable
            </span>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-600/20 border border-red-500/30 mx-4 mt-4 p-3 rounded-lg">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-red-500 rounded-full"></div>
            <span className="text-red-200 text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Live Data Indicator */}
      {isOnline && !error && (
        <div className="bg-green-600/20 border border-green-500/30 mx-4 mt-4 p-3 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-green-200 text-sm">Live data connected</span>
            </div>
            {marketSummary && (
              <div className="text-green-200 text-xs">
                {marketSummary.totalTokens} tokens • {marketSummary.activeSignals} active signals
              </div>
            )}
          </div>
        </div>
      )}

      <main className="container mx-auto px-4 py-8">
        {/* Market Summary */}
        {marketSummary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-lg p-4">
              <div className="text-gray-400 text-sm">Total Volume</div>
              <div className="text-white text-lg font-semibold">
                ${(marketSummary.totalVolume / 1e9).toFixed(2)}B
              </div>
            </div>
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-lg p-4">
              <div className="text-gray-400 text-sm">Avg Change 24h</div>
              <div className={`text-lg font-semibold ${
                marketSummary.averageChange24h >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {marketSummary.averageChange24h >= 0 ? '+' : ''}{marketSummary.averageChange24h.toFixed(2)}%
              </div>
            </div>
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-lg p-4">
              <div className="text-gray-400 text-sm">Positive/Negative</div>
              <div className="text-white text-lg font-semibold">
                <span className="text-green-400">{marketSummary.positivePerformers}</span>
                /
                <span className="text-red-400">{marketSummary.negativePerformers}</span>
              </div>
            </div>
            <div className="bg-gray-800/50 backdrop-blur-sm border border-gray-700/50 rounded-lg p-4">
              <div className="text-gray-400 text-sm">Active Signals</div>
              <div className="text-blue-400 text-lg font-semibold">
                {marketSummary.activeSignals}
              </div>
            </div>
          </div>
        )}

        <TokenGrid
          tokens={marketData.tokens}
          selectedToken={marketData.selectedToken}
          onSelectToken={selectToken}
          getTokenSignals={getTokenSignals}
        />

        <SignalsSection
          signals={marketData.signals}
          tokens={marketData.tokens}
          selectedToken={marketData.selectedToken}
        />
      </main>

      <footer className="border-t border-gray-700/50 bg-gray-900/50 backdrop-blur-sm mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-gray-400">
          <p>Trading Bot Dashboard - Real-time market signals and analysis</p>
          <div className="text-xs mt-2 flex items-center justify-center gap-4">
            <span>Status: {isOnline ? '🟢 Online' : '🔴 Offline'}</span>
            <span>Tokens: {marketData.tokens.length}</span>
            <span>Signals: {marketData.signals.length}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
