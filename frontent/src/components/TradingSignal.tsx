import React from 'react';
import { TradingSignal as TradingSignalType, Token } from '../types/trading';
import { ArrowUp, ArrowDown, Target, Shield, TrendingUp } from 'lucide-react';

interface TradingSignalProps {
  signal: TradingSignalType;
  token: Token;
}

export const TradingSignal: React.FC<TradingSignalProps> = ({ signal, token }) => {
  const formatPrice = (price: number) => {
    if (price >= 1) {
      return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `$${price.toFixed(4)}`;
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / (1000 * 60));
    
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE': return 'text-emerald-400 bg-emerald-400/10';
      case 'COMPLETED': return 'text-blue-400 bg-blue-400/10';
      case 'CANCELLED': return 'text-red-400 bg-red-400/10';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 75) return 'text-emerald-400';
    if (confidence >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  const currentPrice = token.price;
  const pnlPercent = signal.type === 'LONG' 
    ? ((currentPrice - signal.entry) / signal.entry) * 100
    : ((signal.entry - currentPrice) / signal.entry) * 100;

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${signal.type === 'LONG' ? 'bg-emerald-500/20' : 'bg-red-500/20'}`}>
            {signal.type === 'LONG' ? 
              <ArrowUp className="text-emerald-400" size={20} /> : 
              <ArrowDown className="text-red-400" size={20} />
            }
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg">
              {signal.type} {token.symbol}
            </h3>
            <p className="text-gray-400 text-sm">{formatTime(signal.timestamp)}</p>
          </div>
        </div>
        
        <div className="text-right">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(signal.status)}`}>
            {signal.status}
          </span>
          <p className="text-gray-400 text-sm mt-1">
            Confidence: <span className={getConfidenceColor(signal.confidence)}>{signal.confidence}%</span>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="bg-gray-700/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <TrendingUp className="text-blue-400" size={16} />
            <span className="text-gray-400 text-sm">Entry</span>
          </div>
          <p className="text-white font-semibold">{formatPrice(signal.entry)}</p>
        </div>
        
        <div className="bg-gray-700/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <Shield className="text-red-400" size={16} />
            <span className="text-gray-400 text-sm">Stop Loss</span>
          </div>
          <p className="text-white font-semibold">{formatPrice(signal.stopLoss)}</p>
        </div>
        
        <div className="bg-gray-700/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <Target className="text-emerald-400" size={16} />
            <span className="text-gray-400 text-sm">Take Profit</span>
          </div>
          <p className="text-white font-semibold">{formatPrice(signal.takeProfit)}</p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-gray-700/50">
        <div>
          <span className="text-gray-400 text-sm">Current Price</span>
          <p className="text-white font-semibold">{formatPrice(currentPrice)}</p>
        </div>
        <div className="text-right">
          <span className="text-gray-400 text-sm">Unrealized P&L</span>
          <p className={`font-semibold ${pnlPercent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
          </p>
        </div>
      </div>
    </div>
  );
};