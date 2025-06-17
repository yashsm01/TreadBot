import React from 'react';
import { useMarketData } from './hooks/useMarketData';
import { Header } from './components/Header';
import { TokenGrid } from './components/TokenGrid';
import { SignalsSection } from './components/SignalsSection';

function App() {
  const {
    marketData,
    isLoading,
    selectToken,
    getTokenSignals,
    refreshData
  } = useMarketData();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <Header onRefresh={refreshData} isLoading={isLoading} />

      <main className="container mx-auto px-4 py-8">
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
        </div>
      </footer>
    </div>
  );
}

export default App;
