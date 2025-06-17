import React from 'react';
import { Token, TradingSignal as TradingSignalType } from '../types/trading';
import { TradingSignal } from './TradingSignal';
import { AlertCircle } from 'lucide-react';

interface SignalsSectionProps {
  signals: TradingSignalType[];
  tokens: Token[];
  selectedToken: string | null;
}

export const SignalsSection: React.FC<SignalsSectionProps> = ({
  signals,
  tokens,
  selectedToken
}) => {
  const filteredSignals = selectedToken 
    ? signals.filter(signal => signal.tokenId === selectedToken)
    : signals;

  const getTokenById = (tokenId: string) => {
    return tokens.find(token => token.id === tokenId);
  };

  const selectedTokenData = selectedToken ? getTokenById(selectedToken) : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white text-2xl font-bold">
          Trading Signals
          {selectedTokenData && (
            <span className="text-emerald-400 ml-2">
              - {selectedTokenData.symbol}
            </span>
          )}
        </h2>
        <div className="flex items-center space-x-2 text-gray-400">
          <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
          <span className="text-sm">Live</span>
        </div>
      </div>

      {filteredSignals.length === 0 ? (
        <div className="bg-gray-800/30 border border-gray-700/50 rounded-xl p-8 text-center">
          <AlertCircle className="text-gray-400 mx-auto mb-3" size={48} />
          <h3 className="text-white text-lg font-semibold mb-2">No Active Signals</h3>
          <p className="text-gray-400">
            {selectedToken 
              ? `No signals available for ${selectedTokenData?.symbol}. Try selecting another token.`
              : 'No trading signals available at the moment. Check back soon!'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredSignals.map(signal => {
            const token = getTokenById(signal.tokenId);
            if (!token) return null;
            
            return (
              <TradingSignal
                key={signal.id}
                signal={signal}
                token={token}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};