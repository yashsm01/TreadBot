import React from 'react';
import { Token } from '../types/trading';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface TokenCardProps {
  token: Token;
  isSelected: boolean;
  onSelect: (tokenId: string) => void;
  hasSignals: boolean;
}

export const TokenCard: React.FC<TokenCardProps> = ({ 
  token, 
  isSelected, 
  onSelect, 
  hasSignals 
}) => {
  const formatPrice = (price: number) => {
    if (price >= 1) {
      return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `$${price.toFixed(4)}`;
  };

  const formatVolume = (volume: number) => {
    if (volume >= 1e9) {
      return `$${(volume / 1e9).toFixed(1)}B`;
    }
    if (volume >= 1e6) {
      return `$${(volume / 1e6).toFixed(1)}M`;
    }
    return `$${(volume / 1e3).toFixed(1)}K`;
  };

  const isPositive = token.change24h >= 0;

  return (
    <div
      onClick={() => onSelect(token.id)}
      className={`
        relative p-4 rounded-xl cursor-pointer transition-all duration-200
        border backdrop-blur-sm
        ${isSelected 
          ? 'bg-emerald-500/10 border-emerald-500/50 shadow-lg shadow-emerald-500/20' 
          : 'bg-gray-800/50 border-gray-700/50 hover:bg-gray-800/70 hover:border-gray-600/50'
        }
        hover:scale-[1.02] active:scale-[0.98]
      `}
    >
      {hasSignals && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full animate-pulse" />
      )}
      
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-gray-700 to-gray-800 rounded-full flex items-center justify-center text-lg font-bold">
            {token.icon}
          </div>
          <div>
            <h3 className="text-white font-semibold text-lg">{token.symbol}</h3>
            <p className="text-gray-400 text-sm">{token.name}</p>
          </div>
        </div>
        
        <div className="text-right">
          <p className="text-white font-bold text-lg">{formatPrice(token.price)}</p>
          <div className={`flex items-center space-x-1 ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
            {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span className="text-sm font-medium">
              {isPositive ? '+' : ''}{token.change24h.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>
      
      <div className="flex justify-between text-sm text-gray-400">
        <div>
          <span className="block">Volume</span>
          <span className="text-white font-medium">{formatVolume(token.volume)}</span>
        </div>
        <div className="text-right">
          <span className="block">Market Cap</span>
          <span className="text-white font-medium">{formatVolume(token.marketCap)}</span>
        </div>
      </div>
    </div>
  );
};